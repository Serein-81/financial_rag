"""Shared helpers for compact blackboard payloads and final report inputs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from app.utils.json_compat import json


@dataclass
class BlackboardPayloadConfig:
    max_text_chars: int = 12000
    max_list_items: int = 20
    max_rag_doc_chars: int = 1200
    max_synthesis_payload_chars: int = 32000
    max_summary_chars: int = 4000


class BlackboardPayloadFormatter:
    """Compact large expert/RAG payloads before they are written to shared state."""

    LARGE_COLLECTION_KEYS = {"embedding", "vector", "vectors", "raw_documents", "documents", "chunks"}
    ERROR_ONLY_KEYS = {"success", "error", "fallback", "error_type"}

    def __init__(self, config: BlackboardPayloadConfig | None = None):
        self.config = config or BlackboardPayloadConfig()

    def truncate_text(self, text: Any, limit: int) -> str:
        text = "" if text is None else str(text)
        if len(text) <= limit:
            return text
        omitted = len(text) - limit
        return text[:limit].rstrip() + f"\n\n...[truncated {omitted} chars; full content remains in source data]"

    def compact_value(self, value: Any, depth: int = 0) -> Any:
        if depth >= 4:
            return self.truncate_text(value, 1000)

        if isinstance(value, str):
            limit = self.config.max_text_chars if depth == 0 else 4000
            return self.truncate_text(value, limit)

        if isinstance(value, dict):
            compacted: Dict[str, Any] = {}
            for key, item in value.items():
                if str(key).lower() in self.LARGE_COLLECTION_KEYS:
                    compacted[key] = self.summarize_large_collection(item)
                else:
                    compacted[key] = self.compact_value(item, depth + 1)
            return compacted

        if isinstance(value, list):
            items = value[: self.config.max_list_items]
            compacted_items = [self.compact_value(item, depth + 1) for item in items]
            if len(value) > len(items):
                compacted_items.append({"omitted_items": len(value) - len(items)})
            return compacted_items

        return value

    def summarize_large_collection(self, value: Any) -> Dict[str, Any]:
        if not isinstance(value, list):
            return {"preview": self.truncate_text(value, 1000), "truncated": True}

        samples = []
        for item in value[:5]:
            if isinstance(item, dict):
                samples.append(
                    {
                        "source": item.get("source") or item.get("id") or item.get("document_id"),
                        "score": item.get("score") or item.get("relevance_score"),
                        "preview": self.truncate_text(item.get("content") or item.get("text") or item, 500),
                    }
                )
            else:
                samples.append(self.truncate_text(item, 500))

        return {"count": len(value), "samples": samples, "truncated": len(value) > len(samples)}

    def compact_rag_docs(self, results: List[Any]) -> List[Dict[str, Any]]:
        docs = []
        for result in results[:5]:
            content = getattr(result, "content", "") or ""
            docs.append(
                {
                    "content": self.truncate_text(content, self.config.max_rag_doc_chars),
                    "source": getattr(result, "source", None),
                    "score": getattr(result, "relevance_score", None),
                    "original_chars": len(content),
                }
            )
        return docs

    def normalize_specialist_result(
        self,
        source: str,
        content: str,
        data: Dict[str, Any],
        confidence: float,
        success: bool,
    ) -> Dict[str, Any]:
        compact_data = self.compact_value(data if isinstance(data, dict) else {"value": data})
        compact_content = self.truncate_text(content, self.config.max_text_chars)
        return {
            "source": source,
            "content": compact_content,
            "data": compact_data,
            "confidence": confidence,
            "success": success,
            "blackboard_meta": {
                "schema_version": "specialist_result_v1",
                "content_chars": len(content or ""),
                "data_chars": len(json.dumps(data, ensure_ascii=False, default=str)) if data is not None else 0,
                "compacted": len(content or "") > len(compact_content),
            },
        }

    def prepare_synthesis_payload(self, specialist_results: list) -> Tuple[Dict[str, Any], list, list]:
        synthesis_data: Dict[str, Any] = {}
        failed_sources = []
        used_sources = []
        total_chars = 0

        for result in specialist_results:
            if not isinstance(result, dict):
                continue

            source = result.get("source", "unknown")
            data = result.get("data", {})
            success = result.get("success")
            if success is None and isinstance(data, dict):
                success = data.get("success")
            if success is False:
                failed_sources.append(source)
                continue

            if isinstance(data, dict) and self.ERROR_ONLY_KEYS.issuperset(data.keys()):
                continue

            compact_data = self.compact_value(data)
            content = result.get("content")
            payload = {
                "analysis": compact_data,
                "expert_summary": self.truncate_text(content, self.config.max_summary_chars) if content else "",
                "confidence": result.get("confidence", 0.0),
            }

            payload_chars = len(json.dumps(payload, ensure_ascii=False, default=str))
            if total_chars + payload_chars > self.config.max_synthesis_payload_chars:
                payload["analysis"] = {"summary": "Expert result was large; only a summary is retained for synthesis."}
                payload["expert_summary"] = self.truncate_text(
                    content or json.dumps(compact_data, ensure_ascii=False, default=str),
                    3000,
                )
                payload_chars = len(json.dumps(payload, ensure_ascii=False, default=str))

            synthesis_data[source] = payload
            used_sources.append(source)
            total_chars += payload_chars

        return synthesis_data, failed_sources, used_sources

    def ensure_final_markdown(self, text: str, user_query: str, used_sources: list, failed_sources: list) -> str:
        text = (text or "").strip()
        if not text:
            return ""

        if not text.lstrip().startswith("#"):
            text = f"## 综合分析报告\n\n{text}"

        required_sections = ["## 结论", "## 依据", "## 建议"]
        if any(section in text for section in required_sections):
            return text

        source_line = "、".join(used_sources) if used_sources else "系统分析"
        failed_line = f"\n\n> 部分专家未参与最终合成：{'、'.join(failed_sources)}" if failed_sources else ""
        return (
            f"## 结论\n\n{text}\n\n"
            f"## 依据\n\n- 用户问题：{user_query}\n"
            f"- 参与合成：{source_line}{failed_line}\n\n"
            "## 建议\n\n- 如需进一步分析，请补充具体期间、主体、金额或业务场景。"
        )
