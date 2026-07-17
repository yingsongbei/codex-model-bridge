# codex-model-bridge

Connect GLM, DeepSeek, Qwen, Kimi, OpenRouter, or another OpenAI-compatible model to Codex as an external MCP model agent.

Codex remains the main orchestrator. The external model appears as an `ask_*` tool that Codex calls only when needed.

## What This Does Not Change

The bridge does not replace the Codex model, change the Codex login, or modify Codex billing and authentication. It does not set Codex's global `model`, `model_provider`, or API endpoint.

Installation adds only one local MCP server entry:

```toml
[mcp_servers.model_bridge]
```

Use provider-specific environment variable names such as `ZHIPU_API_KEY` or `DEEPSEEK_API_KEY`. Avoid reusing `OPENAI_API_KEY` unless you intentionally understand the effect on other applications.

## Requirements

- Python 3.10 or newer
- Codex with local MCP server support
- An API key created in the external model provider's own console
- Git, unless you download the repository as a ZIP file

Never paste a real API key into Codex, another AI chat, GitHub, a screenshot, or the bridge JSON file.

## Step 1: Install The Skill

This repository contains the distributable Skill in the inner `codex-model-bridge/` folder. Copy that inner folder, not the repository root.

If you do not use Git, click **Code > Download ZIP** on GitHub, extract the ZIP, open the extracted repository folder, and copy its inner `codex-model-bridge` folder to `C:\Users\<you>\.codex\skills\codex-model-bridge`. Do not copy the outer repository folder as the Skill.

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

Confirm that this file exists:

```text
~/.codex/skills/codex-model-bridge/SKILL.md
```

## Step 2: Configure A Model

Run the interactive configurator:

```powershell
python "$HOME\.codex\skills\codex-model-bridge\scripts\model_bridge.py" configure --config "$HOME\.codex\model-bridge\config.json"
```

The wizard asks for the provider, model, endpoint, tool name, environment variable name, and optional thinking behavior. It never asks for the API key itself and never stores a key in JSON.

Choose a provider preset or `custom`. For thinking-capable models, the wizard asks whether thinking is supported, how the provider encodes it, and whether it should be enabled by default.

At the end, the wizard prints local API key instructions for the configured model.

## Step 3: Set The API Key Locally

You can display the instructions again at any time:

```powershell
python "$HOME\.codex\skills\codex-model-bridge\scripts\model_bridge.py" key-help --config "$HOME\.codex\model-bridge\config.json" --model glm-5-2
```

Replace `glm-5-2` with your configured model id when necessary.

### Windows Example

Create or copy the key in the provider's website, then run this command locally:

```powershell
[Environment]::SetEnvironmentVariable("ZAI_API_KEY", "PASTE_YOUR_KEY_HERE", "User")
```

Replace only `PASTE_YOUR_KEY_HERE`. Keep the environment variable name shown by `key-help`.

**A successful `SetEnvironmentVariable` command prints nothing.** PowerShell simply returns to the `PS>` prompt. This is normal and does not mean that the command failed. Do not paste the key into chat to ask whether it worked.

Verify safely without displaying the key:

```powershell
if ([string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable("ZAI_API_KEY", "User"))) { "NOT SET" } else { "SET" }
```

Expected output:

```text
SET
```

This verification prints only `SET` or `NOT SET`; it never prints the key.

After it prints `SET`, close that PowerShell window and open a new one. Existing terminals and already-running Codex processes do not automatically inherit changed user environment variables.

### macOS / Linux Example

Set the key in the current terminal:

```bash
export ZAI_API_KEY='PASTE_YOUR_KEY_HERE'
```

`export` is also silent on success. Verify without displaying the key:

```bash
if [ -n "${ZAI_API_KEY:-}" ]; then echo "SET"; else echo "NOT SET"; fi
```

This applies to the current terminal. Use the same terminal for testing. For persistence, use your shell profile or operating-system secret manager, then restart Codex from an environment that inherits the variable.

## Step 4: Check The Local Setup

Run `doctor` in the newly opened terminal. This check does not call the provider and does not consume model quota:

```powershell
python "$HOME\.codex\skills\codex-model-bridge\scripts\model_bridge.py" doctor --config "$HOME\.codex\model-bridge\config.json"
```

`key found via ZAI_API_KEY` means the new process can see an environment variable with that name. It does not prove that the key is valid.

If `doctor` reports a missing key, run `key-help`, confirm that the variable name matches the model config, and open a new terminal after setting it.

## Step 5: Make One Low-Cost Real Test

Test the provider before adding the MCP entry to Codex:

```powershell
python "$HOME\.codex\skills\codex-model-bridge\scripts\model_bridge.py" ask --config "$HOME\.codex\model-bridge\config.json" --model glm-5-2 --prompt "Reply exactly: OK" --max-tokens 32 --thinking disabled
```

Use `--thinking disabled` only when `doctor` reports that thinking is supported. Omit that option for models that do not support it.

Continue only after the model returns `OK`. This real request consumes a small amount of the external provider's quota, not the Codex model quota for the external response itself. Codex still consumes its normal usage when orchestrating tools later.

## Step 6: Connect The Tested Model To Codex

Add the bridge to `~/.codex/config.toml`. On Windows, use forward slashes in TOML paths:

```toml
[mcp_servers.model_bridge]
command = "python"
args = ["C:/Users/you/.codex/skills/codex-model-bridge/scripts/model_bridge.py", "serve", "--config", "C:/Users/you/.codex/model-bridge/config.json"]
```

Do not change the existing Codex `model`, `model_provider`, login, or authentication settings.

Fully exit every Codex window and reopen Codex. The bridge exposes:

- `model_bridge_status` for safe API key and thinking diagnostics
- One `ask_*` tool for each enabled external model
- `compare_external_models` when at least two models are enabled

The external model remains an optional tool. It does not become the default Codex model.

## Replace Or Rotate An API Key

Use these steps when a key expires, is disabled, or may have been exposed:

1. Create a new key in the external provider's console.
2. Disable or revoke the old key in that console.
3. Run `key-help` to confirm the environment variable name.
4. Run the same local environment-variable command with the new value. The same name overwrites the old value.
5. Remember that successful local setting is silent and produces no confirmation message.
6. Use the safe `SET/NOT SET` command.
7. Fully restart the terminal and Codex.
8. Run `doctor`, followed by one low-cost real test.

Do not edit `config.json` when only the key value changes. The JSON stores the environment variable name, not the key. Do not change Codex authentication settings.

## Change The Model Or Thinking Settings

Run `configure` again when changing the provider, endpoint, model id, tool name, or thinking behavior:

```powershell
python "$HOME\.codex\skills\codex-model-bridge\scripts\model_bridge.py" configure --config "$HOME\.codex\model-bridge\config.json"
```

This is separate from API key replacement.

## Manual Model Format

Advanced users can edit each item in `models` directly:

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

Only enable capabilities documented by that exact provider model. Use `thinking_field` and `thinking_values` for APIs that do not use Z.AI-style `{"thinking":{"type":"enabled"}}`. See `codex-model-bridge/references/providers.md` for examples.

## Security And Usage

- Never commit or publish a real API key.
- Never ask a user to paste a key into an AI conversation.
- If a key appears in chat, screenshots, logs, or Git history, revoke it and create a new one.
- External calls consume the external provider's quota.
- Codex remains the orchestrator and consumes its normal usage for tool selection and result handling.

## License

MIT
