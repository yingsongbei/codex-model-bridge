# codex-model-bridge

Add external OpenAI-compatible LLMs to Codex as MCP-powered model agents.

Use GLM, DeepSeek, Qwen, Kimi, OpenRouter, or a custom endpoint as an external reviewer, writer, planner, code critic, or second-opinion model. Codex remains the orchestrator.

## Requirements

- Python 3.10 or newer
- Codex with local MCP server support
- An API key from each external provider you want to call

## Install

This repository contains the distributable Skill in the inner `codex-model-bridge/` folder. Copy that inner folder, not the repository root.

### Windows PowerShell

```powershell
git clone https://github.com/yingsongbei/codex-model-bridge.git
Set-Location .\codex-model-bridge
New-Item -ItemType Directory -Force "$HOME\.codex\skills\codex-model-bridge" | Out-Null
Copy-Item -Recurse -Force ".\codex-model-bridge\*" "$HOME\.codex\skills\codex-model-bridge"
```

### macOS / Linux

```bash
git clone https://github.com/yingsongbei/codex-model-bridge.git
cd codex-model-bridge
mkdir -p ~/.codex/skills/codex-model-bridge
cp -R ./codex-model-bridge/. ~/.codex/skills/codex-model-bridge/
```

The installed file should be `~/.codex/skills/codex-model-bridge/SKILL.md`.

## Configure Models

Run the interactive configurator. It offers GLM, DeepSeek, and Qwen starters, but every endpoint, model id, tool name, and environment variable remains editable. Choose `custom` for any OpenAI-compatible API.

```powershell
python "$HOME\.codex\skills\codex-model-bridge\scripts\model_bridge.py" configure --config "$HOME\.codex\model-bridge\config.json"
```

For models that support it, the wizard asks whether the API accepts thinking, which request field and value style it uses, and whether thinking should be enabled by default. It supports object, string, boolean, and custom JSON values. It never asks for or stores an API key.

Run `configure` again to add or update another model. You can also edit the private JSON directly. Set `enabled` to `false` to keep a model definition without exposing its tool to Codex.

## Set API Keys

Store secrets in environment variables named by your config, never in JSON. Example for Windows:

```powershell
[Environment]::SetEnvironmentVariable("ZAI_API_KEY", "your-key", "User")
```

Open a new PowerShell window, or refresh the current process before testing:

```powershell
$env:ZAI_API_KEY = [Environment]::GetEnvironmentVariable("ZAI_API_KEY", "User")
```

On macOS or Linux, export the variable through your shell profile or secret manager:

```bash
export ZAI_API_KEY="your-key"
```

Fully exit and reopen Codex after adding or changing an environment variable. Already-running Codex processes cannot see the new value.

## Diagnose And Test

Check configuration, key detection, enabled models, and thinking defaults without making a paid API call:

```powershell
python "$HOME\.codex\skills\codex-model-bridge\scripts\model_bridge.py" doctor --config "$HOME\.codex\model-bridge\config.json"
```

Make a low-cost GLM connectivity test:

```powershell
python "$HOME\.codex\skills\codex-model-bridge\scripts\model_bridge.py" ask --config "$HOME\.codex\model-bridge\config.json" --model glm-5-2 --prompt "Reply with OK." --max-tokens 128 --thinking disabled
```

Omit `--thinking disabled` for a model whose API does not support that field.

## Connect To Codex

Add the bridge to `~/.codex/config.toml`. Use forward slashes in Windows paths:

```toml
[mcp_servers.model_bridge]
command = "python"
args = ["C:/Users/you/.codex/skills/codex-model-bridge/scripts/model_bridge.py", "serve", "--config", "C:/Users/you/.codex/model-bridge/config.json"]
```

Restart Codex. The bridge exposes:

- `model_bridge_status` for safe key and thinking diagnostics
- One `ask_*` tool for each enabled model
- `compare_external_models` when at least two models are enabled; models with missing keys are skipped by default

## Manual Model Format

Each item in `models` is independently customizable:

```json
{
  "id": "my-model",
  "tool_name": "ask_my_model",
  "display_name": "My Model",
  "endpoint": "https://example.com/v1/chat/completions",
  "api_key_envs": ["MY_MODEL_API_KEY"],
  "model": "provider-model-id",
  "enabled": true,
  "capabilities": {
    "thinking": false,
    "reasoning_effort": false
  },
  "temperature": 0.7,
  "max_tokens": 2048
}
```

Only set a capability to `true` when that exact provider model documents the corresponding request field. For APIs that do not use Z.AI-style `{"thinking":{"type":"enabled"}}`, configure `thinking_field` and `thinking_values` through the wizard or JSON. Put other provider-specific defaults in `extra_body`. See `codex-model-bridge/references/providers.md` for examples.

## Usage And Security

External calls consume the provider's quota. Codex usage is still consumed for orchestration, tool selection, and summarizing results.

Never commit real API keys. If a key is exposed in chat, screenshots, logs, or Git history, rotate it in the provider console.

## License

MIT
