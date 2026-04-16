"""
Agent Card

A2A 协议中的 Agent 能力描述卡片
用于 Agent 发现和能力匹配
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from .models import AgentCapabilities, Security


class AgentSkill(BaseModel):
    """Agent 技能定义"""
    id: str = Field(description="技能唯一标识")
    name: str = Field(description="技能名称")
    description: str = Field(description="技能详细描述")
    inputModes: List[str] = Field(
        default_factory=lambda: ["text"],
        description="支持的输入模式"
    )
    outputModes: List[str] = Field(
        default_factory=lambda: ["text"],
        description="支持的输出模式"
    )
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AgentCard(BaseModel):
    """
    Agent Card - Agent 能力描述卡
    
    遵循 A2A Protocol Agent Card 规范
    用于：
    1. Agent 能力发现
    2. 路由匹配
    3. 协议协商
    """
    name: str = Field(description="Agent 名称")
    description: str = Field(description="Agent 功能描述")
    url: str = Field(description="Agent 服务地址")
    version: str = Field(default="1.0.0", description="Agent 版本")
    provider: Dict[str, str] = Field(
        default_factory=dict,
        description="Agent 提供者信息"
    )
    documentationUrl: Optional[str] = Field(
        None,
        description="Agent 文档地址"
    )
    capabilities: AgentCapabilities = Field(
        default_factory=AgentCapabilities,
        description="Agent 能力"
    )
    skills: List[AgentSkill] = Field(
        default_factory=list,
        description="Agent 支持的技能列表"
    )
    security: Optional[List[Security]] = Field(
        None,
        description="安全认证配置"
    )
    defaultInputModes: List[str] = Field(
        default_factory=lambda: ["text"],
        description="默认输入模式"
    )
    defaultOutputModes: List[str] = Field(
        default_factory=lambda: ["text"],
        description="默认输出模式"
    )
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    def get_skill(self, skill_id: str) -> Optional[AgentSkill]:
        """根据 ID 获取技能"""
        for skill in self.skills:
            if skill.id == skill_id:
                return skill
        return None
    
    def has_skill(self, skill_id: str) -> bool:
        """检查是否拥有某个技能"""
        return self.get_skill(skill_id) is not None
    
    def matches_query(self, query: str) -> float:
        """
        检查 Agent 是否匹配查询
        
        Args:
            query: 用户查询
            
        Returns:
            匹配度分数 0.0 - 1.0
        """
        score = 0.0
        
        if query.lower() in self.description.lower():
            score += 0.5
        
        for skill in self.skills:
            if query.lower() in skill.description.lower():
                score += 0.3 / len(self.skills)
            if query.lower() in skill.name.lower():
                score += 0.2
        
        return min(score, 1.0)


class AgentCardBuilder:
    """Agent Card 构建器"""
    
    def __init__(self, name: str, description: str, url: str):
        self.card = AgentCard(name=name, description=description, url=url)
    
    def with_version(self, version: str) -> "AgentCardBuilder":
        self.card.version = version
        return self
    
    def with_provider(self, organization: str, url: str) -> "AgentCardBuilder":
        self.card.provider = {"organization": organization, "url": url}
        return self
    
    def with_capabilities(
        self,
        streaming: bool = False,
        push_notifications: bool = False,
        state_transition_reports: bool = False,
        artifact_updates: bool = False
    ) -> "AgentCardBuilder":
        self.card.capabilities = AgentCapabilities(
            streaming=streaming,
            pushNotifications=push_notifications,
            stateTransitionReports=state_transition_reports,
            artifactUpdates=artifact_updates
        )
        return self
    
    def with_skill(
        self,
        skill_id: str,
        name: str,
        description: str,
        input_modes: List[str] = None,
        output_modes: List[str] = None
    ) -> "AgentCardBuilder":
        skill = AgentSkill(
            id=skill_id,
            name=name,
            description=description,
            inputModes=input_modes or ["text"],
            outputModes=output_modes or ["text"]
        )
        self.card.skills.append(skill)
        return self
    
    def with_tags(self, tags: List[str]) -> "AgentCardBuilder":
        self.card.tags.extend(tags)
        return self
    
    def build(self) -> AgentCard:
        return self.card
