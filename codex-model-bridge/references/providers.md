# Provider Notes

Use OpenAI-compatible chat completion endpoints whenever possible. Each configured model needs an `endpoint`, `model`, and one or more `api_key_envs`.

Prefer a provider-specific environment variable name to avoid conflicts with Codex and other applications. Run `key-help` after configuration; it explains local setup, silent command success, safe verification, testing, and later key replacement without displaying the key.

## Z.AI GLM

Example endpoint:

```text
https://api.z.ai/api/paas/v4/chat/completions
```

Example model:

```text
glm-5.2
```

Useful environment variable names:

```text
ZAI_API_KEY
ZHIPU_API_KEY
```

GLM reasoning can be configured through `extra_body`, for example:

```json
{
  "capabilities": {
    "thinking": true,
    "reasoning_effort": true
  },
  "extra_body": {
    "thinking": { "type": "enabled" },
    "reasoning_effort": "high"
  }
}
```

The interactive `configure` command asks whether thinking should be enabled by default. For a low-cost connectivity test, override it with `--thinking disabled --max-tokens 128`.

## DeepSeek

Example endpoint:

```text
https://api.deepseek.com/chat/completions
```

Common model ids include `deepseek-chat` and provider-specific reasoning models. Check current provider docs before hard-coding production model ids.

Do not enable `thinking` or `reasoning_effort` capabilities merely because another model from the same provider supports them. Configure capabilities for the exact endpoint and model.

## Qwen / DashScope

Example OpenAI-compatible endpoint:

```text
https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions
```

Common model ids include `qwen-plus`, `qwen-max`, and other DashScope model names.

Thinking support varies by model and API mode. Confirm the provider request schema before setting a capability to `true`.

## Kimi / Moonshot

Use the provider's OpenAI-compatible endpoint and set `MOONSHOT_API_KEY` or another chosen environment variable name in the config.

## OpenRouter

Use the OpenRouter chat completions endpoint and set a model id such as `z-ai/glm-4.5` or another routed model. Add optional headers in config if the provider requires them.

## Generic OpenAI-Compatible Provider

For any compatible API:

```json
{
  "id": "my-model",
  "tool_name": "ask_my_model",
  "endpoint": "https://example.com/v1/chat/completions",
  "api_key_envs": ["MY_MODEL_API_KEY"],
  "model": "provider-model-id",
  "enabled": true,
  "capabilities": {
    "thinking": false,
    "reasoning_effort": false
  }
}
```

Add any provider-specific JSON fields under `extra_body` and non-secret HTTP headers under `headers`. Keep credentials in environment variables. Run `configure` repeatedly to add or update as many models as needed; model ids and tool names must remain unique.

For a provider that uses a boolean field such as `"enable_thinking": true`, configure the mapping explicitly:

```json
{
  "capabilities": {
    "thinking": true,
    "thinking_field": "enable_thinking",
    "thinking_values": {
      "enabled": true,
      "disabled": false
    }
  },
  "extra_body": {
    "enable_thinking": true
  }
}
```

The same mapping accepts strings, objects, numbers, or other JSON values. The `configure` wizard can generate common mappings and prompts for custom JSON values when needed.
