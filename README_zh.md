# Gemini Claw

[English](README.md) | [中文](README_zh.md)

Gemini Claw 是一个基于 [Gemini CLI](https://github.com/google/gemini-cli) 驱动的 Discord 机器人。它作为一个桥梁，让你能直接从 Discord 服务器上与 Gemini CLI 智能体进行交互。

## 为什么选择 Gemini Claw？

Gemini CLI 本身已经是一个非常强大、全功能的 AI 智能体了。然而，它主要是为本地终端操作设计的，缺乏远程通信的渠道。Gemini Claw 通过搭建一个无缝连接到 Discord 的桥梁，完美解决了这个问题。

不同于从零开始构建一个全新的智能体，Gemini Claw 充分利用了现有生态的力量：
- **内置安全性：** 继承了 Gemini CLI 强大的安全策略支持，确保命令的安全执行。
- **极简设计：** 非常精简且易于理解的 Python 代码库，仅仅充当一个解耦层。
- **高可扩展性：** 通过原生的 Gemini CLI 扩展来增加新功能，而不是重复造轮子。

## 截图演示

<div align="center">
  <img src="images/ss1.PNG" alt="Screenshot 1" width="30%">
  <img src="images/ss2.PNG" alt="Screenshot 2" width="30%">
  <img src="images/ss3.PNG" alt="Screenshot 3" width="30%">
</div>

### 线程交互 (Threaded Interactions)
<img src="images/threads.png">

### 多机器人聊天 (Multi bots chat)
<img src="images/debate_1.png">
<img src="images/debate_2.png">

## 架构

Gemini Claw 使用了稳定可靠、基于 SQLite 的架构，将 Discord 机器人和 Gemini CLI 的执行完全解耦。这确保了在执行复杂且耗时的命令时，绝不会丢失任何消息。

```text
入站频道 (Discord) -> SQLite 数据库 -> 轮询循环 (Python 异步任务) -> Gemini CLI 子进程 -> 出站响应
```

## 前置要求

### 依赖项
- **Python:** 确保你已经安装了 [Python](https://www.python.org/downloads/)。
- **uv:** 本项目使用 `uv` 进行依赖管理。可以通过 `curl -LsSf https://astral.sh/uv/install.sh | sh` 命令安装。
- **Gemini CLI:** 确保你已经安装并认证了 Gemini CLI。

### Discord 机器人配置
在运行安装程序前，你需要在 Discord 上创建一个机器人：
1. 前往 [Discord 开发者中心](https://discord.com/developers/applications)。
2. 点击 **New Application** 并为它命名。
3. 在左侧菜单中，点击 **Bot**。
4. **将其设为私有：** 首先前往 **App Settings** -> **Installation**，将 **Install Link** 设置为 **None**。设置完成后，返回 **Bot** 标签页，并取消勾选 **Public Bot**，这样只有你才能将它加入服务器。
5. 点击 **Reset Token** 并复制你新的 `DISCORD_TOKEN`。
6. **非常重要：** 向下滚动到 **Privileged Gateway Intents** 区域，并将 **Message Content Intent** 设置为 **ON**。
7. 在左侧菜单中，点击 **OAuth2** -> **OAuth2 URL Generator**。
8. 在 **Scopes** 下，勾选 **bot**。
9. 在 **Bot Permissions** 下，分别勾选 **Send Messages**, **Read Message History** 和 **View Channels**。
10. 在页面底部，**复制生成的 URL**。
11. 在新浏览器标签页中粘贴该 URL，选择你的服务器，然后点击 **Authorize** 邀请机器人。
12. 想要获取用于配置的 `DISCORD_GUILD_ID` (Server ID)，请打开 Discord，前往 **User Settings** (用户设置) -> **Advanced** (高级)，开启 **Developer Mode** (开发者模式)。然后，在左边栏右键点击你的服务器图标，选择 **Copy Server ID**。

## 安装

你可以直接使用 `uv tool` 来安装和运行 `geminiclaw`，无需克隆源代码：

```bash
uv tool install git+https://github.com/codescv/geminiclaw.git
```

### 初始化机器人
安装完成后，执行以下命令初始化配置：
```bash
geminiclaw init
```
这会在当前目录下创建一个 `config.toml` 文件，并初始化 SQLite 数据库。请编辑 `config.toml` 文件以添加你的 `DISCORD_TOKEN` 以及 Gemini 相关的配置。

*注意：如果你的 Gemini CLI 或 Discord API 服务器需要代理，请在 Shell 环境变量中设置 `HTTP_PROXY` 和 `HTTPS_PROXY`。*

### 手动启动机器人（首次设置时推荐使用）
手动启动机器人，以验证所有的配置均已正确。
```bash
geminiclaw start
```
现在你应该就可以在服务器里直接对机器人喊话了。

### 管理后台服务

`geminiclaw` CLI 提供了一些命令，以便在 macOS / Linux 上作为后台服务进行管理。

- **安装服务：** `geminiclaw service install`
- **启动服务：** `geminiclaw service start`
- **停止服务：** `geminiclaw service stop`
- **查看状态：** `geminiclaw service status`

## 开发与源代码运行

如果你想进行二次开发或直接运行源代码，你可以在克隆的仓库中使用 `uv run`。

### 初始化机器人 (针对源代码)
`geminiclaw` 包内含一个自建的 CLI，用来管理配置文件及数据库。

在 `geminiclaw` 的根目录下运行以下命令来进行初始化：
```bash
uv run geminiclaw init
```
这会从示例配置创建一个 `config.toml` 文件，并初始化 SQLite 数据库。编辑 `config.toml` 文件填入你的 `DISCORD_TOKEN` 和 Gemini 设置。

*注意：如有需要，同样可以在环境里设置代理 `HTTP_PROXY`，`HTTPS_PROXY`。*

### 手动启动 (源代码)

如果你想实时观察日志或者排查任何可能的问题（如网络断开或 intent 配置错误），建议在前端直接手动启动：
```bash
uv run geminiclaw start
```
这是在初期配置排错时最推荐的方法。

## 如何使用
启动服务后，只需在 Discord 服务器里艾特你的机器人并加上你想说的话，或者给它发送一条私信。

```text
@GeminiClaw 请帮我写一个用来反转字符串的 Python 脚本
```

## 多机器人聊天 (Multi-Bot Chat)

Gemini Claw 原生支持多机器人互动！你可以运行机器人的多个实例（可搭配不同的配置和 System Prompts），并让它们在同一个线程中彼此甚至与用户一起连麦互动。

- **无缝加入线程**: 在单条消息里艾特多个机器人（例如：`@Bot1 @Bot2 我们来聊聊 Python`）。它们会自动协调好状态，并一起加入到这同一个话题线程，避免重复建楼。
- **智能流转控场**: 就在机器人生成一段还在半截子的回复时，它们会在消息末尾默默加上一个 `(incomplete)`（未完成）标记。其他的机器人在看到这个标记时会耐心等待，直到对方完全发完最后一句话才会回应，从而杜绝了它们半路抢话打断别人的毛病。
- **紧急制动**: 如果遇到机器人们相互争辩停不下来，你只要在线程里发送一条 `-stop` 命令即可。这瞬间就能使这个线程下线，让所有在侧耳倾听的机器人瞬间退出，强行打断自动回复的怪圈。
- **让它们继续**: 当你什么时候希望这群机器人再次留意线程中的信息时，再次发送 `-continue` 就能恢复所有的机器人监听，它们将继续参与对话。
 
## 附件支持 (Attachments Support)
 
Gemini Claw 支持双向的附件处理：
- **入站 (接收用户文件)：** 支持下载 Discord 消息里附带的各种附件（例如文件、图片等），并将它们放置在 Gemini CLI 工作区。
- **出站 (发送文件给用户)：** 你的 Agent 也能把工作区里的文件发给你。只需在响应中写上 `[attachment: path/to/file]`，机器人便会自动将该文件作为 Discord 附件上传发送。
 
### 附件配置
你可以在你的 `config.toml` 文件里的 `[gemini]` 区域设置去哪里保存附件：
 
```toml
[gemini]
# 可选：用于保存接收附件的文件夹（支持相对或绝对路径）。
# 默认为工作区内的 "attachments"。
attachments_dir = "attachments"
```
 
## 定时任务 (Cronjobs)

你可以配置一些定期的任务 (cronjobs)。它们会去读取一个 prompt 文件，交给 Gemini 执行，并且自动帮你在这指定的 Discord 频道里丢进一个新建的线程中。

### 定时任务配置

在你的 `config.toml` (或者 `private/config.toml`) 里加上一个 `[[cronjob]]` 区域：

```toml
[[cronjob]]
schedule = "*/5 * * * *"                     # Cron 定时表达式
prompt = "cronjobs/daily_summary.md"         # prompt 文件的相对/绝对路径
channel_id = "123456789012345678"            # Discord 频道 ID (能在 https://discord.com/channels/server_id/channel_id 里找到)
mention_user_id = "123456789012345678"       # 可选：配置上了你的用户 ID，机器人建好贴子之后会自动把你也 @ 进来
silent = false                               # 可选：设为 true 可以在后台安静执行任务而不发送任何 Discord 消息
```

### 📖 小贴士：如何找到你自己的 Discord User ID

为了让机器人建好的帖子自动喊你，填上你自己的 `mention_user_id` 即可。

1. **启用 Developer Mode (开发者模式)**:
   - 进入 Discord **User Settings (用户设置)** -> **Advanced (高级)**。
   - 打开 **Developer Mode (开发者模式)**。

2. **复制 User ID**:
   - 在任何聊天频道或是成员列表寻找你自己的头像/名字。右键点击你的头像或名字。
   - 在底部选择 **Copy User ID**。
