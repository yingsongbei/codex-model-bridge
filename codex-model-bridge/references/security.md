# Security Checklist

## User Setup

- Never ask a user to paste an API key into Codex, another AI chat, an issue, or a screenshot.
- Run `configure` only for provider settings and environment variable names. It never needs a key value.
- Run `key-help` to show local setup and replacement commands.
- Prefer provider-specific names such as `ZHIPU_API_KEY` or `DEEPSEEK_API_KEY` to avoid conflicts with Codex or other applications.
- Explain that PowerShell `SetEnvironmentVariable` and POSIX `export` normally print nothing on success. Returning to the prompt without a message is expected.
- Verify only `SET` or `NOT SET`. Never print the environment variable value.
- Fully restart the terminal and Codex after setting or changing a user environment variable.
- Run `doctor`, then one low-cost real provider request before adding the MCP entry.

## Key Replacement

1. Create a new key in the provider console.
2. Disable or revoke the old key in that console.
3. Run `key-help` to confirm the existing environment variable name.
4. Run the same local environment-variable command with the new value. This overwrites the old value.
5. Remind the user that successful setting is silent.
6. Restart the terminal and Codex.
7. Run `doctor` and a low-cost real request.

Changing only the key value does not require editing the bridge JSON or Codex authentication settings.

## Publishing

- Confirm no API key values appear in tracked files or Git history.
- Commit example configs only with environment variable names.
- Keep private configs outside the repository or add them to `.gitignore`.
- If a key appears in chat, logs, screenshots, or commits, revoke it and create a new one.
- The `doctor` command and `model_bridge_status` report only whether a variable is present and never print its value.

Suggested private config locations:

```text
~/.codex/model-bridge/config.json
C:/Users/<you>/.codex/model-bridge/config.json
```
