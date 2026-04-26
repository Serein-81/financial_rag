"""
认知层：发票智能分析服务

职责：
- 独立唤醒 TaxSpecialist（无需 AgentOrchestrator）
- 从发票文本中提取结构化事实
- 输出语义层面的可疑性（建议性，非判定性）
- 不输出 risk_level（这是控制层的职责）

复用组件：
- TaxSpecialist: app.multi_agent_system.agents.tax_specialist
- LLMAdapterFactory: app.agent_framework.llm.factory
- ToolManager: app.agent_framework.tools.tool_manager
"""

import json
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class InvoiceLLMExtraction(BaseModel):
    """
    大模型提取的发票信息（只含事实，不含风险判定）
    
    认知层（大模型）职责：
    - 提取事实（金额、税率、发票号等）
    - 语义层面的可疑性（建议性）
    - 输出置信度
    
    控制层（纯 Python）职责：
    - 数字比较和阈值判定
    - risk_level 输出
    """
    
    amount: Optional[float] = Field(None, description="发票总金额（含税）")
    tax_amount: Optional[float] = Field(None, description="税额")
    tax_rate: Optional[float] = Field(None, description="税率（如 0.13 表示 13%）")
    
    invoice_number: Optional[str] = Field(None, description="发票号码")
    invoice_date: Optional[str] = Field(None, description="开票日期")
    invoice_type: Optional[str] = Field(None, description="发票类型（增值税专用发票/普通发票）")
    
    seller_name: Optional[str] = Field(None, description="销售方名称")
    seller_tax_id: Optional[str] = Field(None, description="销售方税号")
    buyer_name: Optional[str] = Field(None, description="购买方名称")
    buyer_tax_id: Optional[str] = Field(None, description="购买方税号")
    
    items: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="商品明细列表")
    
    semantic_suspicion: List[str] = Field(
        default_factory=list,
        description="语义层面的可疑点（建议性），如：'供应商名称与历史记录不符'，'发票格式存在轻微异常'。大模型不确定时如实描述。"
    )
    
    confidence: float = Field(
        description="大模型对该提取结果的置信度（0-1）",
        ge=0.0,
        le=1.0
    )
    
    raw_analysis: Optional[str] = Field(None, description="大模型原始分析文本")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "amount": 1160000.0,
                "tax_amount": 160000.0,
                "tax_rate": 0.13,
                "invoice_number": "NO1234567890",
                "invoice_date": "2024-03-15",
                "invoice_type": "增值税专用发票",
                "seller_name": "XX贸易有限公司",
                "seller_tax_id": "91110000123456789X",
                "buyer_name": "YY科技有限公司",
                "buyer_tax_id": "91110000987654321X",
                "items": [
                    {"name": "商品A", "quantity": 100, "unit_price": 10000, "amount": 1000000, "tax": 130000},
                    {"name": "商品B", "quantity": 50, "unit_price": 3200, "amount": 160000, "tax": 30000}
                ],
                "semantic_suspicion": [
                    "供应商名称为新注册公司，建议核实",
                    "单笔金额较大，建议人工复核"
                ],
                "confidence": 0.92,
                "raw_analysis": "该发票为增值税专用发票，金额116万元，税率13%，包含商品明细..."
            }
        }
    }


class InvoiceCognitionService:
    """
    认知服务：税务智能体分析发票
    
    核心设计：
    - 无图谱唤醒（Graph-less Invocation）
    - 直接实例化 TaxSpecialist，绕过 AgentOrchestrator
    - 伪造极简状态，直接调用
    """
    
    def __init__(
        self,
        llm_adapter=None
    ):
        """
        初始化认知服务
        
        Args:
            llm_adapter: LLM 适配器（可选，默认创建）
        """
        self._llm_adapter = llm_adapter
        self._initialized = False
    
    def _ensure_initialized(self):
        """延迟初始化 LLM 适配器"""
        if self._initialized:
            return
        
        try:
            if self._llm_adapter is None:
                from app.agent_framework.llm.factory import LLMAdapterFactory
                self._llm_adapter = LLMAdapterFactory.create_adapter()
                logger.info("✅ [认知层] LLM 适配器初始化完成")
            
            self._initialized = True
            
        except Exception as e:
            logger.error(f"❌ [认知层] LLM 适配器初始化失败: {e}")
            self._initialized = True
    
    async def analyze_invoice(
        self,
        invoice_text: str,
        tenant_id: str,
        user_id: Optional[str] = None
    ) -> InvoiceLLMExtraction:
        """
        税务智能体分析发票
        
        Args:
            invoice_text: 发票文本（已提取）
            tenant_id: 租户ID
            user_id: 用户ID（可选）
            
        Returns:
            InvoiceLLMExtraction: 大模型提取结果（只含事实，无 risk_level）
        """
        self._ensure_initialized()
        
        if self._llm_adapter is None:
            logger.error("❌ [认知层] LLM 适配器未初始化，返回空结果")
            return InvoiceLLMExtraction(
                confidence=0.0,
                semantic_suspicion=["系统初始化失败，无法完成分析"]
            )
        
        logger.info(f"🤖 [认知层] 直接调用 LLM 分析发票...")
        logger.info(f"   - 文本长度: {len(invoice_text)} 字符")
        logger.info(f"   - 租户ID: {tenant_id}")
        
        try:
            system_prompt = self._get_invoice_system_prompt()
            user_prompt = self._build_invoice_analysis_prompt(invoice_text)
            
            full_prompt = f"{system_prompt}\n\n{user_prompt}"
            
            logger.info(f"📝 [认知层] 发送请求到 LLM，提示词长度: {len(full_prompt)} 字符")
            
            llm_response = await self._llm_adapter.generate(
                prompt=full_prompt,
                temperature=0.3
            )
            
            response_text = llm_response.content if hasattr(llm_response, 'content') else str(llm_response)
            
            logger.info(f"📥 [认知层] 收到 LLM 响应，长度: {len(response_text)} 字符")
            
            extraction = self._parse_analysis_result({"response": response_text}, invoice_text)
            
            logger.info(f"✅ [认知层] 分析完成，置信度: {extraction.confidence:.2f}")
            if extraction.semantic_suspicion:
                for suspicion in extraction.semantic_suspicion:
                    logger.info(f"   ⚠️ {suspicion}")
            
            return extraction
            
        except Exception as e:
            logger.error(f"❌ [认知层] 发票分析失败: {e}")
            return InvoiceLLMExtraction(
                confidence=0.0,
                semantic_suspicion=[f"发票分析过程出现异常: {str(e)}"]
            )
    
    async def analyze_non_invoice_document(
        self,
        document_text: str,
        original_filename: str,
        tenant_id: str,
        user_id: Optional[str] = None
    ) -> InvoiceLLMExtraction:
        """
        分析非发票文档（如名单、表格等）
        
        Args:
            document_text: 文档文本（已提取）
            original_filename: 原始文件名
            tenant_id: 租户ID
            user_id: 用户ID（可选）
            
        Returns:
            InvoiceLLMExtraction: 大模型提取结果（适配非发票文档）
        """
        self._ensure_initialized()
        
        if self._llm_adapter is None:
            logger.error("❌ [认知层] LLM 适配器未初始化，返回空结果")
            return InvoiceLLMExtraction(
                confidence=0.0,
                semantic_suspicion=["系统初始化失败，无法完成分析"]
            )
        
        logger.info(f"🤖 [认知层] 分析非发票文档...")
        logger.info(f"   - 文件名: {original_filename}")
        logger.info(f"   - 文本长度: {len(document_text)} 字符")
        logger.info(f"   - 租户ID: {tenant_id}")
        
        try:
            system_prompt = self._get_non_invoice_system_prompt()
            user_prompt = self._build_non_invoice_analysis_prompt(document_text, original_filename)
            
            full_prompt = f"{system_prompt}\n\n{user_prompt}"
            
            logger.info(f"📝 [认知层] 发送请求到 LLM，提示词长度: {len(full_prompt)} 字符")
            
            llm_response = await self._llm_adapter.generate(
                prompt=full_prompt,
                temperature=0.3
            )
            
            response_text = llm_response.content if hasattr(llm_response, 'content') else str(llm_response)
            
            logger.info(f"📥 [认知层] 收到 LLM 响应，长度: {len(response_text)} 字符")
            
            extraction = self._parse_non_invoice_result({"response": response_text}, document_text, original_filename)
            
            logger.info(f"✅ [认知层] 分析完成，置信度: {extraction.confidence:.2f}")
            if extraction.semantic_suspicion:
                for suspicion in extraction.semantic_suspicion:
                    logger.info(f"   ⚠️ {suspicion}")
            
            return extraction
            
        except Exception as e:
            logger.error(f"❌ [认知层] 非发票文档分析失败: {e}")
            return InvoiceLLMExtraction(
                confidence=0.0,
                semantic_suspicion=[f"文档分析失败: {str(e)}"]
            )
    
    def _get_non_invoice_system_prompt(self) -> str:
        """获取非发票文档分析系统提示词"""
        return """你是一位专业的文档分析助手，负责分析各种Excel文档、名单、表格等非发票类文档。

## 你的职责
1. 识别文档类型和内容结构
2. 提取文档中的关键信息
3. 对文档内容进行合理的解读和分析
4. 输出置信度

## 重要说明
- 这份文档不是发票，不要尝试从中提取发票字段
- 如果文档中包含财务数据，可以尝试提取
- 如果文档是名单、表格等，如实描述其内容
- 在 semantic_suspicion 中说明文档的实际内容和你对其的判断

## 禁止事项
- 绝对不要输出 risk_level、risk_score 或任何风险判定
- 绝对不要进行数字比较和阈值判断
- 风险判定是控制层（Python 代码）的职责

## 输出格式要求
返回一个结构化的 JSON 对象，包含以下字段：
- amount: 如果文档中有金额信息则提取，否则设为 0
- tax_amount: 如果文档中有税额信息则提取，否则设为 0
- tax_rate: 如果文档中有税率信息则提取，否则设为 0.0
- invoice_number: "非发票文档"（固定值）
- invoice_date: 如果有日期信息则提取，否则设为 "未找到"
- invoice_type: 文档类型，如"名单"、"表格"、"财务表"等
- seller_name: "非发票文档"（固定值）
- seller_tax_id: "非发票文档"（固定值）
- buyer_name: "非发票文档"（固定值）
- buyer_tax_id: "非发票文档"（固定值）
- items: 空列表（固定值）
- semantic_suspicion: 描述文档的实际内容和你的判断
- confidence: 你对分析结果的置信度（0-1）
- raw_analysis: 你的原始分析文本"""
    
    def _build_non_invoice_analysis_prompt(self, document_text: str, filename: str) -> str:
        """构建非发票文档分析提示词"""
        return f"""请分析以下文档，这不是发票，而是一份普通的Excel文档或表格。

## 文件名
{filename}

## 文档文本
```
{document_text}
```

## 要求
1. 识别文档类型（名单、表格、财务表等）
2. 描述文档的主要内容
3. 如果有金额、日期等结构化数据，可以提取
4. 如实评估你的置信度
5. 在 semantic_suspicion 中说明文档的实际内容

请直接输出 JSON，不要使用 markdown 代码块标记。"""
    
    def _parse_non_invoice_result(
        self,
        result: Dict[str, Any],
        original_text: str,
        filename: str
    ) -> InvoiceLLMExtraction:
        """解析非发票文档分析结果"""
        try:
            if isinstance(result, dict):
                if "response" in result:
                    raw_text = result["response"]
                elif "content" in result:
                    raw_text = result["content"]
                else:
                    raw_text = json.dumps(result, ensure_ascii=False)
            else:
                raw_text = str(result)
            
            extracted_data = self._extract_json_from_text(raw_text)
            
            if extracted_data:
                return InvoiceLLMExtraction(
                    amount=extracted_data.get("amount", 0),
                    tax_amount=extracted_data.get("tax_amount", 0),
                    tax_rate=extracted_data.get("tax_rate", 0.0),
                    invoice_number=extracted_data.get("invoice_number", "非发票文档"),
                    invoice_date=extracted_data.get("invoice_date", "未找到"),
                    invoice_type=extracted_data.get("invoice_type", "未知文档"),
                    seller_name=extracted_data.get("seller_name", "非发票文档"),
                    seller_tax_id=extracted_data.get("seller_tax_id", "非发票文档"),
                    buyer_name=extracted_data.get("buyer_name", "非发票文档"),
                    buyer_tax_id=extracted_data.get("buyer_tax_id", "非发票文档"),
                    items=extracted_data.get("items", []),
                    semantic_suspicion=extracted_data.get("semantic_suspicion", [
                        f"文档 '{filename}' 不是发票，已作为普通文档分析"
                    ]),
                    confidence=extracted_data.get("confidence", 0.5),
                    raw_analysis=extracted_data.get("raw_analysis", raw_text)
                )
            
            return InvoiceLLMExtraction(
                amount=0,
                tax_amount=0,
                tax_rate=0.0,
                invoice_number="非发票文档",
                invoice_date="未找到",
                invoice_type="未知文档",
                seller_name="非发票文档",
                seller_tax_id="非发票文档",
                buyer_name="非发票文档",
                buyer_tax_id="非发票文档",
                items=[],
                semantic_suspicion=[f"文档 '{filename}' 不是发票文件，无法提取发票信息，请人工审核"],
                confidence=0.3,
                raw_analysis=raw_text
            )
            
        except Exception as e:
            logger.warning(f"⚠️ [认知层] 解析非发票文档结果失败: {e}")
            return InvoiceLLMExtraction(
                amount=0,
                tax_amount=0,
                tax_rate=0.0,
                invoice_number="非发票文档",
                invoice_date="未找到",
                invoice_type="未知文档",
                seller_name="非发票文档",
                seller_tax_id="非发票文档",
                buyer_name="非发票文档",
                buyer_tax_id="非发票文档",
                items=[],
                semantic_suspicion=[f"文档分析异常: {str(e)}"],
                confidence=0.0,
                raw_analysis=str(result)
            )
    
    def _get_invoice_system_prompt(self) -> str:
        """获取发票分析系统提示词（从文件加载增强版）"""
        try:
            from pathlib import Path
            
            # 优先加载增强版提示词
            enhanced_prompt_path = Path(__file__).parent.parent.parent / "prompts" / "agents" / "tax" / "invoice_recognition_enhanced.md"
            default_prompt_path = Path(__file__).parent.parent.parent / "prompts" / "agents" / "tax" / "invoice_recognition.md"
            
            prompt_path = enhanced_prompt_path if enhanced_prompt_path.exists() else default_prompt_path
            
            if prompt_path.exists():
                with open(prompt_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    prompt_type = "增强版" if "enhanced" in str(prompt_path) else "标准版"
                    logger.info(f"✅ [认知层] 从文件加载发票识别提示词（{prompt_type}）: {prompt_path}")
                    return content
            else:
                logger.warning(f"⚠️ [认知层] 提示词文件不存在: {prompt_path}，使用内置提示词")
                return self._get_builtin_invoice_prompt()
        except Exception as e:
            logger.error(f"❌ [认知层] 加载提示词文件失败: {e}，使用内置提示词")
            return self._get_builtin_invoice_prompt()
    
    def _get_builtin_invoice_prompt(self) -> str:
        """内置发票分析提示词（备用）"""
        return """你是一位专业的发票审查员，负责从发票文本中提取结构化信息。

## 你的职责（严格遵守）
1. 提取发票中的事实信息（金额、税率、发票号等）
2. 识别语义层面的可疑点（建议性，非判定性）
3. 诚实报告你的置信度

## 缺失数据处理规则（关键）
如果某些字段无法从文本中识别：
- **金额字段**：设为 0（如金额、税额、税率、价税合计）
- **其他字段**：标记为缺失（如发票号码、开票日期、购销方名称）

## 重要提醒
1. **不要留空**：所有字段必须有值，缺失的设为 0 或 "未找到"
2. **明确标注**：在 semantic_suspicion 中明确说明哪些字段缺失
3. **计算验证**：如果金额和税率明确，必须计算税额
4. **合理置信度**：根据缺失字段数量合理评估置信度

## 禁止事项
- 绝对不要输出 risk_level、risk_score 或任何风险判定
- 绝对不要进行数字比较和阈值判断
- 风险判定是控制层（Python 代码）的职责

## 输出格式要求
你必须返回一个结构化的 JSON 对象，包含以下字段：
- amount: 发票总金额（含税），缺失设为 0
- tax_amount: 税额，缺失设为 0
- tax_rate: 税率（如 0.13 表示 13%），缺失设为 0.0
- invoice_number: 发票号码，缺失设为 "未找到"
- invoice_date: 开票日期，缺失设为 "未找到"
- invoice_type: 发票类型
- seller_name: 销售方名称，缺失设为 "未找到"
- seller_tax_id: 销售方税号
- buyer_name: 购买方名称，缺失设为 "未找到"
- buyer_tax_id: 购买方税号
- items: 商品明细列表（每项包含 name, quantity, unit_price, amount, tax）
- semantic_suspicion: 语义层面的可疑点列表，必须包含所有缺失字段的说明
- confidence: 你对提取结果的置信度（0-1）
- raw_analysis: 你的原始分析文本

## 语义可疑性识别示例
- "⚠️ 缺失字段：税额（未找到明确的税额标注，设为0）"
- "⚠️ 缺失字段：购买方税号（文本中未包含）"
- "💡 建议：人工核实金额和税率信息"

注意：如果无法提取某个字段，将其设为 0（数值字段）或 "未找到"（文本字段），并在 semantic_suspicion 中明确说明原因。"""
    
    def _build_invoice_analysis_prompt(self, invoice_text: str) -> str:
        """构建发票分析提示词"""
        return f"""请分析以下发票文本，提取结构化信息并识别可能的可疑点。

## 发票文本
```
{invoice_text}
```

## 要求
1. 尽可能提取所有可见信息
2. 如果某些信息不可见或不确定，在对应字段填 null
3. 在 semantic_suspicion 中列出任何你发现的可疑点（即使是轻微的）
4. 如实评估你的置信度

请直接输出 JSON，不要使用 markdown 代码块标记。"""
    
    def _parse_analysis_result(
        self,
        result: Dict[str, Any],
        original_text: str
    ) -> InvoiceLLMExtraction:
        """解析 TaxSpecialist 返回结果"""
        try:
            if isinstance(result, dict):
                if "analysis_report" in result:
                    raw_text = result["analysis_report"]
                elif "response" in result:
                    raw_text = result["response"]
                elif "content" in result:
                    raw_text = result["content"]
                else:
                    raw_text = json.dumps(result, ensure_ascii=False)
            else:
                raw_text = str(result)
            
            extracted_data = self._extract_json_from_text(raw_text)
            
            if extracted_data:
                # 应用后处理：验证、调整、清洗
                extraction = self._post_process_extraction(extracted_data, original_text)
                return extraction
            
            return self._fallback_extraction(original_text, raw_text)
            
        except Exception as e:
            logger.warning(f"⚠️ [认知层] 解析结果失败，使用降级方案: {e}")
            return self._fallback_extraction(original_text, str(result))
    
    def _post_process_extraction(
        self,
        data: Dict[str, Any],
        original_text: str
    ) -> InvoiceLLMExtraction:
        """后处理提取结果：验证、调整、清洗"""
        try:
            # 1. 验证金额关系并调整置信度
            amount = data.get("amount", 0)
            tax_amount = data.get("tax_amount", 0)
            tax_rate = data.get("tax_rate", 0)
            
            confidence_adjustments = []
            semantic_suspicion = data.get("semantic_suspicion", [])
            
            # 验证金额计算
            if amount and tax_rate and tax_amount:
                expected_tax = round(amount * tax_rate, 2)
                if abs(expected_tax - tax_amount) < 0.1:
                    confidence_adjustments.append(("金额计算验证通过", 0.20))
                    semantic_suspicion.append("💡 金额计算验证通过：{} × {}% = {}".format(
                        amount, tax_rate * 100, tax_amount
                    ))
                else:
                    confidence_adjustments.append(("金额计算验证失败", -0.20))
                    semantic_suspicion.append("⚠️ 金额计算验证失败：{} × {}% = {}，但提取到 {}".format(
                        amount, tax_rate * 100, expected_tax, tax_amount
                    ))
            
            # 2. 检查数据完整性并调整置信度
            required_fields = ["seller_name", "buyer_name", "amount", "tax_rate"]
            missing_fields = []
            for field in required_fields:
                if not data.get(field) or data.get(field) == "未找到" or data.get(field) == 0:
                    missing_fields.append(field)
            
            if missing_fields:
                confidence_adjustments.append(("缺少关键字段: {}".format(", ".join(missing_fields)), -0.15 * len(missing_fields)))
            
            # 3. 检查是否从乱码中提取
            if "乱码" in original_text or "| eae" in original_text or "fh | Sh:" in original_text:
                if data.get("seller_name") and data.get("seller_name") != "未找到":
                    confidence_adjustments.append(("成功从乱码中提取信息", 0.15))
                    semantic_suspicion.append("💡 成功从 OCR 乱码中提取关键信息")
            
            # 4. 计算最终置信度
            base_confidence = data.get("confidence", 0.5)
            for reason, adjustment in confidence_adjustments:
                base_confidence += adjustment
            
            # 限制置信度在 0-1 之间
            final_confidence = max(0.0, min(1.0, base_confidence))
            
            # 5. 清理和标准化数据
            cleaned_data = self._clean_extracted_data(data)
            
            logger.info(f"[认知层] 后处理完成: 置信度 {data.get('confidence', 0.5):.2f} -> {final_confidence:.2f}")
            for reason, adjustment in confidence_adjustments:
                logger.info(f"  - {reason}: {adjustment:+.2f}")
            
            return InvoiceLLMExtraction(
                amount=cleaned_data.get("amount"),
                tax_amount=cleaned_data.get("tax_amount"),
                tax_rate=cleaned_data.get("tax_rate"),
                invoice_number=cleaned_data.get("invoice_number"),
                invoice_date=cleaned_data.get("invoice_date"),
                invoice_type=cleaned_data.get("invoice_type"),
                seller_name=cleaned_data.get("seller_name"),
                seller_tax_id=cleaned_data.get("seller_tax_id"),
                buyer_name=cleaned_data.get("buyer_name"),
                buyer_tax_id=cleaned_data.get("buyer_tax_id"),
                items=cleaned_data.get("items", []),
                semantic_suspicion=semantic_suspicion,
                confidence=final_confidence,
                raw_analysis=data.get("raw_analysis", "")
            )
            
        except Exception as e:
            logger.warning(f"⚠️ [认知层] 后处理失败: {e}")
            # 返回原始数据，不做后处理
            return InvoiceLLMExtraction(
                amount=data.get("amount"),
                tax_amount=data.get("tax_amount"),
                tax_rate=data.get("tax_rate"),
                invoice_number=data.get("invoice_number"),
                invoice_date=data.get("invoice_date"),
                invoice_type=data.get("invoice_type"),
                seller_name=data.get("seller_name"),
                seller_tax_id=data.get("seller_tax_id"),
                buyer_name=data.get("buyer_name"),
                buyer_tax_id=data.get("buyer_tax_id"),
                items=data.get("items", []),
                semantic_suspicion=data.get("semantic_suspicion", []),
                confidence=data.get("confidence", 0.5),
                raw_analysis=data.get("raw_analysis", "")
            )
    
    def _clean_extracted_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """清理和标准化提取的数据"""
        import re
        
        cleaned = data.copy()
        
        # 清理公司名称
        for field in ["seller_name", "buyer_name"]:
            if field in cleaned and cleaned[field]:
                name = str(cleaned[field])
                # 移除乱码前缀
                name = re.sub(r'^\|?\s*eae\s*', '', name, flags=re.IGNORECASE)
                name = re.sub(r'^\|?\s*fh\s*\|?\s*', '', name, flags=re.IGNORECASE)
                # 清理多余空格和特殊字符
                name = re.sub(r'\s+', ' ', name).strip()
                cleaned[field] = name
        
        # 清理税号
        for field in ["seller_tax_id", "buyer_tax_id"]:
            if field in cleaned and cleaned[field]:
                tax_id = str(cleaned[field])
                # 移除空格和特殊字符
                tax_id = re.sub(r'[\s\-_]', '', tax_id)
                cleaned[field] = tax_id
        
        # 清理金额字段 - 处理科学计数法和异常值
        for field in ["amount", "tax_amount"]:
            if field in cleaned and cleaned[field] is not None:
                try:
                    value = float(cleaned[field])
                    
                    # 检测科学计数法或异常大的值（如 2.532e+19）
                    # 或者值看起来不合理（小于1但又不是正常的金额）
                    if abs(value) > 1e10 or 'e+' in str(cleaned[field]).lower():
                        logger.warning(f"[认知层] 检测到异常值 {field}={value}，尝试修正")
                        # 如果是金额或税额，设为 0 让降级方案重新提取
                        if field in ["amount", "tax_amount"]:
                            cleaned[field] = None
                            continue
                    
                    # 验证金额合理性：税额不应该大于金额（如果有的话）
                    if field == "tax_amount" and cleaned.get("amount") and cleaned.get("amount") > 0:
                        amount = float(cleaned.get("amount", 0))
                        if amount > 0 and value > amount:
                            logger.warning(f"[认知层] 税额 {value} 大于金额 {amount}，尝试修正")
                            # 重新计算税额
                            if cleaned.get("tax_rate"):
                                tax_rate = float(cleaned.get("tax_rate", 0))
                                if 0 < tax_rate <= 1:
                                    cleaned[field] = round(amount * tax_rate, 2)
                                    logger.info(f"[认知层] 自动修正税额: {amount} × {tax_rate} = {cleaned[field]}")
                                    continue
                                else:
                                    # 如果没有有效的税率信息，也设为 None 让降级方案重新提取
                                    cleaned[field] = None
                                    continue
                            else:
                                # 如果没有税率信息，也设为 None 让降级方案重新提取
                                cleaned[field] = None
                                continue
                    
                    # 验证税额与税率的一致性（如果金额也正常的话）
                    if field == "tax_amount" and cleaned.get("amount") and cleaned.get("amount") > 0 and cleaned.get("tax_rate"):
                        amount = float(cleaned.get("amount", 0))
                        tax_rate = float(cleaned.get("tax_rate", 0))
                        if amount > 0 and tax_rate > 0 and value > 0:  # 只有当税额大于0时才验证
                            expected_tax = round(amount * tax_rate, 2)
                            # 如果税额与期望值差距超过 20%，认为是异常值
                            # 例如：金额 75.47，税率 6%，期望税额 4.53
                            # 如果税额是 2.532（明显错误），差距 = |2.532 - 4.53| / 4.53 = 44% > 20%
                            if abs(value - expected_tax) / max(expected_tax, 1) > 0.2:
                                logger.warning(f"[认知层] 税额 {value} 与期望值 {expected_tax} 差距过大，重新计算")
                                cleaned[field] = expected_tax
                                logger.info(f"[认知层] 自动修正税额: {amount} × {tax_rate} = {expected_tax}")
                                continue
                except (ValueError, TypeError):
                    cleaned[field] = 0
        
        # 清理税率字段
        if "tax_rate" in cleaned and cleaned["tax_rate"] is not None:
            try:
                value = float(cleaned["tax_rate"])
                # 如果税率大于1（例如 13），转换为小数（例如 0.13）
                if value > 1:
                    value = value / 100
                cleaned["tax_rate"] = round(value, 4)
            except (ValueError, TypeError):
                cleaned["tax_rate"] = 0.0
        
        return cleaned
    
    def _extract_json_from_text(self, text: str) -> Optional[Dict[str, Any]]:
        """从文本中提取 JSON"""
        text = text.strip()
        
        json_patterns = [
            r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}',
            r'```json\s*([\s\S]*?)\s*```',
            r'```\s*([\s\S]*?)\s*```'
        ]
        
        for pattern in json_patterns:
            import re
            matches = re.findall(pattern, text, re.DOTALL)
            for match in matches:
                try:
                    return json.loads(match.strip())
                except json.JSONDecodeError:
                    continue
        
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        
        return None
    
    def _fallback_extraction(
        self,
        original_text: str,
        raw_analysis: str
    ) -> InvoiceLLMExtraction:
        """降级提取方案（当 JSON 解析失败时）"""
        import re
        
        extraction = InvoiceLLMExtraction(
            confidence=0.3,
            raw_analysis=raw_analysis,
            semantic_suspicion=["无法完整解析发票，建议人工复核"]
        )
        
        text_to_parse = original_text + "\n" + raw_analysis
        
        patterns = {
            "amount": [
                r'¥([\d,]+\.?\d*)',
                r'\*\*金额\*\*[：:]\s*¥?([\d,]+\.?\d*)',
                r'(?:金额|总额|价税合计)[：:]\s*¥?([\d,]+\.?\d*)',
                r'金额[：:]\*?([\d,]+\.?\d*)',
                r'\*\*金额\*\*[：:]\*?([\d,]+\.?\d*)',
                r'([\d]+\.[\d]{2})(?:\s|$|\n)',  # 匹配标准金额格式 75.47
                r'(?:^|\n)\s*([\d]+\.[\d]{2})\s*(?:\n|%)',  # 匹配表格中的金额
            ],
            "tax_amount": [
                r'\*\*税额估算\*\*[：:]\s*¥?([\d,]+\.?\d*)',
                r'税额估算[：:]\s*¥?([\d,]+\.?\d*)',
                r'(?:税额|增值税)[：:]\s*¥?([\d,]+\.?\d*)',
                r'税额[：:]\*?([\d,]+\.?\d*)',
            ],
            "tax_rate": [
                r'\*\*适用税率\*\*[：:]\s*(\d+(?:\.\d+)?)',
                r'适用税率[：:]\s*(\d+(?:\.\d+)?)',
                r'\*\*税率\*\*[：:]\s*(\d+(?:\.\d+)?)\s*%',
                r'(?:税率)[：:]\s*(\d+(?:\.\d+)?)\s*%',
                r'税率[：:]\s*(\d+(?:\.\d+)?)\s*%',
                r'税率[：:]\*?(\d+(?:\.\d+)?)',
                r'税率[：:]\*?(\d+(?:\.\d+)?)\s*%',
                r'(?:^|\n)\s*(\d+)%\s*(?:\n|$)',  # 支持表格中的税率格式 6%
            ],
            "invoice_number": [
                r'\*\*税号\*\*[：:]\s*([A-Z0-9]+)',
                r'(?:发票号|发票编号)[：:]\s*([A-Z0-9]+)',
                r'发票号[：:]\*?([A-Z0-9]+)',
                r'发票号码[：:\s]+([0-9]{20})',  # 支持20位发票号码
            ],
            "invoice_date": [
                r'\*\*税务期间\*\*[：:]\s*(\d{4}[-/年]\d{1,2}[-/月]\d{0,2}[日]?)',
                r'(?:开票日期|开票时间)[：:]\s*(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日]?)',
                r'(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日]?)',
                r'\d{4}年\d{1,2}月\d{1,2}日',
            ]
        }
        
        for field, field_patterns in patterns.items():
            for pattern in field_patterns:
                match = re.search(pattern, text_to_parse)
                if match:
                    value = match.group(1).replace(',', '')
                    try:
                        if field in ["amount", "tax_amount"]:
                            setattr(extraction, field, float(value))
                        elif field == "tax_rate":
                            rate = float(value)
                            if rate > 1:
                                rate = rate / 100
                            setattr(extraction, field, rate)
                        else:
                            setattr(extraction, field, value)
                        break
                    except (ValueError, IndexError):
                        continue

        # 自动计算税额（如果金额和税率都提取到了，但税额没有）
        if extraction.amount and extraction.tax_rate and not extraction.tax_amount:
            calculated_tax = round(extraction.amount * extraction.tax_rate, 2)
            extraction.tax_amount = calculated_tax
            logger.info(f"[认知层] 自动计算税额: {extraction.amount} × {extraction.tax_rate} = {calculated_tax}")

        return extraction


async def quick_analyze_invoice(
    invoice_text: str,
    tenant_id: str,
    user_id: Optional[str] = None
) -> InvoiceLLMExtraction:
    """
    快速分析发票（便捷函数）
    
    适用于单次分析场景，无需手动创建 InvoiceCognitionService
    
    Args:
        invoice_text: 发票文本
        tenant_id: 租户ID
        user_id: 用户ID（可选）
        
    Returns:
        InvoiceLLMExtraction: 分析结果
    """
    service = InvoiceCognitionService()
    return await service.analyze_invoice(invoice_text, tenant_id, user_id)


async def quick_analyze_non_invoice_document(
    document_text: str,
    filename: str,
    tenant_id: str,
    user_id: Optional[str] = None
) -> InvoiceLLMExtraction:
    """
    快速分析非发票文档（便捷函数）
    
    适用于单次分析场景，无需手动创建 InvoiceCognitionService
    
    Args:
        document_text: 文档文本
        filename: 原始文件名
        tenant_id: 租户ID
        user_id: 用户ID（可选）
        
    Returns:
        InvoiceLLMExtraction: 分析结果
    """
    service = InvoiceCognitionService()
    return await service.analyze_non_invoice_document(document_text, filename, tenant_id, user_id)