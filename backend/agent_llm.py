"""LLM Gateway: provider-agnostic access to DeepSeek / Zhipu (OpenAI-compatible)."""
import os
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

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