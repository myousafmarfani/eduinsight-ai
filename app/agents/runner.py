"""Minimal tool-calling loop on top of langchain-core chat models.

Uses only stable APIs (`bind_tools`, `AIMessage.tool_calls`, `ToolMessage`, `with_structured_output`)
so it works across LangChain 0.3 and 1.x without the deprecated AgentExecutor.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)

logger = logging.getLogger(__name__)


@dataclass
class ToolLoopResult:
    text: str = ""
    parsed: Any = None
    tools_used: list[str] = field(default_factory=list)
    messages: list[BaseMessage] = field(default_factory=list)


def message_text(content: Any) -> str:
    """Flatten chat-model content (a string or a list of content blocks) to text."""
    if isinstance(content, str):
        return content
    parts = []
    for block in content or []:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict) and block.get("type") == "text":
            parts.append(str(block.get("text", "")))
    return "".join(parts)


def run_tool_loop(
    llm: Any,
    tools: list[Any],
    system_prompt: str,
    user_prompt: str,
    history: list[BaseMessage] | None = None,
    output_model: type | None = None,
    final_instruction: str | None = None,
    max_iterations: int = 6,
) -> ToolLoopResult:
    """Let the model call `tools` until it answers; optionally finish with a structured output."""
    tool_map = {t.name: t for t in tools}
    bound = llm.bind_tools(tools) if tools else llm
    messages: list[BaseMessage] = [SystemMessage(content=system_prompt), *(history or []), HumanMessage(content=user_prompt)]
    used: list[str] = []
    answer = ""

    for _ in range(max_iterations):
        ai = bound.invoke(messages)
        messages.append(ai)
        calls = getattr(ai, "tool_calls", None) or []
        if not calls:
            answer = message_text(ai.content)
            break
        for call in calls:
            name = call.get("name", "")
            tool = tool_map.get(name)
            if tool is None:
                result: Any = {"error": f"Unknown tool '{name}'."}
            else:
                try:
                    result = tool.invoke(call.get("args") or {})
                    used.append(name)
                except Exception as exc:  # noqa: BLE001 - report tool errors back to the model
                    logger.warning("Tool %s failed: %s", name, exc)
                    result = {"error": f"Tool failed: {exc}"}
            messages.append(ToolMessage(content=json.dumps(result, default=str), tool_call_id=call.get("id", ""), name=name))
    else:
        # iteration budget exhausted while the model kept calling tools: force a final answer
        messages.append(HumanMessage(content="Answer now using only the tool results gathered so far."))
        answer = message_text(llm.invoke(messages).content)

    parsed = None
    if output_model is not None:
        structured = llm.with_structured_output(output_model, method="function_calling")
        parsed = structured.invoke(messages + [HumanMessage(content=final_instruction or "Return your findings in the required structure.")])
    return ToolLoopResult(text=answer, parsed=parsed, tools_used=used, messages=messages)
