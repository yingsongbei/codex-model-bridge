---
name: codex-model-bridge
description: Connect external OpenAI-compatible LLMs to Codex as MCP-powered external model agents. Use when the user wants to add, configure, test, or invoke models such as GLM, DeepSeek, Qwen, Kimi, Baichuan, OpenRouter, or other domestic and third-party models from Codex as reviewer, writer, planner, code critic, second-opinion agent, or model-comparison assistant.
---

# Codex Model Bridge

## Overview

Use this skill to install and operate a local MCP server that exposes external LLMs as Codex-callable tools. Treat these models as external expert agents, not native Codex subagents: they can provide analysis, writing, critique, review, and alternatives, while Codex remains the orchestrator.

## Safety Rules

- Never write API keys into Git-tracked files, Codex config, or examples.
- Store secrets in environment variables named by the bridge config.
- Inspect generated configs before publishing or committing.
- Prefer `thinking` or reasoning options only for providers that document them.
- Tell the user that external model calls consume the provider's quota as well as normal Codex orchestration usage.

## Quick Workflow

1. Confirm Python 3.10 or newer is available.
2. Prefer the interactive configurator, which supports presets and fully custom OpenAI-compatible models:

```bash
python path/to/scripts/model_bridge.py configure --config ~/.codex/model-bridge/config.json
```

3. When a model supports thinking, explicitly ask the user whether to enable it by default. Do not infer support for unknown APIs. The configurator records the choice without storing an API key.
4. Set provider API keys as user environment variables, then restart the terminal and Codex so they inherit the new values.
5. Run the local diagnostics:

```bash
python path/to/scripts/model_bridge.py doctor --config ~/.codex/model-bridge/config.json
```

6. Add an MCP entry to Codex config pointing to the bridge server:

```toml
[mcp_servers.model_bridge]
command = "python"
args = ["path/to/codex-model-bridge/scripts/model_bridge.py", "serve", "--config", "path/to/config.json"]
```

7. Restart Codex so it reloads the MCP server.
8. Use `model_bridge_status` first, then a configured model tool or `compare_external_models`.

## Common Tasks

### Add A New Model

Run `configure` again or edit the private JSON config. Each model can define a unique `id`, `tool_name`, provider `endpoint`, remote `model`, environment variable names, and optional headers or request fields. Set `enabled` to `false` to keep a model in the config without exposing it to Codex.

Declare `capabilities.thinking` and `capabilities.reasoning_effort` only when the provider supports those request fields. Use `thinking_field` and `thinking_values` for APIs that encode the toggle as a different field, string, boolean, or custom JSON value. Store defaults in `extra_body`; the bridge exposes per-call overrides only for declared capabilities. Existing configs that already contain these fields in `extra_body` remain compatible.

Use `references/providers.md` when configuring common providers such as Z.AI GLM, DeepSeek, Qwen, Kimi, OpenRouter, or generic OpenAI-compatible endpoints.

### Test A Model

Use the CLI before wiring the model into Codex:

```bash
python path/to/scripts/model_bridge.py ask --config path/to/config.json --model glm-5-2 --prompt "Reply with OK." --max-tokens 128 --thinking disabled
```

Use `--thinking disabled` only when `doctor` reports that thinking is supported.

### Expose Tools To Codex

Run the MCP server through Codex config. The bridge creates one MCP tool per configured model. Each tool accepts:

- `prompt`: the task to send to the external model.
- `system`: optional model instruction.
- `thinking`: optional provider-specific reasoning mode.
- `reasoning_effort`: optional provider-specific reasoning strength.
- `max_tokens`, `temperature`: generation controls.

The bridge always exposes `model_bridge_status`. It also exposes `compare_external_models` when two or more models are enabled; its default call skips models whose API keys are not detected.

## Resources

- `scripts/model_bridge.py`: MCP server and CLI for external models.
- `assets/config.example.json`: safe example config with no secrets.
- `references/providers.md`: provider configuration notes.
- `references/mcp-config.md`: Codex MCP setup patterns.
- `references/security.md`: secret handling and publishing checklist.
