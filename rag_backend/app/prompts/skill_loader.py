"""
结构化 Skill 加载与导入工具。

Skill 是可复用的提示词操作说明，用来描述智能体应该如何使用一个或多个工具。
Skill 本身不执行代码，实际执行仍然由 Tool/MCP 层负责。
"""

from __future__ import annotations

import importlib.util
import inspect
import logging
import shutil
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional

import yaml

logger = logging.getLogger(__name__)

PROMPTS_ROOT = Path(__file__).parent
SKILLS_DIR = PROMPTS_ROOT / "skills"

ALLOWED_SKILL_FILES = {"skill.yaml", "instructions.md", "README.md", "tools.py"}


@dataclass(frozen=True)
class SkillDefinition:
    name: str
    display_name: str
    description: str = ""
    version: str = "1.0.0"
    domains: List[str] = field(default_factory=list)
    triggers: Dict[str, Any] = field(default_factory=dict)
    tools: List[str] = field(default_factory=list)
    allowed_agents: List[str] = field(default_factory=list)
    required_tools: List[str] = field(default_factory=list)
    optional_tools: List[str] = field(default_factory=list)
    priority: int = 50
    risk_level: str = "low"
    source: str = "local"
    path: Optional[Path] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any], path: Optional[Path] = None, source: str = "local") -> "SkillDefinition":
        name = str(data.get("name") or (path.name if path else "")).strip()
        if not name:
            raise ValueError("Skill 名称不能为空")

        return cls(
            name=name,
            display_name=str(data.get("display_name") or name),
            description=str(data.get("description") or ""),
            version=str(data.get("version") or "1.0.0"),
            domains=[str(item) for item in data.get("domains", []) or []],
            triggers=data.get("triggers", {}) or {},
            tools=[str(item) for item in data.get("tools", []) or []],
            allowed_agents=[str(item) for item in data.get("allowed_agents", []) or []],
            required_tools=[str(item) for item in data.get("required_tools", []) or []],
            optional_tools=[str(item) for item in data.get("optional_tools", []) or []],
            priority=int(data.get("priority", 50) or 50),
            risk_level=str(data.get("risk_level") or "low"),
            source=str(data.get("source") or source),
            path=path,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "version": self.version,
            "domains": self.domains,
            "triggers": self.triggers,
            "tools": self.tools,
            "allowed_agents": self.allowed_agents,
            "required_tools": self.required_tools,
            "optional_tools": self.optional_tools,
            "priority": self.priority,
            "risk_level": self.risk_level,
            "source": self.source,
        }


@dataclass(frozen=True)
class SkillToolDefinition:
    name: str
    description: str
    func: Callable[..., Any]
    skill_name: str
    parameters: Dict[str, Dict[str, Any]] = field(default_factory=dict)


class SkillLoader:
    """从 prompts/skills 目录加载、渲染和选择 Skill。"""

    def __init__(self, skills_dir: Optional[Path] = None):
        self.skills_dir = Path(skills_dir) if skills_dir else SKILLS_DIR
        self._definition_cache: Dict[str, SkillDefinition] = {}
        self._instruction_cache: Dict[str, str] = {}

    def list_skills(self) -> List[str]:
        return [skill.name for skill in self.get_all_skills()]

    def get_all_skills(self) -> List[SkillDefinition]:
        if not self.skills_dir.exists():
            return []

        skills: Dict[str, SkillDefinition] = {}

        for item in self.skills_dir.iterdir():
            if item.is_dir() and (item / "skill.yaml").exists():
                try:
                    skill = self.load_skill(item.name)
                    if skill:
                        skills[skill.name] = skill
                except Exception as exc:
                    logger.warning("加载 Skill 目录失败 %s: %s", item, exc)

        for item in self.skills_dir.glob("*.txt"):
            name = item.stem
            if name not in skills:
                skills[name] = self._load_legacy_skill(item)

        return sorted(skills.values(), key=lambda skill: skill.name)

    def load_skill(self, name: str) -> Optional[SkillDefinition]:
        safe_name = self._safe_name(name)
        if safe_name in self._definition_cache:
            return self._definition_cache[safe_name]

        skill_dir = self.skills_dir / safe_name
        yaml_file = skill_dir / "skill.yaml"

        if yaml_file.exists():
            with open(yaml_file, "r", encoding="utf-8") as file:
                data = yaml.safe_load(file) or {}
            skill = SkillDefinition.from_dict(data, path=skill_dir)
            self._definition_cache[skill.name] = skill
            return skill

        legacy_file = self.skills_dir / f"{safe_name}.txt"
        if legacy_file.exists():
            skill = self._load_legacy_skill(legacy_file)
            self._definition_cache[skill.name] = skill
            return skill

        return None

    def load_instructions(self, name: str) -> Optional[str]:
        safe_name = self._safe_name(name)
        if safe_name in self._instruction_cache:
            return self._instruction_cache[safe_name]

        skill_dir = self.skills_dir / safe_name
        instruction_file = skill_dir / "instructions.md"
        legacy_file = self.skills_dir / f"{safe_name}.txt"

        content = None
        if instruction_file.exists():
            content = instruction_file.read_text(encoding="utf-8")
        elif legacy_file.exists():
            content = legacy_file.read_text(encoding="utf-8")

        if content is not None:
            self._instruction_cache[safe_name] = content

        return content

    def load_tool_definitions(self, skill_names: Optional[Iterable[str]] = None) -> List[SkillToolDefinition]:
        """加载 Skill 目录中显式声明的本地工具实现。"""
        skills = [self.load_skill(name) for name in skill_names] if skill_names else self.get_all_skills()
        definitions: List[SkillToolDefinition] = []

        for skill in skills:
            if not skill or not skill.path:
                continue

            tools_file = skill.path / "tools.py"
            if not tools_file.exists():
                continue

            module = self._load_tools_module(skill.name, tools_file)
            raw_tools = getattr(module, "SKILL_TOOLS", [])
            if not isinstance(raw_tools, list):
                raise ValueError(f"Skill {skill.name} 的 SKILL_TOOLS 必须是列表")

            for raw_tool in raw_tools:
                definitions.append(self._parse_tool_definition(skill.name, raw_tool))

        return definitions

    def register_skill_tools(self, tool_manager: Any, skill_names: Optional[Iterable[str]] = None) -> List[str]:
        """将 Skill 中的本地工具实现注册到 ToolManager。"""
        registered = []
        for tool in self.load_tool_definitions(skill_names):
            if tool.parameters:
                tool_manager.tools[tool.name] = {
                    "func": tool.func,
                    "description": tool.description,
                    "parameters": tool.parameters,
                    "args_schema": None,
                    "type": "skill_tool",
                    "skill_name": tool.skill_name,
                }
            else:
                tool_manager.register_function(
                    name=tool.name,
                    func=tool.func,
                    description=tool.description,
                )
                tool_manager.tools[tool.name]["type"] = "skill_tool"
                tool_manager.tools[tool.name]["skill_name"] = tool.skill_name

            registered.append(tool.name)

        return registered

    def select_skills(
        self,
        user_input: str = "",
        tools: Optional[Iterable[Any]] = None,
        explicit_skills: Optional[Iterable[str]] = None,
        active_skills: Optional[Iterable[str]] = None,
        agent_name: Optional[str] = None,
        intent: Optional[str] = None,
        file_type: Optional[str] = None,
        skill_strategy: str = "refresh",
        limit: int = 5,
    ) -> List[SkillDefinition]:
        selected: Dict[str, SkillDefinition] = {}
        tool_names = self._extract_tool_names(tools or [])
        normalized_agent = self._normalize_agent_name(agent_name)

        for name in explicit_skills or []:
            skill = self.load_skill(str(name))
            if skill and self._is_skill_allowed(skill, normalized_agent, tool_names, explicit=True):
                selected[skill.name] = skill

        if skill_strategy == "merge":
            for name in active_skills or []:
                skill = self.load_skill(str(name))
                if skill and self._is_skill_allowed(skill, normalized_agent, tool_names, explicit=True):
                    selected.setdefault(skill.name, skill)

        user_text = (user_input or "").lower()
        normalized_intent = self._normalize_trigger_value(intent)
        normalized_file_type = self._normalize_trigger_value(file_type)

        scored: List[tuple[float, int, SkillDefinition]] = []
        for skill in self.get_all_skills():
            if skill.name in selected:
                continue
            if not self._is_skill_allowed(skill, normalized_agent, tool_names):
                continue

            score = 0.0
            declared_tools = set(skill.tools) | set(skill.optional_tools)
            if tool_names and declared_tools.intersection(tool_names):
                score += 3.0
            if tool_names and set(skill.required_tools).issubset(tool_names) and skill.required_tools:
                score += 2.0
            for keyword in skill.triggers.get("keywords", []) or []:
                if str(keyword).lower() in user_text:
                    score += 2.0
            skill_intents = self._normalize_trigger_values(skill.triggers.get("intents", []))
            if normalized_intent and normalized_intent in skill_intents:
                score += 4.0
            skill_file_types = self._normalize_trigger_values(skill.triggers.get("file_types", []))
            if normalized_file_type and normalized_file_type in skill_file_types:
                score += 3.0
            for domain in skill.domains:
                if domain.lower() in user_text:
                    score += 1.0
            if score > 0:
                scored.append((score, skill.priority, skill))

        for _, _, skill in sorted(scored, key=lambda item: (-item[0], -item[1], item[2].name)):
            selected.setdefault(skill.name, skill)
            if len(selected) >= limit:
                break

        return list(selected.values())[:limit]

    def render_skills(self, skills: Iterable[SkillDefinition]) -> str:
        sections = []
        for skill in skills:
            instructions = self.load_instructions(skill.name)
            if not instructions:
                continue
            sections.append(
                "\n".join(
                    [
                        f"## 技能：{skill.display_name}（{skill.name}）",
                        f"- 版本：{skill.version}",
                        f"- 风险等级：{self._risk_level_label(skill.risk_level)}",
                        f"- 工具：{', '.join(skill.tools) if skill.tools else '未声明'}",
                        "",
                        instructions.strip(),
                    ]
                )
            )

        if not sections:
            return ""

        return "# 可用技能\n\n" + "\n\n".join(sections)

    def render_selected_skills(
        self,
        user_input: str = "",
        tools: Optional[Iterable[Any]] = None,
        explicit_skills: Optional[Iterable[str]] = None,
        active_skills: Optional[Iterable[str]] = None,
        agent_name: Optional[str] = None,
        intent: Optional[str] = None,
        file_type: Optional[str] = None,
        skill_strategy: str = "refresh",
        limit: int = 5,
    ) -> str:
        return self.render_skills(
            self.select_skills(
                user_input=user_input,
                tools=tools,
                explicit_skills=explicit_skills,
                active_skills=active_skills,
                agent_name=agent_name,
                intent=intent,
                file_type=file_type,
                skill_strategy=skill_strategy,
                limit=limit,
            )
        )

    def clear_cache(self) -> None:
        self._definition_cache.clear()
        self._instruction_cache.clear()

    def _load_legacy_skill(self, path: Path) -> SkillDefinition:
        name = path.stem
        return SkillDefinition(
            name=name,
            display_name=name.replace("_", " ").title(),
            description=f"从旧版提示词文件 {path.name} 加载的 Skill",
            tools=[name],
            optional_tools=[name],
            triggers={"keywords": [name.replace("_", " ")]},
            source="legacy_txt",
            path=path,
        )

    def _load_tools_module(self, skill_name: str, tools_file: Path) -> Any:
        module_name = f"app.prompts.skills.{skill_name}.tools"
        spec = importlib.util.spec_from_file_location(module_name, tools_file)
        if not spec or not spec.loader:
            raise ImportError(f"无法加载 Skill 工具模块：{tools_file}")

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def _parse_tool_definition(self, skill_name: str, raw_tool: Any) -> SkillToolDefinition:
        if not isinstance(raw_tool, dict):
            raise ValueError(f"Skill {skill_name} 的工具声明必须是字典")

        func = raw_tool.get("func")
        if not callable(func):
            raise ValueError(f"Skill {skill_name} 的工具 {raw_tool.get('name')} 缺少可调用函数")

        name = str(raw_tool.get("name") or getattr(func, "__name__", "")).strip()
        description = str(raw_tool.get("description") or inspect.getdoc(func) or "").strip()
        if not name or not description:
            raise ValueError(f"Skill {skill_name} 的工具必须声明名称和中文描述")

        parameters = raw_tool.get("parameters") or self._infer_parameters(func)
        return SkillToolDefinition(
            name=name,
            description=description,
            func=func,
            skill_name=skill_name,
            parameters=parameters,
        )

    def _infer_parameters(self, func: Callable[..., Any]) -> Dict[str, Dict[str, Any]]:
        parameters = {}
        signature = inspect.signature(func)
        for param_name, param in signature.parameters.items():
            parameters[param_name] = {
                "type": self._annotation_to_schema_type(param.annotation),
                "description": f"{param_name} 参数",
                "required": param.default == inspect.Parameter.empty,
            }
        return parameters

    def _annotation_to_schema_type(self, annotation: Any) -> str:
        if annotation is int:
            return "integer"
        if annotation is float:
            return "number"
        if annotation is bool:
            return "boolean"
        return "string"

    def _is_skill_allowed(
        self,
        skill: SkillDefinition,
        agent_name: Optional[str],
        tool_names: set[str],
        explicit: bool = False,
    ) -> bool:
        allowed_agents = {self._normalize_agent_name(item) for item in skill.allowed_agents}
        if skill.allowed_agents and agent_name and agent_name not in allowed_agents:
            return False

        required_tools = set(skill.required_tools)
        if required_tools and tool_names and not required_tools.issubset(tool_names):
            return False
        if required_tools and not tool_names and not explicit:
            return False

        return True

    def _extract_tool_names(self, tools: Iterable[Any]) -> set[str]:
        names = set()
        for tool in tools:
            if isinstance(tool, str):
                names.add(tool)
            elif isinstance(tool, dict) and tool.get("name"):
                names.add(str(tool["name"]))
            elif hasattr(tool, "name"):
                names.add(str(tool.name))
        return names

    def _safe_name(self, name: str) -> str:
        safe_name = Path(str(name)).name
        if safe_name in {"", ".", ".."} or safe_name != str(name).replace("\\", "/").split("/")[-1]:
            raise ValueError(f"非法 Skill 名称：{name}")
        return safe_name

    def _normalize_agent_name(self, agent_name: Optional[str]) -> Optional[str]:
        if not agent_name:
            return None
        return str(agent_name).lower().replace("-", "_")

    def _normalize_trigger_value(self, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return str(value).strip().lower().replace("-", "_")

    def _normalize_trigger_values(self, values: Iterable[Any]) -> set[str]:
        return {normalized for item in values if (normalized := self._normalize_trigger_value(str(item)))}

    def _risk_level_label(self, risk_level: str) -> str:
        labels = {
            "low": "低",
            "medium": "中",
            "high": "高",
        }
        return labels.get(str(risk_level).lower(), str(risk_level))


class SkillLibraryImporter:
    """校验结构后，从本地目录或 zip 包导入 Skill 库。"""

    def __init__(self, skills_dir: Optional[Path] = None):
        self.skills_dir = Path(skills_dir) if skills_dir else SKILLS_DIR

    def import_from_directory(self, source_dir: Path, overwrite: bool = False) -> List[str]:
        source_dir = Path(source_dir).resolve()
        if not source_dir.exists() or not source_dir.is_dir():
            raise FileNotFoundError(f"未找到 Skill 库目录：{source_dir}")

        imported = []
        for skill_dir in self._discover_skill_dirs(source_dir):
            imported.append(self._copy_skill_dir(skill_dir, overwrite=overwrite))
        return imported

    def import_from_zip(self, zip_path: Path, overwrite: bool = False) -> List[str]:
        zip_path = Path(zip_path).resolve()
        if not zip_path.exists():
            raise FileNotFoundError(f"未找到 Skill 库 zip 包：{zip_path}")

        with zipfile.ZipFile(zip_path) as archive:
            self._validate_zip_members(archive)

            self.skills_dir.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(dir=self.skills_dir.parent) as temp_dir:
                temp_path = Path(temp_dir)
                archive.extractall(temp_path)
                return self.import_from_directory(temp_path, overwrite=overwrite)

    def _discover_skill_dirs(self, root: Path) -> List[Path]:
        candidates = []
        if (root / "skill.yaml").exists():
            candidates.append(root)
        candidates.extend(path.parent for path in root.rglob("skill.yaml") if path.parent != root)
        return sorted(set(candidates))

    def _copy_skill_dir(self, source_dir: Path, overwrite: bool) -> str:
        data = yaml.safe_load((source_dir / "skill.yaml").read_text(encoding="utf-8")) or {}
        skill = SkillDefinition.from_dict(data, path=source_dir, source="imported")
        target_dir = self.skills_dir / skill.name

        self._validate_skill_dir(source_dir)
        if target_dir.exists():
            if not overwrite:
                raise FileExistsError(f"Skill already exists: {skill.name}")
            shutil.rmtree(target_dir)

        target_dir.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source_dir, target_dir, ignore=self._ignore_unsupported_files)
        return skill.name

    def _validate_skill_dir(self, skill_dir: Path) -> None:
        files = {path.name for path in skill_dir.iterdir() if path.is_file()}
        if "skill.yaml" not in files or "instructions.md" not in files:
            raise ValueError(f"Skill 必须包含 skill.yaml 和 instructions.md：{skill_dir}")
        unsupported = files - ALLOWED_SKILL_FILES
        if unsupported:
            raise ValueError(f"Skill {skill_dir.name} 包含不支持的文件：{sorted(unsupported)}")

    def _validate_zip_members(self, archive: zipfile.ZipFile) -> None:
        for member in archive.infolist():
            member_path = Path(member.filename)
            if member_path.is_absolute() or ".." in member_path.parts:
                raise ValueError(f"Skill 压缩包包含不安全路径：{member.filename}")

    def _ignore_unsupported_files(self, directory: str, names: List[str]) -> List[str]:
        ignored = []
        for name in names:
            path = Path(directory) / name
            if path.is_file() and name not in ALLOWED_SKILL_FILES:
                ignored.append(name)
        return ignored


_skill_loader: Optional[SkillLoader] = None


def get_skill_loader() -> SkillLoader:
    global _skill_loader
    if _skill_loader is None:
        _skill_loader = SkillLoader()
    return _skill_loader
