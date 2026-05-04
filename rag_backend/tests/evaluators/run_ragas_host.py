"""
RAGAS 评估（宿主机版）

读取容器输出的 v2_system_answers.csv，在宿主机上运行 RAGAS 评估。
避免与 Docker 镜像的 fsspec 版本冲突。

用法：
    # 1. 先在容器里跑完 run_v2_system
    # 2. 复制结果到宿主机
    docker cp rag_backend:/app/tests/evaluators/v2_system_answers.csv tests/evaluators/

    # 3. 在宿主机独立虚拟环境运行本脚本
    uv pip install ragas datasets langchain-openai pandas
    python tests/evaluators/run_ragas_host.py
"""

import os
import ast
import pandas as pd
from pathlib import Path

ANSWERS_PATH = Path(__file__).parent / "v2_system_answers.csv"
REPORT_PATH = Path(__file__).parent / "ragas_report.csv"

JUDGE_MODEL = os.getenv("JUDGE_MODEL", "deepseek-chat")
JUDGE_API_KEY = os.getenv("OPENAI_API_KEY", "")
JUDGE_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com/v1")


def main():
    if not JUDGE_API_KEY:
        print("请设置 OPENAI_API_KEY 环境变量")
        return

    if not ANSWERS_PATH.exists():
        print(f"未找到: {ANSWERS_PATH}")
        print("请先: docker cp rag_backend:/app/tests/evaluators/v2_system_answers.csv tests/evaluators/")
        return

    df = pd.read_csv(ANSWERS_PATH)

    # 解析 contexts 字段
    def parse_contexts(val):
        if isinstance(val, str):
            try:
                return ast.literal_eval(val)
            except:
                return [val] if val else []
        return val if isinstance(val, list) else []

    df['contexts'] = df['contexts'].apply(parse_contexts)
    df = df[df['contexts'].apply(len) > 0]
    print(f"加载 {len(df)} 条有效数据")

    from datasets import Dataset
    from ragas import evaluate
    from ragas.metrics import context_precision, context_recall, faithfulness
    from langchain_openai import ChatOpenAI, OpenAIEmbeddings

    dataset = Dataset.from_pandas(df)

    judge_llm = ChatOpenAI(
        model=JUDGE_MODEL, temperature=0,
        openai_api_key=JUDGE_API_KEY,
        openai_api_base=JUDGE_BASE_URL,
    )
    # DeepSeek 做推理裁判，SiliconFlow 做向量（DeepSeek 无 embedding）
    embedding_key = os.getenv("SILICONFLOW_API_KEY", JUDGE_API_KEY)
    embedding_base = os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1")
    judge_embeddings = OpenAIEmbeddings(
        model="BAAI/bge-m3",
        openai_api_key=embedding_key,
        openai_api_base=embedding_base,
    )

    print("RAGAS 评估中...")
    result = evaluate(
        dataset=dataset,
        metrics=[context_precision, context_recall, faithfulness],
        llm=judge_llm,
        embeddings=judge_embeddings,
    )

    print("\n" + "=" * 60)
    print("         RAGAS 评估报告")
    print("=" * 60)
    print(result)
    print("=" * 60)

    try:
        df_result = result.to_pandas()
        df_result.to_csv(REPORT_PATH, index=False, encoding="utf-8")
        print(f"报告已保存: {REPORT_PATH}")
    except Exception as e:
        print(f"保存失败: {e}")


if __name__ == "__main__":
    main()
