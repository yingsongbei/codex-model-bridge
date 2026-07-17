# Security Checklist

Before publishing or committing:

- Confirm no API key values appear in tracked files.
- Commit example configs only with environment variable names.
- Keep private configs outside the repository or add them to `.gitignore`.
- Do not paste provider keys into issue reports, screenshots, or README examples.
- If a key was exposed in chat, logs, screenshots, or commits, rotate it in the provider console.
- Prefer user-level environment variables on Windows and shell profile or secret manager variables on macOS/Linux.
- The `configure` command asks only for environment variable names. If any prompt appears to request a key value, stop and inspect the script before continuing.
- The `doctor` command and `model_bridge_status` tool report only whether a variable is present and never print its value.

Suggested private config locations:

```text
~/.codex/model-bridge/config.json
C:/Users/<you>/.codex/model-bridge/config.json
```
