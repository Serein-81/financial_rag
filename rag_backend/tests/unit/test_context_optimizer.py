"""
上下文优化器单元测试
"""
import json
import sys
sys.path.insert(0, ".")

from app.services.context_optimizer import ContextOptimizer


def test_level1_deduplicate():
    """Level 1: 删除空消息"""
    opt = ContextOptimizer()
    msgs = [
        {"role": "system", "content": "你是一个财务专家。"},
        {"role": "assistant", "content": "", "tool_calls": None},  # 应被删除
        {"role": "user", "content": "分析利润"},
    ]
    result = opt._level1_deduplicate(msgs)
    assert len(result) == 2, f"期望 2 条, 实际 {len(result)}"
    print(f"[PASS] Level 1: {len(msgs)} -> {len(result)}")


def test_level2_compress():
    """Level 2: JSON -> 单行摘要"""
    opt = ContextOptimizer()
    raw = json.dumps({
        "status": "success",
        "data": {"total_revenue": 42918130.0, "total_profit": 16217370.0},
        "summary": {
            "total_revenue": "42,918,130.00",
            "total_profit": "16,217,370.00",
            "avg_profit_margin": "37.42%"
        },
        "fiscal_year": 2024
    })
    msgs = [{"role": "tool", "tool_call_id": "c1", "content": raw}]
    result = opt._level2_compress_tool_results(msgs)
    compressed = result[0]["content"]

    # 验证包含关键字段
    assert "success" in compressed
    assert "fy=2024" in compressed
    assert len(compressed) < len(raw), f"压缩未减小: {len(compressed)} >= {len(raw)}"
    ratio = (1 - len(compressed) / len(raw)) * 100
    print(f"[PASS] Level 2: {len(raw)} -> {len(compressed)} chars ({ratio:.0f}%)")
    print(f"  压缩结果: {compressed}")


def test_level3_rollup():
    """Level 3: 多轮压缩"""
    opt = ContextOptimizer()
    tool_result = json.dumps({"status": "success", "summary": {"total_revenue": "42M"}, "fiscal_year": 2024})

    msgs = [{"role": "system", "content": "system prompt"}]
    for i in range(3):
        msgs.append({"role": "assistant", "content": f"查{i}数据", "tool_calls": [{"function": {"name": "get_fin_overview", "arguments": "{}"}}]})
        msgs.append({"role": "tool", "tool_call_id": f"c{i}", "content": tool_result})
    msgs.append({"role": "user", "content": "分析利润"})

    result = opt._level3_rollup(msgs)
    assert len(result) < len(msgs), f"压缩未减小: {len(result)} >= {len(msgs)}"
    assert result[0]["role"] == "system"
    assert result[-1]["role"] == "user"
    print(f"[PASS] Level 3: {len(msgs)} -> {len(result)} msgs")


def test_full_optimize_below_threshold():
    """低于阈值时不压缩"""
    opt = ContextOptimizer()
    opt.token_limit = 100000  # 高阈值，不会触发
    msgs = [
        {"role": "system", "content": "你是一个财务专家。"},
        {"role": "user", "content": "分析利润"},
    ]
    result = opt.optimize(msgs)
    assert len(result) == len(msgs), "不应压缩"
    print(f"[PASS] Full (below threshold): {len(msgs)} 条不变")


def test_full_optimize_above_threshold():
    """高于阈值时触发三级压缩"""
    opt = ContextOptimizer()
    opt.token_limit = 200  # 低阈值，强制触发

    tool_result = json.dumps({
        "status": "success",
        "summary": {"total_revenue": "42,918,130.00", "total_profit": "16,217,370.00"},
        "fiscal_year": 2024
    })

    msgs = [{"role": "system", "content": "你是一名财务专家。" * 100}]
    for i in range(3):
        msgs.append({"role": "assistant", "content": f"查询第{i+1}轮", "tool_calls": [{"function": {"name": "get_financial_overview", "arguments": "{}"}}]})
        msgs.append({"role": "tool", "tool_call_id": f"c{i}", "content": tool_result})
    msgs.append({"role": "user", "content": "分析利润"})

    before = len(msgs)
    result = opt.optimize(msgs)
    after = len(result)

    assert after <= before, f"压缩后消息数不应增加: {after} > {before}"
    bt = opt._estimate_tokens(msgs)
    at = opt._estimate_tokens(result)
    print(f"[PASS] Full (above threshold): {before} msgs, {bt} tokens -> {after} msgs, {at} tokens")

    # 验证关键消息被保留
    roles = [m["role"] for m in result]
    assert "system" in roles
    assert "user" in roles
    assert result[-1]["role"] == "user", "最后一条应为用户消息"


if __name__ == "__main__":
    test_level1_deduplicate()
    test_level2_compress()
    test_level3_rollup()
    test_full_optimize_below_threshold()
    test_full_optimize_above_threshold()
    print("\n所有测试通过 \u2705")
