# codex-model-bridge

[简体中文](#zh-cn) | [English](#english)

<a id="zh-cn"></a>
## 简体中文

将 GLM、DeepSeek、Qwen、Kimi、OpenRouter 或其他兼容 OpenAI API 的模型接入 Codex，作为外部 MCP 模型子 Agent 使用。

Codex 仍然是主 Agent 和任务编排者。外部模型会显示为一个 `ask_*` 工具，只有在 Codex 判断需要时才会被调用。

### 不会修改什么

本项目不会替换 Codex 的主模型，不会改变 Codex 登录方式，也不会修改 Codex 的额度、计费或认证设置。它不会设置 Codex 全局的 `model`、`model_provider` 或 API 地址。

安装时只会新增一个本地 MCP 服务配置：

```toml
[mcp_servers.model_bridge]
```

请使用服务商专属的环境变量名，例如 `ZHIPU_API_KEY` 或 `DEEPSEEK_API_KEY`。除非你清楚这会怎样影响电脑上的其他程序，否则不要复用 `OPENAI_API_KEY`。

### 环境要求

- Python 3.10 或更高版本
- 支持本地 MCP 服务的 Codex
- 在外部模型服务商官网创建的 API Key
- Git；如果使用 ZIP 下载，则不需要 Git

不要把真实 API Key 粘贴到 Codex、其他 AI 对话、GitHub、截图或本项目的 JSON 配置文件中。

### 第 1 步：安装 Skill

本仓库中真正需要安装的 Skill 位于内层的 `codex-model-bridge/` 文件夹。请复制这个内层文件夹，而不是整个仓库根目录。

如果你不使用 Git，请在 GitHub 页面点击 **Code > Download ZIP**，解压后打开仓库文件夹，把里面的 `codex-model-bridge` 文件夹复制到 `C:\Users\<你的用户名>\.codex\skills\codex-model-bridge`。不要把最外层仓库文件夹直接当作 Skill 复制。

#### Windows PowerShell

```powershell
git clone https://github.com/yingsongbei/codex-model-bridge.git
Set-Location .\codex-model-bridge
New-Item -ItemType Directory -Force "$HOME\.codex\skills\codex-model-bridge" | Out-Null
Copy-Item -Recurse -Force ".\codex-model-bridge\*" "$HOME\.codex\skills\codex-model-bridge"
```

#### macOS / Linux

```bash
git clone https://github.com/yingsongbei/codex-model-bridge.git
cd codex-model-bridge
mkdir -p ~/.codex/skills/codex-model-bridge
cp -R ./codex-model-bridge/. ~/.codex/skills/codex-model-bridge/
```

安装后请确认以下文件存在：

```text
~/.codex/skills/codex-model-bridge/SKILL.md
```

### 第 2 步：配置外部模型

运行交互式配置向导：

```powershell
python "$HOME\.codex\skills\codex-model-bridge\scripts\model_bridge.py" configure --config "$HOME\.codex\model-bridge\config.json"
```

向导会询问服务商、模型、API 地址、工具名称、环境变量名和可选的 Thinking 设置。向导不会要求输入 API Key，也不会把 API Key 保存到 JSON 中。

你可以选择一个预设服务商，也可以选择 `custom` 自定义模型。对于支持深度思考的模型，向导会询问该模型是否支持 Thinking、服务商采用哪种请求格式，以及是否默认开启 Thinking。

配置完成后，向导会自动显示这个模型对应的本地 API Key 设置说明。

### 第 3 步：在本机设置 API Key

你可以随时再次显示 API Key 设置说明：

```powershell
python "$HOME\.codex\skills\codex-model-bridge\scripts\model_bridge.py" key-help --config "$HOME\.codex\model-bridge\config.json" --model glm-5-2
```

如果你配置的模型 id 不是 `glm-5-2`，请把它替换为自己的模型 id。

#### Windows 示例

先在模型服务商官网创建或复制 API Key，然后只在你自己的 PowerShell 中运行：

```powershell
[Environment]::SetEnvironmentVariable("ZAI_API_KEY", "PASTE_YOUR_KEY_HERE", "User")
```

只替换 `PASTE_YOUR_KEY_HERE`。环境变量名称必须使用 `key-help` 显示的名称。

**这条命令执行成功时不会显示任何内容。** PowerShell 只会回到 `PS>` 提示符，这是正常现象，并不代表失败。不要因为没有提示而反复执行，也不要把 API Key 粘贴到聊天中询问是否成功。

使用下面的命令安全检查，命令不会显示 API Key：

```powershell
if ([string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable("ZAI_API_KEY", "User"))) { "NOT SET" } else { "SET" }
```

预期输出：

```text
SET
```

这个检查只会显示 `SET` 或 `NOT SET`，不会打印 API Key。

看到 `SET` 后，关闭当前 PowerShell 窗口，再打开一个新的 PowerShell。已经打开的终端和正在运行的 Codex 不会自动读取刚刚修改的用户环境变量。

#### macOS / Linux 示例

在当前终端中设置 API Key：

```bash
export ZAI_API_KEY='PASTE_YOUR_KEY_HERE'
```

`export` 执行成功时同样不会显示任何内容。使用下面的命令安全检查：

```bash
if [ -n "${ZAI_API_KEY:-}" ]; then echo "SET"; else echo "NOT SET"; fi
```

这种方式只对当前终端有效，请继续使用同一个终端完成测试。如果需要长期保存，请使用 Shell 配置文件或操作系统的密码管理工具，然后从能够读取该变量的环境中重新启动 Codex。

### 第 4 步：检查本机配置

在新打开的终端中运行 `doctor`。这项检查不会请求模型服务商，也不会消耗模型额度：

```powershell
python "$HOME\.codex\skills\codex-model-bridge\scripts\model_bridge.py" doctor --config "$HOME\.codex\model-bridge\config.json"
```

如果看到 `key found via ZAI_API_KEY`，表示新进程能够读取这个名称的环境变量，但这还不能证明 API Key 本身有效。

如果 `doctor` 报告没有找到 API Key，请运行 `key-help`，确认配置中的环境变量名完全一致，并确保设置后重新打开了终端。

### 第 5 步：进行一次低成本真实测试

在把 MCP 配置添加到 Codex 之前，先直接测试模型服务商：

```powershell
python "$HOME\.codex\skills\codex-model-bridge\scripts\model_bridge.py" ask --config "$HOME\.codex\model-bridge\config.json" --model glm-5-2 --prompt "Reply exactly: OK" --max-tokens 32 --thinking disabled
```

只有当 `doctor` 显示模型支持 Thinking 时，才使用 `--thinking disabled`。如果模型不支持 Thinking，请删除这个选项。

模型成功返回 `OK` 后再继续。这次真实请求会消耗少量外部模型服务商的额度，而不是由外部回复消耗 Codex 模型额度。以后由 Codex 编排和处理工具结果时，Codex 本身仍会正常消耗自己的使用额度。

### 第 6 步：把测试成功的模型接入 Codex

把下面的配置添加到 `~/.codex/config.toml`。Windows 用户请在 TOML 路径中使用正斜杠：

```toml
[mcp_servers.model_bridge]
command = "python"
args = ["C:/Users/you/.codex/skills/codex-model-bridge/scripts/model_bridge.py", "serve", "--config", "C:/Users/you/.codex/model-bridge/config.json"]
```

不要修改 Codex 原有的 `model`、`model_provider`、登录或认证设置。

完全退出所有 Codex 窗口，然后重新打开 Codex。Bridge 会提供：

- `model_bridge_status`：安全检查 API Key 和 Thinking 配置
- 每个已启用外部模型对应的一个 `ask_*` 工具
- 启用至少两个模型时提供 `compare_external_models`

外部模型始终只是可选的子 Agent 工具，不会成为 Codex 的默认主模型，也不会与 Codex 自身的登录和认证冲突。

### 更换或轮换 API Key

API Key 到期、被禁用或可能泄露时，请按以下步骤处理：

1. 在外部模型服务商控制台创建新的 API Key。
2. 在服务商控制台禁用或撤销旧 API Key。
3. 运行 `key-help`，确认应该使用的环境变量名称。
4. 使用相同的本地环境变量命令写入新值；名称相同时，新值会覆盖旧值。
5. 记住：本地设置成功时不会返回确认内容，这是正常的。
6. 使用安全的 `SET/NOT SET` 命令检查。
7. 完全关闭终端和 Codex，然后重新打开。
8. 先运行 `doctor`，再进行一次低成本真实测试。

如果只是更换 API Key 的值，不需要编辑 `config.json`。JSON 只保存环境变量名称，不保存 API Key。也不要修改 Codex 的认证设置。

### 修改模型或 Thinking 设置

如果要修改服务商、API 地址、模型 id、工具名称或 Thinking 行为，请重新运行 `configure`：

```powershell
python "$HOME\.codex\skills\codex-model-bridge\scripts\model_bridge.py" configure --config "$HOME\.codex\model-bridge\config.json"
```

这与更换 API Key 是两件不同的事情。

### 手动配置格式

高级用户可以直接编辑 `models` 中的项目：

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

只有当对应服务商的准确模型文档明确支持时，才开启相关能力。如果 API 不使用 Z.AI 风格的 `{"thinking":{"type":"enabled"}}`，请配置 `thinking_field` 和 `thinking_values`。更多示例见 `codex-model-bridge/references/providers.md`。

### 安全与额度

- 不要提交或公开真实 API Key。
- 不要要求用户把 API Key 粘贴到 AI 对话中。
- 如果 API Key 出现在聊天、截图、日志或 Git 历史中，请立即撤销并创建新 Key。
- 外部模型调用会消耗外部服务商的额度。
- Codex 仍然负责工具选择和结果处理，并正常消耗 Codex 自己的使用额度。

### 许可证

MIT

---

<a id="english"></a>
## English

Connect GLM, DeepSeek, Qwen, Kimi, OpenRouter, or another OpenAI-compatible model to Codex as an external MCP model agent.

Codex remains the main orchestrator. The external model appears as an `ask_*` tool that Codex calls only when needed.

### What This Does Not Change

The bridge does not replace the Codex model, change the Codex login, or modify Codex billing and authentication. It does not set Codex's global `model`, `model_provider`, or API endpoint.

Installation adds only one local MCP server entry:

```toml
[mcp_servers.model_bridge]
```

Use provider-specific environment variable names such as `ZHIPU_API_KEY` or `DEEPSEEK_API_KEY`. Avoid reusing `OPENAI_API_KEY` unless you intentionally understand the effect on other applications.

### Requirements

- Python 3.10 or newer
- Codex with local MCP server support
- An API key created in the external model provider's own console
- Git, unless you download the repository as a ZIP file

Never paste a real API key into Codex, another AI chat, GitHub, a screenshot, or the bridge JSON file.

### Step 1: Install The Skill

This repository contains the distributable Skill in the inner `codex-model-bridge/` folder. Copy that inner folder, not the repository root.

If you do not use Git, click **Code > Download ZIP** on GitHub, extract the ZIP, open the extracted repository folder, and copy its inner `codex-model-bridge` folder to `C:\Users\<you>\.codex\skills\codex-model-bridge`. Do not copy the outer repository folder as the Skill.

#### Windows PowerShell

```powershell
git clone https://github.com/yingsongbei/codex-model-bridge.git
Set-Location .\codex-model-bridge
New-Item -ItemType Directory -Force "$HOME\.codex\skills\codex-model-bridge" | Out-Null
Copy-Item -Recurse -Force ".\codex-model-bridge\*" "$HOME\.codex\skills\codex-model-bridge"
```

#### macOS / Linux

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

### Step 2: Configure A Model

Run the interactive configurator:

```powershell
python "$HOME\.codex\skills\codex-model-bridge\scripts\model_bridge.py" configure --config "$HOME\.codex\model-bridge\config.json"
```

The wizard asks for the provider, model, endpoint, tool name, environment variable name, and optional thinking behavior. It never asks for the API key itself and never stores a key in JSON.

Choose a provider preset or `custom`. For thinking-capable models, the wizard asks whether thinking is supported, how the provider encodes it, and whether it should be enabled by default.

At the end, the wizard prints local API key instructions for the configured model.

### Step 3: Set The API Key Locally

You can display the instructions again at any time:

```powershell
python "$HOME\.codex\skills\codex-model-bridge\scripts\model_bridge.py" key-help --config "$HOME\.codex\model-bridge\config.json" --model glm-5-2
```

Replace `glm-5-2` with your configured model id when necessary.

#### Windows Example

Create or copy the key in the provider's website, then run this command locally:

```powershell
[Environment]::SetEnvironmentVariable("ZAI_API_KEY", "PASTE_YOUR_KEY_HERE", "User")
```

Replace only `PASTE_YOUR_KEY_HERE`. Keep the environment variable name shown by `key-help`.

**A successful `SetEnvironmentVariable` command prints nothing.** PowerShell simply returns to the `PS>` prompt. This is normal and does not mean that the command failed. Do not repeat the command because there is no message, and do not paste the key into chat to ask whether it worked.

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

#### macOS / Linux Example

Set the key in the current terminal:

```bash
export ZAI_API_KEY='PASTE_YOUR_KEY_HERE'
```

`export` is also silent on success. Verify without displaying the key:

```bash
if [ -n "${ZAI_API_KEY:-}" ]; then echo "SET"; else echo "NOT SET"; fi
```

This applies to the current terminal. Use the same terminal for testing. For persistence, use your shell profile or operating-system secret manager, then restart Codex from an environment that inherits the variable.

### Step 4: Check The Local Setup

Run `doctor` in the newly opened terminal. This check does not call the provider and does not consume model quota:

```powershell
python "$HOME\.codex\skills\codex-model-bridge\scripts\model_bridge.py" doctor --config "$HOME\.codex\model-bridge\config.json"
```

`key found via ZAI_API_KEY` means the new process can see an environment variable with that name. It does not prove that the key is valid.

If `doctor` reports a missing key, run `key-help`, confirm that the variable name matches the model config, and open a new terminal after setting it.

### Step 5: Make One Low-Cost Real Test

Test the provider before adding the MCP entry to Codex:

```powershell
python "$HOME\.codex\skills\codex-model-bridge\scripts\model_bridge.py" ask --config "$HOME\.codex\model-bridge\config.json" --model glm-5-2 --prompt "Reply exactly: OK" --max-tokens 32 --thinking disabled
```

Use `--thinking disabled` only when `doctor` reports that thinking is supported. Omit that option for models that do not support it.

Continue only after the model returns `OK`. This real request consumes a small amount of the external provider's quota, not the Codex model quota for the external response itself. Codex still consumes its normal usage when orchestrating tools later.

### Step 6: Connect The Tested Model To Codex

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

The external model remains an optional sub-agent tool. It does not become the default Codex model or conflict with Codex login and authentication.

### Replace Or Rotate An API Key

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

### Change The Model Or Thinking Settings

Run `configure` again when changing the provider, endpoint, model id, tool name, or thinking behavior:

```powershell
python "$HOME\.codex\skills\codex-model-bridge\scripts\model_bridge.py" configure --config "$HOME\.codex\model-bridge\config.json"
```

This is separate from API key replacement.

### Manual Model Format

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

### Security And Usage

- Never commit or publish a real API key.
- Never ask a user to paste a key into an AI conversation.
- If a key appears in chat, screenshots, logs, or Git history, revoke it and create a new one.
- External calls consume the external provider's quota.
- Codex remains the orchestrator and consumes its normal usage for tool selection and result handling.

### License

MIT
