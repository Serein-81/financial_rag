"""
提示词管理系统

提供统一的提示词加载和管理功能
"""

from .loader import (
    AgentPromptLoader,
    AgentPromptRegistry,
    get_agent_prompt_loader,
    get_prompt_registry,
    load_agent_prompt,
    load_greeting_prompt,
    get_all_agents,
    list_available_agents,
    PromptLoader,
    load_prompt_file,
    load_prompt_template,
)

from .llm_functions import (
    TriageFunction,
    triage_document,
    QualityReviewFunction,
    review_quality,
)

__all__ = [
    'AgentPromptLoader',
    'AgentPromptRegistry',
    'get_agent_prompt_loader',
    'get_prompt_registry',
    'load_agent_prompt',
    'load_greeting_prompt',
    'get_all_agents',
    'list_available_agents',
    'PromptLoader',
    'load_prompt_file',
    'load_prompt_template',
    'TriageFunction',
    'triage_document',
    'QualityReviewFunction',
    'review_quality'
]
