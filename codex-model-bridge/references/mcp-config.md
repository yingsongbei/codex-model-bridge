# MCP Config

Add the bridge as a local stdio MCP server in Codex config.

```toml
[mcp_servers.model_bridge]
command = "python"
args = ["C:/path/to/codex-model-bridge/codex-model-bridge/scripts/model_bridge.py", "serve", "--config", "C:/Users/you/.codex/model-bridge/config.json"]
```

Use forward slashes in Windows paths to avoid TOML escaping surprises.

Restart Codex after editing config. Existing sessions may not see newly added MCP servers until restart.

User-level environment variable changes are also inherited only by newly started terminals and Codex processes. Fully exit and reopen Codex after setting or changing an API key.

For local testing without Codex:

```bash
python scripts/model_bridge.py validate-config --config assets/config.example.json
python scripts/model_bridge.py doctor --config assets/config.example.json
python scripts/model_bridge.py list-tools --config assets/config.example.json
```

To test a real provider call:

```bash
python scripts/model_bridge.py ask --config path/to/private-config.json --model glm-5-2 --prompt "Reply with OK." --max-tokens 128 --thinking disabled
```

The bridge exposes `model_bridge_status` inside Codex. It reports which environment variable was detected for each model and the configured thinking default, but never prints key values.
