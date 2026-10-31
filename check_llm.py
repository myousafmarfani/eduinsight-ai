"""Check the OpenRouter setup:  python check_llm.py

Runs three small calls (plain reply, tool calling, structured output) and prints exactly what fails.
"""
from __future__ import annotations

from app.agents.llm import get_llm
from app.config import get_settings


def main() -> None:
    settings = get_settings()
    print(f"Model: {settings.llm_model}\nBase URL: {settings.openrouter_base_url}\nKey set: {settings.llm_configured}")
    llm = get_llm(settings)
    if llm is None:
        print("-> No LLM: set OPENROUTER_API_KEY in .env.")
        return

    from langchain_core.tools import tool
    from pydantic import BaseModel

    @tool
    def get_number() -> int:
        """Return the secret number."""
        return 42

    class Answer(BaseModel):
        word: str

    steps = [
        ("plain reply", lambda: llm.invoke("Reply with the single word OK.").content),
        ("tool calling", lambda: llm.bind_tools([get_number]).invoke("Call the get_number tool.").tool_calls),
        ("structured output", lambda: llm.with_structured_output(Answer, method="function_calling").invoke("Set word to hello.")),
    ]
    for name, run in steps:
        try:
            print(f"[ok]   {name}: {run()}")
        except Exception as exc:  # noqa: BLE001
            print(f"[FAIL] {name}: {type(exc).__name__}: {str(exc)[:400]}")


if __name__ == "__main__":
    main()