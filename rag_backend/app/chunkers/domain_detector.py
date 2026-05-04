"""
领域检测器 (Domain Detector)

三级策略（从上到下优先级递减）：
1. 用户上传时选择的 KB category（显式指定，最高优先级）
2. 文件名启发式匹配
3. LLM 快速分类（极简 Prompt，单 token 输出）
"""

import logging
from typing import Optional
from app.services.llm_service import llm_service
from app.models.structured_document import StructuredDocument

logger = logging.getLogger(__name__)


class DomainDetector:
    """
    领域检测器：判断文档属于哪个领域。

    检测结果用于后续分派到不同的领域切块器。
    """

    # 文件名启发式规则
    FILENAME_PATTERNS = {
        "finance": [
            "财报", "审计", "财务", "利润表", "资产负债表",
            "现金流量表", "年报", "季报", "营收", "财务报告",
            "审计报告", "balance sheet", "income statement",
        ],
        "tax": [
            "税务", "税法", "增值税", "所得税", "发票",
            "纳税", "申报", "税收", "税率", "tax",
        ],
        "legal": [
            "合同", "协议", "法务", "条款", "律师", "诉讼",
            "判决", "裁定", "契约", "agreement", "contract",
        ],
    }

    async def detect(
        self,
        filename: str,
        parsed_doc: Optional[StructuredDocument] = None,
        kb_category: Optional[str] = None,
    ) -> str:
        """
        检测文档所属领域。

        Args:
            filename: 文件名
            parsed_doc: 已解析的结构化文档（可选，用于 LLM 分类）
            kb_category: 用户上传时指定的知识库分类（可选）

        Returns:
            "finance" | "tax" | "legal" | "general"
        """
        # 1. 用户显式指定
        if kb_category and kb_category in ("finance", "tax", "legal", "general"):
            logger.info(f"[DomainDetector] 用户指定领域: {kb_category}")
            return kb_category

        # 2. 文件名启发式
        domain_from_filename = self._detect_from_filename(filename)
        if domain_from_filename:
            logger.info(f"[DomainDetector] 文件名匹配领域: {domain_from_filename}")
            return domain_from_filename

        # 3. LLM 快速分类
        if parsed_doc:
            domain_from_llm = await self._llm_classify(parsed_doc)
            if domain_from_llm:
                logger.info(f"[DomainDetector] LLM 分类领域: {domain_from_llm}")
                return domain_from_llm

        # 4. 默认回退
        logger.info(f"[DomainDetector] 未检测到领域，默认: general")
        return "general"

    def _detect_from_filename(self, filename: str) -> Optional[str]:
        """通过文件名关键词匹配检测领域"""
        filename_lower = filename.lower()
        for domain, keywords in self.FILENAME_PATTERNS.items():
            if any(kw.lower() in filename_lower for kw in keywords):
                return domain
        return None

    async def _llm_classify(self, doc: StructuredDocument) -> Optional[str]:
        """
        使用 LLM 快速分类文档。

        Prompt 从 prompts/chunkers/domain_classify_prompt.md 加载。
        {preview} 占位符运行时替换为文档前 800 字符。
        """
        preview = doc.to_markdown()[:800]
        if not preview.strip():
            return None

        from app.prompts.loader import load_prompt_template
        prompt = load_prompt_template(
            "chunkers/domain_classify_prompt.md",
            preview=preview,
        )

        try:
            result = await llm_service.get_answer(prompt, [], [])
            result = result.strip().lower()
            if result in ("finance", "tax", "legal"):
                return result
            return "general"
        except Exception as e:
            logger.warning(f"[DomainDetector] LLM 分类失败: {e}")
            return None


# 全局单例
domain_detector = DomainDetector()
