"""
检索质量简易评估（替代 RAGAS，零额外依赖）

读取 run_v2_system.py 输出的 v2_system_answers.csv，
计算基础检索指标，不需要安装 ragas/datasets 等重型依赖。

指标说明：
- has_ground_truth: 答案中是否包含标准答案的关键信息
- context_count:   检索到的上下文片段数量
- context_has_source: 上下文是否包含预期的源文档名

用法：
    python -m tests.evaluators.run_ragas_eval
"""

import ast
import json
import pandas as pd
from pathlib import Path

ANSWERS_PATH = Path(__file__).parent / "v2_system_answers.csv"
REPORT_PATH = Path(__file__).parent / "eval_report.json"


def main():
    if not ANSWERS_PATH.exists():
        print(f"文件不存在: {ANSWERS_PATH}")
        print("请先运行: python -m tests.evaluators.run_v2_system")
        return

    df = pd.read_csv(ANSWERS_PATH)

    # 解析 contexts 字段
    def parse_contexts(val):
        if isinstance(val, str):
            try:
                return ast.literal_eval(val)
            except:
                return [val]
        return val if isinstance(val, list) else []

    df['contexts'] = df['contexts'].apply(parse_contexts)

    results = []
    for _, row in df.iterrows():
        question = row.get("question", "")
        answer = str(row.get("answer", ""))
        ground_truth = str(row.get("ground_truth", ""))
        contexts = row.get("contexts", [])
        domain = row.get("domain", "")

        # 指标1: 上下文数量
        ctx_count = len(contexts)

        # 指标2: 答案是否包含标准答案的关键词
        # 从 ground_truth 中提取关键词（取前 15 个字符作为关键信息）
        gt_key = ground_truth[:30] if ground_truth else ""
        has_gt = gt_key in answer if gt_key else False

        # 指标3: 答案是否包含数字/比例等关键事实
        import re
        has_numbers = bool(re.search(r'\d+', answer)) if answer else False

        # 指标4: 是否回复了"资料中未提及"
        is_fallback = "未提及" in answer or "未找到" in answer or "未检索" in answer

        results.append({
            "question": question[:50],
            "domain": domain,
            "context_count": ctx_count,
            "has_ground_truth_key": has_gt,
            "has_numbers": has_numbers,
            "is_fallback": is_fallback,
            "answer_preview": answer[:100],
        })

    # 汇总
    total = len(results)
    passed_gt = sum(1 for r in results if r["has_ground_truth_key"])
    passed_numbers = sum(1 for r in results if r["has_numbers"])
    fallbacks = sum(1 for r in results if r["is_fallback"])
    avg_ctx = sum(r["context_count"] for r in results) / total if total > 0 else 0

    print("=" * 60)
    print("         检索质量评估报告")
    print("=" * 60)
    print(f"总题数:               {total}")
    print(f"含关键事实的答案:      {passed_gt}/{total} ({passed_gt/total*100:.0f}%)")
    print(f"含数字/比例的答案:     {passed_numbers}/{total} ({passed_numbers/total*100:.0f}%)")
    print(f"回复'未提及'（失败）:   {fallbacks}/{total} ({fallbacks/total*100:.0f}%)")
    print(f"平均上下文片段数:      {avg_ctx:.1f}")
    print("=" * 60)

    # 逐题明细
    print("\n逐题明细:")
    for i, r in enumerate(results, 1):
        icon = "✅" if r["has_ground_truth_key"] else ("⚠️" if r["is_fallback"] else "❌")
        print(f"  {icon} [{i}] ctx={r['context_count']} | {r['answer_preview'][:60]}...")

    # 保存报告
    report = {
        "summary": {
            "total": total,
            "has_ground_truth_key": passed_gt,
            "has_numbers": passed_numbers,
            "fallbacks": fallbacks,
            "avg_context_count": round(avg_ctx, 1),
        },
        "details": results,
    }
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n详细报告已保存至: {REPORT_PATH}")


if __name__ == "__main__":
    main()
