> [English](README.md) | [中文](README_zh.md)

# Gemini Claw

Gemini Claw 是一个由 [Gemini CLI](https://github.com/google/gemini-cli) 驱动的 Discord 机器人通信桥接层，让你能够直接在你的 Discord 服务器中与 Gemini 智能体交流。

# 为什么选择 Gemini Claw？

Gemini CLI 本身已经是一个极其强大、功能完备的 AI 智能体。然而，它主要设计用于本地终端操作，缺乏支持远程交互的通信渠道。Gemini Claw 通过提供一个连接至 Discord 的无缝通信桥梁解决了这一痛点。

与其从零开始构建一个新的智能体，Gemini Claw 充分利用了现有生态系统的强大能力：
- **内置安全支持：** 继承自 Gemini CLI 强大的安全策略与权限支持，确保安全地执行命令。
- **极简设计：** 一套小巧、易读懂的 Python 代码流，仅充当通信解耦层。
- **可扩展性：** 通过原生的 Gemini CLI 扩展功能添加新功能，而不是去重复造轮子。

# 特色功能

- **多线程交互：** 支持与多位 Gemini CLI 智能体进行基于线程的独立对话交互。
- **记忆管理：** 提供针对项目进度、学习用户偏好等内容的记忆管理系统。
- **安全防护：** 与 Gemini CLI 沙盒及安全策略限制完美集成，防止 API 密钥等私密凭证泄露。
- **基于频道主题的系统提示词：** 支持将 Discord 频道的主题自动解析注入为系统提示词，以提供基于频道的个性化设定。
- **定时任务 (Cronjobs)：** 支持自动化定时任务读取提示词文件，利用 Gemini CLI 执行并把结果发送至指定 Discord 新线程中。
- **角色扮演：** 支持针对不同频道定制 **多位** 不同身份的独立角色扮演。
- **后台耗时任务：** 支持支持脱离线程的后台长期运行任务，并提供自动心跳监控上报。
- **多机器人群聊：** 支持支持多个独立配置的 Gemini CLI 智能体在同一个 Discord 频道中相互交流。
- **附件处理：** 支持支持多向的图片、说话视频、语音及文件附件传输处理。


# 界面截图

<div align="center">
  <img src="images/ss1.PNG" alt="Screenshot 1" width="30%">
  <img src="images/ss2.PNG" alt="Screenshot 2" width="30%">
  <img src="images/ss3.PNG" alt="Screenshot 3" width="30%">
</div>

## 基于线程的交互
<img src="images/threads.png">

## 多机器人交流
<img src="images/debate_1.png">
<img src="images/debate_2.png">


# 运行前提要求

## 系统依赖
- **Python：** 请确保您已安装 [Python](https://www.python.org/downloads/)。
- **uv：** 本项目采用 `uv` 作为依赖管理工具。通过 `curl -LsSf https://astral.sh/uv/install.sh | sh` 安装它。
- **Gemini CLI：** 请确保您已安装 Gemini CLI 并配置好相关的认证。

## Discord 机器人配置
在运行初始化前，您需要在 Discord 上创建一个专属的机器人应用：
1. 访问 [Discord 开发者平台](https://discord.com/developers/applications)。
2. 点击 **New Application** 新建应用并为其命名。
3. 在左侧边栏，选择 **Bot** 标签页。
4. **设为私有：** 首先，进入 **App Settings** -> **Installation** 将 **Install Link** 设置为 **None**。设置完毕后，切回 **Bot** 标签页，取消勾选 **Public Bot** 开关，以确保只有您自己能将它邀请到您的服务器中。
5. 点击 **Reset Token** 获取并复制您全新的 `DISCORD_TOKEN`。
6. **关键操作：** 向下滚动至 **Privileged Gateway Intents** 配置段，将 **Message Content Intent** 开关设置为 **ON**。
7. 在左侧边栏，点击 **OAuth2** -> **OAuth2 URL Generator**。
8. 在 **Scopes** 下，勾选 **bot** 复选框。
9. 在 **Bot Permissions** 下，勾选 **Send Messages**、**Read Message History** 及 **View Channels**。
10. 滚动到页面底部，**复制生成的授权 URL 链接**。
11. 在新浏览器标签页中打开该 URL，选择您的服务器，然后点击 **Authorize** 完成机器人邀请。


# 安装指引

您无需克隆源代码，即可使用 `uv tool` 直接安装并运行 `geminiclaw`：

```bash
uv tool install git+https://github.com/codescv/geminiclaw.git
```

# 初始化配置
安装完成后，运行以下命令以初始化所需环境配置：
```bash
geminiclaw init
```
这将会将内置工作区中的所有资源文件复制至当前目录，初始化建置 SQLite 数据库，并打印输出推荐的配置建议说明。

*注意：当您连接 Gemini CLI 以及 Discord API 服务需要通过代理时，请在 shell 环境变量中配置好 `HTTP_PROXY` 和 `HTTPS_PROXY`。*

# 作为系统后台服务运行

`geminiclaw` 提供了用来管理 macOS / Linux 系统后台守护程序的命令接口。

- **安装后台服务：** `geminiclaw service install` (安装系统守护进程)
- **启动服务：** `geminiclaw service start` (启动后台服务守护)
- **停止服务：** `geminiclaw service stop` (关闭并停止运行守护程序)
- **重启服务：** `geminiclaw service restart` (重新启动守护进程)
- **查看服务状态：** `geminiclaw service status` (查询服务当前的运行状态)

# 使用机器人交互
服务启动后，只需在您的 Discord 频道中直接提及机器人并附上您的提示词需求，或是向机器人发送单独的私信 (Direct Message) 即可。

```text
@GeminiClaw 写一个用 Python 翻转字符串的脚本
```

 
# 核心文件配置管理
所有可调节的自定义配置项均被保存在 `config.toml` 文件中。请详细阅读注释以获取指引支持。

## 免提及白名单回复配置 (Always Reply)

您可以指定机器人总是自动答复配置在白名单中的用户，无需每次都在句首额外提及机器人。这一配置只有当消息不处于公共对话线程中且从未提及任何其他对象时才会生效。

在 `config.toml` 内的 `[discord]` 段落中增加对应的白名单列表 `always_reply`：

```toml
[discord]
always_reply = ["user1", "user2"]
```

## 提示词定制化管理

你可以通过修改 `prompts` 目录下的 Markdown 文件，来自定义 Gemini CLI 智能体调用的底层系统基准提示词。这些文件将在调用时无缝注入智能体内。

```toml
[prompt]
user = ["user.md", ...]
```

## 自动化定时任务机制 (Cronjobs)

你可以配置一系列周期性运行的后台任务，这会读取提示词、调用 Gemini 执行并将响应输出开辟一个新的对话线程自动推送上报。

### 配置

在您的 `config.toml` (或位于 `private/config.toml`) 中增加 `[[cronjob]]` 规则：

```toml
[[cronjob]]
schedule = "*/5 * * * *"                     # 标准 cron 计划表达式
prompt = "cronjobs/daily_summary.md"         # 调用的提示词文件路径
channel_id = "123456789012345678"            # 指定接受报告的 Discord 频道 ID
mention_user_id = "123456789012345678"       # 可选填：自动将对应用户邀请入新线程的用户 ID
silent = false                               # 可选填：设为 true 则在后台完全静默运行，不向 Discord 发送任何上报消息
probability = 1.0                            # 可选填：0.0 到 1.0 区间代表按概率执行
```

# 📖 提示技巧：如何查找您的 Discord 用户 ID 与频道 ID

部分特殊配置可能要求填入对应的 Discord 用户 ID 或是特定的频道 ID。以下是查找的快速指引：

1. **启动开发者模式:**
   - 进入您的 Discord **User Settings** -> **Advanced**。
   - 将 **Developer Mode** 切换开启为 **ON**。

2. **复制您的专属用户 ID:**
   - 在好友或成员列表中，右键点击您的 **头像或名称**。
   - 在弹出的菜单底部点击 **Copy User ID** 完成复制。

3. **复制目标频道的 ID:**
   - 在频道列表导航页中右键点击 **频道名称**。
   - 在菜单底部点击 **Copy Channel ID** 进行复制。

# 详细进阶教程导航

为了学习和运用高级交互流程与更多功能指引，请参看我们专用的中文版教程文档：

- [角色扮演](tutorials/role_playing_zh.md)
- [记忆管理](tutorials/memory_management_zh.md)
- [后台运行任务](tutorials/background_tasks_zh.md)
- [安全配置](tutorials/security_zh.md)
