#!/usr/bin/env python3
"""
cron_report.py - Token Monitor 定时报告

功能:
1. 生成每日统计摘要
2. 保存历史快照
3. 生成报告文本（适合 iMessage 发送）

用法:
  python cron_report.py          # 生成报告并保存快照
  python cron_report.py report   # 仅生成报告文本
  python cron_report.py snapshot # 仅保存快照
  python cron_report.py send     # 生成报告并发送 iMessage
"""

import json
import os
import sys
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

# 添加当前目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from token_monitor import (
    get_claude_code_stats,
    get_moltbot_stats,
    get_dmxapi_usage,
    format_tokens,
    export_json
)
from history import save_snapshot, get_latest_snapshot, load_snapshot, compare_snapshots, list_snapshots

# 配置
EDDIE_PHONE = "+8618257004233"


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
    snapshots = list_snapshots(2)
    if len(snapshots) >= 2:
        today = snapshots[0]
        yesterday = snapshots[1]
        diff = compare_snapshots(yesterday, today)
        changes = diff.get("changes", {})

        if changes:
            lines.append("[vs Yesterday]")
            dmx_diff = changes.get("dmxapi_usage", 0)
            if dmx_diff != 0:
                lines.append(f"dmxapi: +CNY {dmx_diff / 10000:.2f}")
            session_diff = changes.get("claude_sessions", 0)
            if session_diff != 0:
                lines.append(f"Claude Sessions: +{session_diff}")
            msg_diff = changes.get("claude_messages", 0)
            if msg_diff != 0:
                lines.append(f"Claude Messages: +{msg_diff}")

    return "\n".join(lines)


def send_imessage(message: str, to: str = EDDIE_PHONE) -> bool:
    """发送 iMessage"""
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


def run_daily_report(send: bool = False) -> None:
    """执行每日报告"""
    print(f"[{datetime.now().isoformat()}] Token Monitor Daily Report")
    print("-" * 50)

    # 1. 保存快照
    print("Saving snapshot...")
    try:
        path = save_snapshot()
        print(f"  Snapshot saved: {path}")
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
        path = save_snapshot()
        print(f"Snapshot saved: {path}")

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
