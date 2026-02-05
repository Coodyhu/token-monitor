#!/usr/bin/env python3
"""
Token Monitor - Claude Code 和 Moltbot Token 使用统计监控

数据来源:
1. Claude Code: ~/.claude/stats-cache.json
2. Moltbot: ~/.clawdbot/agents/main/sessions/sessions.json
3. dmxapi: API 查询总用量
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
import urllib.request
import urllib.error

from pricing import estimate_cost, get_total_estimated_cost, format_cost, print_pricing_table

# 配置
CLAUDE_STATS_PATH = Path.home() / ".claude" / "stats-cache.json"
MOLTBOT_SESSIONS_PATH = Path.home() / ".clawdbot" / "agents" / "main" / "sessions" / "sessions.json"
DMXAPI_BASE_URL = "https://www.dmxapi.cn"
CONFIG_PATH = Path(__file__).parent / "config.json"


def load_config() -> dict:
    """加载配置文件"""
    try:
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        print("警告: config.json 不存在，请复制 config.example.json 并填入配置", file=sys.stderr)
        return {}


def get_dmxapi_key() -> str:
    """获取 dmxapi key"""
    # 优先从环境变量获取
    key = os.environ.get("DMXAPI_KEY")
    if key:
        return key
    # 从配置文件获取
    config = load_config()
    return config.get("dmxapi_key", "")


def load_json(path: Path) -> dict | None:
    """加载 JSON 文件"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"警告: 无法加载 {path}: {e}", file=sys.stderr)
        return None


def get_dmxapi_usage() -> dict | None:
    """查询 dmxapi 总用量"""
    api_key = get_dmxapi_key()
    if not api_key:
        print("警告: 未配置 dmxapi_key", file=sys.stderr)
        return None

    url = f"{DMXAPI_BASE_URL}/v1/dashboard/billing/usage"
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {api_key}")

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.load(resp)
            return {"total_usage": data.get("total_usage", 0)}
    except (urllib.error.URLError, json.JSONDecodeError) as e:
        print(f"警告: dmxapi 查询失败: {e}", file=sys.stderr)
        return None


def format_tokens(tokens: int) -> str:
    """格式化 token 数量"""
    if tokens >= 1_000_000:
        return f"{tokens / 1_000_000:.2f}M"
    elif tokens >= 1_000:
        return f"{tokens / 1_000:.1f}K"
    return str(tokens)


def get_claude_code_stats() -> dict[str, Any]:
    """获取 Claude Code 统计"""
    data = load_json(CLAUDE_STATS_PATH)
    if not data:
        return {}

    result = {
        "last_computed": data.get("lastComputedDate", "unknown"),
        "total_sessions": data.get("totalSessions", 0),
        "total_messages": data.get("totalMessages", 0),
        "models": {}
    }

    model_usage = data.get("modelUsage", {})
    for model, usage in model_usage.items():
        input_tokens = usage.get("inputTokens", 0)
        output_tokens = usage.get("outputTokens", 0)
        cache_read = usage.get("cacheReadInputTokens", 0)
        cache_write = usage.get("cacheCreationInputTokens", 0)
        total = input_tokens + output_tokens + cache_read + cache_write

        result["models"][model] = {
            "input": input_tokens,
            "output": output_tokens,
            "cache_read": cache_read,
            "cache_write": cache_write,
            "total": total
        }

    return result


def get_moltbot_stats() -> dict[str, Any]:
    """获取 Moltbot 统计"""
    data = load_json(MOLTBOT_SESSIONS_PATH)
    if not data:
        return {}

    # 按 provider/model 聚合
    by_provider: dict[str, dict] = {}
    total_input = 0
    total_output = 0
    session_count = 0

    for session_key, session in data.items():
        if not isinstance(session, dict):
            continue

        session_count += 1
        provider = session.get("modelProvider", "unknown")
        model = session.get("model", "unknown")
        input_tokens = session.get("inputTokens", 0)
        output_tokens = session.get("outputTokens", 0)

        total_input += input_tokens
        total_output += output_tokens

        key = f"{provider}/{model}"
        if key not in by_provider:
            by_provider[key] = {"input": 0, "output": 0, "sessions": 0}

        by_provider[key]["input"] += input_tokens
        by_provider[key]["output"] += output_tokens
        by_provider[key]["sessions"] += 1

    return {
        "session_count": session_count,
        "total_input": total_input,
        "total_output": total_output,
        "by_model": by_provider
    }


def print_report():
    """打印统计报告"""
    print("=" * 60)
    print(f"Token 使用统计报告 - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    # Claude Code 统计
    print("\n📊 Claude Code 统计")
    print("-" * 40)
    claude_stats = get_claude_code_stats()
    if claude_stats:
        print(f"统计日期: {claude_stats.get('last_computed', 'N/A')}")
        print(f"会话数: {claude_stats.get('total_sessions', 0)}")
        print(f"消息数: {claude_stats.get('total_messages', 0)}")

        models = claude_stats.get("models", {})
        if models:
            print("\n模型使用:")
            for model, usage in models.items():
                cost = estimate_cost(
                    model,
                    usage['input'],
                    usage['output'],
                    usage['cache_read'],
                    usage['cache_write']
                )
                print(f"  {model}:")
                print(f"    Input:       {format_tokens(usage['input'])}")
                print(f"    Output:      {format_tokens(usage['output'])}")
                print(f"    Cache Read:  {format_tokens(usage['cache_read'])}")
                print(f"    Cache Write: {format_tokens(usage['cache_write'])}")
                print(f"    Total:       {format_tokens(usage['total'])}")
                print(f"    Est. Cost:   {format_cost(cost)}")
    else:
        print("  无数据")

    # Moltbot 统计
    print("\n📊 Moltbot 统计")
    print("-" * 40)
    moltbot_stats = get_moltbot_stats()
    if moltbot_stats:
        print(f"会话数: {moltbot_stats.get('session_count', 0)}")
        print(f"总 Input:  {format_tokens(moltbot_stats.get('total_input', 0))}")
        print(f"总 Output: {format_tokens(moltbot_stats.get('total_output', 0))}")

        by_model = moltbot_stats.get("by_model", {})
        if by_model:
            print("\n按模型统计:")
            for model_key, usage in sorted(by_model.items(), key=lambda x: x[1]["input"], reverse=True):
                total = usage["input"] + usage["output"]
                model = model_key.split("/")[-1] if "/" in model_key else model_key
                cost = estimate_cost(model, usage["input"], usage["output"])
                print(f"  {model_key}:")
                print(f"    Sessions: {usage['sessions']}")
                print(f"    Input:    {format_tokens(usage['input'])}")
                print(f"    Output:   {format_tokens(usage['output'])}")
                print(f"    Total:    {format_tokens(total)}")
                print(f"    Est. Cost: {format_cost(cost)}")
    else:
        print("  无数据")

    # dmxapi 总用量
    print("\n📊 dmxapi 账户总用量")
    print("-" * 40)
    dmx_usage = get_dmxapi_usage()
    if dmx_usage:
        total = dmx_usage.get("total_usage", 0)
        print(f"总消费: ¥{total / 10000:.2f}")
    else:
        print("  查询失败")

    # 费用汇总
    print("\n💰 费用估算汇总")
    print("-" * 40)
    all_stats = {
        "claude_code": claude_stats,
        "moltbot": moltbot_stats
    }
    cost_summary = get_total_estimated_cost(all_stats)
    print(f"Claude Code: {format_cost(cost_summary['claude_code']['total'])}")
    print(f"Moltbot:     {format_cost(cost_summary['moltbot']['total'])}")
    print(f"总计:        {format_cost(cost_summary['grand_total'])}")

    print("\n" + "=" * 60)


def print_cost_report():
    """打印费用明细报告"""
    print("=" * 70)
    print(f"费用估算明细 - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 70)

    claude_stats = get_claude_code_stats()
    moltbot_stats = get_moltbot_stats()

    all_stats = {
        "claude_code": claude_stats,
        "moltbot": moltbot_stats
    }
    cost_summary = get_total_estimated_cost(all_stats)

    # Claude Code 费用明细
    print("\n📊 Claude Code 费用明细")
    print("-" * 70)
    print(f"{'模型':<40} {'Input':>10} {'Output':>10} {'Cost':>10}")
    print("-" * 70)

    cc_costs = cost_summary["claude_code"]["by_model"]
    for model, data in sorted(cc_costs.items(), key=lambda x: x[1]["cost"], reverse=True):
        print(f"{model:<40} {format_tokens(data['input_tokens']):>10} "
              f"{format_tokens(data['output_tokens']):>10} {format_cost(data['cost']):>10}")

    print("-" * 70)
    print(f"{'小计':<40} {'':<10} {'':<10} {format_cost(cost_summary['claude_code']['total']):>10}")

    # Moltbot 费用明细
    print("\n📊 Moltbot 费用明细")
    print("-" * 70)
    print(f"{'模型':<40} {'Input':>10} {'Output':>10} {'Cost':>10}")
    print("-" * 70)

    mb_costs = cost_summary["moltbot"]["by_model"]
    for model, data in sorted(mb_costs.items(), key=lambda x: x[1]["cost"], reverse=True):
        print(f"{model:<40} {format_tokens(data['input_tokens']):>10} "
              f"{format_tokens(data['output_tokens']):>10} {format_cost(data['cost']):>10}")

    print("-" * 70)
    print(f"{'小计':<40} {'':<10} {'':<10} {format_cost(cost_summary['moltbot']['total']):>10}")

    # 总计
    print("\n" + "=" * 70)
    print(f"{'总计估算费用':<40} {'':<10} {'':<10} {format_cost(cost_summary['grand_total']):>10}")
    print("=" * 70)

    # dmxapi 实际消费对比
    dmx_usage = get_dmxapi_usage()
    if dmx_usage:
        actual_cny = dmx_usage.get("total_usage", 0) / 10000
        actual_usd = actual_cny / 7.2  # 假设汇率
        print(f"\ndmxapi 实际消费: ¥{actual_cny:.2f} (~${actual_usd:.2f})")


def export_json() -> dict:
    """导出 JSON 格式数据"""
    return {
        "timestamp": datetime.now().isoformat(),
        "claude_code": get_claude_code_stats(),
        "moltbot": get_moltbot_stats(),
        "dmxapi": get_dmxapi_usage()
    }


def main():
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "json":
            print(json.dumps(export_json(), indent=2, ensure_ascii=False))
        elif cmd == "claude":
            stats = get_claude_code_stats()
            print(json.dumps(stats, indent=2, ensure_ascii=False))
        elif cmd == "moltbot":
            stats = get_moltbot_stats()
            print(json.dumps(stats, indent=2, ensure_ascii=False))
        elif cmd == "dmxapi":
            stats = get_dmxapi_usage()
            print(json.dumps(stats, indent=2, ensure_ascii=False))
        elif cmd == "cost":
            print_cost_report()
        elif cmd == "pricing":
            print_pricing_table()
        elif cmd == "snapshot":
            # 保存当前快照到历史
            from history import save_snapshot
            claude_stats = get_claude_code_stats()
            moltbot_stats = get_moltbot_stats()
            count = save_snapshot(claude_stats, moltbot_stats)
            print(f"快照已保存，共 {count} 条记录")
        elif cmd == "history":
            # 显示历史数据
            from history import print_history
            days = int(sys.argv[2]) if len(sys.argv) > 2 else 7
            print_history(days)
        elif cmd == "trend":
            # 显示趋势分析
            from history import print_trend
            print_trend()
        elif cmd == "notify":
            # 通知命令
            from notify import send_daily_report, send_alert, check_cost_threshold
            if len(sys.argv) > 2:
                subcmd = sys.argv[2]
                if subcmd == "daily":
                    send_daily_report()
                elif subcmd == "alert":
                    if len(sys.argv) > 3:
                        send_alert(" ".join(sys.argv[3:]))
                    else:
                        print("用法: token_monitor.py notify alert <message>")
                elif subcmd == "check":
                    threshold = float(sys.argv[3]) if len(sys.argv) > 3 else 50.0
                    exceeded = check_cost_threshold(threshold)
                    if not exceeded:
                        print(f"费用在阈值内 (${threshold:.2f})")
                else:
                    print(f"未知子命令: {subcmd}")
                    print("用法: token_monitor.py notify [daily|alert|check]")
            else:
                # 默认发送日报
                send_daily_report()
        else:
            print(f"用法: {sys.argv[0]} [json|claude|moltbot|dmxapi|cost|pricing|snapshot|history|trend|notify]")
            sys.exit(1)
    else:
        print_report()


if __name__ == "__main__":
    main()
