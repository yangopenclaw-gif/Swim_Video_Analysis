"""LLM Gateway: provider-agnostic access to DeepSeek / Zhipu (OpenAI-compatible)."""
import json
import os
import logging
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Dict, List, Optional

import httpx

logger = logging.getLogger("agent.llm")


@dataclass
class ProviderConfig:
    name: str
    base_url: str
    api_key: str
    chat_model: str
    reasoner_model: str = ""

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def url(self) -> str:
        return f"{self.base_url.rstrip('/')}/chat/completions"


@dataclass
class LLMResponse:
    content: str = ""
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    finish_reason: str = ""
    model: str = ""
    raw: Dict[str, Any] = field(default_factory=dict)


def _load_providers() -> Dict[str, ProviderConfig]:
    providers: Dict[str, ProviderConfig] = {}

    ds_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    providers["deepseek"] = ProviderConfig(
        name="deepseek",
        base_url=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
        api_key=ds_key,
        chat_model=os.environ.get("DEEPSEEK_MODEL", "deepseek-chat"),
        reasoner_model=os.environ.get("DEEPSEEK_REASONER_MODEL", "deepseek-reasoner"),
    )

    zp_key = (os.environ.get("LLM_API_KEY") or os.environ.get("ZHIPU_API_KEY") or "").strip()
    providers["zhipu"] = ProviderConfig(
        name="zhipu",
        base_url=os.environ.get("LLM_BASE_URL", "https://open.bigmodel.cn/api/paas/v4"),
        api_key=zp_key,
        chat_model=os.environ.get("GLM_CHAT_MODEL", "glm-4-flash"),
        reasoner_model=os.environ.get("GLM_REASONER_MODEL", "glm-4.5"),
    )

    return providers


PROVIDERS = _load_providers()


def default_provider() -> Optional[str]:
    order = os.environ.get("AGENT_PROVIDER", "auto").strip().lower()
    if order in PROVIDERS and PROVIDERS[order].available:
        return order
    for name in ("deepseek", "zhipu"):
        if PROVIDERS[name].available:
            return name
    return None


async def chat(
    messages: List[Dict[str, Any]],
    tools: Optional[List[Dict[str, Any]]] = None,
    *,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
    reason: bool = False,
    timeout: float = 60.0,
) -> LLMResponse:
    name = provider or default_provider()
    if not name:
        raise RuntimeError(
            "未配置任何可用的 LLM provider，请在 .env 中设置 DEEPSEEK_API_KEY 或 LLM_API_KEY"
        )
    cfg = PROVIDERS[name]

    payload: Dict[str, Any] = {
        "model": model or (cfg.reasoner_model if reason else cfg.chat_model),
        "messages": messages,
        "temperature": temperature,
        "stream": False,
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"
    if max_tokens:
        payload["max_tokens"] = max_tokens

    headers = {
        "Authorization": f"Bearer {cfg.api_key}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(cfg.url(), headers=headers, json=payload)
    except httpx.HTTPError as e:
        raise RuntimeError(f"LLM {name} 请求失败: {e}") from e

    if resp.status_code != 200:
        body = resp.text[:500]
        raise RuntimeError(f"LLM {name} 返回 {resp.status_code}: {body}")

    return _parse_response(resp.json())


def _parse_response(data: Dict[str, Any]) -> LLMResponse:
    choices = data.get("choices") or []
    msg = (choices[0].get("message") if choices else {}) or {}
    content = msg.get("content") or ""
    tool_calls = msg.get("tool_calls") or []
    finish = (choices[0].get("finish_reason") if choices else "") or ""
    return LLMResponse(
        content=content,
        tool_calls=tool_calls,
        finish_reason=finish,
        model=data.get("model", ""),
        raw=data,
    )


async def stream_chat(
    messages: List[Dict[str, Any]],
    tools: Optional[List[Dict[str, Any]]] = None,
    *,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: Optional[int] = 1024,
    reason: bool = False,
    timeout: float = 60.0,
) -> AsyncIterator[Dict[str, Any]]:
    """流式调用 LLM。

    边生成边 yield {"content": <增量文本>}；一轮结束时 yield：
    {"done": True, "tool_calls": [...], "content_full": <本轮完整文本>}。
    若模型本轮要调用工具，则 content 通常为空、tool_calls 非空。
    """
    name = provider or default_provider()
    if not name:
        raise RuntimeError(
            "未配置任何可用的 LLM provider，请在 .env 中设置 DEEPSEEK_API_KEY 或 LLM_API_KEY"
        )
    cfg = PROVIDERS[name]

    payload: Dict[str, Any] = {
        "model": model or (cfg.reasoner_model if reason else cfg.chat_model),
        "messages": messages,
        "temperature": temperature,
        "stream": True,
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"
    if max_tokens:
        payload["max_tokens"] = max_tokens

    headers = {
        "Authorization": f"Bearer {cfg.api_key}",
        "Content-Type": "application/json",
    }

    content_parts: List[str] = []
    tool_calls: List[Dict[str, Any]] = []
    in_tool_mode = False

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream("POST", cfg.url(), headers=headers, json=payload) as resp:
                if resp.status_code != 200:
                    body = (await resp.aread()).decode("utf-8", "replace")[:500]
                    raise RuntimeError(f"LLM {name} 返回 {resp.status_code}: {body}")
                async for line in resp.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        obj = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    choices = obj.get("choices") or []
                    if not choices:
                        continue
                    delta = choices[0].get("delta") or {}
                    tcs = delta.get("tool_calls") or []
                    if tcs:
                        in_tool_mode = True
                        for tc in tcs:
                            idx = tc.get("index", 0)
                            while len(tool_calls) <= idx:
                                tool_calls.append({
                                    "id": "",
                                    "type": "function",
                                    "function": {"name": "", "arguments": ""},
                                })
                            fn = tc.get("function") or {}
                            if tc.get("id"):
                                tool_calls[idx]["id"] = tc["id"]
                            if fn.get("name"):
                                tool_calls[idx]["function"]["name"] += fn["name"]
                            if fn.get("arguments"):
                                tool_calls[idx]["function"]["arguments"] += fn["arguments"]
                        continue
                    c = delta.get("content")
                    if c and not in_tool_mode:
                        content_parts.append(c)
                        yield {"content": c}
    except httpx.HTTPError as e:
        raise RuntimeError(f"LLM {name} 请求失败: {e}") from e

    yield {"done": True, "tool_calls": tool_calls, "content_full": "".join(content_parts)}