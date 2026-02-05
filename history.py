#!/usr/bin/env python3
"""
历史趋势记录模块 - Token 使用历史数据存储和查询

数据存储: ~/.token-monitor/history.db (SQLite)
"""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

# 数据库路径
DB_DIR = Path.home() / ".token-monitor"
DB_PATH = DB_DIR / "history.db"


def get_connection() -> sqlite3.Connection:
    """获取数据库连接，自动创建表"""
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # 创建表
    conn.execute("""
        CREATE TABLE IF NOT EXISTS daily_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            source TEXT NOT NULL,
            model TEXT NOT NULL,
            input_tokens INTEGER DEFAULT 0,
            output_tokens INTEGER DEFAULT 0,
            cache_read INTEGER DEFAULT 0,
            cache_write INTEGER DEFAULT 0,
            sessions INTEGER DEFAULT 0,
            cost_estimate REAL DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(date, source, model)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_date ON daily_stats(date)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_source ON daily_stats(source)")
    conn.commit()
    return conn


def save_snapshot(claude_stats: dict, moltbot_stats: dict, date: str | None = None) -> int:
    """
    保存当前快照到历史

    Args:
        claude_stats: Claude Code 统计数据
        moltbot_stats: Moltbot 统计数据
        date: 日期 (YYYY-MM-DD)，默认今天

    Returns:
        插入/更新的记录数
    """
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    conn = get_connection()
    count = 0

    # 保存 Claude Code 数据
    models = claude_stats.get("models", {})
    sessions = claude_stats.get("total_sessions", 0)

    for model, usage in models.items():
        input_tokens = usage.get("input", 0)
        output_tokens = usage.get("output", 0)
        cache_read = usage.get("cache_read", 0)
        cache_write = usage.get("cache_write", 0)

        # 估算成本 (基于 Claude 定价)
        cost = estimate_claude_cost(model, input_tokens, output_tokens, cache_read, cache_write)

        conn.execute("""
            INSERT INTO daily_stats (date, source, model, input_tokens, output_tokens,
                                     cache_read, cache_write, sessions, cost_estimate)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(date, source, model) DO UPDATE SET
                input_tokens = excluded.input_tokens,
                output_tokens = excluded.output_tokens,
                cache_read = excluded.cache_read,
                cache_write = excluded.cache_write,
                sessions = excluded.sessions,
                cost_estimate = excluded.cost_estimate
        """, (date, "claude", model, input_tokens, output_tokens,
              cache_read, cache_write, sessions, cost))
        count += 1

    # 保存 Moltbot 数据
    by_model = moltbot_stats.get("by_model", {})
    for model_key, usage in by_model.items():
        input_tokens = usage.get("input", 0)
        output_tokens = usage.get("output", 0)
        sessions = usage.get("sessions", 0)

        # Moltbot 成本估算 (简化)
        cost = estimate_moltbot_cost(model_key, input_tokens, output_tokens)

        conn.execute("""
            INSERT INTO daily_stats (date, source, model, input_tokens, output_tokens,
                                     cache_read, cache_write, sessions, cost_estimate)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(date, source, model) DO UPDATE SET
                input_tokens = excluded.input_tokens,
                output_tokens = excluded.output_tokens,
                sessions = excluded.sessions,
                cost_estimate = excluded.cost_estimate
        """, (date, "moltbot", model_key, input_tokens, output_tokens,
              0, 0, sessions, cost))
        count += 1

    conn.commit()
    conn.close()
    return count


def estimate_claude_cost(model: str, input_tokens: int, output_tokens: int,
                         cache_read: int, cache_write: int) -> float:
    """估算 Claude 成本 (USD)"""
    # 定价 (per 1M tokens)
    pricing = {
        "claude-sonnet-4-20250514": {"input": 3.0, "output": 15.0, "cache_read": 0.30, "cache_write": 3.75},
        "claude-opus-4-5-20251101": {"input": 15.0, "output": 75.0, "cache_read": 1.50, "cache_write": 18.75},
        "claude-3-5-sonnet-20241022": {"input": 3.0, "output": 15.0, "cache_read": 0.30, "cache_write": 3.75},
        "claude-3-opus-20240229": {"input": 15.0, "output": 75.0, "cache_read": 1.50, "cache_write": 18.75},
    }

    # 默认使用 Sonnet 定价
    prices = pricing.get(model, pricing["claude-sonnet-4-20250514"])

    cost = (
        (input_tokens / 1_000_000) * prices["input"] +
        (output_tokens / 1_000_000) * prices["output"] +
        (cache_read / 1_000_000) * prices["cache_read"] +
        (cache_write / 1_000_000) * prices["cache_write"]
    )
    return round(cost, 4)


def estimate_moltbot_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """估算 Moltbot 成本 (USD) - 简化版"""
    # 默认按 GPT-4 级别估算
    input_price = 10.0  # per 1M
    output_price = 30.0  # per 1M

    if "gpt-3.5" in model.lower():
        input_price = 0.5
        output_price = 1.5
    elif "gpt-4o" in model.lower():
        input_price = 2.5
        output_price = 10.0
    elif "claude" in model.lower():
        input_price = 3.0
        output_price = 15.0

    cost = (
        (input_tokens / 1_000_000) * input_price +
        (output_tokens / 1_000_000) * output_price
    )
    return round(cost, 4)


def get_history(days: int = 7, source: str | None = None) -> list[dict[str, Any]]:
    """
    获取最近 N 天的历史数据

    Args:
        days: 天数
        source: 数据源过滤 (claude/moltbot)

    Returns:
        历史记录列表
    """
    conn = get_connection()

    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    if source:
        cursor = conn.execute("""
            SELECT date, source, model, input_tokens, output_tokens,
                   cache_read, cache_write, sessions, cost_estimate
            FROM daily_stats
            WHERE date >= ? AND source = ?
            ORDER BY date DESC, source, model
        """, (start_date, source))
    else:
        cursor = conn.execute("""
            SELECT date, source, model, input_tokens, output_tokens,
                   cache_read, cache_write, sessions, cost_estimate
            FROM daily_stats
            WHERE date >= ?
            ORDER BY date DESC, source, model
        """, (start_date,))

    results = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return results


def get_daily_summary(days: int = 7) -> list[dict[str, Any]]:
    """
    获取每日汇总数据

    Args:
        days: 天数

    Returns:
        每日汇总列表
    """
    conn = get_connection()

    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    cursor = conn.execute("""
        SELECT date,
               SUM(input_tokens) as total_input,
               SUM(output_tokens) as total_output,
               SUM(cache_read) as total_cache_read,
               SUM(cache_write) as total_cache_write,
               SUM(sessions) as total_sessions,
               SUM(cost_estimate) as total_cost
        FROM daily_stats
        WHERE date >= ?
        GROUP BY date
        ORDER BY date DESC
    """, (start_date,))

    results = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return results


def get_trend() -> dict[str, Any]:
    """
    计算趋势数据

    Returns:
        趋势分析结果
    """
    conn = get_connection()
    today = datetime.now().strftime("%Y-%m-%d")
    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    two_weeks_ago = (datetime.now() - timedelta(days=14)).strftime("%Y-%m-%d")

    # 本周数据
    cursor = conn.execute("""
        SELECT SUM(input_tokens) as input,
               SUM(output_tokens) as output,
               SUM(cache_read) as cache_read,
               SUM(cache_write) as cache_write,
               SUM(cost_estimate) as cost,
               COUNT(DISTINCT date) as days
        FROM daily_stats
        WHERE date >= ?
    """, (week_ago,))
    this_week = dict(cursor.fetchone())

    # 上周数据
    cursor = conn.execute("""
        SELECT SUM(input_tokens) as input,
               SUM(output_tokens) as output,
               SUM(cache_read) as cache_read,
               SUM(cache_write) as cache_write,
               SUM(cost_estimate) as cost,
               COUNT(DISTINCT date) as days
        FROM daily_stats
        WHERE date >= ? AND date < ?
    """, (two_weeks_ago, week_ago))
    last_week = dict(cursor.fetchone())

    # 今日数据
    cursor = conn.execute("""
        SELECT SUM(input_tokens) as input,
               SUM(output_tokens) as output,
               SUM(cache_read) as cache_read,
               SUM(cache_write) as cache_write,
               SUM(cost_estimate) as cost
        FROM daily_stats
        WHERE date = ?
    """, (today,))
    today_data = dict(cursor.fetchone())

    # 计算日均
    this_week_days = this_week.get("days") or 1
    last_week_days = last_week.get("days") or 1

    daily_avg_input = (this_week.get("input") or 0) / this_week_days
    daily_avg_output = (this_week.get("output") or 0) / this_week_days
    daily_avg_cost = (this_week.get("cost") or 0) / this_week_days

    # 计算周环比
    this_week_total = (this_week.get("input") or 0) + (this_week.get("output") or 0)
    last_week_total = (last_week.get("input") or 0) + (last_week.get("output") or 0)

    if last_week_total > 0:
        week_over_week = ((this_week_total - last_week_total) / last_week_total) * 100
    else:
        week_over_week = 0 if this_week_total == 0 else 100

    this_week_cost = this_week.get("cost") or 0
    last_week_cost = last_week.get("cost") or 0

    if last_week_cost > 0:
        cost_wow = ((this_week_cost - last_week_cost) / last_week_cost) * 100
    else:
        cost_wow = 0 if this_week_cost == 0 else 100

    conn.close()

    return {
        "today": {
            "input": today_data.get("input") or 0,
            "output": today_data.get("output") or 0,
            "cost": today_data.get("cost") or 0,
        },
        "this_week": {
            "input": this_week.get("input") or 0,
            "output": this_week.get("output") or 0,
            "cost": this_week.get("cost") or 0,
            "days": this_week_days,
        },
        "last_week": {
            "input": last_week.get("input") or 0,
            "output": last_week.get("output") or 0,
            "cost": last_week.get("cost") or 0,
            "days": last_week_days,
        },
        "daily_average": {
            "input": round(daily_avg_input),
            "output": round(daily_avg_output),
            "cost": round(daily_avg_cost, 4),
        },
        "week_over_week": {
            "tokens_change_percent": round(week_over_week, 2),
            "cost_change_percent": round(cost_wow, 2),
        }
    }


def format_tokens(tokens: int) -> str:
    """格式化 token 数量"""
    if tokens >= 1_000_000:
        return f"{tokens / 1_000_000:.2f}M"
    elif tokens >= 1_000:
        return f"{tokens / 1_000:.1f}K"
    return str(tokens)


def print_history(days: int = 7):
    """打印历史数据"""
    print(f"\n{'=' * 60}")
    print(f"Token 使用历史 - 最近 {days} 天")
    print(f"{'=' * 60}")

    summary = get_daily_summary(days)

    if not summary:
        print("\n  暂无历史数据")
        print("  使用 'snapshot' 命令保存当前数据")
        return

    print(f"\n{'日期':<12} {'Input':<12} {'Output':<12} {'Cache':<12} {'成本(USD)':<10}")
    print("-" * 60)

    for day in summary:
        date = day["date"]
        input_t = format_tokens(day["total_input"] or 0)
        output_t = format_tokens(day["total_output"] or 0)
        cache = format_tokens((day["total_cache_read"] or 0) + (day["total_cache_write"] or 0))
        cost = f"${day['total_cost'] or 0:.4f}"
        print(f"{date:<12} {input_t:<12} {output_t:<12} {cache:<12} {cost:<10}")

    print("-" * 60)


def print_trend():
    """打印趋势分析"""
    print(f"\n{'=' * 60}")
    print("Token 使用趋势分析")
    print(f"{'=' * 60}")

    trend = get_trend()

    # 今日
    print("\n[今日]")
    print(f"  Input:  {format_tokens(trend['today']['input'])}")
    print(f"  Output: {format_tokens(trend['today']['output'])}")
    print(f"  成本:   ${trend['today']['cost']:.4f}")

    # 本周
    print(f"\n[本周] ({trend['this_week']['days']} 天)")
    print(f"  Input:  {format_tokens(trend['this_week']['input'])}")
    print(f"  Output: {format_tokens(trend['this_week']['output'])}")
    print(f"  成本:   ${trend['this_week']['cost']:.4f}")

    # 日均
    print("\n[日均]")
    print(f"  Input:  {format_tokens(trend['daily_average']['input'])}")
    print(f"  Output: {format_tokens(trend['daily_average']['output'])}")
    print(f"  成本:   ${trend['daily_average']['cost']:.4f}")

    # 周环比
    print("\n[周环比]")
    tokens_change = trend['week_over_week']['tokens_change_percent']
    cost_change = trend['week_over_week']['cost_change_percent']

    tokens_arrow = "+" if tokens_change >= 0 else ""
    cost_arrow = "+" if cost_change >= 0 else ""

    print(f"  Token 变化: {tokens_arrow}{tokens_change:.1f}%")
    print(f"  成本变化:   {cost_arrow}{cost_change:.1f}%")

    print(f"\n{'=' * 60}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "history":
            days = int(sys.argv[2]) if len(sys.argv) > 2 else 7
            print_history(days)
        elif cmd == "trend":
            print_trend()
        else:
            print(f"用法: {sys.argv[0]} [history [days]|trend]")
    else:
        print_history()
        print_trend()
