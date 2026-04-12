# app/agent_framework/tools/langchain_compat.py

"""
LangChain 兼容层

提供与 LangChain 工具的兼容性
"""

from typing import List, Any
from .tool_manager import ToolManager


class LangChainCompatLayer:
    """
    LangChain 兼容层
    
    自动转换和注册 LangChain 工具
    """
    
    def __init__(self, tool_manager: ToolManager):
        """
        初始化兼容层
        
        Args:
            tool_manager: 工具管理器实例
        """
        self.tool_manager = tool_manager
        
        print("LangChain 兼容层初始化完成")
    
    def register_langchain_tools(self, langchain_tools: List[Any]):
        """
        批量注册 LangChain 工具
        
        Args:
            langchain_tools: LangChain 工具列表
        """
        print(f"开始注册 {len(langchain_tools)} 个 LangChain 工具...")
        
        success_count = 0
        for tool in langchain_tools:
            try:
                self.tool_manager.register_langchain_tool(tool)
                success_count += 1
            except Exception as e:
                print(f"[ERROR] 注册工具失败: {getattr(tool, 'name', 'unknown')} - {str(e)}")
        
        print(f"成功注册 {success_count}/{len(langchain_tools)} 个工具")
        
        return success_count
    
    def get_compatible_tools_info(self) -> List[dict]:
        """
        获取兼容工具信息
        
        Returns:
            工具信息列表
        """
        compatible_tools = []
        
        for name, info in self.tool_manager.tools.items():
            if info["type"] == "langchain":
                compatible_tools.append({
                    "name": name,
                    "description": info["description"],
                    "parameters": info["parameters"],
                    "source": "langchain"
                })
        
        return compatible_tools