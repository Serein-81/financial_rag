请快速审查以下输出是否有明显问题。

【用户问题】
{user_query}

【AI 输出】
{output}

【快速检查项】
1. 是否为空或过短（<10字）？
2. 是否包含敏感信息（密码、密钥等）？
3. 是否包含内部标记（[xxx]、__xxx__等）？
4. 开头是否机械化（抱歉、根据显示等）？

请返回 JSON：
{{
    "has_issues": true/false,
    "issue_type": "sensitive|internal|empty|mechanical|other|none",
    "quick_score": 0-10
}}
