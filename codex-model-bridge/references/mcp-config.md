# MCP Config

Treat the bridge as an optional external MCP agent. Keep Codex as the orchestrator.

Before editing Codex config:

1. Configure the external model.
2. Run `key-help` and set the key locally.
3. Open a new terminal, run `doctor`, and make one low-cost real request.
4. Continue only after the external model responds successfully.

Add only the local stdio MCP server entry:

```toml
[mcp_servers.model_bridge]
command = "python"
args = ["C:/path/to/codex-model-bridge/codex-model-bridge/scripts/model_bridge.py", "serve", "--config", "C:/Users/you/.codex/model-bridge/config.json"]
```

Do not change Codex's global `model`, `model_provider`, API endpoint, login, or authentication settings. Use forward slashes in Windows TOML paths.

Fully exit and reopen Codex after editing MCP config or changing an API key. Existing Codex and terminal processes do not inherit changed user environment variables.

For local testing without Codex:

```bash
python scripts/model_bridge.py validate-config --config assets/config.example.json
python scripts/model_bridge.py key-help --config assets/config.example.json --model glm-5-2
python scripts/model_bridge.py doctor --config assets/config.example.json
python scripts/model_bridge.py list-tools --config assets/config.example.json
```

To test a real provider call:

```bash
python scripts/model_bridge.py ask --config path/to/private-config.json --model glm-5-2 --prompt "Reply exactly: OK" --max-tokens 32 --thinking disabled
```

The bridge exposes `model_bridge_status` inside Codex. It reports the detected environment variable name and thinking default without printing key values. External models remain `ask_*` tools and never become the default Codex model.
