"""
深度分析服务
提供基于LLM的深度分析和推理能力
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

from app.core.exceptions import (
    LLMServiceException,
    ServiceException,
    ValidationException
)

logger = logging.getLogger(__name__)


class DeepAnalysisService:
    """
    深度分析服务
    
    提供多维度的深度分析和推理能力
    """

    def __init__(self):
        self.llm_service = None
        self._init_llm_service()

    def _init_llm_service(self):
        """初始化LLM服务"""
        try:
            from app.services.llm_service import LLMService
            self.llm_service = LLMService()
            logger.info("✅ 深度分析服务初始化: LLM服务已连接")
        except ImportError as e:
            logger.warning(f"⚠️ LLM服务导入失败: {e}")
            self.llm_service = None
        except Exception as e:
            logger.warning(f"⚠️ LLM服务初始化失败: {e}")
            self.llm_service = None

    async def analyze_tax_compliance(
        self,
        financial_data: Dict[str, Any],
        historical_data: Optional[List[Dict[str, Any]]] = None,
        industry_benchmark: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        深度税务合规分析
        
        Args:
            financial_data: 财务数据
            historical_data: 历史数据（用于趋势分析）
            industry_benchmark: 行业基准数据
            
        Returns:
            深度分析结果
        """
        if not self.llm_service:
            raise LLMServiceException(
                message="LLM服务不可用，无法进行税务合规分析",
                provider="llm_service"
            )
        
        try:
            prompt = self._build_tax_compliance_prompt(
                financial_data,
                historical_data,
                industry_benchmark
            )

            response = await self.llm_service.get_answer(
                query=prompt,
                context_chunks=[],
                add_truncation_notification=False
            )

            return self._parse_tax_compliance_response(response, financial_data)

        except LLMServiceException:
            raise
        except ValidationException:
            raise
        except (ValueError, KeyError) as e:
            raise LLMServiceException(
                message=f"税务合规分析数据错误: {str(e)}",
                details={"error_type": "data_error", "original_error": str(e)}
            )
        except (OSError, IOError) as e:
            raise LLMServiceException(
                message=f"税务合规分析IO错误: {str(e)}",
                details={"error_type": "io_error", "original_error": str(e)}
            )
        except Exception as e:
            raise LLMServiceException(
                message=f"税务合规分析失败: {str(e)}",
                provider="llm_service",
                response_text=str(e)
            )

    def _build_tax_compliance_prompt(
        self,
        financial_data: Dict[str, Any],
        historical_data: Optional[List[Dict[str, Any]]],
        industry_benchmark: Optional[Dict[str, Any]]
    ) -> str:
        """构建税务合规分析提示词"""
        prompt = f"""
请对以下财务数据进行深度税务合规分析：

## 当前财务数据
{self._format_dict(financial_data)}

## 历史趋势数据
{self._format_list(historical_data) if historical_data else "无历史数据"}

## 行业基准
{self._format_dict(industry_benchmark) if industry_benchmark else "无行业基准数据"}

请进行以下分析：
1. 税务风险评估（高/中/低）
2. 异常指标识别
3. 合规建议
4. 潜在优化空间
5. 预警事项

请以JSON格式返回分析结果。
"""
        return prompt

    async def analyze_financial_anomaly(
        self,
        transaction_data: List[Dict[str, Any]],
        patterns: Dict[str, Any],
        threshold_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        财务异常深度分析
        
        Args:
            transaction_data: 交易数据
            patterns: 识别到的模式
            threshold_config: 阈值配置
            
        Returns:
            异常分析结果
        """
        if not self.llm_service:
            raise LLMServiceException(
                message="LLM服务不可用，无法进行财务异常分析",
                provider="llm_service"
            )
        
        try:
            prompt = f"""
请对以下财务异常进行深度分析：

## 交易数据样本
{self._format_list(transaction_data[:10])}

## 检测到的模式
{self._format_dict(patterns)}

## 阈值配置
{self._format_dict(threshold_config)}

请分析：
1. 异常的根因
2. 可能的业务解释
3. 是否需要人工审核
4. 建议的响应措施

请以JSON格式返回分析结果。
"""
            response = await self.llm_service.get_answer(
                query=prompt,
                context_chunks=[],
                add_truncation_notification=False
            )

            return self._parse_anomaly_response(response)

        except LLMServiceException:
            raise
        except ValidationException:
            raise
        except (ValueError, KeyError) as e:
            raise LLMServiceException(
                message=f"财务异常分析数据错误: {str(e)}",
                details={"error_type": "data_error", "original_error": str(e)}
            )
        except (OSError, IOError) as e:
            raise LLMServiceException(
                message=f"财务异常分析IO错误: {str(e)}",
                details={"error_type": "io_error", "original_error": str(e)}
            )
        except Exception as e:
            raise LLMServiceException(
                message=f"财务异常分析失败: {str(e)}",
                provider="llm_service",
                response_text=str(e)
            )

    async def analyze_contract_risk(
        self,
        contract_text: str,
        contract_type: str,
        counterparty_info: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        合同风险深度分析
        
        Args:
            contract_text: 合同文本
            contract_type: 合同类型
            counterparty_info: 交易对方信息
            
        Returns:
            风险分析结果
        """
        if not self.llm_service:
            raise LLMServiceException(
                message="LLM服务不可用，无法进行合同风险分析",
                provider="llm_service"
            )
        
        try:
            prompt = f"""
请对以下{contract_type}合同进行深度风险分析：

## 合同文本（部分）
{contract_text[:5000]}

## 交易对方信息
{self._format_dict(counterparty_info) if counterparty_info else "无详细信息"}

请分析：
1. 关键风险条款识别
2. 不利条款评估
3. 潜在法律风险
4. 条款修改建议
5. 谈判优先级

请以JSON格式返回分析结果。
"""
            response = await self.llm_service.get_answer(
                query=prompt,
                context_chunks=[],
                add_truncation_notification=False
            )

            return self._parse_contract_risk_response(response)

        except LLMServiceException:
            raise
        except ValidationException:
            raise
        except (ValueError, KeyError) as e:
            raise LLMServiceException(
                message=f"合同风险分析数据错误: {str(e)}",
                details={"error_type": "data_error", "original_error": str(e)}
            )
        except (OSError, IOError) as e:
            raise LLMServiceException(
                message=f"合同风险分析IO错误: {str(e)}",
                details={"error_type": "io_error", "original_error": str(e)}
            )
        except Exception as e:
            raise LLMServiceException(
                message=f"合同风险分析失败: {str(e)}",
                provider="llm_service",
                response_text=str(e)
            )

    async def analyze_policy_impact(
        self,
        policy_text: str,
        enterprise_profile: Dict[str, Any],
        historical_compliance: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        政策影响分析
        
        Args:
            policy_text: 政策文本
            enterprise_profile: 企业画像
            historical_compliance: 历史合规情况
            
        Returns:
            影响分析结果
        """
        if not self.llm_service:
            raise LLMServiceException(
                message="LLM服务不可用，无法进行政策影响分析",
                provider="llm_service"
            )
        
        try:
            prompt = f"""
请分析以下政策对企业的影响：

## 政策内容
{policy_text[:5000]}

## 企业画像
{self._format_dict(enterprise_profile)}

## 历史合规情况
{self._format_dict(historical_compliance) if historical_compliance else "无历史数据"}

请分析：
1. 政策适用性
2. 合规影响评估
3. 需要调整的事项
4. 时间节点要求
5. 建议的行动计划

请以JSON格式返回分析结果。
"""
            response = await self.llm_service.get_answer(
                query=prompt,
                context_chunks=[],
                add_truncation_notification=False
            )

            return self._parse_policy_impact_response(response)

        except LLMServiceException:
            raise
        except ValidationException:
            raise
        except (ValueError, KeyError) as e:
            raise LLMServiceException(
                message=f"政策影响分析数据错误: {str(e)}",
                details={"error_type": "data_error", "original_error": str(e)}
            )
        except (OSError, IOError) as e:
            raise LLMServiceException(
                message=f"政策影响分析IO错误: {str(e)}",
                details={"error_type": "io_error", "original_error": str(e)}
            )
        except Exception as e:
            raise LLMServiceException(
                message=f"政策影响分析失败: {str(e)}",
                provider="llm_service",
                response_text=str(e)
            )

    async def generate_insights(
        self,
        data_sources: List[Dict[str, Any]],
        business_context: str
    ) -> List[str]:
        """
        生成业务洞察
        
        Args:
            data_sources: 数据源列表
            business_context: 业务背景
            
        Returns:
            洞察列表
        """
        if not self.llm_service:
            raise LLMServiceException(
                message="LLM服务不可用，无法生成业务洞察",
                provider="llm_service"
            )
        
        try:
            prompt = f"""
基于以下业务数据，生成深度洞察：

## 业务背景
{business_context}

## 数据源
{self._format_list(data_sources)}

请生成5-10条有价值的业务洞察，包括：
- 趋势发现
- 风险预警
- 优化机会
- 行动建议

请以JSON格式返回洞察列表。
"""
            response = await self.llm_service.get_answer(
                query=prompt,
                context_chunks=[],
                add_truncation_notification=False
            )

            return self._parse_insights_response(response)

        except LLMServiceException:
            raise
        except ValidationException:
            raise
        except (ValueError, KeyError) as e:
            raise LLMServiceException(
                message=f"洞察生成数据错误: {str(e)}",
                details={"error_type": "data_error", "original_error": str(e)}
            )
        except (OSError, IOError) as e:
            raise LLMServiceException(
                message=f"洞察生成IO错误: {str(e)}",
                details={"error_type": "io_error", "original_error": str(e)}
            )
        except Exception as e:
            raise LLMServiceException(
                message=f"洞察生成失败: {str(e)}",
                provider="llm_service",
                response_text=str(e)
            )

    async def multi_step_reasoning(
        self,
        problem: str,
        constraints: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        多步推理分析
        
        Args:
            problem: 问题描述
            constraints: 约束条件
            context: 上下文信息
            
        Returns:
            推理结果
        """
        if not self.llm_service:
            raise LLMServiceException(
                message="LLM服务不可用，无法进行多步推理",
                provider="llm_service"
            )
        
        try:
            prompt = f"""
请对这个复杂问题进行多步推理分析：

## 问题
{problem}

## 约束条件
{self._format_dict(constraints)}

## 上下文信息
{self._format_dict(context) if context else "无额外上下文"}

请进行以下推理步骤：
1. 问题拆解
2. 假设设定
3. 逻辑推演
4. 结论验证
5. 风险评估
6. 建议方案

请以JSON格式返回完整的推理过程和结论。
"""
            response = await self.llm_service.get_answer(
                query=prompt,
                context_chunks=[],
                add_truncation_notification=False
            )

            return self._parse_reasoning_response(response)

        except LLMServiceException:
            raise
        except ValidationException:
            raise
        except (ValueError, KeyError) as e:
            raise LLMServiceException(
                message=f"多步推理数据错误: {str(e)}",
                details={"error_type": "data_error", "original_error": str(e)}
            )
        except (OSError, IOError) as e:
            raise LLMServiceException(
                message=f"多步推理IO错误: {str(e)}",
                details={"error_type": "io_error", "original_error": str(e)}
            )
        except Exception as e:
            raise LLMServiceException(
                message=f"多步推理失败: {str(e)}",
                provider="llm_service",
                response_text=str(e)
            )

    def _format_dict(self, data: Any) -> str:
        """格式化字典数据"""
        if not data:
            return "无数据"
        if isinstance(data, dict):
            import json
            return json.dumps(data, ensure_ascii=False, indent=2)
        return str(data)

    def _format_list(self, data: Any) -> str:
        """格式化列表数据"""
        if not data:
            return "无数据"
        if isinstance(data, list):
            return "\n".join([f"- {self._format_dict(item)}" for item in data[:5]])
        return str(data)

    def _parse_tax_compliance_response(self, response: str, original_data: Dict) -> Dict[str, Any]:
        """解析税务合规分析响应"""
        try:
            import json
            import re

            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                result["raw_analysis"] = response[:500]
                return result

        except json.JSONDecodeError as e:
            logger.warning(f"JSON解析税务合规响应失败: {e}")
        except re.error as e:
            logger.warning(f"正则表达式解析税务合规响应失败: {e}")
        except (ValueError, KeyError) as e:
            logger.warning(f"解析税务合规响应数据错误: {e}")
        except (OSError, IOError) as e:
            logger.warning(f"解析税务合规响应IO错误: {e}")
        except Exception as e:
            logger.warning(f"解析税务合规响应失败: {e}")

        return {
            "risk_level": "medium",
            "findings": response[:1000],
            "raw_analysis": response
        }

    def _parse_anomaly_response(self, response: str) -> Dict[str, Any]:
        """解析异常分析响应"""
        try:
            import json
            import re

            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                return result

        except json.JSONDecodeError as e:
            logger.warning(f"JSON解析异常分析响应失败: {e}")
        except re.error as e:
            logger.warning(f"正则表达式解析异常分析响应失败: {e}")
        except (ValueError, KeyError) as e:
            logger.warning(f"解析异常分析响应数据错误: {e}")
        except (OSError, IOError) as e:
            logger.warning(f"解析异常分析响应IO错误: {e}")
        except Exception as e:
            logger.warning(f"解析异常分析响应失败: {e}")

        return {
            "root_cause": response[:500],
            "needs_review": True
        }

    def _parse_contract_risk_response(self, response: str) -> Dict[str, Any]:
        """解析合同风险分析响应"""
        try:
            import json
            import re

            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                return result

        except json.JSONDecodeError as e:
            logger.warning(f"JSON解析合同风险响应失败: {e}")
        except re.error as e:
            logger.warning(f"正则表达式解析合同风险响应失败: {e}")
        except (ValueError, KeyError) as e:
            logger.warning(f"解析合同风险响应数据错误: {e}")
        except (OSError, IOError) as e:
            logger.warning(f"解析合同风险响应IO错误: {e}")
        except Exception as e:
            logger.warning(f"解析合同风险响应失败: {e}")

        return {
            "risk_level": "medium",
            "key_risks": response[:1000]
        }

    def _parse_policy_impact_response(self, response: str) -> Dict[str, Any]:
        """解析政策影响分析响应"""
        try:
            import json
            import re

            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                return result

        except json.JSONDecodeError as e:
            logger.warning(f"JSON解析政策影响响应失败: {e}")
        except re.error as e:
            logger.warning(f"正则表达式解析政策影响响应失败: {e}")
        except (ValueError, KeyError) as e:
            logger.warning(f"解析政策影响响应数据错误: {e}")
        except (OSError, IOError) as e:
            logger.warning(f"解析政策影响响应IO错误: {e}")
        except Exception as e:
            logger.warning(f"解析政策影响响应失败: {e}")

        return {
            "applicability": "需要评估",
            "action_items": response[:1000]
        }

    def _parse_insights_response(self, response: str) -> List[str]:
        """解析洞察响应"""
        try:
            import json
            import re

            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if json_match:
                insights = json.loads(json_match.group())
                if isinstance(insights, list):
                    return insights

        except json.JSONDecodeError as e:
            logger.warning(f"JSON解析洞察响应失败: {e}")
        except re.error as e:
            logger.warning(f"正则表达式解析洞察响应失败: {e}")
        except (ValueError, KeyError) as e:
            logger.warning(f"解析洞察响应数据错误: {e}")
        except (OSError, IOError) as e:
            logger.warning(f"解析洞察响应IO错误: {e}")
        except Exception as e:
            logger.warning(f"解析洞察响应失败: {e}")

        lines = response.strip().split('\n')
        return [line.strip('- *') for line in lines if line.strip()][:10]

    def _parse_reasoning_response(self, response: str) -> Dict[str, Any]:
        """解析推理响应"""
        try:
            import json
            import re

            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                return result

        except json.JSONDecodeError as e:
            logger.warning(f"JSON解析推理响应失败: {e}")
        except re.error as e:
            logger.warning(f"正则表达式解析推理响应失败: {e}")
        except (ValueError, KeyError) as e:
            logger.warning(f"解析推理响应数据错误: {e}")
        except (OSError, IOError) as e:
            logger.warning(f"解析推理响应IO错误: {e}")
        except Exception as e:
            logger.warning(f"解析推理响应失败: {e}")

        return {
            "reasoning": response[:2000],
            "conclusion": "请参考完整推理过程"
        }


deep_analysis_service = DeepAnalysisService()
