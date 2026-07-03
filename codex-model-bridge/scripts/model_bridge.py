#!/usr/bin/env python
"""OpenAI-compatible model bridge for Codex MCP."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import traceback
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


DEFAULT_PROTOCOL_VERSION = "2025-03-26"


def clean(value: Any) -> Any:
    if isinstance(value, str):
        return value.encode("utf-8", "replace").decode("utf-8")
    if isinstance(value, list):
        return [clean(item) for item in value]
    if isinstance(value, dict):
        return {key: clean(item) for key, item in value.items()}
    return value


def load_config(path: str | Path) -> dict[str, Any]:
    config_path = Path(path).expanduser()
    with config_path.open("r", encoding="utf-8") as handle:
        config = json.load(handle)
    validate_config(config)
    return config


def validate_config(config: dict[str, Any]) -> None:
    models = config.get("models")
    if not isinstance(models, list) or not models:
        raise ValueError("Config must contain a non-empty 'models' list.")

    seen_ids: set[str] = set()
    seen_tools: set[str] = set()
    for index, model in enumerate(models):
        if not isinstance(model, dict):
            raise ValueError(f"models[{index}] must be an object.")
        for field in ("id", "endpoint", "model"):
            if not model.get(field):
                raise ValueError(f"models[{index}] is missing '{field}'.")
        model_id = str(model["id"])
        if model_id in seen_ids:
            raise ValueError(f"Duplicate model id: {model_id}")
        seen_ids.add(model_id)

        tool_name = tool_name_for(model)
        if tool_name in seen_tools:
            raise ValueError(f"Duplicate tool name: {tool_name}")
        if not re.fullmatch(r"[a-zA-Z0-9_]+", tool_name):
            raise ValueError(f"Tool name must contain only letters, digits, and underscores: {tool_name}")
        seen_tools.add(tool_name)

        envs = api_key_envs(model)
        if not envs:
            raise ValueError(f"Model {model_id} must define api_key_env or api_key_envs.")


def api_key_envs(model: dict[str, Any]) -> list[str]:
    if "api_key_envs" in model:
        envs = model["api_key_envs"]
        if isinstance(envs, str):
            return [envs]
        return [str(item) for item in envs]
    if "api_key_env" in model:
        return [str(model["api_key_env"])]
    return []


def api_key_for(model: dict[str, Any]) -> str:
    for env_name in api_key_envs(model):
        value = os.environ.get(env_name)
        if value:
            return value
    names = ", ".join(api_key_envs(model))
    raise RuntimeError(f"Missing API key environment variable for {model['id']}: {names}")


def tool_name_for(model: dict[str, Any]) -> str:
    if model.get("tool_name"):
        return str(model["tool_name"])
    safe = re.sub(r"[^a-zA-Z0-9]+", "_", str(model["id"])).strip("_").lower()
    return f"ask_{safe}"


def model_by_id_or_tool(config: dict[str, Any], name: str) -> dict[str, Any]:
    for model in config["models"]:
        if model["id"] == name or tool_name_for(model) == name:
            return model
    raise KeyError(f"Unknown model or tool: {name}")


def chat_completion(
    model: dict[str, Any],
    prompt: str,
    system: str | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
    thinking: str | None = None,
    reasoning_effort: str | None = None,
) -> dict[str, Any]:
    headers = {
        "Authorization": f"Bearer {api_key_for(model)}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    headers.update(model.get("headers") or {})

    messages: list[dict[str, str]] = []
    system_text = system if system is not None else model.get("system")
    if system_text:
        messages.append({"role": "system", "content": str(system_text)})
    messages.append({"role": "user", "content": prompt})

    body: dict[str, Any] = {
        "model": model["model"],
        "messages": messages,
        "stream": False,
    }
    if temperature is not None:
        body["temperature"] = temperature
    elif "temperature" in model:
        body["temperature"] = model["temperature"]
    if max_tokens is not None:
        body["max_tokens"] = max_tokens
    elif "max_tokens" in model:
        body["max_tokens"] = model["max_tokens"]

    body.update(model.get("extra_body") or {})
    if thinking is not None:
        body["thinking"] = {"type": thinking}
    if reasoning_effort is not None:
        body["reasoning_effort"] = reasoning_effort

    data = json.dumps(clean(body), ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        str(model["endpoint"]),
        data=data,
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=int(model.get("timeout_seconds", 180))) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} from {model['id']}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Request failed for {model['id']}: {exc}") from exc

    result = json.loads(raw)
    choice = (result.get("choices") or [{}])[0]
    message = choice.get("message") or {}
    return {
        "content": message.get("content") or "",
        "finish_reason": choice.get("finish_reason"),
        "model": result.get("model") or model["model"],
        "usage": result.get("usage") or {},
        "request_id": result.get("request_id") or result.get("id"),
        "raw": result,
    }


def tool_schema(model: dict[str, Any]) -> dict[str, Any]:
    display = model.get("display_name") or model["id"]
    return {
        "name": tool_name_for(model),
        "description": f"Ask {display} as an external model agent for Codex.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "Task or question for the external model."},
                "system": {"type": "string", "description": "Optional system instruction."},
                "thinking": {
                    "type": "string",
                    "enum": ["enabled", "disabled"],
                    "description": "Provider-specific reasoning toggle when supported.",
                },
                "reasoning_effort": {
                    "type": "string",
                    "enum": ["none", "minimal", "low", "medium", "high", "xhigh", "max"],
                    "description": "Provider-specific reasoning effort when supported.",
                },
                "max_tokens": {"type": "integer", "minimum": 1},
                "temperature": {"type": "number", "minimum": 0, "maximum": 2},
            },
            "required": ["prompt"],
            "additionalProperties": False,
        },
    }


def compare_tool_schema() -> dict[str, Any]:
    return {
        "name": "compare_external_models",
        "description": "Send one prompt to multiple configured external models and return their responses.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string"},
                "models": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional model ids or tool names. Defaults to all configured models.",
                },
                "system": {"type": "string"},
                "max_tokens": {"type": "integer", "minimum": 1},
                "temperature": {"type": "number", "minimum": 0, "maximum": 2},
            },
            "required": ["prompt"],
            "additionalProperties": False,
        },
    }


def mcp_respond(message_id: Any, result: Any = None, error: Any = None) -> None:
    message = {"jsonrpc": "2.0", "id": message_id}
    if error is None:
        message["result"] = result
    else:
        message["error"] = error
    sys.stdout.write(json.dumps(clean(message), ensure_ascii=False, separators=(",", ":")) + "\n")
    sys.stdout.flush()


def mcp_error(code: int, message: str, data: Any = None) -> dict[str, Any]:
    payload = {"code": code, "message": message}
    if data is not None:
        payload["data"] = data
    return payload


class McpServer:
    def __init__(self, config: dict[str, Any]):
        self.config = config

    def handle(self, request: dict[str, Any]) -> None:
        method = request.get("method")
        message_id = request.get("id")
        params = request.get("params") or {}

        if method == "initialize":
            server = self.config.get("server") or {}
            mcp_respond(
                message_id,
                {
                    "protocolVersion": params.get("protocolVersion", DEFAULT_PROTOCOL_VERSION),
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {
                        "name": server.get("name", "model-bridge"),
                        "version": server.get("version", "0.1.0"),
                    },
                },
            )
            return

        if method in {"notifications/initialized", "notifications/cancelled"}:
            return

        if method == "ping":
            mcp_respond(message_id, {})
            return

        if method == "tools/list":
            tools = [tool_schema(model) for model in self.config["models"]]
            if len(self.config["models"]) > 1:
                tools.append(compare_tool_schema())
            mcp_respond(message_id, {"tools": tools})
            return

        if method == "tools/call":
            self.call_tool(message_id, params)
            return

        if message_id is not None:
            mcp_respond(message_id, error=mcp_error(-32601, f"Method not found: {method}"))

    def call_tool(self, message_id: Any, params: dict[str, Any]) -> None:
        name = params.get("name")
        args = params.get("arguments") or {}
        try:
            if name == "compare_external_models":
                text = self.compare_models(args)
            else:
                model = model_by_id_or_tool(self.config, str(name))
                result = chat_completion(
                    model,
                    prompt=str(args["prompt"]),
                    system=args.get("system"),
                    max_tokens=args.get("max_tokens"),
                    temperature=args.get("temperature"),
                    thinking=args.get("thinking"),
                    reasoning_effort=args.get("reasoning_effort"),
                )
                text = format_result(result)
            mcp_respond(message_id, {"content": [{"type": "text", "text": text}], "isError": False})
        except Exception as exc:
            print(traceback.format_exc(), file=sys.stderr, flush=True)
            mcp_respond(
                message_id,
                {"content": [{"type": "text", "text": str(exc)}], "isError": True},
            )

    def compare_models(self, args: dict[str, Any]) -> str:
        selected = args.get("models") or [model["id"] for model in self.config["models"]]
        sections: list[str] = []
        for name in selected:
            model = model_by_id_or_tool(self.config, str(name))
            try:
                result = chat_completion(
                    model,
                    prompt=str(args["prompt"]),
                    system=args.get("system"),
                    max_tokens=args.get("max_tokens"),
                    temperature=args.get("temperature"),
                )
                sections.append(f"## {model.get('display_name') or model['id']}\n\n{format_result(result)}")
            except Exception as exc:
                sections.append(f"## {model.get('display_name') or model['id']}\n\nERROR: {exc}")
        return "\n\n".join(sections)


def format_result(result: dict[str, Any]) -> str:
    usage = result.get("usage") or {}
    suffix = ""
    if usage:
        suffix = "\n\n---\nUsage: " + json.dumps(clean(usage), ensure_ascii=False)
    return (result.get("content") or "") + suffix


def serve(config_path: str) -> int:
    server = McpServer(load_config(config_path))
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
            if isinstance(request, list):
                for item in request:
                    server.handle(item)
            else:
                server.handle(request)
        except Exception as exc:
            print(traceback.format_exc(), file=sys.stderr, flush=True)
            mcp_respond(None, error=mcp_error(-32700, "Parse error", str(exc)))
    return 0


def command_validate(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    print(f"OK: {len(config['models'])} model(s) configured.")
    for model in config["models"]:
        print(f"- {model['id']} -> {tool_name_for(model)} ({model['model']})")
    return 0


def command_list_tools(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    for model in config["models"]:
        print(tool_name_for(model))
    if len(config["models"]) > 1:
        print("compare_external_models")
    return 0


def command_ask(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    model = model_by_id_or_tool(config, args.model)
    result = chat_completion(
        model,
        prompt=args.prompt or sys.stdin.read(),
        system=args.system,
        max_tokens=args.max_tokens,
        temperature=args.temperature,
        thinking=args.thinking,
        reasoning_effort=args.reasoning_effort,
    )
    if args.json:
        without_raw = {key: value for key, value in result.items() if key != "raw"}
        print(json.dumps(clean(without_raw), ensure_ascii=False, indent=2))
    else:
        print(result["content"])
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Codex external model bridge.")
    sub = parser.add_subparsers(dest="command", required=True)

    serve_parser = sub.add_parser("serve", help="Run the stdio MCP server.")
    serve_parser.add_argument("--config", required=True)
    serve_parser.set_defaults(func=lambda args: serve(args.config))

    validate = sub.add_parser("validate-config", help="Validate bridge config.")
    validate.add_argument("--config", required=True)
    validate.set_defaults(func=command_validate)

    list_tools = sub.add_parser("list-tools", help="List MCP tool names for a config.")
    list_tools.add_argument("--config", required=True)
    list_tools.set_defaults(func=command_list_tools)

    ask = sub.add_parser("ask", help="Call one configured model from the CLI.")
    ask.add_argument("--config", required=True)
    ask.add_argument("--model", required=True, help="Model id or tool name.")
    ask.add_argument("--prompt", help="Prompt text. If omitted, stdin is used.")
    ask.add_argument("--system")
    ask.add_argument("--thinking", choices=["enabled", "disabled"])
    ask.add_argument("--reasoning-effort")
    ask.add_argument("--max-tokens", type=int)
    ask.add_argument("--temperature", type=float)
    ask.add_argument("--json", action="store_true")
    ask.set_defaults(func=command_ask)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())
