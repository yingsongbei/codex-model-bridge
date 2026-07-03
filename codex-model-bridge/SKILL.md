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

1. Copy `assets/config.example.json` to a private location, usually `~/.codex/model-bridge/config.json`.
2. Edit provider names, endpoints, model ids, and environment variable names.
3. Set provider API keys as user environment variables.
4. Validate the config:

```bash
python path/to/codex-model-bridge/scripts/model_bridge.py validate-config --config path/to/config.json
```

5. Add an MCP entry to Codex config pointing to the bridge server:

```toml
[mcp_servers.model_bridge]
command = "python"
args = ["path/to/codex-model-bridge/scripts/model_bridge.py", "serve", "--config", "path/to/config.json"]
```

6. Restart Codex so it reloads the MCP server.
7. Use the exposed tools, for example `ask_glm_5_2`, `ask_deepseek`, or `compare_external_models`, depending on the config.

## Common Tasks

### Add A New Model

Edit the private JSON config. Add one object to `models` with a unique `id`, `tool_name`, provider `endpoint`, `model`, and secret environment variable name.

Use `references/providers.md` when configuring common providers such as Z.AI GLM, DeepSeek, Qwen, Kimi, OpenRouter, or generic OpenAI-compatible endpoints.

### Test A Model

Use the CLI before wiring the model into Codex:

```bash
python path/to/scripts/model_bridge.py ask --config path/to/config.json --model glm-5-2 --prompt "Reply with OK."
```

For a low-cost test, set `max_tokens` small and disable provider-specific reasoning options if supported.

### Expose Tools To Codex

Run the MCP server through Codex config. The bridge creates one MCP tool per configured model. Each tool accepts:

- `prompt`: the task to send to the external model.
- `system`: optional model instruction.
- `thinking`: optional provider-specific reasoning mode.
- `reasoning_effort`: optional provider-specific reasoning strength.
- `max_tokens`, `temperature`: generation controls.

The bridge also exposes `compare_external_models` when two or more models are configured.

## Resources

- `scripts/model_bridge.py`: MCP server and CLI for external models.
- `assets/config.example.json`: safe example config with no secrets.
- `references/providers.md`: provider configuration notes.
- `references/mcp-config.md`: Codex MCP setup patterns.
- `references/security.md`: secret handling and publishing checklist.
