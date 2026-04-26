"""
Agent 容错 Wrapper

实现"鞭打机制"：当 LLM 输出格式错误时，反向抽打模型重新输出
"""

import json
import re
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ValidationError:
    """验证错误"""
    error_type: str
    message: str
    field_path: Optional[str] = None


class AgentResponseValidator:
    """
    Agent 响应验证器
    
    验证 LLM 输出是否符合 blackboard_action 协议
    """
    
    REQUIRED_FIELDS = {
        "blackboard_action": {
            "type": "object",
            "required": ["status", "output_data"],
            "optional": ["new_sub_tasks", "error_message"]
        },
        "thought_process": {
            "type": "string",
            "required": False,
            "optional": True
        }
    }
    
    VALID_STATUSES = {"COMPLETED", "FAILED", "WAITING_DEPENDENCY"}
    
    @classmethod
    def validate(cls, response_text: str) -> tuple[bool, Optional[Dict[str, Any]], List[ValidationError]]:
        """
        验证响应是否符合协议
        
        Args:
            response_text: LLM 原始响应文本
            
        Returns:
            (is_valid, parsed_json, errors)
        """
        errors = []
        
        # 1. 尝试解析 JSON
        parsed_json = cls._try_parse_json(response_text)
        if parsed_json is None:
            errors.append(ValidationError(
                error_type="JSON_PARSE_ERROR",
                message="无法解析 JSON 格式",
                field_path="root"
            ))
            return False, None, errors
        
        # 2. 验证 blackboard_action 字段
        if "blackboard_action" not in parsed_json:
            errors.append(ValidationError(
                error_type="MISSING_FIELD",
                message="缺少 blackboard_action 字段",
                field_path="blackboard_action"
            ))
            return False, parsed_json, errors
        
        blackboard_action = parsed_json["blackboard_action"]
        
        # 3. 验证 status 字段
        if "status" not in blackboard_action:
            errors.append(ValidationError(
                error_type="MISSING_FIELD",
                message="缺少 status 字段",
                field_path="blackboard_action.status"
            ))
        elif blackboard_action["status"] not in cls.VALID_STATUSES:
            errors.append(ValidationError(
                error_type="INVALID_VALUE",
                message=f"status 必须是 {cls.VALID_STATUSES} 之一",
                field_path="blackboard_action.status"
            ))
        
        # 4. 验证 output_data 字段
        if "output_data" not in blackboard_action:
            errors.append(ValidationError(
                error_type="MISSING_FIELD",
                message="缺少 output_data 字段",
                field_path="blackboard_action.output_data"
            ))
        elif not isinstance(blackboard_action["output_data"], dict):
            errors.append(ValidationError(
                error_type="INVALID_TYPE",
                message="output_data 必须是对象类型",
                field_path="blackboard_action.output_data"
            ))
        
        # 5. 验证 error_message（如果 status 是 FAILED）
        if blackboard_action.get("status") == "FAILED" and not blackboard_action.get("error_message"):
            errors.append(ValidationError(
                error_type="MISSING_FIELD",
                message="status 为 FAILED 时必须提供 error_message",
                field_path="blackboard_action.error_message"
            ))
        
        is_valid = len([e for e in errors if e.error_type in {"MISSING_FIELD", "INVALID_VALUE", "INVALID_TYPE"}]) == 0
        
        return is_valid, parsed_json, errors
    
    @classmethod
    def _try_parse_json(cls, text: str) -> Optional[Dict[str, Any]]:
        """
        尝试解析 JSON
        
        支持从 Markdown 代码块中提取 JSON
        """
        if not text or not isinstance(text, str):
            return None
        
        text = text.strip()
        
        # 尝试直接解析
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        
        # 尝试从 ```json 代码块中提取
        json_block_pattern = r"```json\s*(.*?)\s*```"
        match = re.search(json_block_pattern, text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1).strip())
            except json.JSONDecodeError:
                pass
        
        # 尝试从 ``` 代码块中提取
        code_block_pattern = r"```\s*(.*?)\s*```"
        match = re.search(code_block_pattern, text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1).strip())
            except json.JSONDecodeError:
                pass
        
        # 尝试提取 JSON 对象（查找第一个 { 和最后一个 }）
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and start < end:
            try:
                return json.loads(text[start:end+1])
            except json.JSONDecodeError:
                pass
        
        return None


class AgentWrapper:
    """
    Agent 容错 Wrapper
    
    实现"鞭打机制"，当 LLM 输出格式错误时自动重试
    """
    
    DEFAULT_MAX_RETRIES = 3
    DEFAULT_WHIP_PROMPT = """你刚才输出的 JSON 格式违反了契约：
    
错误类型：{error_type}
错误信息：{error_message}
字段路径：{field_path}

请立即修正你的 JSON 并重新输出！

要求：
1. 必须包含 blackboard_action 字段
2. blackboard_action 必须包含 status 和 output_data
3. status 必须是 COMPLETED | FAILED | WAITING_DEPENDENCY 之一
4. 如果 status 是 FAILED，必须提供 error_message
5. output_data 必须是一个对象

请严格按照以下格式输出：
```json
{{
  "thought_process": "你的推理过程（简短）",
  "blackboard_action": {{
    "status": "COMPLETED | FAILED | WAITING_DEPENDENCY",
    "output_data": {{...}},
    "new_sub_tasks": [...],
    "error_message": "如果失败，填写原因"
  }}
}}
```
"""
    
    def __init__(
        self,
        agent,
        max_retries: int = DEFAULT_MAX_RETRIES,
        whip_prompt_template: Optional[str] = None
    ):
        """
        初始化 Agent Wrapper
        
        Args:
            agent: 原始 Agent 实例
            max_retries: 最大重试次数
            whip_prompt_template: 自定义鞭打提示模板
        """
        self.agent = agent
        self.max_retries = max_retries
        self.whip_prompt_template = whip_prompt_template or self.DEFAULT_WHIP_PROMPT
    
    async def run_with_retry(
        self,
        user_input: str,
        history: List[Dict] = None,
        task_context: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        带重试的 Agent 执行
        
        Args:
            user_input: 用户输入
            history: 对话历史
            task_context: 任务上下文（包含 task_id, retry_count, max_retries）
            **kwargs: 其他参数
            
        Returns:
            {
                "success": bool,
                "result": parsed_json,
                "attempts": int,
                "final_error": Optional[str]
            }
        """
        task_id = task_context.get("task_id") if task_context else None
        max_retries = task_context.get("max_retries", self.max_retries) if task_context else self.max_retries
        current_retry = task_context.get("retry_count", 0) if task_context else 0
        
        attempts = 0
        last_error = None
        last_valid_response = None
        
        while attempts < max_retries:
            attempts += 1
            
            logger.info(f"🔄 [AgentWrapper] 第 {attempts}/{max_retries} 次尝试" +
                       (f" (任务: {task_id})" if task_id else ""))
            
            try:
                # 调用 Agent 获取响应
                if attempts == 1:
                    # 首次调用，传入原始输入
                    response = await self.agent.run(user_input, history, **kwargs)
                else:
                    # 后续调用，追加鞭打提示
                    whip_prompt = self._build_whip_prompt(last_error)
                    enhanced_input = f"{user_input}\n\n{whip_prompt}"
                    response = await self.agent.run(enhanced_input, history, **kwargs)
                
                # 验证响应
                is_valid, parsed_json, errors = AgentResponseValidator.validate(response)
                
                if is_valid:
                    logger.info(f"✅ [AgentWrapper] 第 {attempts} 次尝试成功" +
                              (f" (任务: {task_id})" if task_id else ""))
                    
                    return {
                        "success": True,
                        "result": parsed_json,
                        "attempts": attempts,
                        "final_error": None
                    }
                else:
                    # 记录错误信息
                    error_summary = self._summarize_errors(errors)
                    last_error = error_summary
                    last_valid_response = parsed_json  # 保存部分有效的响应
                    
                    logger.warning(f"⚠️ [AgentWrapper] 第 {attempts} 次尝试验证失败: {error_summary}" +
                                 (f" (任务: {task_id})" if task_id else ""))
                
            except Exception as e:
                last_error = f"执行异常: {str(e)}"
                logger.error(f"❌ [AgentWrapper] 第 {attempts} 次尝试执行异常: {str(e)}" +
                           (f" (任务: {task_id})" if task_id else ""), exc_info=True)
        
        # 所有重试都失败了
        logger.error(f"❌ [AgentWrapper] 所有 {max_retries} 次尝试都失败了" +
                   (f" (任务: {task_id})" if task_id else ""))
        
        # 如果有部分有效的响应，返回它但标记为失败
        if last_valid_response:
            return {
                "success": False,
                "result": {
                    **last_valid_response,
                    "blackboard_action": {
                        **last_valid_response.get("blackboard_action", {}),
                        "status": "FAILED",
                        "error_message": f"重试 {max_retries} 次后仍无法获得有效响应。最后错误: {last_error}"
                    }
                },
                "attempts": attempts,
                "final_error": last_error
            }
        
        # 如果完全没有有效响应，返回错误响应
        return {
            "success": False,
            "result": {
                "thought_process": "执行失败",
                "blackboard_action": {
                    "status": "FAILED",
                    "output_data": {},
                    "new_sub_tasks": [],
                    "error_message": f"重试 {max_retries} 次后仍无法获得有效响应。最后错误: {last_error}"
                }
            },
            "attempts": attempts,
            "final_error": last_error
        }
    
    def _build_whip_prompt(self, error_summary: str) -> str:
        """
        构建鞭打提示
        
        Args:
            error_summary: 错误摘要
            
        Returns:
            鞭打提示文本
        """
        # 解析错误摘要，提取关键信息
        error_type = "VALIDATION_ERROR"
        field_path = "unknown"
        message = error_summary
        
        # 简单解析
        if "MISSING_FIELD" in error_summary:
            error_type = "MISSING_FIELD"
            if "blackboard_action" in error_summary:
                field_path = "blackboard_action"
            elif "status" in error_summary:
                field_path = "blackboard_action.status"
            elif "output_data" in error_summary:
                field_path = "blackboard_action.output_data"
        elif "INVALID_VALUE" in error_summary:
            error_type = "INVALID_VALUE"
        elif "INVALID_TYPE" in error_summary:
            error_type = "INVALID_TYPE"
        elif "JSON_PARSE" in error_summary:
            error_type = "JSON_PARSE_ERROR"
            field_path = "root"
        
        return self.whip_prompt_template.format(
            error_type=error_type,
            error_message=message,
            field_path=field_path
        )
    
    def _summarize_errors(self, errors: List[ValidationError]) -> str:
        """
        汇总错误信息
        
        Args:
            errors: 错误列表
            
        Returns:
            错误摘要字符串
        """
        if not errors:
            return "未知错误"
        
        summaries = []
        for error in errors:
            if error.error_type == "JSON_PARSE_ERROR":
                summaries.append("无法解析 JSON 格式")
            elif error.error_type == "MISSING_FIELD":
                summaries.append(f"缺少字段: {error.field_path}")
            elif error.error_type == "INVALID_VALUE":
                summaries.append(f"无效值: {error.message}")
            elif error.error_type == "INVALID_TYPE":
                summaries.append(f"无效类型: {error.message}")
            else:
                summaries.append(error.message)
        
        return "; ".join(summaries)


def wrap_agent(agent, max_retries: int = 3) -> AgentWrapper:
    """
    包装 Agent 实例
    
    Args:
        agent: 原始 Agent 实例
        max_retries: 最大重试次数
        
    Returns:
        AgentWrapper 实例
    """
    return AgentWrapper(agent, max_retries=max_retries)
