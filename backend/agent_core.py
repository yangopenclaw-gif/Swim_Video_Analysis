"""Agent Core: lightweight ReAct loop with native function calling."""
import inspect
import json
import logging
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, List, Optional, AsyncIterator

logger = logging.getLogger("agent.core")


@dataclass
class Tool:
    name: str
    description: str
    parameters: Dict[str, Any]
    handler: Callable[[Dict[str, Any]], Any]

    def to_openai(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


async def _call_handler(handler: Callable[[Dict[str, Any]], Any], args: Dict[str, Any]) -> str:
    try:
        result = handler(args)
        if inspect.isawaitable(result):
            result = await result
        if isinstance(result, str):
            return result
        return json.dumps(result, ensure_ascii=False, default=str)
    except Exception as e:
        logger.exception("tool failed")
        return json.dumps({"error": str(e)}, ensure_ascii=False)


def _chunk(text: str, size: int = 12) -> List[str]:
    return [text[i:i + size] for i in range(0, len(text), size)]


async def run_agent(
    llm_chat: Callable[..., Awaitable[Any]],
    messages: List[Dict[str, Any]],
    tools: Dict[str, Tool],
    *,
    max_iterations: int = 5,
) -> AsyncIterator[Dict[str, Any]]:
    """Run the ReAct loop, yielding event dicts.

    Events:
      {"type": "status", "text": ...}
      {"type": "tool", "name": ..., "args": ...}
      {"type": "token", "text": ...}
      {"type": "done"}
      {"type": "error", "text": ...}
    """
    tool_specs = [t.to_openai() for t in tools.values()]
    final_text = ""

    try:
        for _ in range(max_iterations):
            resp = await llm_chat(messages, tools=tool_specs)

            if resp.tool_calls:
                messages.append({
                    "role": "assistant",
                    "content": resp.content or None,
                    "tool_calls": resp.tool_calls,
                })
                for tc in resp.tool_calls:
                    fn = tc.get("function", {})
                    name = fn.get("name", "")
                    raw_args = fn.get("arguments", "{}") or "{}"
                    try:
                        args = json.loads(raw_args)
                    except (json.JSONDecodeError, TypeError):
                        args = {}
                    if not isinstance(args, dict):
                        args = {}

                    tool = tools.get(name)
                    status = tool.description if tool else f"调用工具 {name}"
                    yield {"type": "status", "text": status}

                    if tool is None:
                        result = json.dumps({"error": f"未知工具 {name}"}, ensure_ascii=False)
                    else:
                        yield {"type": "tool", "name": name, "args": args}
                        result = await _call_handler(tool.handler, args)

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.get("id", ""),
                        "content": result,
                    })
                continue

            final_text = resp.content or ""
            break

        if not final_text:
            final_text = "抱歉，我暂时无法处理这个请求，请换个说法试试。"

        for chunk in _chunk(final_text):
            yield {"type": "token", "text": chunk}
        yield {"type": "done"}
    except Exception as e:
        logger.exception("agent run failed")
        yield {"type": "error", "text": str(e)}