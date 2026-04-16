"""
工具依赖图谱服务

提供工具依赖关系管理、依赖发现和执行规划功能

功能：
1. 工具依赖关系存储（使用 Neo4j）
2. 基于调用历史的自动依赖发现
3. LLM 分析工具依赖
4. 拓扑排序执行规划
"""

import json
import logging
from typing import Dict, List, Optional, Set, Any, Tuple
from collections import defaultdict, Counter
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class ToolDependency:
    """工具依赖"""
    tool_name: str
    depends_on: List[str]
    confidence: float = 1.0
    reason: str = ""
    discovered_at: Optional[datetime] = None
    usage_count: int = 0


@dataclass
class ExecutionPlan:
    """执行计划"""
    tools: List[str]
    execution_order: List[str]
    parallel_groups: List[List[str]]
    estimated_cost: float = 0.0
    total_tools: int = 0


class ToolDependencyDiscovery:
    """
    从工具调用历史中自动发现依赖关系

    依赖发现策略：
    1. 频繁共现：经常一起调用的工具
    2. 调用顺序：总是 A 在 B 之前调用
    3. 输入输出匹配：A 的输出是 B 的输入
    """

    def __init__(self, min_cooccurrence: int = 2, min_sequence_count: int = 3):
        self.min_cooccurrence = min_cooccurrence
        self.min_sequence_count = min_sequence_count

    def discover_from_history(
        self,
        call_sequences: List[List[str]],
        tool_schemas: Optional[Dict[str, Dict]] = None
    ) -> Dict[str, ToolDependency]:
        """
        从调用序列中发现依赖关系

        Args:
            call_sequences: 工具调用序列列表
            tool_schemas: 工具的输入输出模式

        Returns:
            工具依赖关系字典
        """
        if not call_sequences:
            return {}

        co_occurrence = defaultdict(Counter)
        sequence_patterns = Counter()
        total_sequences = len(call_sequences)

        for sequence in call_sequences:
            if not sequence:
                continue

            tools_in_sequence = set(sequence)

            for i, tool_a in enumerate(sequence):
                for tool_b in sequence[i+1:]:
                    co_occurrence[tool_a][tool_b] += 1

            sorted_sequence = tuple(sorted(sequence))
            sequence_patterns[sorted_sequence] += 1

        directed_dependencies: Dict[str, List[Tuple[str, int]]] = defaultdict(list)

        for tool_a, related in co_occurrence.items():
            for tool_b, count in related.items():
                if count >= self.min_cooccurrence:
                    confidence = min(1.0, count / self.min_sequence_count)
                    directed_dependencies[tool_a].append((tool_b, count))

        dependencies = {}
        for tool_name, deps in directed_dependencies.items():
            if deps:
                sorted_deps = sorted(deps, key=lambda x: x[1], reverse=True)
                dependency_list = [dep[0] for dep in sorted_deps]

                total_count = sum(count for _, count in deps)
                avg_confidence = min(1.0, total_count / (self.min_sequence_count * len(deps)))

                dependencies[tool_name] = ToolDependency(
                    tool_name=tool_name,
                    depends_on=dependency_list,
                    confidence=avg_confidence,
                    reason=f"从 {total_count} 次共现序列中发现",
                    discovered_at=datetime.now(),
                    usage_count=total_count
                )

        if tool_schemas:
            io_dependencies = self._match_input_output(tool_schemas)
            for tool_name, dep_list in io_dependencies.items():
                if tool_name not in dependencies:
                    dependencies[tool_name] = ToolDependency(
                        tool_name=tool_name,
                        depends_on=dep_list,
                        confidence=0.9,
                        reason="基于输入输出模式匹配",
                        discovered_at=datetime.now()
                    )
                else:
                    for dep in dep_list:
                        if dep not in dependencies[tool_name].depends_on:
                            dependencies[tool_name].depends_on.append(dep)

        return dependencies

    def _match_input_output(self, tool_schemas: Dict[str, Dict]) -> Dict[str, List[str]]:
        """基于输入输出模式匹配依赖"""
        dependencies = {}

        tool_outputs: Dict[str, Set[str]] = {}
        tool_inputs: Dict[str, Set[str]] = {}

        for tool_name, schema in tool_schemas.items():
            outputs = set()
            inputs = set()

            if "output_schema" in schema:
                for field_name in schema["output_schema"].get("properties", {}).keys():
                    outputs.add(field_name.lower())

            if "input_schema" in schema:
                for field_name in schema["input_schema"].get("properties", {}).keys():
                    inputs.add(field_name.lower())

            tool_outputs[tool_name] = outputs
            tool_inputs[tool_name] = inputs

        for consumer_tool, consumer_inputs in tool_inputs.items():
            producers = []
            for producer_tool, producer_outputs in tool_outputs.items():
                if producer_tool == consumer_tool:
                    continue

                if consumer_inputs & producer_outputs:
                    producers.append(producer_tool)

            if producers:
                dependencies[consumer_tool] = producers

        return dependencies


class LLMDependencyAnalyzer:
    """
    使用 LLM 分析工具之间的依赖关系

    分析策略：
    1. 分析每个工具的输入输出
    2. 匹配输出 → 输入的兼容性
    3. 生成依赖关系图
    """

    def __init__(self, llm_service=None):
        self.llm_service = llm_service

    async def analyze_dependencies(
        self,
        tools: List[Dict[str, Any]]
    ) -> Dict[str, ToolDependency]:
        """
        使用 LLM 分析工具依赖

        Args:
            tools: 工具定义列表

        Returns:
            依赖关系图
        """
        if not self.llm_service:
            try:
                from app.services.llm_service import llm_service as _llm
                self.llm_service = _llm
            except ImportError:
                logger.warning("无法导入 LLM 服务，返回空依赖图")
                return {}

        tools_desc = "\n".join([
            f"- {t.get('name', 'unknown')}: {t.get('description', '')}\n"
            f"  输入: {json.dumps(t.get('input_schema', {}), ensure_ascii=False)}\n"
            f"  输出: {json.dumps(t.get('output_schema', {}), ensure_ascii=False)}"
            for t in tools
        ])

        prompt = f"""分析以下工具之间的依赖关系。

工具 A 依赖工具 B 的条件：
1. A 的输入需要 B 的输出作为数据源
2. A 完成后，B 才能执行（顺序依赖）
3. A 和 B 需要共享上下文（数据依赖）

工具列表：
{tools_desc}

请分析并返回 JSON 格式的依赖关系：
{{
  "dependencies": {{
    "tool_a": ["tool_b", "tool_c"],
    "tool_d": ["tool_b"]
  }},
  "reasoning": "简要说明分析逻辑"
}}

仅返回 JSON，不要其他内容。"""

        try:
            result = await self.llm_service.generate(prompt)

            parsed = json.loads(result)
            dependencies = {}

            for tool_name, deps in parsed.get("dependencies", {}).items():
                if isinstance(deps, list):
                    dependencies[tool_name] = ToolDependency(
                        tool_name=tool_name,
                        depends_on=deps,
                        confidence=0.85,
                        reason=parsed.get("reasoning", "LLM 分析"),
                        discovered_at=datetime.now()
                    )

            return dependencies

        except json.JSONDecodeError as e:
            logger.error(f"LLM 返回格式错误: {e}")
            return {}
        except (ValueError, KeyError) as e:
            logger.error(f"LLM 分析数据错误: {e}")
            return {}
        except (OSError, IOError) as e:
            logger.error(f"LLM 分析IO错误: {e}")
            return {}
        except Exception as e:
            logger.error(f"LLM 分析失败: {e}")
            return {}


class ToolDependencyGraph:
    """
    工具依赖图谱（集成 Neo4j）

    特点：
    1. 使用现有 Neo4j 存储
    2. 自动学习 + 手动配置
    3. 支持实时更新
    4. 提供拓扑排序执行
    """

    def __init__(self, neo4j_manager=None):
        self.neo4j = neo4j_manager
        self.discovery = ToolDependencyDiscovery()
        self.analyzer = LLMDependencyAnalyzer()
        self._local_cache: Dict[str, ToolDependency] = {}
        self._initialized = False

    async def initialize(self):
        """初始化，从 Neo4j 加载已有依赖"""
        if self._initialized:
            return

        if not self.neo4j:
            try:
                from app.knowledge_graph.neo4j_manager import Neo4jManager
                self.neo4j = Neo4jManager()
            except (ValueError, KeyError) as e:
                logger.warning(f"无法初始化 Neo4j 连接数据错误: {e}")
                self.neo4j = None
            except (OSError, IOError) as e:
                logger.warning(f"无法初始化 Neo4j 连接IO错误: {e}")
                self.neo4j = None
            except Exception as e:
                logger.warning(f"无法初始化 Neo4j 连接: {e}")
                self.neo4j = None
                return

        self._load_from_neo4j()
        self._initialized = True

    def _load_from_neo4j(self):
        """从 Neo4j 加载依赖关系"""
        if not self.neo4j or not self.neo4j.driver:
            return

        try:
            with self.neo4j.driver.session(database="neo4j") as session:
                result = session.run("""
                    MATCH (t:Tool)-[r:DEPENDS_ON]->(d:Tool)
                    RETURN t.name as tool, collect(d.name) as dependencies
                """)

                for record in result:
                    tool_name = record["tool"]
                    dependencies = record["dependencies"]
                    self._local_cache[tool_name] = ToolDependency(
                        tool_name=tool_name,
                        depends_on=dependencies,
                        confidence=1.0,
                        discovered_at=datetime.now()
                    )

            logger.info(f"从 Neo4j 加载了 {len(self._local_cache)} 个工具依赖")

        except (ValueError, KeyError) as e:
            logger.warning(f"从 Neo4j 加载依赖数据错误: {e}")
        except (OSError, IOError) as e:
            logger.warning(f"从 Neo4j 加载依赖IO错误: {e}")
        except Exception as e:
            logger.warning(f"从 Neo4j 加载依赖失败: {e}")

    async def add_dependency(
        self,
        tool_name: str,
        depends_on: List[str],
        confidence: float = 1.0,
        reason: str = ""
    ):
        """
        添加工具依赖关系

        Args:
            tool_name: 工具名称
            depends_on: 依赖的工具列表
            confidence: 置信度
            reason: 依赖原因
        """
        dependency = ToolDependency(
            tool_name=tool_name,
            depends_on=depends_on,
            confidence=confidence,
            reason=reason,
            discovered_at=datetime.now()
        )

        self._local_cache[tool_name] = dependency

        if self.neo4j and self.neo4j.driver:
            try:
                self._save_to_neo4j(dependency)
            except (ValueError, KeyError) as e:
                logger.error(f"保存依赖到 Neo4j 数据错误: {e}")
            except (OSError, IOError) as e:
                logger.error(f"保存依赖到 Neo4j IO错误: {e}")
            except Exception as e:
                logger.error(f"保存依赖到 Neo4j 失败: {e}")

    def _save_to_neo4j(self, dependency: ToolDependency):
        """保存依赖关系到 Neo4j"""
        if not self.neo4j or not self.neo4j.driver:
            return

        with self.neo4j.driver.session(database="neo4j") as session:
            for dep_tool in dependency.depends_on:
                session.run("""
                    MERGE (t:Tool {name: $tool_name})
                    MERGE (d:Tool {name: $dep_tool})
                    MERGE (t)-[r:DEPENDS_ON]->(d)
                    SET r.confidence = $confidence,
                        r.reason = $reason,
                        r.created_at = datetime()
                """,
                    tool_name=dependency.tool_name,
                    dep_tool=dep_tool,
                    confidence=dependency.confidence,
                    reason=dependency.reason
                )

    async def learn_from_history(
        self,
        call_sequences: List[List[str]],
        tool_schemas: Optional[Dict[str, Dict]] = None
    ):
        """
        从调用历史学习依赖关系

        Args:
            call_sequences: 调用序列
            tool_schemas: 工具模式
        """
        discovered = self.discovery.discover_from_history(call_sequences, tool_schemas)

        for tool_name, dependency in discovered.items():
            existing = self._local_cache.get(tool_name)

            if not existing or dependency.confidence > existing.confidence:
                await self.add_dependency(
                    tool_name=dependency.tool_name,
                    depends_on=dependency.depends_on,
                    confidence=dependency.confidence,
                    reason=dependency.reason
                )

        logger.info(f"从历史学习发现 {len(discovered)} 个新依赖")

    async def analyze_with_llm(self, tools: List[Dict[str, Any]]):
        """使用 LLM 分析工具依赖"""
        analyzed = await self.analyzer.analyze_dependencies(tools)

        for tool_name, dependency in analyzed.items():
            existing = self._local_cache.get(tool_name)

            if not existing or dependency.confidence > existing.confidence:
                await self.add_dependency(
                    tool_name=dependency.tool_name,
                    depends_on=dependency.depends_on,
                    confidence=dependency.confidence,
                    reason=dependency.reason
                )

        logger.info(f"LLM 分析发现 {len(analyzed)} 个依赖")

    def get_dependencies(self, tool_name: str) -> Optional[ToolDependency]:
        """获取工具的依赖"""
        return self._local_cache.get(tool_name)

    def get_all_dependencies(self) -> Dict[str, List[str]]:
        """获取所有依赖关系"""
        return {
            name: dep.depends_on
            for name, dep in self._local_cache.items()
        }

    def suggest_execution_order(self, required_tools: List[str]) -> List[str]:
        """
        建议工具执行顺序（拓扑排序）

        Args:
            required_tools: 需要执行的工具列表

        Returns:
            排序后的执行顺序
        """
        all_deps = self.get_all_dependencies()

        required_set = set(required_tools)
        dependencies = {t: all_deps.get(t, []) for t in required_tools}

        return self._topological_sort(dependencies, list(required_set))

    def _topological_sort(
        self,
        dependencies: Dict[str, List[str]],
        nodes: List[str]
    ) -> List[str]:
        """拓扑排序（Kahn 算法）"""
        in_degree = {n: 0 for n in nodes}
        adj_list = {n: [] for n in nodes}

        for node, deps in dependencies.items():
            for dep in deps:
                if dep in nodes:
                    adj_list[dep].append(node)
                    in_degree[node] += 1

        queue = [n for n in nodes if in_degree[n] == 0]
        result = []

        while queue:
            node = queue.pop(0)
            result.append(node)

            for neighbor in adj_list[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        remaining = [n for n in nodes if n not in result]
        result.extend(remaining)

        return result

    def plan_execution(
        self,
        required_tools: List[str],
        max_parallel: int = 3
    ) -> ExecutionPlan:
        """
        规划工具执行

        Args:
            required_tools: 需要执行的工具列表
            max_parallel: 最大并行数

        Returns:
            执行计划
        """
        all_deps = self.get_all_dependencies()
        dependencies = {t: all_deps.get(t, []) for t in required_tools}

        execution_order = self._topological_sort(dependencies, required_tools)

        parallel_groups = []
        executed: Set[str] = set()

        remaining = list(required_tools)
        while remaining:
            ready = [
                tool for tool in remaining
                if all(dep in executed for dep in dependencies.get(tool, []))
            ]

            if not ready:
                ready = [remaining[0]]

            batch = ready[:max_parallel]
            parallel_groups.append(batch)

            for tool in batch:
                executed.add(tool)
                remaining.remove(tool)

        return ExecutionPlan(
            tools=required_tools,
            execution_order=execution_order,
            parallel_groups=parallel_groups,
            total_tools=len(required_tools)
        )

    def get_tool_health_score(self, tool_name: str) -> float:
        """
        获取工具健康分数

        基于依赖深度和依赖数量计算

        Args:
            tool_name: 工具名称

        Returns:
            健康分数 0.0 - 1.0
        """
        deps = self._local_cache.get(tool_name)
        if not deps:
            return 1.0

        depth_score = 1.0 / (1 + len(deps.depends_on))
        confidence_score = deps.confidence
        recency_score = 1.0

        if deps.discovered_at:
            days_since = (datetime.now() - deps.discovered_at).days
            recency_score = max(0.5, 1.0 - days_since / 30)

        return (depth_score * 0.3 + confidence_score * 0.5 + recency_score * 0.2)


tool_dependency_graph = ToolDependencyGraph()
