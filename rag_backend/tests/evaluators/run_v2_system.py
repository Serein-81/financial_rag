"""
V2 检索系统自动化测试脚本

读取 evaluation_dataset_ragas.json 中的测试问题，
调用项目的 V2 检索链路 + LLM 生成答案，
输出结果供 RAGAS 评估。

用法：
    # 先设置必要的环境变量
    export KB_ID="你的知识库ID"
    export TENANT_ID="你的租户ID"

    cd rag_backend
    python -m tests.evaluators.run_v2_system
"""

import os
import json
import asyncio
import pandas as pd
from pathlib import Path

# ── 配置：通过环境变量传入 ──
KB_ID = os.getenv("KB_ID", "")
TENANT_ID = os.getenv("TENANT_ID", "test_tenant_001")
USER_ID = os.getenv("USER_ID", "8cbd5945-6712-40ce-9e35-e30083ef93e8")
SESSION_ID = os.getenv("SESSION_ID", "eval-session-001")

# 数据集路径
DATASET_PATH = Path(__file__).parent / "evaluation_dataset_ragas.json"
OUTPUT_PATH = Path(__file__).parent / "v2_system_answers.csv"


async def main():
    # 1. 加载黄金考卷
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        eval_data = json.load(f)

    if not KB_ID:
        print("请设置环境变量 KB_ID（知识库ID）")
        return

    # 延迟导入，避免模块加载时依赖项目环境
    from app.services.unified_retriever import unified_retriever
    from app.services.llm_service import llm_service

    results = []
    print(f"开始 V2 系统评估: {len(eval_data)} 道题")
    print(f"知识库: {KB_ID}, 租户: {TENANT_ID}")
    print("=" * 60)

    for idx, item in enumerate(eval_data, 1):
        query = item["question"]
        print(f"\n[{idx}/{len(eval_data)}] {query[:40]}...")

        try:
            # ── Step 1: 调用 V2 检索链路 ──
            # 触发 QueryAnalyzer → HybridSearch → Reranker → Cliff Prune
            # → Temporal Dedup → Relationship Expansion → Context Assembly
            # 评估模式下跳过指标过滤（metrics 取决于文档 OCR 质量，非检索问题）
            retrieval_result = await unified_retriever.retrieve(
                query=query,
                kb_id=KB_ID,
                session_id=SESSION_ID,
                user_id=USER_ID,
                top_k=5,
                enable_routing=True,
                enable_graph=False,       # 测试 RAG 检索，跳过图谱
                tenant_id=TENANT_ID,
                _skip_metric_filter=True,
            )

            # ── Step 2: 提取检索到的上下文 ──
            combined_context = retrieval_result.get("combined_context", "")
            rag_results = retrieval_result.get("rag_results", [])

            # 取每个 chunk 的 content 作为独立上下文
            retrieved_contexts = []
            for chunk in rag_results:
                content = chunk.get("content", "") if isinstance(chunk, dict) else getattr(chunk, "content", "")
                if content:
                    retrieved_contexts.append(content)

            # 如果没有检索到结果，使用 combined_context 作为兜底
            if not retrieved_contexts and combined_context:
                retrieved_contexts = [combined_context]

            print(f"  检索到 {len(retrieved_contexts)} 个上下文片段")

            # ── Step 3: 生成答案 ──
            system_prompt = (
                "你是一个专业的文档分析助手。请严格基于以下提供的资料，"
                "用中文准确、简洁地回答用户的问题。\n\n"
                "规则：\n"
                "1. 只回答资料中明确写明的信息，不要推测\n"
                "2. 如果资料中找不到相关信息，请明确说'资料中未提及'\n"
                "3. 如果资料中有数字或比例，请直接引用原文数字\n"
                "4. 不要编造法律法规条款\n"
                "5. 如果不确定，请说'无法从资料中确定'\n"
            )
            answer = await llm_service.get_answer(
                query=f"{system_prompt}\n\n用户问题：{query}",
                context_chunks=retrieved_contexts,
                history=[],
            )

            print(f"  回答: {answer[:80]}...")

        except Exception as e:
            print(f"  ❌ 处理失败: {e}")
            import traceback
            traceback.print_exc()
            answer = f"[ERROR] {e}"
            retrieved_contexts = []

        # ── Step 4: 记录结果 ──
        results.append({
            "question": query,
            "answer": answer,
            "contexts": retrieved_contexts,
            "ground_truth": item["ground_truth"],
            "domain": item.get("domain", ""),
            "question_id": item.get("id", f"q-{idx}"),
        })

    # ── Step 5: 保存结果 ──
    df = pd.DataFrame(results)
    df.to_csv(OUTPUT_PATH, index=False, encoding="utf-8")
    print(f"\n{'=' * 60}")
    print(f"评估完成！结果已保存至: {OUTPUT_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
