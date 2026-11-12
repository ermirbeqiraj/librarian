"""The Mistral chat client, shared by everyone who asks it for structured output: the
drafter and the refine step. The default model is the drafter's (refine pins its own), and
the retry while an answer doesn't fit the schema."""

import json
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.runnables import Runnable
from langchain_mistralai import ChatMistralAI
from pydantic import BaseModel

MODEL = "mistral-small-2603"  # pinned: what mistral-small-latest pointed to on 2026-11-12
MAX_RETRIES = 5


def structured[T: BaseModel](schema: type[T], model_name: str = MODEL) -> Runnable[Any, Any]:
    """A Mistral chat model that answers in `schema`, with the raw answer kept for retries."""
    return ChatMistralAI(model_name=model_name, temperature=0).with_structured_output(
        schema, include_raw=True
    )


def ask[T: BaseModel](
    model: Runnable[Any, Any],
    schema: type[T],
    messages: list[tuple[str, str]],
    max_retries: int = MAX_RETRIES,
) -> T:
    """Asks again while the answer doesn't fit the schema, then raises its error."""
    asked = list(messages)
    result = model.invoke(asked)
    for _ in range(max_retries):
        if result["parsing_error"] is None and isinstance(result["parsed"], schema):
            break
        asked.append(("ai", _answer(result["raw"])))
        asked.append(("human", _invalid(result["parsing_error"])))
        result = model.invoke(asked)
    if result["parsing_error"] is not None:
        raise result["parsing_error"]
    parsed = result["parsed"]
    if not isinstance(parsed, schema):
        raise TypeError(f"expected a {schema.__name__}, got {type(parsed).__name__}")
    return parsed


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
