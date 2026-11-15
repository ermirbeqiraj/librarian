"""Mistral's chat models: an answer in a schema (the drafter, refine), asked again while it
doesn't fit, or a turn with tools (the agent)."""

import json
from typing import Any

import httpx
from langchain_core.language_models import LanguageModelInput
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool
from langchain_mistralai import ChatMistralAI
from pydantic import BaseModel

from librarian.application.ingest.paid_calls import PaidCalls
from librarian.application.retrieve.ports import Usage

MAX_RETRIES = 5


class Mistral:
    def __init__(self, model: str, max_retries: int = MAX_RETRIES) -> None:
        self.model = model
        self.max_retries = max_retries

    def answer[T: BaseModel](
        self,
        schema: type[T],
        messages: list[tuple[str, str]],
        *,
        paid_calls: PaidCalls | None = None,
        usage: Usage | None = None,
    ) -> T:
        chat = ChatMistralAI(model_name=self.model, temperature=0)
        if paid_calls is not None:
            watch(chat.client, paid_calls)
        structured = chat.with_structured_output(schema, include_raw=True)
        return ask(structured, schema, messages, self.max_retries, usage)

    def with_tools(
        self, tools: list[BaseTool], reasoning_effort: str, tool_choice: str | None = None
    ) -> Runnable[LanguageModelInput, AIMessage]:
        chat = ChatMistralAI(
            model_name=self.model,
            temperature=0,
            model_kwargs={"reasoning_effort": reasoning_effort},
        )
        return chat.bind_tools(tools, tool_choice=tool_choice)


def watch(client: httpx.Client, paid_calls: PaidCalls) -> None:
    """Every request the client sends spends one paid call, its own retries included."""

    def spend(request: httpx.Request) -> None:
        paid_calls.spend()

    client.event_hooks["request"].append(spend)


def ask[T: BaseModel](
    model: Runnable[Any, Any],
    schema: type[T],
    messages: list[tuple[str, str]],
    max_retries: int = MAX_RETRIES,
    usage: Usage | None = None,
) -> T:
    """Asks again while the answer doesn't fit the schema, then raises its error."""
    asked = list(messages)
    result = _invoke(model, asked, usage)
    for _ in range(max_retries):
        if result["parsing_error"] is None and isinstance(result["parsed"], schema):
            break
        asked.append(("ai", _answer(result["raw"])))
        asked.append(("human", _invalid(result["parsing_error"])))
        result = _invoke(model, asked, usage)
    if result["parsing_error"] is not None:
        raise result["parsing_error"]
    parsed = result["parsed"]
    if not isinstance(parsed, schema):
        raise TypeError(f"expected a {schema.__name__}, got {type(parsed).__name__}")
    return parsed


def _invoke(model: Runnable[Any, Any], messages: list[tuple[str, str]], usage: Usage | None) -> Any:
    result = model.invoke(messages)
    raw = result["raw"]
    if usage is not None and isinstance(raw, AIMessage) and raw.usage_metadata is not None:
        usage.input_tokens += raw.usage_metadata["input_tokens"]
        usage.output_tokens += raw.usage_metadata["output_tokens"]
    return result


def _answer(raw: BaseMessage) -> str:
    if isinstance(raw, AIMessage) and raw.tool_calls:
        return json.dumps(raw.tool_calls[0]["args"], ensure_ascii=False)
    return str(raw.content)


def _invalid(error: BaseException | None) -> str:
    if error is None:
        return "Your answer has no structured output. Return the whole object."
    return (
        f"Your answer does not fit the schema:\n{error}\nFix it and return the whole object again."
    )
