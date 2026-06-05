"""
政策通知智能体 (Policy Notification Agent)

真正的 AI Agent，整合政策理解和通知推送功能：
1. 语义理解政策内容和影响
2. 智能匹配企业和政策
3. 生成个性化通知文案
4. 提供智能推荐和风险提示

这是对 PolicyAgent 和 NotificationAgent 的真正整合
"""

from app.utils.json_compat import json
import logging
import re
from typing import Dict, List, Any, Optional, TYPE_CHECKING
from pydantic import BaseModel, Field

from app.agent_framework.llm.base_adapter import BaseLLMAdapter
from app.agent_framework.tools.tool_manager import ToolManager

if TYPE_CHECKING:
    from app.skills.skill_registry import SkillRegistry

logger = logging.getLogger(__name__)


def _extract_json_object(
    text: str,
    expected_keys: Optional[set] = None
) -> Optional[Dict[str, Any]]:
    """
    从 LLM 输出中尽力提取 JSON 对象

    依次处理以下常见情况：
    1. 纯 JSON 输出
    2. Markdown 代码块包裹（```json ... ```）
    3. JSON 前后混有解释文字
    4. 目标对象被包在 thought_process / analysis 等外层结构中

    Args:
        text: LLM 原始输出
        expected_keys: 期望出现的字段名集合，用于在嵌套结构中定位目标对象

    Returns:
        Optional[Dict]: 提取到的 JSON 对象，失败返回 None
    """
    if not text:
        return None

    obj: Optional[Dict[str, Any]] = None

    def _try_load(s: str) -> Optional[Dict[str, Any]]:
        try:
            parsed = json.loads(s)
            return parsed if isinstance(parsed, dict) else None
        except (json.JSONDecodeError, ValueError, TypeError):
            return None

    cleaned = text.strip()
    obj = _try_load(cleaned)

    if obj is None:
        fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL)
        if fence:
            obj = _try_load(fence.group(1))

    if obj is None:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if 0 <= start < end:
            obj = _try_load(cleaned[start:end + 1])

    if obj is None or not expected_keys:
        return obj

    if expected_keys & obj.keys():
        return obj

    # 在嵌套 dict 中寻找包含最多期望字段的子对象（处理 thought_process 包裹）
    best, best_hits = None, 0
    stack: List[Dict[str, Any]] = [obj]
    while stack:
        current = stack.pop()
        for value in current.values():
            if isinstance(value, dict):
                hits = len(expected_keys & value.keys())
                if hits > best_hits:
                    best, best_hits = value, hits
                stack.append(value)

    return best or obj


def _as_str_list(value: Any) -> List[str]:
    """把 LLM 返回的字段安全转换为字符串列表"""
    if isinstance(value, list):
        return [str(v) for v in value if v]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


class MatchScore(BaseModel):
    """匹配评分（LLM增强版）"""
    total_score: float = Field(ge=0.0, le=1.0, description="总分")
    semantic_score: float = Field(ge=0.0, le=1.0, description="语义匹配分")
    industry_score: float = Field(ge=0.0, le=1.0, description="行业匹配分")
    region_score: float = Field(ge=0.0, le=1.0, description="地区匹配分")
    scale_score: float = Field(ge=0.0, le=1.0, description="规模匹配分")
    tax_type_score: float = Field(ge=0.0, le=1.0, description="税种匹配分")
    urgency_score: float = Field(ge=0.0, le=1.0, description="紧迫度分")


class MatchReason(BaseModel):
    """匹配原因（LLM增强版）"""
    category: str
    reason: str
    matched_items: List[str]
    confidence: float = Field(ge=0.0, le=1.0, default=0.8)


class PolicyUnderstanding(BaseModel):
    """政策深度理解"""
    policy_id: str
    title: str
    summary: str
    core_objectives: List[str] = Field(default_factory=list)
    applicable_conditions: List[str] = Field(default_factory=list)
    key_requirements: List[str] = Field(default_factory=list)
    deadlines: List[str] = Field(default_factory=list)
    compliance_changes: List[str] = Field(default_factory=list)
    opportunities: List[str] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)
    impact_level: str = "medium"
    confidence: float = Field(ge=0.0, le=1.0, default=0.85)


class EnterpriseProfile(BaseModel):
    """企业画像（增强版）"""
    enterprise_id: str
    name: str
    industry: Optional[str] = None
    region: Optional[str] = None
    scale: Optional[str] = None
    tax_types: List[str] = Field(default_factory=list)
    keywords: List[str] = Field(default_factory=list)
    business_scope: Optional[str] = None
    recent_interests: List[str] = Field(default_factory=list)
    preferences: Dict[str, Any] = Field(default_factory=dict)


class NotificationContent(BaseModel):
    """个性化通知内容（LLM生成）"""
    title: str
    content: str
    key_points: List[str] = Field(default_factory=list)
    action_items: List[str] = Field(default_factory=list)
    urgency_level: str
    recommended_actions: List[str] = Field(default_factory=list)
    risk_warnings: List[str] = Field(default_factory=list)
    related_policies: List[str] = Field(default_factory=list)
    call_to_action: str


class PolicyNotificationAgent:
    """
    政策通知智能体（真正的 Agent）
    
    核心能力：
    1. LLM 深度理解政策语义
    2. LLM 智能匹配企业与政策
    3. LLM 生成个性化通知文案
    4. 智能优先级排序和推荐
    
    提示词来源：
    - 使用 AgentPromptLoader 从 app/prompts/agents/policy_notification/system.md 加载
    """

    def __init__(
        self,
        llm_adapter: BaseLLMAdapter,
        tool_manager: ToolManager,
        skill_registry: Any = None,  # 🆕 技能系统
    ):
        """
        初始化政策通知智能体

        Args:
            llm_adapter: 大模型适配器（必须）
            tool_manager: 工具管理器
            skill_registry: 技能注册表（可选），传入后可在 system prompt 中渲染 {skill_descriptions}
        """
        self.llm_adapter = llm_adapter
        self.tool_manager = tool_manager
        self.skill_registry = skill_registry  # 🆕 技能系统

        self.match_weights = {
            "semantic": 0.3,
            "industry": 0.2,
            "region": 0.15,
            "scale": 0.1,
            "tax_type": 0.15,
            "urgency": 0.1
        }

        self.system_prompt = self._load_system_prompt()
        
        if not getattr(PolicyNotificationAgent, '_initialized', False):
            PolicyNotificationAgent._initialized = True
            logger.debug(
                "Policy notification agent initialized: match_weights=%s",
                self.match_weights,
            )
    
    def _load_system_prompt(self) -> str:
        """
        从结构化提示词系统加载系统提示词

        加载顺序：
        1. 从 app/prompts/agents/policy_notification/system.md 加载
        2. 渲染 {skill_descriptions}（如果 skill_registry 已初始化）
        3. 如果加载失败，使用回退提示词

        Returns:
            系统提示词
        """
        try:
            from app.prompts.loader import AgentPromptLoader

            loader = AgentPromptLoader()
            prompt = loader.load_system_prompt("policy_notification")

            if prompt:
                # 🆕 渲染 {skill_descriptions}
                skill_desc = self._get_skill_descriptions()
                if skill_desc:
                    prompt = prompt.replace("{skill_descriptions}", skill_desc)
                else:
                    prompt = prompt.replace("{skill_descriptions}", "当前暂无可用技能。")
                logger.info("✅ [PolicyNotificationAgent] 成功加载结构化提示词")
                return prompt
            else:
                logger.warning("⚠️ [PolicyNotificationAgent] 加载提示词失败，使用回退提示词")
                return self._get_fallback_prompt()

        except Exception as e:
            logger.error(f"❌ [PolicyNotificationAgent] 加载提示词异常: {e}")
            return self._get_fallback_prompt()

    def _get_skill_descriptions(self) -> str:
        """获取技能描述文本（从 SkillRegistry）"""
        if not self.skill_registry:
            return ""
        try:
            if self.skill_registry.is_initialized():
                return self.skill_registry.format_domain_skill_descriptions("public")
        except Exception:
            pass
        return ""
    
    def _get_fallback_prompt(self) -> str:
        """获取回退提示词（当模板加载失败时使用）"""
        return """你是一位专业的税收政策顾问，擅长：
1. 深度理解政策文本的意图和影响
2. 分析政策对不同类型企业的适用性
3. 生成清晰、准确、有价值的政策通知
4. 识别政策风险和机会

请始终保持专业、客观、友善的态度。"""
    
    async def understand_policy(
        self,
        policy_content: str,
        policy_id: str = "",
        title: str = ""
    ) -> PolicyUnderstanding:
        """
        深度理解政策内容（使用 LLM）
        
        不再是简单的关键词提取，而是理解：
        1. 政策的核心目标和意图
        2. 适用企业的具体条件
        3. 对企业的影响和风险
        4. 需要采取的行动
        
        Args:
            policy_content: 政策文本内容
            policy_id: 政策ID
            title: 政策标题
            
        Returns:
            PolicyUnderstanding: 深度理解结果
        """
        logger.info(f"🧠 LLM 深度理解政策: {policy_id or title[:30]}...")
        
        prompt = f"""{self.system_prompt}

请深度分析以下政策文本，提取关键信息：

政策标题: {title or '未知'}

政策内容:
{policy_content[:3000]}

请以 JSON 格式返回分析结果：
{{
    "policy_id": "{policy_id}",
    "title": "政策标题",
    "summary": "100字左右的政策摘要",
    "core_objectives": ["核心目标1", "核心目标2"],
    "applicable_conditions": ["适用条件1", "适用条件2"],
    "key_requirements": ["关键要求1", "关键要求2"],
    "deadlines": ["重要时间节点"],
    "compliance_changes": ["合规要求变化"],
    "opportunities": ["政策带来的机会"],
    "risks": ["潜在风险"],
    "impact_level": "high/medium/low",
    "confidence": 0.85
}}

注意：
- 直接输出 JSON 对象本身：不要用 Markdown 代码块包裹，不要输出思考过程或其他说明文字
- 如果信息不明确，confidence 可以适当降低
- focus on 对企业有实际影响的内容
"""

        try:
            response = await self.llm_adapter.generate(prompt)

            result = _extract_json_object(
                response.content,
                expected_keys={"summary", "core_objectives", "impact_level"}
            )

            if result is None:
                logger.error(
                    f"❌ JSON 解析失败: LLM 输出中未找到有效 JSON: "
                    f"{(response.content or '')[:120]}..."
                )
                return self._fallback_understanding(policy_id, title)

            understanding = self._build_understanding(result, policy_id, title)
            logger.info(f"✅ 政策理解完成: {understanding.impact_level} 级别")

            return understanding

        except Exception as e:
            logger.error(f"❌ 政策理解失败: {e}")
            return self._fallback_understanding(policy_id, title)

    def _build_understanding(
        self,
        result: Dict[str, Any],
        policy_id: str,
        title: str
    ) -> PolicyUnderstanding:
        """
        容错构建 PolicyUnderstanding

        policy_id / title 以调用方传入为准（不依赖 LLM 回显），
        缺失字段使用默认值，非法值自动归一化。
        """
        impact_level = str(result.get("impact_level", "medium")).lower()
        if impact_level not in ("high", "medium", "low"):
            impact_level = "medium"

        try:
            confidence = float(result.get("confidence", 0.85))
        except (TypeError, ValueError):
            confidence = 0.85
        confidence = min(1.0, max(0.0, confidence))

        return PolicyUnderstanding(
            policy_id=policy_id or str(result.get("policy_id", "")),
            title=title or str(result.get("title", "")),
            summary=str(result.get("summary") or title or "政策摘要缺失"),
            core_objectives=_as_str_list(result.get("core_objectives")),
            applicable_conditions=_as_str_list(result.get("applicable_conditions")),
            key_requirements=_as_str_list(result.get("key_requirements")),
            deadlines=_as_str_list(result.get("deadlines")),
            compliance_changes=_as_str_list(result.get("compliance_changes")),
            opportunities=_as_str_list(result.get("opportunities")),
            risks=_as_str_list(result.get("risks")),
            impact_level=impact_level,
            confidence=confidence,
        )
    
    def _fallback_understanding(
        self,
        policy_id: str,
        title: str
    ) -> PolicyUnderstanding:
        """回退理解（当 LLM 调用失败时）"""
        return PolicyUnderstanding(
            policy_id=policy_id,
            title=title,
            summary="政策理解失败",
            impact_level="medium",
            confidence=0.3
        )
    
    async def match_enterprise_policy(
        self,
        policy: Dict[str, Any],
        enterprise_profile: EnterpriseProfile
    ) -> tuple[MatchScore, List[MatchReason], PolicyUnderstanding]:
        """
        智能匹配企业与政策（使用 LLM + 规则）
        
        结合：
        1. LLM 语义理解政策
        2. LLM 分析企业特征
        3. 规则计算精确匹配
        
        Args:
            policy: 政策数据
            enterprise_profile: 企业画像
            
        Returns:
            tuple: (匹配评分, 匹配原因, 政策理解)
        """
        logger.info(f"🎯 智能匹配: {enterprise_profile.name} <-> {policy.get('title', policy.get('policy_id', 'unknown'))}")
        
        policy_content = policy.get("content", "") or policy.get("summary", "")
        policy_title = policy.get("title", "")
        policy_id = str(policy.get("policy_id", policy.get("id", "")))
        
        understanding = await self.understand_policy(
            policy_content=policy_content,
            policy_id=policy_id,
            title=policy_title
        )
        
        semantic_score, semantic_reasons = await self._calculate_semantic_match(
            understanding, enterprise_profile
        )
        
        industry_score, industry_reasons = self._calculate_industry_score(
            policy.get("industries", []),
            enterprise_profile.industry
        )
        
        region_score, region_reasons = self._calculate_region_score(
            policy.get("regions", []),
            enterprise_profile.region
        )
        
        scale_score, scale_reasons = self._calculate_scale_score(
            policy.get("scales", []),
            enterprise_profile.scale
        )
        
        tax_type_score, tax_reasons = self._calculate_tax_type_score(
            policy.get("tax_types", []),
            enterprise_profile.tax_types
        )
        
        urgency_score = self._calculate_urgency_score(
            understanding, policy.get("priority")
        )
        
        total_score = (
            semantic_score * self.match_weights["semantic"] +
            industry_score * self.match_weights["industry"] +
            region_score * self.match_weights["region"] +
            scale_score * self.match_weights["scale"] +
            tax_type_score * self.match_weights["tax_type"] +
            urgency_score * self.match_weights["urgency"]
        )
        
        total_score = min(1.0, max(0.0, total_score))
        
        all_reasons = (
            semantic_reasons +
            industry_reasons +
            region_reasons +
            scale_reasons +
            tax_reasons
        )
        
        return (
            MatchScore(
                total_score=total_score,
                semantic_score=semantic_score,
                industry_score=industry_score,
                region_score=region_score,
                scale_score=scale_score,
                tax_type_score=tax_type_score,
                urgency_score=urgency_score
            ),
            all_reasons,
            understanding
        )
    
    async def _calculate_semantic_match(
        self,
        understanding: PolicyUnderstanding,
        enterprise: EnterpriseProfile
    ) -> tuple[float, List[MatchReason]]:
        """使用 LLM 计算语义匹配度"""
        
        prompt = f"""分析以下政策理解与企业画像的语义匹配度：

政策理解：
- 目标: {', '.join(understanding.core_objectives[:3])}
- 适用条件: {', '.join(understanding.applicable_conditions[:3])}
- 风险: {', '.join(understanding.risks[:2])}

企业画像：
- 行业: {enterprise.industry}
- 地区: {enterprise.region}
- 业务范围: {enterprise.business_scope or '未知'}
- 关注领域: {', '.join(enterprise.recent_interests[:3] or ['未记录'])}

请评估语义匹配度（0-1之间的数字），考虑：
1. 政策目标与企业业务的契合度
2. 适用条件与企业特征的匹配度
3. 企业是否关注这个领域

只返回一个 0-1 的数字，不需要其他内容。
"""
        
        try:
            response = await self.llm_adapter.generate(prompt)
            raw = (response.content or "").strip()

            # 提取输出中第一个 0-1 范围的数字（容忍模型附带文字）
            number_match = re.search(r"(?:0?\.\d+|[01](?:\.0+)?)", raw)
            if not number_match:
                raise ValueError(f"无法从 LLM 输出中提取分数: {raw[:50]}")

            score = float(number_match.group(0))
            score = min(1.0, max(0.0, score))

            return score, [
                MatchReason(
                    category="semantic",
                    reason="语义层面与企业业务相关",
                    matched_items=understanding.core_objectives[:2],
                    confidence=score
                )
            ]
        except Exception:
            return 0.5, [
                MatchReason(
                    category="semantic",
                    reason="语义匹配（降级）",
                    matched_items=[],
                    confidence=0.5
                )
            ]
    
    def _calculate_industry_score(
        self,
        policy_industries: List[str],
        enterprise_industry: Optional[str]
    ) -> tuple[float, List[MatchReason]]:
        """计算行业匹配分"""
        if not enterprise_industry:
            return 0.5, []
        
        industry_keywords = {
            "制造业": ["制造", "生产", "加工"],
            "服务业": ["服务", "咨询", "外包"],
            "信息技术": ["IT", "软件", "互联网", "科技"],
            "建筑业": ["建筑", "施工", "工程"],
            "批发零售": ["批发", "零售", "商贸"]
        }
        
        enterprise_lower = enterprise_industry.lower()
        matched = []
        
        for pi in policy_industries:
            pi_lower = pi.lower()
            
            if enterprise_lower == pi_lower:
                matched.append(pi)
            else:
                for keyword, variants in industry_keywords.items():
                    if enterprise_lower in variants and keyword in pi_lower:
                        matched.append(pi)
                        break
        
        score = min(1.0, len(matched) / max(1, min(3, len(policy_industries)))) if policy_industries else 0.5
        
        return score, [
            MatchReason(
                category="industry",
                reason=f"行业匹配: {enterprise_industry}",
                matched_items=matched[:3],
                confidence=score
            )
        ]
    
    def _calculate_region_score(
        self,
        policy_regions: List[str],
        enterprise_region: Optional[str]
    ) -> tuple[float, List[MatchReason]]:
        """计算地区匹配分"""
        if not enterprise_region:
            return 0.5, []
        
        matched = []
        
        for pr in policy_regions:
            pr_lower = pr.lower()
            er_lower = enterprise_region.lower()
            
            if pr_lower in er_lower or er_lower in pr_lower:
                matched.append(pr)
            elif "全国" in pr or "全国" in enterprise_region:
                matched.append("全国")
        
        score = 1.0 if matched else 0.3
        
        return score, [
            MatchReason(
                category="region",
                reason=f"地区: {enterprise_region}",
                matched_items=matched[:3],
                confidence=score
            )
        ]
    
    def _calculate_scale_score(
        self,
        policy_scales: List[str],
        enterprise_scale: Optional[str]
    ) -> tuple[float, List[MatchReason]]:
        """计算规模匹配分"""
        if not enterprise_scale:
            return 0.5, []
        
        scale_mapping = {
            "大型": ["大型", "规模较大"],
            "中型": ["中型", "中等规模"],
            "小型": ["小型", "小微企业", "小规模"],
            "微型": ["微型", "个体工商户"]
        }
        
        enterprise_lower = enterprise_scale.lower()
        matched = []
        
        for ps in policy_scales:
            ps_lower = ps.lower()
            
            if enterprise_lower == ps_lower:
                matched.append(ps)
            else:
                for scale_key, variants in scale_mapping.items():
                    if enterprise_lower in variants and any(v in ps_lower for v in variants):
                        matched.append(ps)
                        break
        
        score = min(1.0, len(matched) / max(1, len(policy_scales))) if policy_scales else 0.5
        
        return score, [
            MatchReason(
                category="scale",
                reason=f"规模: {enterprise_scale}",
                matched_items=matched[:2],
                confidence=score
            )
        ]
    
    def _calculate_tax_type_score(
        self,
        policy_tax_types: List[str],
        enterprise_tax_types: List[str]
    ) -> tuple[float, List[MatchReason]]:
        """计算税种匹配分"""
        if not enterprise_tax_types or not policy_tax_types:
            return 0.5, []
        
        matched = set(policy_tax_types) & set(enterprise_tax_types)
        
        score = len(matched) / len(policy_tax_types) if policy_tax_types else 0.5
        
        return score, [
            MatchReason(
                category="tax_type",
                reason=f"涉及税种: {', '.join(list(matched)[:3])}",
                matched_items=list(matched)[:5],
                confidence=score
            )
        ]
    
    def _calculate_urgency_score(
        self,
        understanding: PolicyUnderstanding,
        priority: Optional[str]
    ) -> float:
        """计算紧迫度分"""
        score = 0.5
        
        if priority in ["critical", "CRITICAL"]:
            score = 1.0
        elif priority in ["high", "HIGH"]:
            score = 0.8
        elif understanding.deadlines:
            score = max(score, 0.7)
        
        if understanding.risks:
            score = min(1.0, score + 0.2)
        
        return score
    
    async def generate_personalized_notification(
        self,
        policy: Dict[str, Any],
        enterprise: EnterpriseProfile,
        understanding: PolicyUnderstanding,
        match_score: MatchScore
    ) -> NotificationContent:
        """
        生成个性化通知（使用 LLM）
        
        不再是简单的模板填充，而是：
        1. 理解企业特征和需求
        2. 匹配政策的重点内容
        3. 生成自然语言通知
        4. 提供企业特定的建议
        
        Args:
            policy: 政策数据
            enterprise: 企业画像
            understanding: 政策理解
            match_score: 匹配评分
            
        Returns:
            NotificationContent: 个性化通知内容
        """
        logger.info(f"✍️ 生成个性化通知: {enterprise.name} - {policy.get('title', '')[:30]}...")
        
        policy_title = policy.get("title", "未知政策")
        policy_id = str(policy.get("policy_id", policy.get("id", "")))
        
        prompt = f"""{self.system_prompt}

请为这家企业生成个性化的政策通知：

【企业信息】
- 企业名称: {enterprise.name}
- 所属行业: {enterprise.industry or '未记录'}
- 企业规模: {enterprise.scale or '未记录'}
- 所在地区: {enterprise.region or '未记录'}
- 涉及税种: {', '.join(enterprise.tax_types) if enterprise.tax_types else '未记录'}
- 业务范围: {enterprise.business_scope or '未记录'}
- 最近关注: {', '.join(enterprise.recent_interests) if enterprise.recent_interests else '无'}

【政策信息】
- 政策标题: {policy_title}
- 政策摘要: {understanding.summary}
- 核心目标: {', '.join(understanding.core_objectives[:3])}
- 适用条件: {', '.join(understanding.applicable_conditions[:3])}
- 关键要求: {', '.join(understanding.key_requirements[:3])}
- 重要时间: {', '.join(understanding.deadlines[:2]) if understanding.deadlines else '暂无'}
- 潜在风险: {', '.join(understanding.risks[:2]) if understanding.risks else '暂无'}
- 影响级别: {understanding.impact_level}

【匹配信息】
- 匹配分数: {match_score.total_score:.2f}
- 行业匹配: {match_score.industry_score:.2f}
- 地区匹配: {match_score.region_score:.2f}
- 紧迫度: {match_score.urgency_score:.2f}

请生成 JSON 格式的通知内容：
{{
    "title": "通知标题（简洁有力）",
    "content": "通知正文（200字左右，专业但易懂）",
    "key_points": ["要点1", "要点2", "要点3"],
    "action_items": ["需要采取的行动1", "行动2"],
    "urgency_level": "high/medium/low",
    "recommended_actions": ["建议行动1", "建议行动2"],
    "risk_warnings": ["风险提示1"],
    "related_policies": ["相关政策标题"],
    "call_to_action": "行动号召（如：立即查看详情）"
}}

要求：
1. 通知要专业、清晰、有价值
2. 突出与企业最相关的要点
3. 提供可操作的建议
4. 语言亲切，符合企业管理者阅读习惯
5. 直接输出 JSON 对象本身：不要用 Markdown 代码块包裹，不要输出思考过程或其他说明文字
"""

        try:
            response = await self.llm_adapter.generate(prompt)

            result = _extract_json_object(
                response.content,
                expected_keys={"title", "content", "key_points"}
            )

            if result is None:
                logger.error(
                    f"❌ JSON 解析失败: LLM 输出中未找到有效 JSON: "
                    f"{(response.content or '')[:120]}..."
                )
                return self._fallback_notification(policy_title, match_score)

            urgency_level = str(result.get("urgency_level", "medium")).lower()
            if urgency_level not in ("high", "medium", "low"):
                urgency_level = "medium"

            content = NotificationContent(
                title=str(result.get("title") or f"政策通知: {policy_title}"),
                content=str(result.get("content") or "您有一条新的政策通知，请及时查看。"),
                key_points=_as_str_list(result.get("key_points")),
                action_items=_as_str_list(result.get("action_items")),
                urgency_level=urgency_level,
                recommended_actions=_as_str_list(result.get("recommended_actions")),
                risk_warnings=_as_str_list(result.get("risk_warnings")),
                related_policies=_as_str_list(result.get("related_policies")),
                call_to_action=str(result.get("call_to_action") or "查看详情"),
            )

            logger.info(f"✅ 个性化通知生成完成: {content.urgency_level} 级别")

            return content

        except Exception as e:
            logger.error(f"❌ 通知生成失败: {e}")
            return self._fallback_notification(policy_title, match_score)
    
    def _fallback_notification(
        self,
        policy_title: str,
        match_score: MatchScore
    ) -> NotificationContent:
        """回退通知（当 LLM 调用失败时）"""
        return NotificationContent(
            title=f"政策通知: {policy_title}",
            content="您有一条新的政策通知，请及时查看。",
            key_points=["有新政策需要关注"],
            action_items=["查看政策详情"],
            urgency_level="medium",
            recommended_actions=["了解政策详情"],
            risk_warnings=[],
            related_policies=[],
            call_to_action="查看详情"
        )
    
    async def prioritize_policies(
        self,
        policies: List[Dict[str, Any]],
        enterprise: EnterpriseProfile
    ) -> List[Dict[str, Any]]:
        """
        智能优先级排序（使用 LLM）
        
        不再是简单的规则排序，而是：
        1. 理解企业的当前状况
        2. 评估政策的时效性
        3. 判断政策的潜在价值
        4. 动态调整优先级
        
        Args:
            policies: 政策列表
            enterprise: 企业画像
            
        Returns:
            List[Dict]: 排序后的政策列表
        """
        if len(policies) <= 1:
            return policies
        
        logger.info(f"📊 智能排序: {len(policies)} 个政策")
        
        policy_summaries = []
        for i, p in enumerate(policies):
            policy_summaries.append(
                f"{i+1}. {p.get('title', '未知')} "
                f"(优先级: {p.get('priority', 'medium')}, "
                f"匹配分: {p.get('match_score', 0):.2f})"
            )
        
        prompt = f"""{self.system_prompt}

请为这家企业排序以下政策的优先级：

企业信息：
- 名称: {enterprise.name}
- 行业: {enterprise.industry or '未知'}
- 规模: {enterprise.scale or '未知'}
- 关注: {', '.join(enterprise.recent_interests[:3]) if enterprise.recent_interests else '无'}

政策列表：
{chr(10).join(policy_summaries)}

请考虑：
1. 政策的时效性和紧迫程度
2. 企业当前最迫切的需求
3. 政策的实际价值和影响
4. 申报的复杂度和成功率

请按优先级排序（最重要的在前），返回 JSON 格式：
{{
    "ordered_policy_ids": ["policy_id_1", "policy_id_2", ...],
    "reasons": {{
        "policy_id_1": "排序理由1",
        "policy_id_2": "排序理由2"
    }}
}}

直接输出 JSON 对象本身：不要用 Markdown 代码块包裹，不要输出思考过程或其他说明文字。
"""

        try:
            response = await self.llm_adapter.generate(prompt)

            result = _extract_json_object(
                response.content,
                expected_keys={"ordered_policy_ids"}
            ) or {}

            ordered_ids = result.get("ordered_policy_ids", [])
            
            ordered_policies = []
            for pid in ordered_ids:
                for p in policies:
                    if str(p.get("policy_id", p.get("id", ""))) == pid:
                        ordered_policies.append(p)
                        break
            
            for p in policies:
                if p not in ordered_policies:
                    ordered_policies.append(p)
            
            logger.info(f"✅ 排序完成: {len(ordered_policies)} 个政策")
            
            return ordered_policies
            
        except Exception as e:
            logger.error(f"❌ 智能排序失败: {e}")
            return sorted(
                policies,
                key=lambda x: (x.get("match_score", 0), x.get("priority", "")),
                reverse=True
            )


def create_policy_notification_agent(
    llm_adapter: BaseLLMAdapter,
    tool_manager: Optional[ToolManager] = None
) -> PolicyNotificationAgent:
    """
    创建政策通知智能体工厂函数
    
    Args:
        llm_adapter: 大模型适配器（必须）
        tool_manager: 工具管理器
        
    Returns:
        PolicyNotificationAgent: 政策通知智能体实例
    """
    if tool_manager is None:
        try:
            tool_manager = ToolManager()
        except Exception as e:
            logger.warning(f"⚠️ 工具管理器创建失败: {e}")
            tool_manager = None
    
    return PolicyNotificationAgent(
        llm_adapter=llm_adapter,
        tool_manager=tool_manager
    )
