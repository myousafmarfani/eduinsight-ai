"""Small synchronous LangChain-compatible client for the OpenRouter API.

OpenRouter has an HTTP API of its own. This client uses that API directly;
only LangChain core message/tool types are used by the agent pipeline.
"""
from __future__ import annotations

import json
from copy import copy
from typing import Any

import httpx
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from pydantic import ValidationError


class OpenRouterAPIError(RuntimeError):
    """Raised when OpenRouter rejects a request or returns an invalid response."""

    def __init__(self, message: str, *, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def _content_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    return "".join(
        str(block.get("text", "")) if isinstance(block, dict) else str(block)
        for block in (content or [])
        if not isinstance(block, dict) or block.get("type") == "text"
    )


def _message_payload(message: BaseMessage) -> dict[str, Any]:
    role = {"human": "user", "ai": "assistant", "system": "system", "tool": "tool"}.get(
        message.type, message.type
    )
    payload: dict[str, Any] = {"role": role, "content": _content_text(message.content)}
    if role == "tool":
        payload["tool_call_id"] = getattr(message, "tool_call_id", "")
    tool_calls = getattr(message, "tool_calls", None)
    if tool_calls:
        payload["tool_calls"] = [
            {"id": call.get("id", ""), "type": "function",
             "function": {"name": call.get("name", ""), "arguments": json.dumps(call.get("args") or {})}}
            for call in tool_calls
        ]
    return payload


def _tool_schema(tool: Any) -> dict[str, Any]:
    schema = tool.args_schema.model_json_schema() if tool.args_schema else {"type": "object", "properties": {}}
    schema.pop("title", None)
    return {"type": "function", "function": {"name": tool.name, "description": tool.description, "parameters": schema}}


class _StructuredOutput:
    def __init__(self, model: OpenRouterChatModel, schema: type[Any]):
        self.model, self.schema = model, schema

    def invoke(self, messages: Any) -> Any:
        prompt = (
            "Return only valid JSON matching this schema. Do not use markdown fences.\n"
            + json.dumps(self.schema.model_json_schema())
        )
        response = self.model.invoke([*self.model._coerce_messages(messages), HumanMessage(content=prompt)])
        text = _content_text(response.content).strip()
        try:
            return self.schema.model_validate_json(text)
        except ValidationError:
            try:
                return self.schema.model_validate(json.loads(text))
            except (ValidationError, json.JSONDecodeError) as nested:
                raise OpenRouterAPIError(f"OpenRouter returned invalid structured output: {text[:300]}") from nested


class OpenRouterChatModel:
    """Duck-typed chat model used by the existing LangChain-core agent code."""

    def __init__(self, *, model: str, api_key: str, base_url: str, timeout: int, headers: dict[str, str],
                 temperature: float = 0.2, tools: list[Any] | None = None):
        self.model = model
        self.api_key = api_key
        self.base_url = base_url.rstrip("/") + "/chat/completions"
        self.timeout = timeout
        self.headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json", **headers}
        self.temperature = temperature
        self.tools = tools or []

    def _coerce_messages(self, messages: Any) -> list[BaseMessage]:
        if isinstance(messages, str):
            from langchain_core.messages import HumanMessage
            return [HumanMessage(content=messages)]
        return list(messages)

    def bind_tools(self, tools: list[Any]) -> OpenRouterChatModel:
        bound = copy(self)
        bound.tools = list(tools)
        return bound

    def with_structured_output(self, schema: type[Any], **_kwargs: Any) -> _StructuredOutput:
        return _StructuredOutput(self, schema)

    def invoke(self, messages: Any) -> AIMessage:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [_message_payload(message) for message in self._coerce_messages(messages)],
            "temperature": self.temperature,
        }
        if self.tools:
            payload["tools"] = [_tool_schema(tool) for tool in self.tools]
        try:
            response = httpx.post(self.base_url, headers=self.headers, json=payload, timeout=self.timeout)
        except httpx.HTTPError as exc:
            raise OpenRouterAPIError(f"OpenRouter request failed: {exc}") from exc
        if response.status_code >= 400:
            detail = response.text[:500]
            raise OpenRouterAPIError(
                f"OpenRouter HTTP {response.status_code}: {detail}",
                status_code=response.status_code,
            )
        try:
            message = response.json()["choices"][0]["message"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise OpenRouterAPIError("OpenRouter returned an invalid chat response.") from exc
        tool_calls = []
        for call in message.get("tool_calls", []) or []:
            function = call.get("function", {})
            try:
                args = json.loads(function.get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            tool_calls.append({"name": function.get("name", ""), "args": args, "id": call.get("id", "")})
        return AIMessage(content=message.get("content") or "", tool_calls=tool_calls)
