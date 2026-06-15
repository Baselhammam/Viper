"""
MCP client capability — tool registry and transport.

This is the TRANSPORT layer only.  It:
  - Maintains a registry of callable Python functions and their schemas.
  - Executes tool calls when told to (call(name, args)).
  - Returns the raw result — no decision-making about when or whether to call.

Decisions about WHEN to invoke a tool belong in the pipeline layer.

Design note: this is a proper class with instance-level state (no module
globals) so it is independently testable.  The legacy module-level registry
in app/tools/executor.py is preserved for backward compat with demo.py.

Usage:
    mcp = MCPClient()

    # Decorator style
    @mcp.register_tool(
        description="Return the current UTC time.",
        parameters={"type": "object", "properties": {}, "required": []},
    )
    def get_time() -> str:
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()

    # Functional style
    mcp.register("add", lambda a, b: a + b, "Add two numbers",
                 {"type": "object",
                  "properties": {"a": {"type": "number"}, "b": {"type": "number"}},
                  "required": ["a", "b"]})

    schemas = mcp.list_tools()   # pass to LLMCapability.chat_with_tool_response()
    result  = mcp.call("get_time", {})
"""
from typing import Any, Callable, Dict, List

from capabilities.interfaces import MCPCapability


class MCPClient(MCPCapability):
    """
    MCPCapability with an instance-level registry.

    Two built-in tools are registered automatically on init:
      get_current_datetime — returns local date/time string
      calculate            — safe arithmetic evaluator

    Add your own tools via register() or the @register_tool decorator.
    """

    def __init__(self) -> None:
        self._registry: Dict[str, Callable] = {}
        self._schemas:  List[dict] = []

        # Register built-ins immediately so the instance is useful out of the box.
        self._register_builtins()

    # ── MCPCapability interface ────────────────────────────────────────────────

    def register(
        self,
        name: str,
        fn: Callable,
        description: str,
        parameters: dict,
    ) -> None:
        """Add a callable to the registry with its schema."""
        self._registry[name] = fn
        self._schemas.append({
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": parameters,
            },
        })

    def register_tool(self, description: str, parameters: dict):
        """
        Decorator version of register().  The function's __name__ is used as
        the tool name so it matches the LLM's tool-call requests.

        Example:
            @mcp.register_tool(
                description="Greet someone by name.",
                parameters={
                    "type": "object",
                    "properties": {"name": {"type": "string"}},
                    "required": ["name"],
                },
            )
            def greet(name: str) -> str:
                return f"Hello, {name}!"
        """
        def decorator(fn: Callable) -> Callable:
            self.register(fn.__name__, fn, description, parameters)
            return fn
        return decorator

    def call(self, name: str, args: dict) -> Any:
        """
        Execute the named tool with args.
        Raises ValueError if the tool is not registered.
        """
        if name not in self._registry:
            raise ValueError(
                f"Tool '{name}' is not registered.  "
                f"Available: {list(self._registry)}"
            )
        return self._registry[name](**args)

    def list_tools(self) -> List[dict]:
        """Return all OpenAI-compatible tool schemas.  Pass to LLMCapability."""
        return list(self._schemas)

    def has_tool(self, name: str) -> bool:
        """True if a tool with this name is registered."""
        return name in self._registry

    # ── Built-in tools ────────────────────────────────────────────────────────

    def _register_builtins(self) -> None:
        """Register the two default utility tools every instance gets."""

        def get_current_datetime() -> str:
            from datetime import datetime
            return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        self.register(
            name="get_current_datetime",
            fn=get_current_datetime,
            description="Return the current local date and time.",
            parameters={"type": "object", "properties": {}, "required": []},
        )

        def calculate(expression: str) -> str:
            # Whitelist: only digits, operators, parens, dots, spaces.
            # Prevents code injection while supporting all standard arithmetic.
            allowed = set("0123456789+-*/()., ")
            if not all(c in allowed for c in expression):
                return "Error: expression contains disallowed characters."
            try:
                result = eval(expression, {"__builtins__": {}})  # noqa: S307
                return str(result)
            except Exception as exc:
                return f"Calculation error: {exc}"

        self.register(
            name="calculate",
            fn=calculate,
            description=(
                "Evaluate a safe arithmetic expression and return the numeric result. "
                "Supports: + - * / ( ) and decimal numbers."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "A Python arithmetic expression, e.g. '(42 * 1337) / 2'",
                    }
                },
                "required": ["expression"],
            },
        )
