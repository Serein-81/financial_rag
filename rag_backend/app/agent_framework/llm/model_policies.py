# app/agent_framework/llm/model_policies.py

"""
模型家族策略系统

针对不同模型家族的特殊处理策略
"""

from copy import deepcopy
from typing import Tuple, Dict, Optional


class ModelFamilyPolicy:
    """
    模型家族策略基类
    """

    @staticmethod
    def apply(model_name: str, gen_conf: Dict, request_kwargs: Dict) -> Tuple[Dict, Dict]:
        """
        应用模型策略

        Args:
            model_name: 模型名称
            gen_conf: 生成配置
            request_kwargs: 请求参数

        Returns:
            (sanitized_gen_conf, sanitized_kwargs)
        """
        return gen_conf, request_kwargs


class Qwen3Policy(ModelFamilyPolicy):
    """Qwen3 系列策略"""

    @staticmethod
    def apply(model_name: str, gen_conf: Dict, request_kwargs: Dict) -> Tuple[Dict, Dict]:
        model_name_lower = model_name.lower()
        sanitized_gen_conf = deepcopy(gen_conf) if gen_conf else {}
        sanitized_kwargs = dict(request_kwargs) if request_kwargs else {}

        if "qwen3" in model_name_lower:
            sanitized_kwargs["extra_body"] = {"enable_thinking": False}

        return sanitized_gen_conf, sanitized_kwargs


class GPT5Policy(ModelFamilyPolicy):
    """GPT-5 系列策略"""

    @staticmethod
    def apply(model_name: str, gen_conf: Dict, request_kwargs: Dict) -> Tuple[Dict, Dict]:
        model_name_lower = model_name.lower()
        sanitized_gen_conf = deepcopy(gen_conf) if gen_conf else {}
        sanitized_kwargs = dict(request_kwargs) if request_kwargs else {}

        if "gpt-5" in model_name_lower:
            sanitized_gen_conf = {}

        return sanitized_gen_conf, sanitized_kwargs


class HunYuanPolicy(ModelFamilyPolicy):
    """腾讯混元系列策略"""

    @staticmethod
    def apply(model_name: str, gen_conf: Dict, request_kwargs: Dict) -> Tuple[Dict, Dict]:
        model_name_lower = model_name.lower()
        sanitized_gen_conf = deepcopy(gen_conf) if gen_conf else {}
        sanitized_kwargs = dict(request_kwargs) if request_kwargs else {}

        if "hunyuan" in model_name_lower:
            for key in ("presence_penalty", "frequency_penalty"):
                sanitized_gen_conf.pop(key, None)

        return sanitized_gen_conf, sanitized_kwargs


class KimiK25Policy(ModelFamilyPolicy):
    """Kimi K2.5 系列策略"""

    @staticmethod
    def apply(model_name: str, gen_conf: Dict, request_kwargs: Dict) -> Tuple[Dict, Dict]:
        model_name_lower = model_name.lower()
        sanitized_gen_conf = deepcopy(gen_conf) if gen_conf else {}
        sanitized_kwargs = dict(request_kwargs) if request_kwargs else {}

        if "kimi-k2.5" in model_name_lower:
            reasoning = sanitized_gen_conf.pop("reasoning", None)
            thinking = {"type": "enabled"}

            if reasoning is not None:
                thinking = {"type": "enabled"} if reasoning else {"type": "disabled"}
            elif not isinstance(thinking, dict) or thinking.get("type") not in {"enabled", "disabled"}:
                thinking = {"type": "disabled"}

            sanitized_gen_conf["thinking"] = thinking

            thinking_enabled = thinking.get("type") == "enabled"
            sanitized_gen_conf["temperature"] = 1.0 if thinking_enabled else 0.6
            sanitized_gen_conf["top_p"] = 0.95
            sanitized_gen_conf["n"] = 1
            sanitized_gen_conf["presence_penalty"] = 0.0
            sanitized_gen_conf["frequency_penalty"] = 0.0

        return sanitized_gen_conf, sanitized_kwargs


class ModelPolicyManager:
    """
    模型策略管理器

    统一管理和应用各模型家族的特殊策略
    """

    def __init__(self):
        self.policies = {
            "qwen3": Qwen3Policy,
            "qwen_3": Qwen3Policy,
            "gpt-5": GPT5Policy,
            "gpt5": GPT5Policy,
            "hunyuan": HunYuanPolicy,
            "混元": HunYuanPolicy,
            "kimi-k2.5": KimiK25Policy,
            "kimi_k25": KimiK25Policy,
        }

    def apply_policies(
        self,
        model_name: str,
        gen_conf: Optional[Dict] = None,
        request_kwargs: Optional[Dict] = None
    ) -> Tuple[Dict, Dict]:
        """
        应用所有适用的模型策略

        Args:
            model_name: 模型名称
            gen_conf: 生成配置
            request_kwargs: 请求参数

        Returns:
            (sanitized_gen_conf, sanitized_kwargs)
        """
        model_name_lower = model_name.lower()
        sanitized_gen_conf = deepcopy(gen_conf) if gen_conf else {}
        sanitized_kwargs = dict(request_kwargs) if request_kwargs else {}

        for key, policy_class in self.policies.items():
            if key in model_name_lower:
                sanitized_gen_conf, sanitized_kwargs = policy_class.apply(
                    model_name, sanitized_gen_conf, sanitized_kwargs
                )

        return sanitized_gen_conf, sanitized_kwargs


model_policy_manager = ModelPolicyManager()


def apply_model_family_policies(
    model_name: str,
    gen_conf: Optional[Dict] = None,
    request_kwargs: Optional[Dict] = None
) -> Tuple[Dict, Dict]:
    """
    应用模型家族策略的便捷函数

    Args:
        model_name: 模型名称
        gen_conf: 生成配置
        request_kwargs: 请求参数

    Returns:
        (sanitized_gen_conf, sanitized_kwargs)
    """
    return model_policy_manager.apply_policies(model_name, gen_conf, request_kwargs)
