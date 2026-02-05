#!/usr/bin/env python3
"""
Token 费用估算模块

基于 dmxapi 定价计算各模型的使用费用
价格单位: USD per million tokens
"""

from typing import Any

# 模型定价表 (USD per million tokens)
MODEL_PRICING = {
    # Claude 系列
    "claude-opus-4-5-20250514": {
        "input": 15.0,
        "output": 75.0,
        "cache_read": 1.5,
        "cache_write": 18.75,
    },
    "claude-opus-4-5-20251101": {
        "input": 15.0,
        "output": 75.0,
        "cache_read": 1.5,
        "cache_write": 18.75,
    },
    "claude-sonnet-4-5-20250514": {
        "input": 3.0,
        "output": 15.0,
        "cache_read": 0.3,
        "cache_write": 3.75,
    },
    "claude-sonnet-4-5-20241022": {
        "input": 3.0,
        "output": 15.0,
        "cache_read": 0.3,
        "cache_write": 3.75,
    },
    "claude-haiku-4-5-20250514": {
        "input": 0.8,
        "output": 4.0,
        "cache_read": 0.08,
        "cache_write": 1.0,
    },
    # Gemini 系列
    "gemini-3-pro": {
        "input": 1.25,
        "output": 10.0,
        "cache_read": 0.125,
        "cache_write": 1.25,
    },
    "gemini-3-flash": {
        "input": 0.075,
        "output": 0.3,
        "cache_read": 0.0075,
        "cache_write": 0.075,
    },
    "gemini-2.0-flash": {
        "input": 0.075,
        "output": 0.3,
        "cache_read": 0.0075,
        "cache_write": 0.075,
    },
    "gemini-2.0-flash-exp": {
        "input": 0.075,
        "output": 0.3,
        "cache_read": 0.0075,
        "cache_write": 0.075,
    },
    # OpenAI 系列
    "gpt-5": {
        "input": 5.0,
        "output": 15.0,
        "cache_read": 0.5,
        "cache_write": 5.0,
    },
    "gpt-4o": {
        "input": 2.5,
        "output": 10.0,
        "cache_read": 0.25,
        "cache_write": 2.5,
    },
    "gpt-4o-mini": {
        "input": 0.15,
        "output": 0.6,
        "cache_read": 0.015,
        "cache_write": 0.15,
    },
    # DeepSeek 系列
    "deepseek-chat": {
        "input": 0.27,
        "output": 1.1,
        "cache_read": 0.027,
        "cache_write": 0.27,
    },
    "deepseek-reasoner": {
        "input": 0.55,
        "output": 2.19,
        "cache_read": 0.055,
        "cache_write": 0.55,
    },
}

# 模型名称别名映射
MODEL_ALIASES = {
    "opus": "claude-opus-4-5-20250514",
    "sonnet": "claude-sonnet-4-5-20250514",
    "haiku": "claude-haiku-4-5-20250514",
    "gemini-pro": "gemini-3-pro",
    "gemini-flash": "gemini-3-flash",
}


def normalize_model_name(model: str) -> str:
    """标准化模型名称"""
    model_lower = model.lower()

    # 检查别名
    if model_lower in MODEL_ALIASES:
        return MODEL_ALIASES[model_lower]

    # 检查是否包含关键词
    if "opus" in model_lower:
        if "20251101" in model:
            return "claude-opus-4-5-20251101"
        return "claude-opus-4-5-20250514"
    if "sonnet" in model_lower:
        if "20241022" in model:
            return "claude-sonnet-4-5-20241022"
        return "claude-sonnet-4-5-20250514"
    if "haiku" in model_lower:
        return "claude-haiku-4-5-20250514"
    if "gemini" in model_lower:
        if "pro" in model_lower:
            return "gemini-3-pro"
        if "flash" in model_lower:
            return "gemini-3-flash"
    if "gpt-5" in model_lower:
        return "gpt-5"
    if "gpt-4o-mini" in model_lower:
        return "gpt-4o-mini"
    if "gpt-4o" in model_lower:
        return "gpt-4o"
    if "deepseek" in model_lower:
        if "reasoner" in model_lower or "r1" in model_lower:
            return "deepseek-reasoner"
        return "deepseek-chat"

    return model


def get_model_pricing(model: str) -> dict[str, float] | None:
    """获取模型定价"""
    normalized = normalize_model_name(model)
    return MODEL_PRICING.get(normalized)


def estimate_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_read: int = 0,
    cache_write: int = 0
) -> float:
    """
    估算单次调用费用

    Args:
        model: 模型名称
        input_tokens: 输入 token 数
        output_tokens: 输出 token 数
        cache_read: 缓存读取 token 数
        cache_write: 缓存写入 token 数

    Returns:
        估算费用 (USD)
    """
    pricing = get_model_pricing(model)
    if not pricing:
        return 0.0

    cost = 0.0
    cost += (input_tokens / 1_000_000) * pricing["input"]
    cost += (output_tokens / 1_000_000) * pricing["output"]
    cost += (cache_read / 1_000_000) * pricing.get("cache_read", 0)
    cost += (cache_write / 1_000_000) * pricing.get("cache_write", 0)

    return cost


def get_total_estimated_cost(stats: dict[str, Any]) -> dict[str, Any]:
    """
    计算总估算费用

    Args:
        stats: 包含 claude_code 和 moltbot 统计的字典

    Returns:
        按来源汇总的费用明细
    """
    result = {
        "claude_code": {
            "by_model": {},
            "total": 0.0
        },
        "moltbot": {
            "by_model": {},
            "total": 0.0
        },
        "grand_total": 0.0
    }

    # Claude Code 费用
    claude_stats = stats.get("claude_code", {})
    models = claude_stats.get("models", {})
    for model, usage in models.items():
        cost = estimate_cost(
            model,
            usage.get("input", 0),
            usage.get("output", 0),
            usage.get("cache_read", 0),
            usage.get("cache_write", 0)
        )
        result["claude_code"]["by_model"][model] = {
            "cost": cost,
            "input_tokens": usage.get("input", 0),
            "output_tokens": usage.get("output", 0),
            "cache_read": usage.get("cache_read", 0),
            "cache_write": usage.get("cache_write", 0),
        }
        result["claude_code"]["total"] += cost

    # Moltbot 费用
    moltbot_stats = stats.get("moltbot", {})
    by_model = moltbot_stats.get("by_model", {})
    for model_key, usage in by_model.items():
        # model_key 格式: provider/model
        model = model_key.split("/")[-1] if "/" in model_key else model_key
        cost = estimate_cost(
            model,
            usage.get("input", 0),
            usage.get("output", 0)
        )
        result["moltbot"]["by_model"][model_key] = {
            "cost": cost,
            "input_tokens": usage.get("input", 0),
            "output_tokens": usage.get("output", 0),
        }
        result["moltbot"]["total"] += cost

    result["grand_total"] = result["claude_code"]["total"] + result["moltbot"]["total"]

    return result


def format_cost(cost: float) -> str:
    """格式化费用显示"""
    if cost >= 1.0:
        return f"${cost:.2f}"
    elif cost >= 0.01:
        return f"${cost:.3f}"
    else:
        return f"${cost:.4f}"


def print_pricing_table():
    """打印定价表"""
    print("模型定价表 (USD per million tokens)")
    print("-" * 70)
    print(f"{'模型':<35} {'Input':>8} {'Output':>8} {'Cache R':>8} {'Cache W':>8}")
    print("-" * 70)

    for model, pricing in sorted(MODEL_PRICING.items()):
        print(f"{model:<35} ${pricing['input']:>6.2f} ${pricing['output']:>6.2f} "
              f"${pricing.get('cache_read', 0):>6.2f} ${pricing.get('cache_write', 0):>6.2f}")


if __name__ == "__main__":
    print_pricing_table()
