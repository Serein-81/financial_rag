import os

# 动态获取当前项目的 prompts 目录路径，避免因运行位置不同导致路径报错
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROMPTS_DIR = os.path.join(BASE_DIR, "prompts")

def load_prompt(filename: str) -> str:
    """
    通用提示词加载函数
    """
    filepath = os.path.join(PROMPTS_DIR, filename)
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        # 如果文件不存在，立刻报错提示，避免 AI 裸奔
        raise FileNotFoundError(f"❌ 提示词文件未找到: {filepath}。请检查文件是否存在！")

def load_agent_system_prompt() -> str:
    """
    专门用于加载 Agent 核心系统提示词
    """
    return load_prompt("agent_system.txt")

# 未来如果需要加其他提示词，直接在这里新增方法，例如：
# def load_report_prompt() -> str:
#     return load_prompt("report_prompt.txt")