# Token Monitor

Claude Code 和 Moltbot Token 使用统计监控工具。

## 功能

- Token 使用统计（Claude Code + Moltbot）
- 费用估算（支持多种模型定价）
- 历史趋势记录（SQLite）
- iMessage 通知 + Apple Notes 同步
- 定时报告（LaunchAgent，每天 21:00）
- 错过补发机制

## 安装

```bash
# 克隆仓库
git clone https://github.com/Coodyhu/token-monitor.git
cd token-monitor

# 配置
cp config.example.json config.json
# 编辑 config.json 填入你的 API Key 和通知号码

# 安装定时任务（可选）
./install.sh
```

## 配置

复制 `config.example.json` 为 `config.json` 并填入：

```json
{
    "dmxapi_key": "your-dmxapi-key",
    "notify_phone": "+86xxxxxxxxxxx"
}
```

或通过环境变量设置：
```bash
export DMXAPI_KEY="your-key"
export NOTIFY_PHONE="+86xxxxxxxxxxx"
```

## 数据来源

| 来源 | 路径/API | 说明 |
|------|----------|------|
| Claude Code | `~/.claude/stats-cache.json` | 本地统计缓存 |
| Moltbot | `~/.clawdbot/agents/main/sessions/sessions.json` | Session token 记录 |
| dmxapi | `/v1/dashboard/billing/usage` | 账户总消费 |

## 使用方法

```bash
# 完整报告
python3 token_monitor.py

# 费用明细
python3 token_monitor.py cost

# 查看定价表
python3 token_monitor.py pricing

# 历史记录
python3 token_monitor.py snapshot  # 保存快照
python3 token_monitor.py history   # 查看历史
python3 token_monitor.py trend     # 趋势分析

# 通知
python3 token_monitor.py notify         # 发送日报
python3 token_monitor.py notify check   # 检查费用阈值

# 导出 JSON
python3 token_monitor.py json
```

## 定时任务

安装后每天 21:00 自动发送日报。如果错过（电脑关机），下次开机时会补发（最多补发3天）。

```bash
# 安装
./install.sh

# 卸载
./uninstall.sh

# 手动执行
launchctl start com.alex.token-monitor

# 查看日志
cat /tmp/token-monitor.log
```

## 支持的模型定价

| 模型 | Input ($/M) | Output ($/M) |
|------|-------------|--------------|
| Claude Opus 4.5 | $15 | $75 |
| Claude Sonnet 4.5 | $3 | $15 |
| Claude Haiku 4.5 | $0.8 | $4 |
| Gemini 3 Pro | $1.25 | $10 |
| Gemini 3 Flash | $0.075 | $0.3 |
| GPT-5 | $5 | $15 |
| GPT-4o | $2.5 | $10 |

## License

MIT
