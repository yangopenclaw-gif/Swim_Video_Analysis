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


async def run_agent(
    llm_stream: Callable[..., Any],
    messages: List[Dict[str, Any]],
    tools: Dict[str, Tool],
    *,
    max_iterations: int = 5,
) -> AsyncIterator[Dict[str, Any]]:
    """Run the ReAct loop over a streaming LLM, yielding event dicts.

    `llm_stream(messages, tools=...)` 应是一个异步迭代器，yield：
      {"content": <增量文本>}  以及最终的
      {"done": True, "tool_calls": [...], "content_full": <文本>}

    Events:
      {"type": "status", "text": ...}
      {"type": "tool", "name": ..., "args": ...}
      {"type": "token", "text": ...}
      {"type": "done"}
      {"type": "error", "text": ...}
    """
    tool_specs = [t.to_openai() for t in tools.values()]

    try:
        for _ in range(max_iterations):
            content_parts: List[str] = []
            final_tool_calls: List[Dict[str, Any]] = []

            async for ev in llm_stream(messages, tools=tool_specs):
                if ev.get("content"):
                    content_parts.append(ev["content"])
                    yield {"type": "token", "text": ev["content"]}
                if ev.get("done"):
                    final_tool_calls = ev.get("tool_calls") or []
                    break

            if final_tool_calls:
                content = "".join(content_parts)
                messages.append({
                    "role": "assistant",
                    "content": content or None,
                    "tool_calls": final_tool_calls,
                })
                for tc in final_tool_calls:
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

            final_text = "".join(content_parts)
            if not final_text:
                final_text = "抱歉，我暂时无法处理这个请求，请换个说法试试。"
                yield {"type": "token", "text": final_text}
            yield {"type": "done"}
            return
    except Exception as e:
        logger.exception("agent run failed")
        yield {"type": "error", "text": str(e)}