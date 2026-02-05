#!/usr/bin/env python3
"""
notify.py - Token Monitor iMessage 通知模块

功能:
1. send_daily_report(): 发送每日统计报告
2. send_alert(message): 发送告警通知

通知同时写入 Apple 备忘录（家庭文件夹）
"""

import json
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

# 导入 token_monitor 的统计函数
from token_monitor import (
    get_claude_code_stats,
    get_moltbot_stats,
    format_tokens,
    load_config,
)
from pricing import get_total_estimated_cost, format_cost

# 配置
NOTE_FOLDER = "家庭文件"
HISTORY_FILE = Path(__file__).parent / "token_history.json"


def get_notify_phone() -> str:
    """获取通知电话号码"""
    import os
    phone = os.environ.get("NOTIFY_PHONE")
    if phone:
        return phone
    config = load_config()
    return config.get("notify_phone", "")


def run_osascript(script: str) -> Optional[str]:
    """执行 AppleScript"""
    p = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    if p.returncode != 0:
        return None
    return p.stdout.strip()


def send_imessage(message: str, to: str = None) -> bool:
    """发送 iMessage"""
    if to is None:
        to = get_notify_phone()
    if not to:
        print("警告: 未配置 notify_phone", file=sys.stderr)
        return False
    try:
        result = subprocess.run([
            "moltbot", "message", "send",
            "--channel", "imessage",
            "--target", to,
            "--message", message
        ], capture_output=True, timeout=30)
        return result.returncode == 0
    except Exception as e:
        print(f"发送失败: {e}")
        return False


def save_to_notes(title: str, content: str) -> bool:
    """保存到备忘录"""
    html = content.replace("\n", "<br>")
    bs = chr(92)
    safe_body = html.replace(bs, bs + bs).replace('"', bs + '"')

    script = f'''
    tell application "Notes"
        tell folder "{NOTE_FOLDER}"
            try
                set targetNote to note "{title}"
                set body of targetNote to "{safe_body}"
            on error
                make new note with properties {{name:"{title}", body:"{safe_body}"}}
            end try
        end tell
    end tell
    '''
    result = run_osascript(script)
    return result is not None


def get_yesterday_totals() -> Optional[dict]:
    """获取昨日的 token 总量（用于计算变化）"""
    if not HISTORY_FILE.exists():
        return None
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            history = json.load(f)
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        return history.get(yesterday)
    except:
        return None


def save_today_totals(claude_total: int, moltbot_total: int, cost: float):
    """保存今日的 token 总量"""
    history = {}
    if HISTORY_FILE.exists():
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                history = json.load(f)
        except:
            pass

    today = datetime.now().strftime("%Y-%m-%d")
    history[today] = {
        "claude_total": claude_total,
        "moltbot_total": moltbot_total,
        "cost": cost
    }

    # 只保留最近 30 天
    sorted_dates = sorted(history.keys())
    if len(sorted_dates) > 30:
        for old_date in sorted_dates[:-30]:
            del history[old_date]

    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)


def generate_daily_report() -> str:
    """生成每日统计报告"""
    now = datetime.now()

    # 获取统计数据
    claude_stats = get_claude_code_stats()
    moltbot_stats = get_moltbot_stats()

    # 计算 Claude Code 总 token
    claude_total = 0
    for model, usage in claude_stats.get("models", {}).items():
        claude_total += usage.get("total", 0)

    # 计算 Moltbot 总 token
    moltbot_total = moltbot_stats.get("total_input", 0) + moltbot_stats.get("total_output", 0)

    # 使用 pricing 模块计算费用
    all_stats = {
        "claude_code": claude_stats,
        "moltbot": moltbot_stats
    }
    cost_summary = get_total_estimated_cost(all_stats)
    cost = cost_summary["grand_total"]

    # 获取昨日数据计算变化
    yesterday = get_yesterday_totals()
    change_str = ""
    if yesterday:
        yesterday_total = yesterday.get("claude_total", 0) + yesterday.get("moltbot_total", 0)
        today_total = claude_total + moltbot_total
        if yesterday_total > 0:
            change_pct = ((today_total - yesterday_total) / yesterday_total) * 100
            if change_pct >= 0:
                change_str = f"\n较昨日: +{change_pct:.1f}%"
            else:
                change_str = f"\n较昨日: {change_pct:.1f}%"

    # 保存今日数据
    save_today_totals(claude_total, moltbot_total, cost)

    # 生成报告
    lines = [
        f"Token 日报 {now.strftime('%Y-%m-%d')}",
        "",
        f"Claude Code: {format_tokens(claude_total)} tokens",
        f"Moltbot: {format_tokens(moltbot_total)} tokens",
        f"估算费用: {format_cost(cost)}",
    ]

    if change_str:
        lines.append(change_str)

    lines.extend([
        "",
        "---",
        f"{now.strftime('%H:%M')} Token Monitor"
    ])

    return "\n".join(lines)


def send_daily_report() -> bool:
    """发送每日统计报告"""
    print("Generating daily report...")
    report = generate_daily_report()
    print(report)
    print()

    # 发送 iMessage
    print("Sending iMessage...")
    imessage_success = send_imessage(report)
    if imessage_success:
        print("iMessage sent successfully")
    else:
        print("iMessage send failed")

    # 保存到备忘录
    print("Saving to Notes...")
    title = "Token Monitor 日报"
    notes_success = save_to_notes(title, report)
    if notes_success:
        print("Notes saved successfully")
    else:
        print("Notes save failed")

    return imessage_success and notes_success


def send_alert(message: str, alert_type: str = "warning") -> bool:
    """
    发送告警通知

    alert_type: "warning", "critical", "info"
    """
    icons = {
        "warning": "Warning",
        "critical": "ALERT",
        "info": "Info"
    }

    icon = icons.get(alert_type, "Warning")
    now = datetime.now()

    alert_message = f"""[{icon}] Token Monitor

{message}

---
{now.strftime('%Y-%m-%d %H:%M')}"""

    print(f"Sending alert: {alert_type}")
    print(alert_message)
    print()

    # 发送 iMessage
    imessage_success = send_imessage(alert_message)

    # 保存到备忘录
    title = f"Token Alert {now.strftime('%m-%d %H:%M')}"
    notes_success = save_to_notes(title, alert_message)

    if imessage_success:
        print("Alert sent successfully")
    else:
        print("Alert send failed")

    return imessage_success


def check_cost_threshold(threshold: float = 50.0) -> bool:
    """
    检查费用是否超过阈值

    threshold: 费用阈值（美元）
    """
    claude_stats = get_claude_code_stats()
    moltbot_stats = get_moltbot_stats()

    all_stats = {
        "claude_code": claude_stats,
        "moltbot": moltbot_stats
    }
    cost_summary = get_total_estimated_cost(all_stats)
    cost = cost_summary["grand_total"]

    if cost >= threshold:
        send_alert(
            f"Token 费用已达 {format_cost(cost)}，超过阈值 {format_cost(threshold)}",
            alert_type="critical"
        )
        return True
    return False


def main():
    """命令行接口"""
    import sys

    if len(sys.argv) < 2:
        print("Token Monitor Notification System")
        print()
        print("Usage:")
        print("  notify.py daily              # Send daily report")
        print("  notify.py alert <message>    # Send alert")
        print("  notify.py check [threshold]  # Check cost threshold (default: $50)")
        print("  notify.py test               # Send test notification")
        return

    cmd = sys.argv[1]

    if cmd == "daily":
        send_daily_report()

    elif cmd == "alert":
        if len(sys.argv) < 3:
            print("Please provide alert message")
            return
        message = " ".join(sys.argv[2:])
        send_alert(message)

    elif cmd == "check":
        threshold = float(sys.argv[2]) if len(sys.argv) > 2 else 50.0
        exceeded = check_cost_threshold(threshold)
        if not exceeded:
            print(f"Cost is within threshold (${threshold:.2f})")

    elif cmd == "test":
        print("Sending test notification...")
        test_msg = f"Test notification from Token Monitor\n\n{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        if send_imessage(test_msg):
            print("Test notification sent successfully")
        else:
            print("Test notification failed")

    else:
        print(f"Unknown command: {cmd}")


if __name__ == "__main__":
    main()
