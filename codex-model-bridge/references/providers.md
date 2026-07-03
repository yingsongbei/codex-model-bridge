# Provider Notes

Use OpenAI-compatible chat completion endpoints whenever possible. Each configured model needs an `endpoint`, `model`, and one or more `api_key_envs`.

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
  "thinking": { "type": "enabled" },
  "reasoning_effort": "high"
}
```

## DeepSeek

Example endpoint:

```text
https://api.deepseek.com/chat/completions
```

Common model ids include `deepseek-chat` and provider-specific reasoning models. Check current provider docs before hard-coding production model ids.

## Qwen / DashScope

Example OpenAI-compatible endpoint:

```text
https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions
```

Common model ids include `qwen-plus`, `qwen-max`, and other DashScope model names.

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
  "model": "provider-model-id"
}
```
