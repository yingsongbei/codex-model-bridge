#!/usr/bin/env python
"""OpenAI-compatible model bridge for Codex MCP."""

from __future__ import annotations

import argparse
import copy
import json
import os
import re
import shlex
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
BRIDGE_VERSION = "0.3.0"
THINKING_MODES = ("enabled", "disabled")
REASONING_EFFORTS = ("none", "minimal", "low", "medium", "high", "xhigh", "max")
RESERVED_TOOL_NAMES = {"compare_external_models", "model_bridge_status"}

PROVIDER_PRESETS: dict[str, dict[str, Any]] = {
    "glm": {
        "id": "glm-5-2",
        "tool_name": "ask_glm_5_2",
        "display_name": "GLM 5.2",
        "endpoint": "https://api.z.ai/api/paas/v4/chat/completions",
        "api_key_envs": ["ZAI_API_KEY", "ZHIPU_API_KEY"],
        "model": "glm-5.2",
        "capabilities": {"thinking": True, "reasoning_effort": True},
    },
    "deepseek": {
        "id": "deepseek-chat",
        "tool_name": "ask_deepseek",
        "display_name": "DeepSeek Chat",
        "endpoint": "https://api.deepseek.com/chat/completions",
        "api_key_envs": ["DEEPSEEK_API_KEY"],
        "model": "deepseek-chat",
        "capabilities": {"thinking": False, "reasoning_effort": False},
    },
    "qwen": {
        "id": "qwen-plus",
        "tool_name": "ask_qwen",
        "display_name": "Qwen Plus",
        "endpoint": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
        "api_key_envs": ["DASHSCOPE_API_KEY"],
        "model": "qwen-plus",
        "capabilities": {"thinking": False, "reasoning_effort": False},
    },
}


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
        if "enabled" in model and not isinstance(model["enabled"], bool):
            raise ValueError(f"models[{index}].enabled must be true or false.")
        for field in ("id", "endpoint", "model"):
            if not model.get(field):
                raise ValueError(f"models[{index}] is missing '{field}'.")
        model_id = str(model["id"])
        if model_id in seen_ids:
            raise ValueError(f"Duplicate model id: {model_id}")
        seen_ids.add(model_id)

        tool_name = tool_name_for(model)
        if tool_name in RESERVED_TOOL_NAMES:
            raise ValueError(f"Reserved tool name cannot be used by a model: {tool_name}")
        if tool_name in seen_tools:
            raise ValueError(f"Duplicate tool name: {tool_name}")
        if not re.fullmatch(r"[a-zA-Z0-9_]+", tool_name):
            raise ValueError(f"Tool name must contain only letters, digits, and underscores: {tool_name}")
        seen_tools.add(tool_name)

        envs = api_key_envs(model)
        if not envs:
            raise ValueError(f"Model {model_id} must define api_key_env or api_key_envs.")
        for env_name in envs:
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", env_name):
                raise ValueError(
                    f"Model {model_id} API key environment variable must contain only letters, "
                    f"digits, and underscores, and cannot start with a digit: {env_name}"
                )

        capabilities = model.get("capabilities") or {}
        if not isinstance(capabilities, dict):
            raise ValueError(f"Model {model_id} capabilities must be an object.")
        for capability in ("thinking", "reasoning_effort"):
            if capability in capabilities and not isinstance(capabilities[capability], bool):
                raise ValueError(f"Model {model_id} capability '{capability}' must be true or false.")
        if "thinking_field" in capabilities and not (
            isinstance(capabilities["thinking_field"], str) and capabilities["thinking_field"].strip()
        ):
            raise ValueError(f"Model {model_id} capability 'thinking_field' must be a non-empty string.")
        if "thinking_values" in capabilities:
            values = capabilities["thinking_values"]
            if not isinstance(values, dict) or not all(mode in values for mode in THINKING_MODES):
                raise ValueError(
                    f"Model {model_id} capability 'thinking_values' must define enabled and disabled."
                )

        extra_body = model.get("extra_body") or {}
        if not isinstance(extra_body, dict):
            raise ValueError(f"Model {model_id} extra_body must be an object.")
        thinking_field = thinking_field_for(model)
        if capabilities.get("thinking") is False and thinking_field in extra_body:
            raise ValueError(
                f"Model {model_id} sets extra_body.{thinking_field} while capabilities.thinking is false."
            )
        if capabilities.get("reasoning_effort") is False and "reasoning_effort" in extra_body:
            raise ValueError(
                f"Model {model_id} sets extra_body.reasoning_effort while "
                "capabilities.reasoning_effort is false."
            )


def model_is_enabled(model: dict[str, Any]) -> bool:
    return model.get("enabled", True) is not False


def enabled_models(config: dict[str, Any]) -> list[dict[str, Any]]:
    return [model for model in config["models"] if model_is_enabled(model)]


def api_key_envs(model: dict[str, Any]) -> list[str]:
    if "api_key_envs" in model:
        envs = model["api_key_envs"]
        if isinstance(envs, str):
            return [envs.strip()] if envs.strip() else []
        if isinstance(envs, list):
            return [str(item).strip() for item in envs if str(item).strip()]
        return []
    if "api_key_env" in model:
        env = str(model["api_key_env"]).strip()
        return [env] if env else []
    return []


def api_key_for(model: dict[str, Any]) -> str:
    for env_name in api_key_envs(model):
        value = os.environ.get(env_name)
        if value:
            return value
    names = ", ".join(api_key_envs(model))
    raise RuntimeError(f"Missing API key environment variable for {model['id']}: {names}")


def detected_api_key_env(model: dict[str, Any]) -> str | None:
    for env_name in api_key_envs(model):
        if os.environ.get(env_name):
            return env_name
    return None


def supports_capability(model: dict[str, Any], capability: str) -> bool:
    capabilities = model.get("capabilities") or {}
    if capability in capabilities:
        return bool(capabilities[capability])
    return capability in (model.get("extra_body") or {})


def thinking_field_for(model: dict[str, Any]) -> str:
    capabilities = model.get("capabilities") or {}
    return str(capabilities.get("thinking_field") or "thinking").strip()


def thinking_values_for(model: dict[str, Any]) -> dict[str, Any]:
    capabilities = model.get("capabilities") or {}
    configured = capabilities.get("thinking_values")
    if isinstance(configured, dict) and all(mode in configured for mode in THINKING_MODES):
        return configured
    return {
        "enabled": {"type": "enabled"},
        "disabled": {"type": "disabled"},
    }


def thinking_value_for(model: dict[str, Any], mode: str) -> Any:
    return copy.deepcopy(thinking_values_for(model)[mode])


def default_thinking_mode(model: dict[str, Any]) -> str | None:
    value = (model.get("extra_body") or {}).get(thinking_field_for(model))
    for mode, configured_value in thinking_values_for(model).items():
        if value == configured_value:
            return mode
    if isinstance(value, dict):
        value = value.get("type")
    return str(value) if value in THINKING_MODES else None


def default_reasoning_effort(model: dict[str, Any]) -> str | None:
    value = (model.get("extra_body") or {}).get("reasoning_effort")
    return str(value) if value is not None else None


def tool_name_for(model: dict[str, Any]) -> str:
    if model.get("tool_name"):
        return str(model["tool_name"])
    safe = re.sub(r"[^a-zA-Z0-9]+", "_", str(model["id"])).strip("_").lower()
    return f"ask_{safe}"


def model_by_id_or_tool(
    config: dict[str, Any],
    name: str,
    include_disabled: bool = False,
) -> dict[str, Any]:
    models = config["models"] if include_disabled else enabled_models(config)
    for model in models:
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
        if not supports_capability(model, "thinking"):
            raise ValueError(
                f"Model {model['id']} is not configured with thinking support. "
                "Set capabilities.thinking to true only if the provider supports it."
            )
        body[thinking_field_for(model)] = thinking_value_for(model, thinking)
    if reasoning_effort is not None:
        if not supports_capability(model, "reasoning_effort"):
            raise ValueError(
                f"Model {model['id']} is not configured with reasoning_effort support. "
                "Set capabilities.reasoning_effort to true only if the provider supports it."
            )
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
    key_env = detected_api_key_env(model)
    key_note = (
        f"API key detected via {key_env}."
        if key_env
        else f"API key not detected; set one of: {', '.join(api_key_envs(model))}."
    )
    properties: dict[str, Any] = {
        "prompt": {"type": "string", "description": "Task or question for the external model."},
        "system": {"type": "string", "description": "Optional system instruction."},
        "max_tokens": {"type": "integer", "minimum": 1},
        "temperature": {"type": "number", "minimum": 0, "maximum": 2},
    }
    if supports_capability(model, "thinking"):
        default_mode = default_thinking_mode(model)
        default_note = f" Current config default: {default_mode}." if default_mode else ""
        properties["thinking"] = {
            "type": "string",
            "enum": list(THINKING_MODES),
            "description": "Enable or disable provider thinking for this call." + default_note,
        }
    if supports_capability(model, "reasoning_effort"):
        default_effort = default_reasoning_effort(model)
        default_note = f" Current config default: {default_effort}." if default_effort else ""
        properties["reasoning_effort"] = {
            "type": "string",
            "enum": list(REASONING_EFFORTS),
            "description": "Provider reasoning effort for this call." + default_note,
        }
    return {
        "name": tool_name_for(model),
        "description": f"Ask {display} as an external model agent for Codex. {key_note}",
        "inputSchema": {
            "type": "object",
            "properties": properties,
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
                    "description": (
                        "Optional model ids or tool names. By default, models without detected API keys "
                        "are skipped."
                    ),
                },
                "system": {"type": "string"},
                "max_tokens": {"type": "integer", "minimum": 1},
                "temperature": {"type": "number", "minimum": 0, "maximum": 2},
            },
            "required": ["prompt"],
            "additionalProperties": False,
        },
    }


def status_tool_schema() -> dict[str, Any]:
    return {
        "name": "model_bridge_status",
        "description": "Show configured models, API key availability, and thinking defaults without exposing secrets.",
        "inputSchema": {
            "type": "object",
            "properties": {},
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


def model_status_line(model: dict[str, Any]) -> str:
    state = "enabled" if model_is_enabled(model) else "disabled"
    key_env = detected_api_key_env(model)
    key_status = f"key found via {key_env}" if key_env else f"key missing ({', '.join(api_key_envs(model))})"
    if supports_capability(model, "thinking"):
        thinking = default_thinking_mode(model) or "provider default"
        thinking_status = f"thinking supported, default {thinking}"
    else:
        thinking_status = "thinking not enabled for this model"
    return f"- {model['id']} ({model['model']}): {state}; {key_status}; {thinking_status}"


def format_bridge_status(config: dict[str, Any]) -> str:
    ready = sum(1 for model in enabled_models(config) if detected_api_key_env(model))
    active = len(enabled_models(config))
    lines = [f"Model bridge: {ready}/{active} enabled model(s) have an API key."]
    lines.extend(model_status_line(model) for model in config["models"])
    lines.append("Restart Codex after adding or changing user environment variables.")
    return "\n".join(lines)


def models_for_key_help(
    config: dict[str, Any],
    model_name: str | None = None,
) -> list[dict[str, Any]]:
    if model_name:
        return [model_by_id_or_tool(config, model_name, include_disabled=True)]
    return enabled_models(config)


def powershell_quote(value: str | Path) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def format_key_help(
    config: dict[str, Any],
    config_path: str | Path,
    model_name: str | None = None,
    platform_name: str | None = None,
    script_path: str | Path | None = None,
) -> str:
    platform_name = platform_name or ("windows" if os.name == "nt" else "posix")
    if platform_name not in {"windows", "posix"}:
        raise ValueError("platform_name must be 'windows' or 'posix'.")

    models = models_for_key_help(config, model_name)
    resolved_script = Path(script_path or __file__).resolve()
    resolved_config = Path(config_path).expanduser().resolve()
    lines = [
        "API KEY SETUP - LOCAL COMPUTER ONLY",
        "Do not paste an API key into Codex, chat, GitHub, screenshots, or the JSON config.",
        "The bridge is an external MCP agent. These steps do not change Codex's own login or primary model.",
    ]

    if not models:
        lines.append("No enabled models are configured.")
        return "\n".join(lines)

    for model in models:
        display = str(model.get("display_name") or model["id"])
        env_names = api_key_envs(model)
        detected_env = detected_api_key_env(model)
        env_name = detected_env or env_names[0]
        status = f"A key is currently detected via {detected_env}." if detected_env else "No key is detected yet."
        thinking_arg = " --thinking disabled" if supports_capability(model, "thinking") else ""

        lines.extend(
            [
                "",
                f"MODEL: {display} ({model['id']})",
                status,
                f"Accepted environment variable name(s): {', '.join(env_names)}",
                f"The commands below use: {env_name}",
                "1. Create or copy a key in the model provider's own console.",
                "2. Replace PASTE_YOUR_KEY_HERE locally. Never send the real value to an assistant.",
            ]
        )

        if platform_name == "windows":
            script_text = powershell_quote(resolved_script)
            config_text = powershell_quote(resolved_config)
            model_text = powershell_quote(str(model["id"]))
            lines.extend(
                [
                    f'   [Environment]::SetEnvironmentVariable("{env_name}", "PASTE_YOUR_KEY_HERE", "User")',
                    "3. Success is silent: PowerShell prints nothing and simply returns to the PS prompt.",
                    "   This is normal. Do not assume it failed just because no message appeared.",
                    "4. Verify safely without displaying the key:",
                    (
                        f'   if ([string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable("{env_name}", '
                        f'"User"))) {{ "NOT SET" }} else {{ "SET" }}'
                    ),
                    "5. Close that PowerShell window and open a new one so it inherits the new value.",
                    "6. In the new window, run the checks:",
                    f"   python {script_text} doctor --config {config_text}",
                    (
                        f"   python {script_text} ask --config {config_text} --model {model_text} "
                        f"--prompt 'Reply exactly: OK' --max-tokens 32{thinking_arg}"
                    ),
                ]
            )
        else:
            script_text = shlex.quote(str(resolved_script))
            config_text = shlex.quote(str(resolved_config))
            lines.extend(
                [
                    f"   export {env_name}='PASTE_YOUR_KEY_HERE'",
                    "3. Success is silent: export prints nothing and returns to the shell prompt.",
                    "4. Verify safely without displaying the key:",
                    f'   if [ -n "${{{env_name}:-}}" ]; then echo "SET"; else echo "NOT SET"; fi',
                    "5. This export applies to the current terminal. Use the same terminal for the checks:",
                    f"   python {script_text} doctor --config {config_text}",
                    (
                        f"   python {script_text} ask --config {config_text} --model {shlex.quote(str(model['id']))} "
                        f"--prompt 'Reply exactly: OK' --max-tokens 32{thinking_arg}"
                    ),
                    "6. For persistence, use your shell profile or OS secret manager, then restart Codex.",
                ]
            )

        lines.extend(
            [
                "7. Add the MCP entry and restart Codex only after the real request returns OK.",
                "To replace this key later, revoke the old key in the provider console and run the same",
                f"environment-variable command with the new value. Keep the name {env_name} unchanged.",
                "You do not need to edit the bridge JSON or Codex authentication settings.",
            ]
        )

    return "\n".join(lines)


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
                        "version": server.get("version", BRIDGE_VERSION),
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
            models = enabled_models(self.config)
            tools = [status_tool_schema(), *[tool_schema(model) for model in models]]
            if len(models) > 1:
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
            if name == "model_bridge_status":
                text = format_bridge_status(self.config)
            elif name == "compare_external_models":
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
        requested = args.get("models")
        skipped: list[str] = []
        if requested:
            selected = [str(name) for name in requested]
        else:
            models = enabled_models(self.config)
            if not models:
                raise RuntimeError("No models are enabled in the bridge config.")
            selected = [model["id"] for model in models if detected_api_key_env(model)]
            skipped = [model["id"] for model in models if not detected_api_key_env(model)]
            if not selected:
                env_names = sorted({name for model in models for name in api_key_envs(model)})
                raise RuntimeError(
                    "No enabled model has a detected API key. Set one of: " + ", ".join(env_names)
                )
        sections: list[str] = []
        if skipped:
            sections.append("Skipped models without detected API keys: " + ", ".join(skipped))
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


def prompt_text(label: str, default: str | None = None, required: bool = True) -> str:
    suffix = f" [{default}]" if default not in (None, "") else ""
    while True:
        try:
            value = input(f"{label}{suffix}: ").strip()
        except EOFError as exc:
            raise RuntimeError("Interactive configuration requires a terminal with stdin.") from exc
        if value:
            return value
        if default is not None:
            return default
        if not required:
            return ""
        print("A value is required.")


def prompt_yes_no(label: str, default: bool | None = None) -> bool:
    suffix = " [Y/n]" if default is True else " [y/N]" if default is False else " [y/n]"
    while True:
        try:
            value = input(f"{label}{suffix}: ").strip().lower()
        except EOFError as exc:
            raise RuntimeError("Interactive configuration requires a terminal with stdin.") from exc
        if value in {"y", "yes"}:
            return True
        if value in {"n", "no"}:
            return False
        if not value and default is not None:
            return default
        print("Enter y or n.")


def prompt_number(label: str, default: int | float, cast: Any, minimum: float) -> int | float:
    while True:
        raw = prompt_text(label, str(default))
        try:
            value = cast(raw)
        except ValueError:
            print("Enter a valid number.")
            continue
        if value < minimum:
            print(f"Enter a value greater than or equal to {minimum}.")
            continue
        return value


def prompt_choice(label: str, choices: tuple[str, ...], default: str) -> str:
    while True:
        value = prompt_text(label, default).lower()
        if value in choices:
            return value
        print("Choose one of: " + ", ".join(choices) + ".")


def prompt_json_value(label: str, default: Any) -> Any:
    default_text = json.dumps(default, ensure_ascii=False, separators=(",", ":"))
    while True:
        raw = prompt_text(label, default_text)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            print("Enter a valid JSON value.")


def thinking_value_style(model: dict[str, Any]) -> str:
    values = thinking_values_for(model)
    enabled = values["enabled"]
    disabled = values["disabled"]
    if isinstance(enabled, dict) and isinstance(disabled, dict):
        return "object"
    if enabled is True and disabled is False:
        return "boolean"
    if isinstance(enabled, str) and isinstance(disabled, str):
        return "string"
    return "custom"


def choose_preset() -> dict[str, Any]:
    print("Presets: glm, deepseek, qwen, custom")
    aliases = {"1": "glm", "2": "deepseek", "3": "qwen", "4": "custom"}
    while True:
        choice = prompt_text("Choose a preset", "custom").lower()
        choice = aliases.get(choice, choice)
        if choice == "custom":
            return {}
        if choice in PROVIDER_PRESETS:
            return copy.deepcopy(PROVIDER_PRESETS[choice])
        print("Choose glm, deepseek, qwen, or custom.")


def configure_model(base: dict[str, Any], requested_id: str | None = None) -> dict[str, Any]:
    model = copy.deepcopy(base)
    model_id = prompt_text("Local model id", requested_id or model.get("id"))
    model["id"] = model_id
    model["display_name"] = prompt_text("Display name", str(model.get("display_name") or model_id))
    model["tool_name"] = prompt_text("Codex tool name", str(model.get("tool_name") or tool_name_for(model)))
    model["endpoint"] = prompt_text("OpenAI-compatible chat completions endpoint", model.get("endpoint"))
    model["model"] = prompt_text("Provider model id", str(model.get("model") or model_id))

    env_default = ",".join(api_key_envs(model)) or "MODEL_API_KEY"
    env_text = prompt_text("API key environment variable(s), comma-separated", env_default)
    model["api_key_envs"] = [item.strip() for item in env_text.split(",") if item.strip()]
    model.pop("api_key_env", None)

    model["system"] = prompt_text(
        "Default system instruction",
        str(model.get("system") or "You are a careful external expert agent for Codex."),
    )
    model["temperature"] = prompt_number(
        "Default temperature", float(model.get("temperature", 0.7)), float, 0
    )
    model["max_tokens"] = prompt_number(
        "Default max tokens", int(model.get("max_tokens", 2048)), int, 1
    )
    model["enabled"] = prompt_yes_no("Expose this model to Codex", model_is_enabled(model))

    capabilities = dict(model.get("capabilities") or {})
    extra_body = dict(model.get("extra_body") or {})
    old_thinking_field = thinking_field_for(model)
    current_mode = default_thinking_mode(model)
    supports_thinking = prompt_yes_no(
        "Does this API support the thinking field?",
        supports_capability(model, "thinking"),
    )
    capabilities["thinking"] = supports_thinking
    if supports_thinking:
        thinking_field = prompt_text("Thinking request field", old_thinking_field)
        current_values = thinking_values_for(model)
        current_style = thinking_value_style(model)
        value_style = prompt_choice(
            "Thinking value style (object, string, boolean, or custom)",
            ("object", "string", "boolean", "custom"),
            current_style,
        )
        if value_style == current_style and value_style != "custom":
            thinking_values = copy.deepcopy(current_values)
        elif value_style == "object":
            thinking_values = {
                "enabled": {"type": "enabled"},
                "disabled": {"type": "disabled"},
            }
        elif value_style == "string":
            thinking_values = {"enabled": "enabled", "disabled": "disabled"}
        elif value_style == "boolean":
            thinking_values = {"enabled": True, "disabled": False}
        else:
            thinking_values = {
                "enabled": prompt_json_value("JSON value when thinking is enabled", current_values["enabled"]),
                "disabled": prompt_json_value("JSON value when thinking is disabled", current_values["disabled"]),
            }
        capabilities["thinking_field"] = thinking_field
        capabilities["thinking_values"] = thinking_values
        if old_thinking_field != thinking_field:
            extra_body.pop(old_thinking_field, None)
        default_enabled = None if current_mode is None else current_mode == "enabled"
        thinking_enabled = prompt_yes_no("Enable thinking by default", default_enabled)
        mode = "enabled" if thinking_enabled else "disabled"
        extra_body[thinking_field] = copy.deepcopy(thinking_values[mode])
    else:
        extra_body.pop(old_thinking_field, None)
        capabilities.pop("thinking_field", None)
        capabilities.pop("thinking_values", None)

    supports_effort = prompt_yes_no(
        "Does this API support reasoning_effort?",
        supports_capability(model, "reasoning_effort"),
    )
    capabilities["reasoning_effort"] = supports_effort
    if supports_effort:
        current_effort = default_reasoning_effort(model) or ""
        effort = prompt_text(
            "Default reasoning effort (blank for provider default)",
            current_effort,
            required=False,
        ).lower()
        while effort and effort not in REASONING_EFFORTS:
            print("Choose one of: " + ", ".join(REASONING_EFFORTS) + ", or leave blank.")
            effort = prompt_text("Default reasoning effort", "", required=False).lower()
        if effort:
            extra_body["reasoning_effort"] = effort
        else:
            extra_body.pop("reasoning_effort", None)
    else:
        extra_body.pop("reasoning_effort", None)

    model["capabilities"] = capabilities
    if extra_body:
        model["extra_body"] = extra_body
    else:
        model.pop("extra_body", None)
    return model


def command_configure(args: argparse.Namespace) -> int:
    config_path = Path(args.config).expanduser()
    if config_path.exists():
        config = load_config(config_path)
        print(f"Loaded {len(config['models'])} model(s) from {config_path}.")
    else:
        config = {"server": {"name": "model-bridge", "version": BRIDGE_VERSION}, "models": []}
        print(f"Creating {config_path}.")

    print("This wizard stores environment variable names only. It never asks for or stores API keys.")
    while True:
        existing: dict[str, Any] | None = None
        requested_id: str | None = None
        if config["models"]:
            ids = ", ".join(str(model["id"]) for model in config["models"])
            print(f"Configured model ids: {ids}")
            requested_id = prompt_text("Model id to add or update", str(config["models"][0]["id"]))
            existing = next((model for model in config["models"] if model["id"] == requested_id), None)

        base = existing if existing is not None else choose_preset()
        configured = configure_model(base, requested_id=requested_id)
        replaced_ids = {configured["id"]}
        if existing is not None:
            replaced_ids.add(existing["id"])
        config["models"] = [model for model in config["models"] if model["id"] not in replaced_ids]
        config["models"].append(configured)

        if not prompt_yes_no("Configure another model", False):
            break

    validate_config(config)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = config_path.with_name(config_path.name + ".tmp")
    temp_path.write_text(json.dumps(clean(config), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp_path.replace(config_path)

    print(f"Saved {config_path}.")
    print()
    print(format_key_help(config, config_path))
    return 0


def command_validate(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    print(f"OK: {len(config['models'])} model(s) configured.")
    for model in config["models"]:
        state = "enabled" if model_is_enabled(model) else "disabled"
        print(f"- {model['id']} -> {tool_name_for(model)} ({model['model']}, {state})")
    return 0


def command_doctor(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    version_state = "OK" if sys.version_info >= (3, 10) else "Python 3.10+ required"
    print(f"Python: {version} ({version_state})")
    print(f"Config: {Path(args.config).expanduser().resolve()}")
    print(format_bridge_status(config))
    missing = [model for model in enabled_models(config) if not detected_api_key_env(model)]
    if missing:
        print()
        print("One or more enabled models are missing an API key.")
        print(
            f'Run: python "{Path(__file__).resolve()}" key-help --config '
            f'"{Path(args.config).expanduser().resolve()}"'
        )
    else:
        print()
        print("Environment-variable presence check passed. A real provider request is still required.")
    return 0 if sys.version_info >= (3, 10) else 1


def command_key_help(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    print(
        format_key_help(
            config,
            args.config,
            model_name=args.model,
            platform_name=args.platform,
        )
    )
    return 0


def command_list_tools(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    print("model_bridge_status")
    models = enabled_models(config)
    for model in models:
        print(tool_name_for(model))
    if len(models) > 1:
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

    configure = sub.add_parser("configure", help="Interactively create or update a private bridge config.")
    configure.add_argument("--config", required=True)
    configure.set_defaults(func=command_configure)

    validate = sub.add_parser("validate-config", help="Validate bridge config.")
    validate.add_argument("--config", required=True)
    validate.set_defaults(func=command_validate)

    list_tools = sub.add_parser("list-tools", help="List MCP tool names for a config.")
    list_tools.add_argument("--config", required=True)
    list_tools.set_defaults(func=command_list_tools)

    doctor = sub.add_parser("doctor", help="Check config, API key availability, and thinking defaults.")
    doctor.add_argument("--config", required=True)
    doctor.set_defaults(func=command_doctor)

    key_help = sub.add_parser("key-help", help="Show safe local API key setup and replacement steps.")
    key_help.add_argument("--config", required=True)
    key_help.add_argument("--model", help="Optional model id or tool name.")
    key_help.add_argument("--platform", choices=["windows", "posix"])
    key_help.set_defaults(func=command_key_help)

    ask = sub.add_parser("ask", help="Call one configured model from the CLI.")
    ask.add_argument("--config", required=True)
    ask.add_argument("--model", required=True, help="Model id or tool name.")
    ask.add_argument("--prompt", help="Prompt text. If omitted, stdin is used.")
    ask.add_argument("--system")
    ask.add_argument("--thinking", choices=THINKING_MODES)
    ask.add_argument("--reasoning-effort", choices=REASONING_EFFORTS)
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
