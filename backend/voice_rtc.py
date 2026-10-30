"""火山引擎 RTC 托管语音对话：StartVoiceChat 编排 + CustomLLM 回调接小咩。

链路：App(火山RTC SDK进房推流) → 火山托管Bot(ASR) → 回调 /api/voice/llm →
run_agent(小咩 ReAct) → 回复文本 → 火山 TTS 推回房间。

Token 算法逐字节对齐 volcengine/rtc-aigc-embedded-demo server/src/AccessToken.py；
OpenAPI 签名对齐火山官方 SignerV4（docs/6348/69828）。
"""
import asyncio
import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import struct
import time
import uuid
from datetime import datetime, timezone
from urllib.parse import quote
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

logger = logging.getLogger("voice.rtc")

ROUTER = APIRouter(prefix="/api/voice")

VOLC_APP_ID = os.environ.get("VOLC_RTC_APP_ID", "")
VOLC_APP_KEY = os.environ.get("VOLC_RTC_APP_KEY", "")
VOLC_ACCESS_KEY = os.environ.get("VOLC_ACCESS_KEY_ID", "")
VOLC_SECRET_KEY = os.environ.get("VOLC_SECRET_ACCESS_KEY", "")
VOLC_LLM_KEY = os.environ.get("VOLC_VOICE_LLM_KEY", "")
VOLC_TTS_SPEAKER = os.environ.get("VOLC_VOICE_TTS_SPEAKER", "zh_female_linjianvhai_moon_bigtts")
VOLC_LLM_URL_BASE = os.environ.get("VOLC_CUSTOM_LLM_URL", "").strip('"')
VOLC_LLM_MODE = os.environ.get("VOLC_LLM_MODE", "custom").strip().lower()
VOLC_ARK_MODEL = os.environ.get("VOLC_ARK_MODEL", "doubao-seed-2-0-lite-260428")
VOLC_TTS_RESOURCE = os.environ.get("VOLC_TTS_RESOURCE", "seed-tts-2.0")

OPENAPI_HOST = "rtc.volcengineapi.com"
OPENAPI_VERSION = "2025-06-01"
OPENAPI_REGION = "cn-north-1"

TOKEN_VERSION = "001"
PRIV_PUBLISH_STREAM = 0
PRIV_SUBSCRIBE_STREAM = 4
BOT_USER_ID = "xiaomie_bot"

VOICE_PERSONA = (
    "你是小咩，用户的贴心私人助手，正在和用户进行语音通话。"
    "现在是语音对话模式：回复务必口语化、自然、简短（一般1~3句话），"
    "禁止使用任何 Markdown 格式、列表、代码块。涉及金额或日期时用口语念出来。"
)

_sessions: dict = {}



# ---------------- RTC AccessToken（官方算法对齐） ----------------

def _pack_u16(v: int) -> bytes:
    return struct.pack("<H", int(v))


def _pack_u32(v: int) -> bytes:
    return struct.pack("<I", int(v))


def _pack_bytes(b: bytes) -> bytes:
    return _pack_u16(len(b)) + b


def _pack_str(s: str) -> bytes:
    return _pack_bytes(s.encode("utf-8"))


def _pack_privs(privs: dict) -> bytes:
    out = _pack_u16(len(privs))
    for k in sorted(privs):
        out += _pack_u16(k) + _pack_u32(privs[k])
    return out


def gen_rtc_token(room_id: str, user_id: str, ttl_seconds: int = 3600) -> str:
    now = int(time.time())
    expire = now + ttl_seconds
    privs = {
        PRIV_PUBLISH_STREAM: expire,
        1: expire, 2: expire, 3: expire,
        PRIV_SUBSCRIBE_STREAM: expire,
    }
    msg = _pack_u32(secrets.randbelow(99999999) + 1) + _pack_u32(now) + _pack_u32(expire)
    msg += _pack_str(room_id) + _pack_str(user_id) + _pack_privs(privs)
    sig = hmac.new(VOLC_APP_KEY.encode(), msg, hashlib.sha256).digest()
    content = _pack_bytes(msg) + _pack_bytes(sig)
    return TOKEN_VERSION + VOLC_APP_ID + base64.b64encode(content).decode()


# ---------------- 火山 OpenAPI V4 签名 ----------------

def _hmac(key: bytes, s: str) -> bytes:
    return hmac.new(key, s.encode(), hashlib.sha256).digest()


def sign_headers(action: str, body: bytes) -> dict:
    moment = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    date = moment[:8]
    payload_hash = hashlib.sha256(body).hexdigest()

    def canonical_query() -> str:
        q = {"Action": action, "Version": OPENAPI_VERSION}
        return "&".join(f"{quote(k, safe='-_.~')}={quote(v, safe='-_.~')}" for k, v in sorted(q.items()))

    headers = {
        "content-type": "application/json",
        "host": OPENAPI_HOST,
        "x-content-sha256": payload_hash,
        "x-date": moment,
    }
    signed = ";".join(sorted(headers))
    canonical_headers = "".join(f"{k}:{headers[k]}\n" for k in sorted(headers))
    scope = f"{date}/{OPENAPI_REGION}/rtc/request"

    creq = "\n".join(["POST", "/", canonical_query(), canonical_headers, signed, payload_hash])
    sts = "\n".join(["HMAC-SHA256", moment, scope, hashlib.sha256(creq.encode()).hexdigest()])
    key = _hmac(_hmac(_hmac(_hmac(VOLC_SECRET_KEY.encode(), date), OPENAPI_REGION), "rtc"), "request")
    signature = hmac.new(key, sts.encode(), hashlib.sha256).hexdigest()
    return {
        "Content-Type": "application/json",
        "Host": OPENAPI_HOST,
        "X-Content-Sha256": payload_hash,
        "X-Date": moment,
        "Authorization": (
            f"HMAC-SHA256 Credential={VOLC_ACCESS_KEY}/{scope}, "
            f"SignedHeaders={signed}, Signature={signature}"
        ),
    }


async def volc_call(action: str, body: dict) -> dict:
    payload = json.dumps(body, ensure_ascii=False).encode()
    headers = sign_headers(action, payload)
    url = f"https://{OPENAPI_HOST}/?{urlencode({'Action': action, 'Version': OPENAPI_VERSION})}"
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(url, headers=headers, content=payload)
    try:
        data = resp.json()
    except Exception:
        raise HTTPException(status_code=502, detail=f"{action} 网关返回非 JSON (HTTP {resp.status_code})")
    err = (data.get("ResponseMetadata") or {}).get("Error")
    if err:
        raise HTTPException(status_code=502, detail=f"{action} 失败: {err.get('Code')} {err.get('Message')}")
    return data


# ---------------- StartVoiceChat / StopVoiceChat ----------------

def build_start_body(room_id: str, task_id: str, user_id: str) -> dict:
    llm_url = f"{VOLC_LLM_URL_BASE}?task={task_id}"
    feature = {"Http": True} if llm_url.lower().startswith("http://") else None
    llm_cfg: dict
    if VOLC_LLM_MODE == "ark":
        llm_cfg = {
            "Mode": "ArkV3",
            "ModelName": VOLC_ARK_MODEL,
            "SystemMessages": [VOICE_PERSONA],
            "HistoryLength": 8,
            "MaxTokens": 512,
            "Temperature": 0.3,
            "ThinkingType": "disabled",
        }
    else:
        llm_cfg = {
            "Mode": "CustomLLM",
            "Url": llm_url,
            "APIKey": VOLC_LLM_KEY,
            "SystemMessages": [VOICE_PERSONA],
            "HistoryLength": 8,
            "MaxTokens": 512,
            "Temperature": 0.3,
        }
        if feature:
            llm_cfg["Feature"] = json.dumps(feature)
    return {
        "AppId": VOLC_APP_ID,
        "RoomId": room_id,
        "TaskId": task_id,
        "Config": {
            "ASRConfig": {
                "Provider": "volcano",
                "ProviderParams": {
                    "Mode": "bigmodel",
                    "ApiResourceId": "volc.seedasr.sauc.duration",
                    "StreamMode": 2,
                },
            },
            "LLMConfig": llm_cfg,
            "TTSConfig": {
                "Provider": "volcano_bidirection",
                "ProviderParams": {
                    "ResourceId": VOLC_TTS_RESOURCE,
                    "audio": {"voice_type": VOLC_TTS_SPEAKER, "speech_rate": 0},
                },
            },
            "SubtitleConfig": {"SubtitleMode": 1},
            "InterruptMode": 0,
        },
        "AgentConfig": {
            "TargetUserId": [user_id],
            "UserId": BOT_USER_ID,
            "WelcomeMessage": "我在呢，想聊点什么呀？",
            "IdleTimeout": 60,
        },
    }


def get_current_user_id_dep(request: Request) -> str:
    from .main import get_current_user_id
    return get_current_user_id(request)


@ROUTER.post("/session")
async def voice_session(request: Request, user_id: str = Depends(get_current_user_id_dep)):
    if not (VOLC_APP_ID and VOLC_APP_KEY and VOLC_ACCESS_KEY and VOLC_SECRET_KEY):
        raise HTTPException(status_code=503, detail="语音服务未配置")
    if VOLC_LLM_MODE != "ark" and not (VOLC_LLM_KEY and VOLC_LLM_URL_BASE):
        raise HTTPException(status_code=503, detail="语音服务未配置(CustomLLM)")
    body = await request.json()
    room_id = f"room_{uuid.uuid4().hex[:10]}"
    task_id = f"task_{uuid.uuid4().hex[:10]}"
    uid = f"u_{uuid.uuid4().hex[:8]}"
    _sessions[task_id] = {"user_id": user_id, "room_id": room_id, "conversation_id": body.get("conversation_id") or ""}
    await volc_call("StartVoiceChat", build_start_body(room_id, task_id, uid))
    token = gen_rtc_token(room_id, uid, ttl_seconds=3600)
    return {
        "app_id": VOLC_APP_ID,
        "room_id": room_id,
        "task_id": task_id,
        "user_id": uid,
        "token": token,
        "bot_user_id": BOT_USER_ID,
    }


@ROUTER.post("/stop")
async def voice_stop(request: Request, user_id: str = Depends(get_current_user_id_dep)):
    body = await request.json()
    task_id = body.get("task_id") or ""
    room_id = body.get("room_id") or ""
    if not (task_id and room_id):
        raise HTTPException(status_code=400, detail="task_id 与 room_id 必填")
    await volc_call("StopVoiceChat", {
        "AppId": VOLC_APP_ID, "RoomId": room_id, "TaskId": task_id,
    })
    _sessions.pop(task_id, None)
    return {"status": "ok"}



# ---------------- CustomLLM 回调（火山 → 小咩） ----------------

@ROUTER.post("/llm")
async def voice_llm(request: Request):
    auth = request.headers.get("Authorization") or ""
    if VOLC_LLM_KEY and auth != f"Bearer {VOLC_LLM_KEY}":
        raise HTTPException(status_code=401, detail="unauthorized")
    task = request.query_params.get("task") or ""
    sess = _sessions.get(task)
    owner_user_id = (sess or {}).get("user_id") or "voice_user"

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="invalid json")

    incoming = body.get("messages") or []
    want_stream = bool(body.get("stream"))

    from .main import (  # 延迟导入避免循环
        SessionLocal, Conversation, Message, build_agent_tools,
        build_system_prompt, recall_memories, extract_and_save_memories,
    )
    from .agent_core import run_agent
    from .agent_llm import stream_chat as agent_llm_stream

    req_msgs = [m for m in incoming if isinstance(m, dict) and m.get("role") in ("system", "user", "assistant", "tool")]
    last_user = ""
    for m in reversed(req_msgs):
        if m.get("role") == "user":
            last_user = (m.get("content") or "").strip()
            break

    today = datetime.now().strftime("%Y-%m-%d")
    memories = recall_memories(owner_user_id, last_user or "闲聊", top_k=3)
    from .main import get_profile, load_core_memories
    profile = get_profile(owner_user_id)
    core = load_core_memories(owner_user_id)
    system = build_system_prompt(memories, today, profile=profile, core=core)
    messages = [
        {"role": "system", "content": system},
        {"role": "system", "content": VOICE_PERSONA},
    ]
    for m in req_msgs:
        if m.get("role") == "system":
            continue
        messages.append({"role": m["role"], "content": m.get("content") or ""})

    tools = build_agent_tools(owner_user_id)

    conv_id = (sess or {}).get("conversation_id") or ""
    db = SessionLocal()
    try:
        if not conv_id:
            conv = Conversation(id=str(uuid.uuid4()), user_id=owner_user_id, title=(last_user or "语音对话")[:20])
            db.add(conv)
            db.commit()
            conv_id = conv.id
            if sess is not None:
                sess["conversation_id"] = conv_id
        if last_user:
            db.add(Message(id=str(uuid.uuid4()), conversation_id=conv_id,
                           user_id=owner_user_id, role="user", content=last_user))
            db.commit()
    finally:
        db.close()

    reply_id = f"chatcmpl-voice-{uuid.uuid4().hex[:12]}"
    model_name = body.get("model") or "xiaomie"
    created = int(time.time())
    deadline = 8.5

    async def collect() -> str:
        parts: list = []
        try:
            async def run_with_limit():
                async for ev in run_agent(agent_llm_stream, messages, tools, max_iterations=3):
                    if ev.get("type") == "token" and ev.get("text"):
                        parts.append(ev["text"])
                    elif ev.get("type") == "error":
                        parts.append("刚才出了点小问题，你再说一遍好不好？")
                        return
            await asyncio.wait_for(run_with_limit(), timeout=deadline)
        except asyncio.TimeoutError:
            if not parts:
                parts.append("我需要想得久一点，等下再问我不行吗？")
        return "".join(parts).strip() or "嗯，我在听。"

    answer = await collect()

    db = SessionLocal()
    try:
        db.add(Message(id=str(uuid.uuid4()), conversation_id=conv_id,
                       user_id=owner_user_id, role="assistant", content=answer))
        db.query(Conversation).filter(Conversation.id == conv_id).update(
            {Conversation.updated_at: datetime.now()})
        db.commit()
    finally:
        db.close()
    if last_user and answer:
        asyncio.create_task(extract_and_save_memories(owner_user_id, last_user, answer))

    if not want_stream:
        return JSONResponse({
            "id": reply_id, "object": "chat.completion", "created": created, "model": model_name,
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": answer},
                "finish_reason": "stop",
            }],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        })

    async def sse():
        def chunk(delta: dict, finish=None) -> str:
            return "data: " + json.dumps({
                "id": reply_id, "object": "chat.completion.chunk", "created": created,
                "model": model_name, "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
            }, ensure_ascii=False) + "\n\n"

        yield chunk({"role": "assistant"})
        step = 24
        for i in range(0, len(answer), step):
            yield chunk({"content": answer[i:i + step]})
        yield chunk({}, finish="stop")
        yield "data: [DONE]\n\n"

    return StreamingResponse(sse(), media_type="text/event-stream")