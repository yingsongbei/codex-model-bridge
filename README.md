# codex-model-bridge

Add external OpenAI-compatible LLMs to Codex as MCP-powered model agents.

The bridge is useful when you want Codex to consult GLM, DeepSeek, Qwen, Kimi, OpenRouter, or another provider as an external reviewer, writer, planner, code critic, or second-opinion model. Codex remains the orchestrator; the external models are called through local MCP tools.

## Install

Copy the skill folder into your Codex skills directory:

```bash
cp -r codex-model-bridge ~/.codex/skills/
```

On Windows, copy `codex-model-bridge` to:

```text
C:\Users\<you>\.codex\skills\codex-model-bridge
```

## Configure

Copy the example config to a private location:

```bash
mkdir -p ~/.codex/model-bridge
cp codex-model-bridge/assets/config.example.json ~/.codex/model-bridge/config.json
```

Set API keys as environment variables. Do not put secrets in the JSON file.

Example:

```powershell
[Environment]::SetEnvironmentVariable("ZAI_API_KEY", "your-key", "User")
```

Add the MCP server to Codex config:

```toml
[mcp_servers.model_bridge]
command = "python"
args = ["C:/path/to/codex-model-bridge/scripts/model_bridge.py", "serve", "--config", "C:/Users/you/.codex/model-bridge/config.json"]
```

Restart Codex after editing config.

## Validate

```bash
python codex-model-bridge/scripts/model_bridge.py validate-config --config ~/.codex/model-bridge/config.json
python codex-model-bridge/scripts/model_bridge.py list-tools --config ~/.codex/model-bridge/config.json
```

Test a real provider call:

```bash
python codex-model-bridge/scripts/model_bridge.py ask --config ~/.codex/model-bridge/config.json --model glm-5-2 --prompt "Reply with OK."
```

## Notes

External model calls consume the provider's quota. Codex usage is still consumed for orchestration, tool selection, and summarizing results.

Never commit real API keys. If a key is exposed in chat, screenshots, logs, or Git history, rotate it in the provider console.

## License

MIT
