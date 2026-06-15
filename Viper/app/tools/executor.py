"""
Tool registry and agentic executor.

Usage — register a new tool:

    from app.tools.executor import register_tool

    @register_tool(
        description="Look up the weather for a city.",
        parameters={
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "City name"},
            },
            "required": ["city"],
        },
    )
    def get_weather(city: str) -> str:
        return f"Sunny, 22 °C in {city}"  # replace with real API call

The tool loop (run_tool_loop) drives the conversation until the model
stops requesting calls and produces a plain-text answer.
"""
from typing import Any, Callable, Dict, List

# ── Registry ──────────────────────────────────────────────────────────────────

_REGISTRY: Dict[str, Callable] = {}     # name → function
_SCHEMAS: List[dict] = []               # OpenAI-compatible tool definitions


def register_tool(description: str, parameters: dict):
    """Decorator that adds a function to the tool registry."""
    def decorator(fn: Callable) -> Callable:
        _REGISTRY[fn.__name__] = fn
        _SCHEMAS.append({
            "type": "function",
            "function": {
                "name": fn.__name__,
                "description": description,
                "parameters": parameters,
            },
        })
        return fn
    return decorator


def get_tool_schemas() -> List[dict]:
    """Return all registered schemas — pass directly to LLMClient.chat_with_tools."""
    return list(_SCHEMAS)


def execute_tool(name: str, arguments: Dict[str, Any]) -> Any:
    """Call a registered tool by name with the provided arguments dict."""
    if name not in _REGISTRY:
        raise ValueError(f"Unknown tool '{name}'. Available: {list(_REGISTRY)}")
    return _REGISTRY[name](**arguments)


# ── Agentic loop ──────────────────────────────────────────────────────────────

def run_tool_loop(llm_client, messages: List[dict]) -> str:
    """
    Drive the model until it produces a final text answer with no tool calls.

    Steps each iteration:
      1. Call the LLM with tool schemas attached.
      2. If it returns tool_calls, execute each one and append the result.
      3. Repeat until the model stops requesting tools.

    Returns the final assistant text.
    """
    schemas = get_tool_schemas()

    while True:
        msg = llm_client.chat_with_tools(messages, schemas)

        # No tool calls → the model produced its final answer.
        if not msg.tool_calls:
            return msg.content or ""

        # Append the assistant turn (may have partial text + tool_calls).
        messages.append({
            "role": "assistant",
            "content": msg.content or "",
            "tool_calls": msg.tool_calls,
        })

        # Execute each requested tool and feed results back as "tool" messages.
        for call in msg.tool_calls:
            fn_name = call.function.name
            fn_args = call.function.arguments  # already a dict from the Ollama SDK
            try:
                result = execute_tool(fn_name, fn_args)
            except Exception as exc:
                result = f"Error in {fn_name}: {exc}"

            messages.append({"role": "tool", "content": str(result)})


# ── Built-in example tools ────────────────────────────────────────────────────

@register_tool(
    description="Return the current local date and time.",
    parameters={"type": "object", "properties": {}, "required": []},
)
def get_current_datetime() -> str:
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@register_tool(
    description=(
        "Evaluate a safe arithmetic expression and return the result. "
        "Use for calculations like '2 + 2', '10 / 3', '(5 * 8) - 2'."
    ),
    parameters={
        "type": "object",
        "properties": {
            "expression": {
                "type": "string",
                "description": "A Python arithmetic expression using only numbers and +-*/().",
            }
        },
        "required": ["expression"],
    },
)
def calculate(expression: str) -> str:
    # Whitelist: only digits, arithmetic operators, parens, dots, spaces.
    # This prevents code injection while still supporting all standard math.
    allowed = set("0123456789+-*/()., ")
    if not all(c in allowed for c in expression):
        return "Error: expression contains disallowed characters."
    try:
        result = eval(expression, {"__builtins__": {}})  # noqa: S307
        return str(result)
    except Exception as exc:
        return f"Calculation error: {exc}"
