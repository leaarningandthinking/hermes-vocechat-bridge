# hermes-vocechat-bridge

A lightweight bridge that connects [VoceChat](https://voce.chat) to [Hermes Agent](https://github.com/NousResearch/hermes-agent), enabling AI-powered conversations in VoceChat with full Hermes capabilities — memory, skills, tools, and self-improving intelligence.

[English](#english) | [中文](#中文)

---

## English

### How It Works

```
VoceChat User sends message
       ↓ (Webhook)
Bridge receives the message
       ↓
Calls Hermes Agent API Server
       ↓
Hermes processes (with memory, skills, tools)
       ↓
Bridge sends reply back via VoceChat Bot API
```

### Features

- **Full Hermes power** — memory, skills, tools, and self-learning all work through VoceChat
- **Per-user conversation history** — each user has their own context
- **Zero dependencies** — pure Python 3, no pip install needed
- **Lightweight** — ~16MB memory usage
- **Docker support** — ready-to-use Dockerfile and docker-compose
- **systemd service** — auto-start on boot, auto-restart on crash
- **Special commands** — send `/clear` or `清除记忆` to reset conversation

### Prerequisites

- A running **VoceChat** server with HTTPS
- A running **Hermes Agent** with API Server enabled
- Python 3.8+

### Quick Start

#### 1. Enable Hermes API Server

Add to `~/.hermes/.env`:

```bash
API_SERVER_ENABLED=true
API_SERVER_KEY=your-secret-key
```

Restart Hermes:

```bash
hermes gateway restart --system
```

#### 2. Create a Bot in VoceChat

Go to **Settings → Bot & Webhook → New**:
- Name: `Hermes` (or any name you like)
- Webhook URL: leave empty for now
- Save the **API Key**

#### 3. Deploy the Bridge

**Option A: Direct (recommended for single server)**

```bash
mkdir -p /opt/vocechat-bridge
cp bridge.py /opt/vocechat-bridge/
cp .env.example /opt/vocechat-bridge/.env

# Edit .env with your actual values
nano /opt/vocechat-bridge/.env
```

**Option B: Docker**

```bash
cp .env.example .env
# Edit .env with your actual values
docker compose up -d
```

#### 4. Set up systemd (Option A only)

```bash
cp vocechat-hermes-bridge.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable vocechat-hermes-bridge
systemctl start vocechat-hermes-bridge
```

#### 5. Configure Nginx reverse proxy

Add this to your VoceChat's Nginx config, **before** the main `location /` block:

```nginx
location /webhook/ {
    proxy_pass http://127.0.0.1:8010/;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
}
```

Reload Nginx:

```bash
nginx -t && nginx -s reload
```

#### 6. Set Webhook URL in VoceChat

Go to **Settings → Bot & Webhook**, edit your bot's Webhook URL:

```
https://your-vocechat-domain/webhook/
```

#### 7. Test it!

Send a message to the bot in VoceChat. You should get a reply from Hermes.

### Configuration

| Environment Variable | Description | Default |
|---------------------|-------------|---------|
| `VOCECHAT_URL` | VoceChat server URL | (required) |
| `VOCECHAT_API_KEY` | VoceChat Bot API Key | (required) |
| `HERMES_URL` | Hermes API Server URL | `http://localhost:8642/v1/chat/completions` |
| `HERMES_KEY` | Hermes API Server Key | (required) |
| `LISTEN_PORT` | Bridge listening port | `8010` |
| `MAX_HISTORY` | Max messages per user | `20` |
| `HERMES_TIMEOUT` | API timeout (seconds) | `120` |
| `LOG_LEVEL` | Logging level | `INFO` |

### Special Commands

| Command | Action |
|---------|--------|
| `/clear` | Clear conversation history |
| `/reset` | Clear conversation history |
| `清除记忆` | Clear conversation history |

### Troubleshooting

**Bot doesn't reply?**
- Check bridge logs: `journalctl -u vocechat-hermes-bridge -f`
- Verify Hermes is running: `curl http://localhost:8642/v1/chat/completions -H "Authorization: Bearer YOUR_KEY" -H "Content-Type: application/json" -d '{"model":"hermes-agent","messages":[{"role":"user","content":"test"}]}'`
- Verify webhook is accessible: `curl https://your-domain/webhook/`

**"Not Valid URL" in VoceChat?**
- Make sure the URL is publicly accessible (not `127.0.0.1`)
- Check Nginx config and SSL certificate

---

## 中文

### 工作原理

```
VoceChat 用户发送消息
       ↓ (Webhook)
Bridge 接收消息
       ↓
调用 Hermes Agent API Server
       ↓
Hermes 处理（带记忆、技能、工具）
       ↓
Bridge 通过 VoceChat Bot API 发回回复
```

### 特性

- **完整的 Hermes 能力** — 记忆、技能、工具、自我学习，全部通过 VoceChat 使用
- **每用户独立对话历史** — 每个用户有自己的上下文
- **零依赖** — 纯 Python 3，无需安装任何包
- **超轻量** — 仅占用 ~16MB 内存
- **Docker 支持** — 提供 Dockerfile 和 docker-compose
- **systemd 服务** — 开机自启，崩溃自动重启
- **特殊命令** — 发送 `/clear` 或 `清除记忆` 重置对话

### 前提条件

- 已部署的 **VoceChat** 服务器（需 HTTPS）
- 已部署的 **Hermes Agent** 并开启 API Server
- Python 3.8+

### 快速开始

#### 1. 开启 Hermes API Server

在 `~/.hermes/.env` 中添加：

```bash
API_SERVER_ENABLED=true
API_SERVER_KEY=你的密钥
```

重启 Hermes：

```bash
hermes gateway restart --system
```

#### 2. 在 VoceChat 创建机器人

进入 **设置 → 机器人&Webhook → 新增**：
- 名称：`Hermes`（或你喜欢的名字）
- Webhook URL：先留空
- 保存 **API Key**

#### 3. 部署 Bridge

```bash
mkdir -p /opt/vocechat-bridge
cp bridge.py /opt/vocechat-bridge/
cp .env.example /opt/vocechat-bridge/.env

# 编辑 .env 填入你的配置
nano /opt/vocechat-bridge/.env
```

#### 4. 设置 systemd 服务

```bash
cp vocechat-hermes-bridge.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable vocechat-hermes-bridge
systemctl start vocechat-hermes-bridge
```

#### 5. 配置 Nginx 反向代理

在 VoceChat 的 Nginx 配置中，在 `location /` 之前添加：

```nginx
location /webhook/ {
    proxy_pass http://127.0.0.1:8010/;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
}
```

#### 6. 设置 Webhook URL

在 VoceChat 的机器人设置里填写 Webhook URL：

```
https://你的域名/webhook/
```

#### 7. 测试

在 VoceChat 里给机器人发一条消息，应该能收到 Hermes 的回复！

### 常见问题

**机器人不回复？**
- 查看日志：`journalctl -u vocechat-hermes-bridge -f`
- 检查 Hermes 是否运行：`hermes gateway status --system`
- 检查 webhook 是否可访问：`curl https://你的域名/webhook/`

---

## License

MIT — see [LICENSE](LICENSE)

## Contributing

Issues and PRs welcome! If you find this useful, please star the repo.
