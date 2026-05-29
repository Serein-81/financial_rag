"""
工具自动扫描器

扫描指定目录，动态发现所有带 @auto_register_tool 装饰器的工具。
"""

import os
import importlib
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
import sys

logger = logging.getLogger(__name__)


class ToolScanner:
    """
    工具自动扫描器

    扫描指定目录下的所有 Python 文件，发现带有 @auto_register_tool 装饰器的工具。
    """

    def __init__(self, scan_dirs: Optional[List[str]] = None):
        """
        初始化扫描器

        Args:
            scan_dirs: 要扫描的目录列表，相对于项目根目录。
                      默认扫描 ["app/tools", "app/skills"]
        """
        self.scan_dirs = scan_dirs or [
            "app/tools",
            "app/skills"
        ]

    def scan(self) -> List[Dict[str, Any]]:
        """
        扫描并发现所有工具

        Returns:
            工具元数据列表
        """
        discovered_tools = []
        processed_modules = set()

        logger.info(f"🔍 开始扫描工具目录: {self.scan_dirs}")

        for scan_dir in self.scan_dirs:
            tools = self._scan_directory(scan_dir, processed_modules)
            discovered_tools.extend(tools)

        logger.info(f"✅ 扫描完成，共发现 {len(discovered_tools)} 个工具")
        return discovered_tools

    def _scan_directory(
        self,
        directory: str,
        processed_modules: set
    ) -> List[Dict[str, Any]]:
        """
        扫描单个目录

        Args:
            directory: 目录路径
            processed_modules: 已处理的模块集合（避免重复）

        Returns:
            发现的工具列表
        """
        discovered = []

        # 获取目录的绝对路径
        if os.path.isabs(directory):
            base_path = Path(directory)
        else:
            # 相对于当前工作目录
            base_path = Path.cwd() / directory

        if not base_path.exists():
            logger.warning(f"⚠️  目录不存在: {directory}")
            return discovered

        logger.debug(f"扫描目录: {base_path}")

        # 递归查找所有 .py 文件
        py_files = list(base_path.rglob("*.py"))
        logger.debug(f"找到 {len(py_files)} 个 Python 文件")

        for py_file in py_files:
            # 跳过特殊文件
            if py_file.name.startswith("_") and py_file.name != "__init__.py":
                continue

            # 跳过测试文件
            if "test" in py_file.name.lower():
                continue

            # 构造模块路径
            try:
                relative_path = py_file.relative_to(Path.cwd())
                module_path = str(relative_path).replace(os.sep, ".").replace(".py", "")

                # 跳过已处理的模块
                if module_path in processed_modules:
                    continue

                processed_modules.add(module_path)

                # 动态导入模块
                tools = self._import_and_extract_tools(module_path, py_file)
                discovered.extend(tools)

            except Exception as e:
                logger.debug(f"跳过文件 {py_file}: {e}")
                continue

        return discovered

    def _import_and_extract_tools(
        self,
        module_path: str,
        file_path: Path
    ) -> List[Dict[str, Any]]:
        """
        导入模块并提取工具

        Args:
            module_path: 模块路径（如 app.tools.financial_tools）
            file_path: 文件路径

        Returns:
            提取的工具列表
        """
        tools = []

        try:
            # 动态导入模块
            module = importlib.import_module(module_path)

            # 遍历模块中的所有对象
            for attr_name in dir(module):
                # 跳过私有属性
                if attr_name.startswith("_"):
                    continue

                try:
                    attr = getattr(module, attr_name)

                    # 检查是否有自动注册元数据
                    if hasattr(attr, "_auto_register_metadata"):
                        metadata = attr._auto_register_metadata

                        # 确保是字典类型
                        if isinstance(metadata, dict):
                            tools.append(metadata)
                            logger.debug(
                                f"✅ 发现工具: {metadata.get('name', attr_name)} "
                                f"({file_path.name})"
                            )

                except Exception as e:
                    logger.debug(f"检查属性 {attr_name} 失败: {e}")
                    continue

        except ImportError as e:
            logger.warning(f"导入模块失败 {module_path}: {e}")
        except Exception as e:
            logger.error(f"处理模块失败 {module_path}: {e}")

        return tools

    def scan_single_file(self, file_path: str) -> List[Dict[str, Any]]:
        """
        扫描单个文件

        Args:
            file_path: 文件路径

        Returns:
            发现的工具列表
        """
        py_file = Path(file_path)

        if not py_file.exists():
            logger.error(f"文件不存在: {file_path}")
            return []

        if not py_file.suffix == ".py":
            logger.error(f"不是 Python 文件: {file_path}")
            return []

        # 构造模块路径
        try:
            relative_path = py_file.relative_to(Path.cwd())
            module_path = str(relative_path).replace(os.sep, ".").replace(".py", "")

            return self._import_and_extract_tools(module_path, py_file)

        except Exception as e:
            logger.error(f"扫描文件失败 {file_path}: {e}")
            return []


def scan_tools(directories: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """
    便捷函数：扫描工具

    Args:
        directories: 要扫描的目录列表

    Returns:
        发现的工具列表
    """
    scanner = ToolScanner(scan_dirs=directories)
    return scanner.scan()
