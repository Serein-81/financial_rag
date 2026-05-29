"""
工具自动注册服务

提供工具的自动发现、注册和管理功能。
"""

import logging
from typing import Dict, List, Optional, Any
from app.agent_framework.tools.scanner import ToolScanner
from app.agent_framework.tools.tool_manager import ToolManager
from app.agent_framework.tools.decorators import get_auto_registered_tools

logger = logging.getLogger(__name__)


class ToolAutoRegister:
    """
    工具自动注册服务

    功能:
    1. 自动扫描和发现工具
    2. 注册工具到 ToolManager
    3. 支持热重载（开发模式）
    4. 提供工具统计和管理
    """

    def __init__(
        self,
        tool_manager: ToolManager,
        scan_dirs: Optional[List[str]] = None
    ):
        """
        初始化自动注册服务

        Args:
            tool_manager: 工具管理器实例
            scan_dirs: 要扫描的目录列表
        """
        self.tool_manager = tool_manager
        self.scanner = ToolScanner(scan_dirs=scan_dirs)
        self.registered_tools: Dict[str, Dict[str, Any]] = {}
        self.registration_errors: List[Dict[str, str]] = []

    def register_all(self) -> Dict[str, Any]:
        """
        扫描并注册所有工具

        Returns:
            注册结果统计
        """
        logger.info("🔧 开始自动注册工具...")

        # 清空错误记录
        self.registration_errors.clear()

        # 方法1: 从全局装饰器列表获取（已导入的）
        tools_from_decorator = get_auto_registered_tools()
        logger.debug(f"从装饰器列表获取 {len(tools_from_decorator)} 个工具")

        # 方法2: 扫描目录发现（未导入的）
        tools_from_scan = self.scanner.scan()
        logger.debug(f"从目录扫描发现 {len(tools_from_scan)} 个工具")

        # 合并并去重（以 name 为 key）
        all_tools_dict = {}
        for tool_meta in tools_from_decorator + tools_from_scan:
            tool_name = tool_meta.get("name")
            if tool_name:
                all_tools_dict[tool_name] = tool_meta

        all_tools = list(all_tools_dict.values())
        logger.info(f"共发现 {len(all_tools)} 个唯一工具")

        # 注册工具
        registered_count = 0
        skipped_count = 0
        error_count = 0

        for tool_meta in all_tools:
            tool_name = tool_meta.get("name", "unknown")

            # 检查是否启用
            if not tool_meta.get("enabled", True):
                logger.debug(f"⏭️  跳过禁用工具: {tool_name}")
                skipped_count += 1
                continue

            # 注册工具
            try:
                self._register_single_tool(tool_meta)
                self.registered_tools[tool_name] = tool_meta
                registered_count += 1
                logger.info(
                    f"✅ 已注册: {tool_name} "
                    f"(分类: {tool_meta.get('category', 'general')})"
                )

            except Exception as e:
                error_count += 1
                error_msg = f"注册工具 {tool_name} 失败: {str(e)}"
                logger.error(f"❌ {error_msg}")
                self.registration_errors.append({
                    "tool_name": tool_name,
                    "error": str(e)
                })

        # 统计结果
        result = {
            "total_discovered": len(all_tools),
            "registered": registered_count,
            "skipped": skipped_count,
            "errors": error_count,
            "error_details": self.registration_errors
        }

        logger.info(
            f"🎉 工具自动注册完成: "
            f"已注册 {registered_count}/{len(all_tools)} 个工具"
        )

        if error_count > 0:
            logger.warning(f"⚠️  {error_count} 个工具注册失败")

        return result

    def _register_single_tool(self, tool_meta: Dict[str, Any]):
        """
        注册单个工具

        Args:
            tool_meta: 工具元数据

        Raises:
            Exception: 注册失败时抛出异常
        """
        tool_name = tool_meta["name"]
        tool_func = tool_meta["func"]
        tool_desc = tool_meta["description"]
        parameters = tool_meta.get("parameters", {})

        # 方式1: 如果工具管理器支持直接注册函数
        if hasattr(self.tool_manager, "register_function"):
            self.tool_manager.register_function(
                name=tool_name,
                func=tool_func,
                description=tool_desc,
                args_schema=parameters
            )
        else:
            # 方式2: 包装为 LangChain Tool 格式
            from langchain.tools import StructuredTool

            # 构造 LangChain Tool
            langchain_tool = StructuredTool.from_function(
                name=tool_name,
                description=tool_desc,
                func=tool_func if not tool_meta["is_async"] else None,
                coroutine=tool_func if tool_meta["is_async"] else None
            )

            # 附加自定义元数据
            langchain_tool._custom_metadata = {
                "category": tool_meta.get("category", "general"),
                "tags": tool_meta.get("tags", []),
                "source_file": tool_meta.get("source_file", "unknown"),
                "timeout": tool_meta.get("timeout", 30)
            }

            # 注册到工具管理器
            self.tool_manager.register_langchain_tool(langchain_tool)

    def reload_tools(self) -> Dict[str, Any]:
        """
        热重载工具（开发模式）

        清空现有工具并重新扫描注册。

        Returns:
            重载结果统计
        """
        logger.warning("🔄 开始热重载工具...")

        # 清空现有工具
        original_count = len(self.tool_manager.tools)
        self.tool_manager.tools.clear()
        self.registered_tools.clear()

        logger.debug(f"已清空 {original_count} 个现有工具")

        # 清除模块缓存（可选，较激进）
        import sys
        import importlib

        modules_to_reload = [
            name for name in list(sys.modules.keys())
            if name.startswith("app.tools") or name.startswith("app.skills")
        ]

        for module_name in modules_to_reload:
            try:
                if module_name in sys.modules:
                    importlib.reload(sys.modules[module_name])
                    logger.debug(f"重载模块: {module_name}")
            except Exception as e:
                logger.warning(f"重载模块 {module_name} 失败: {e}")

        # 重新注册
        result = self.register_all()
        result["reloaded"] = True
        result["previous_count"] = original_count

        logger.info(
            f"✅ 热重载完成: "
            f"{original_count} → {len(self.registered_tools)} 个工具"
        )

        return result

    def get_statistics(self) -> Dict[str, Any]:
        """
        获取工具注册统计

        Returns:
            统计信息字典
        """
        # 按分类统计
        categories = {}
        for tool_meta in self.registered_tools.values():
            category = tool_meta.get("category", "general")
            categories[category] = categories.get(category, 0) + 1

        # 按标签统计
        tags = {}
        for tool_meta in self.registered_tools.values():
            for tag in tool_meta.get("tags", []):
                tags[tag] = tags.get(tag, 0) + 1

        return {
            "total_registered": len(self.registered_tools),
            "total_in_manager": len(self.tool_manager.tools),
            "by_category": categories,
            "by_tags": tags,
            "registration_errors": len(self.registration_errors),
            "tools": [
                {
                    "name": name,
                    "category": meta.get("category"),
                    "tags": meta.get("tags"),
                    "is_async": meta.get("is_async")
                }
                for name, meta in self.registered_tools.items()
            ]
        }

    def get_tool_info(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """
        获取工具详细信息

        Args:
            tool_name: 工具名称

        Returns:
            工具信息，如果不存在返回 None
        """
        return self.registered_tools.get(tool_name)

    def unregister_tool(self, tool_name: str) -> bool:
        """
        注销工具

        Args:
            tool_name: 工具名称

        Returns:
            是否成功注销
        """
        if tool_name in self.registered_tools:
            # 从工具管理器移除
            if tool_name in self.tool_manager.tools:
                del self.tool_manager.tools[tool_name]

            # 从注册表移除
            del self.registered_tools[tool_name]

            logger.info(f"已注销工具: {tool_name}")
            return True

        return False

    def enable_tool(self, tool_name: str) -> bool:
        """
        启用工具

        Args:
            tool_name: 工具名称

        Returns:
            是否成功启用
        """
        tool_meta = self.registered_tools.get(tool_name)
        if tool_meta:
            tool_meta["enabled"] = True
            logger.info(f"已启用工具: {tool_name}")
            return True
        return False

    def disable_tool(self, tool_name: str) -> bool:
        """
        禁用工具

        Args:
            tool_name: 工具名称

        Returns:
            是否成功禁用
        """
        tool_meta = self.registered_tools.get(tool_name)
        if tool_meta:
            tool_meta["enabled"] = False

            # 从工具管理器移除
            if tool_name in self.tool_manager.tools:
                del self.tool_manager.tools[tool_name]

            logger.info(f"已禁用工具: {tool_name}")
            return True
        return False
