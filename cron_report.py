#!/usr/bin/env python3
"""
cron_report.py - Token Monitor 定时报告

功能:
1. 生成每日统计摘要
2. 保存历史快照
3. 生成报告文本（适合 iMessage 发送）
4. 错过补发机制

用法:
  python cron_report.py          # 生成报告并保存快照
  python cron_report.py report   # 仅生成报告文本
  python cron_report.py snapshot # 仅保存快照
  python cron_report.py send     # 生成报告并发送 iMessage（带补发检查）
"""

import json
import os
import sys
import subprocess
from datetime import datetime, date
from pathlib import Path
from typing import Optional

# 添加当前目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from token_monitor import (
    get_claude_code_stats,
    get_moltbot_stats,
    get_dmxapi_usage,
    format_tokens,
    export_json,
    load_config,
)
from history import save_snapshot, get_daily_summary

# 配置
LAST_SENT_FILE = Path.home() / ".token-monitor" / "last_sent.json"


def get_notify_phone() -> str:
    """获取通知电话号码"""
    phone = os.environ.get("NOTIFY_PHONE")
    if phone:
        return phone
    config = load_config()
    return config.get("notify_phone", "")


def get_last_sent_date() -> Optional[date]:
    """获取上次发送日期"""
    try:
        if LAST_SENT_FILE.exists():
            with open(LAST_SENT_FILE, "r") as f:
                data = json.load(f)
                return date.fromisoformat(data.get("date", ""))
    except Exception:
        pass
    return None


def set_last_sent_date(d: date = None) -> None:
    """记录发送日期"""
    if d is None:
        d = date.today()
    LAST_SENT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LAST_SENT_FILE, "w") as f:
        json.dump({"date": d.isoformat(), "timestamp": datetime.now().isoformat()}, f)


def check_missed_days() -> list[date]:
    """检查错过的天数"""
    last_sent = get_last_sent_date()
    today = date.today()

    if last_sent is None:
        # 首次运行，只发今天
        return [today]

    if last_sent >= today:
        # 今天已发送
        return []

    # 计算错过的天数（最多补发3天）
    missed = []
    current = last_sent
    while current < today:
        from datetime import timedelta
        current = current + timedelta(days=1)
        missed.append(current)
        if len(missed) >= 3:
            break

    return missed


def generate_report_text() -> str:
    """生成报告文本（适合 iMessage）"""
    now = datetime.now()
    lines = []

    lines.append(f"Token Monitor Daily Report")
    lines.append(f"{now.strftime('%Y-%m-%d %H:%M')}")
    lines.append("")

    # Claude Code 统计
    claude_stats = get_claude_code_stats()
    if claude_stats:
        lines.append("[Claude Code]")
        lines.append(f"Sessions: {claude_stats.get('total_sessions', 0)}")
        lines.append(f"Messages: {claude_stats.get('total_messages', 0)}")

        models = claude_stats.get("models", {})
        total_tokens = 0
        for model, usage in models.items():
            total_tokens += usage.get("total", 0)
        lines.append(f"Total Tokens: {format_tokens(total_tokens)}")
        lines.append("")

    # Moltbot 统计
    moltbot_stats = get_moltbot_stats()
    if moltbot_stats:
        lines.append("[Moltbot]")
        lines.append(f"Sessions: {moltbot_stats.get('session_count', 0)}")
        total_input = moltbot_stats.get("total_input", 0)
        total_output = moltbot_stats.get("total_output", 0)
        lines.append(f"Input: {format_tokens(total_input)}")
        lines.append(f"Output: {format_tokens(total_output)}")
        lines.append("")

    # dmxapi 消费
    dmx_usage = get_dmxapi_usage()
    if dmx_usage:
        total = dmx_usage.get("total_usage", 0)
        lines.append("[dmxapi]")
        lines.append(f"Total: CNY {total / 10000:.2f}")
        lines.append("")

    # 与昨日对比
    daily_summary = get_daily_summary(2)
    if len(daily_summary) >= 2:
        today_data = daily_summary[0]
        yesterday_data = daily_summary[1]

        cost_diff = (today_data.get("total_cost") or 0) - (yesterday_data.get("total_cost") or 0)
        input_diff = (today_data.get("total_input") or 0) - (yesterday_data.get("total_input") or 0)

        if cost_diff != 0 or input_diff != 0:
            lines.append("[vs Yesterday]")
            if cost_diff != 0:
                sign = "+" if cost_diff > 0 else ""
                lines.append(f"Cost: {sign}${cost_diff:.2f}")
            if input_diff != 0:
                sign = "+" if input_diff > 0 else ""
                lines.append(f"Input: {sign}{format_tokens(input_diff)}")

    return "\n".join(lines)


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
        print(f"发送失败: {e}", file=sys.stderr)
        return False


def run_daily_report(send: bool = False, check_missed: bool = True) -> None:
    """执行每日报告"""
    print(f"[{datetime.now().isoformat()}] Token Monitor Daily Report")
    print("-" * 50)

    # 检查是否需要补发
    if send and check_missed:
        missed = check_missed_days()
        if not missed:
            print("Today's report already sent, skipping.")
            return

        if len(missed) > 1:
            print(f"Missed {len(missed)} days, will send catch-up reports...")

    # 1. 保存快照
    print("Saving snapshot...")
    try:
        claude_stats = get_claude_code_stats()
        moltbot_stats = get_moltbot_stats()
        count = save_snapshot(claude_stats, moltbot_stats)
        print(f"  Snapshot saved: {count} records")
    except Exception as e:
        print(f"  Error saving snapshot: {e}", file=sys.stderr)

    # 2. 生成报告
    print("Generating report...")
    report = generate_report_text()
    print("\n--- Report ---")
    print(report)
    print("--- End ---\n")

    # 3. 发送 iMessage（如果需要）
    if send:
        print("Sending iMessage...")
        if send_imessage(report):
            print("  Message sent successfully")
            set_last_sent_date()  # 记录发送日期
        else:
            print("  Failed to send message", file=sys.stderr)

    print("-" * 50)
    print(f"[{datetime.now().isoformat()}] Done")


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"

    if cmd == "report":
        # 仅生成报告
        print(generate_report_text())

    elif cmd == "snapshot":
        # 仅保存快照
        claude_stats = get_claude_code_stats()
        moltbot_stats = get_moltbot_stats()
        count = save_snapshot(claude_stats, moltbot_stats)
        print(f"Snapshot saved: {count} records")

    elif cmd == "send":
        # 生成报告并发送
        run_daily_report(send=True)

    elif cmd == "all" or cmd == "run":
        # 完整流程（不发送）
        run_daily_report(send=False)

    elif cmd == "help" or cmd == "-h":
        print(__doc__)

    else:
        print(f"Unknown command: {cmd}")
        print("Use 'help' for usage")
        sys.exit(1)


if __name__ == "__main__":
    main()
