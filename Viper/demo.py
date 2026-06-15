"""
End-to-end demo: ingest the sample manual, then prove the full pipeline works.

Covers:
  1. Document ingestion + RAG question answering
  2. Tool-calling (calculator + datetime)
  3. Plain chat (code generation)

Prerequisites: Ollama running + mistral:latest pulled.
Run: python demo.py
"""
from app.router import Viper

SAMPLE_MANUAL = "data/sample_manual.md"


def separator(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print("=" * 60)


def main() -> None:
    separator("Viper AI Assistant — End-to-End Demo")

    viper = Viper()

    # ── 1. Ingest the sample manual ───────────────────────────────────────────
    separator("Step 1 — Ingest sample manual")
    print(f"File: {SAMPLE_MANUAL}\n")
    chunks = viper.ingest([SAMPLE_MANUAL])
    print(f"\nResult: {chunks} chunks stored in ChromaDB.")

    # ── 2. RAG questions ──────────────────────────────────────────────────────
    separator("Step 2 — RAG Question Answering")

    questions = [
        "How do I reset the device to factory settings?",
        "What does it mean when the LED is blinking red rapidly?",
        "What are the device's Wi-Fi specifications?",
    ]

    for q in questions:
        print(f"\nQ: {q}")
        answer = viper.ask(q)
        print(f"A: {answer}")
        print("-" * 40)

    # ── 3. Tool calling ───────────────────────────────────────────────────────
    separator("Step 3 — Tool Calling (calculator + datetime)")

    tool_prompts = [
        "What is 42 multiplied by 1337?",
        "What is today's date and time?",
        "Calculate (256 * 256) - 1 and tell me the result.",
    ]

    for prompt in tool_prompts:
        print(f"\nPrompt: {prompt}")
        response = viper.run_with_tools(prompt)
        print(f"Response: {response}")
        print("-" * 40)

    # ── 4. Code generation ────────────────────────────────────────────────────
    separator("Step 4 — Code Generation (plain chat)")
    code_prompt = "Write a Python function that reads a JSON file and returns it as a dict."
    print(f"Prompt: {code_prompt}\n")
    code = viper.chat(code_prompt)
    print(code)

    separator("Demo complete!")


if __name__ == "__main__":
    main()
