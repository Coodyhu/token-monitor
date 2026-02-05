# Token Monitor

Claude Code 和 Moltbot Token 使用统计监控工具。

## 数据来源

| 来源 | 路径/API | 说明 |
|------|----------|------|
| Claude Code | `~/.claude/stats-cache.json` | 本地统计缓存 |
| Moltbot | `~/.clawdbot/agents/main/sessions/sessions.json` | Session token 记录 |
| dmxapi | `/v1/dashboard/billing/usage` | 账户总消费 |

## 使用方法

```bash
# 显示完整报告
python3 token_monitor.py

# 导出 JSON
python3 token_monitor.py json

# 单独查询
python3 token_monitor.py claude
python3 token_monitor.py moltbot
python3 token_monitor.py dmxapi
```

## 输出示例

```
============================================================
Token 使用统计报告 - 2026-02-05 22:50
============================================================

📊 Claude Code 统计
----------------------------------------
统计日期: 2026-02-04
会话数: 11
消息数: 3150

模型使用:
  claude-opus-4-5-20251101:
    Input:       4.3K
    Output:      106.6K
    Cache Read:  12.83M
    Cache Write: 982.4K
    Total:       13.92M

📊 Moltbot 统计
----------------------------------------
会话数: 59
总 Input:  1.78M
总 Output: 119.9K
...
```
