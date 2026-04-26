#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
提示词引擎测试脚本

演示动态 Skills 加载功能
"""

import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from app.services.prompt_service import prompt_engine


def test_basic_render():
    """测试基础渲染（不加载 skills）"""
    print("=" * 80)
    print("测试 1: 基础渲染（不加载 Skills）")
    print("=" * 80)
    
    result = prompt_engine.render(
        template_name="agent_base",
        context={
            "role": "企业AI助手",
            "tools": [
                {"name": "search_enterprise_knowledge"},
                {"name": "get_weather"},
                {"name": "get_location_info"}
            ],
            "user_level": "normal"
        },
        load_skills=False  # 不加载 skills
    )
    
    print(result)
    print("\n")


def test_with_skills():
    """测试动态加载 Skills"""
    print("=" * 80)
    print("测试 2: 动态加载 Skills")
    print("=" * 80)
    
    result = prompt_engine.render(
        template_name="agent_base",
        context={
            "role": "企业AI助手",
            "tools": [
                {"name": "search_enterprise_knowledge"},
                {"name": "get_weather"},
                {"name": "get_location_info"}
            ],
            "user_level": "expert"
        },
        load_skills=True  # 自动加载 skills
    )
    
    print(result)
    print("\n")


def test_partial_skills():
    """测试部分工具加载 Skills"""
    print("=" * 80)
    print("测试 3: 部分工具加载 Skills（只加载天气工具）")
    print("=" * 80)
    
    result = prompt_engine.render(
        template_name="agent_base",
        context={
            "role": "天气助手",
            "tools": [
                {"name": "get_weather"}  # 只有天气工具
            ],
            "user_level": "normal"
        },
        load_skills=True
    )
    
    print(result)
    print("\n")


def test_list_skills():
    """测试列出所有可用的 Skills"""
    print("=" * 80)
    print("测试 4: 列出所有可用的 Skills")
    print("=" * 80)
    
    skills = prompt_engine.list_skills()
    print(f"可用的 Skills ({len(skills)} 个):")
    for skill in skills:
        print(f"  - {skill}")
    print("\n")


def test_create_new_skill():
    """测试创建新的 Skill"""
    print("=" * 80)
    print("测试 5: 创建新的 Skill")
    print("=" * 80)
    
    # 创建一个新的 skill
    prompt_engine.create_skill(
        tool_name="send_email",
        content="""## 工具：send_email

### 功能描述
邮件发送工具，支持发送文本邮件和附件。

### 使用场景
当用户需要发送邮件时调用此工具。

### 参数说明
- `to` (必填): 收件人邮箱地址
- `subject` (必填): 邮件主题
- `body` (必填): 邮件正文
- `attachments` (可选): 附件列表

### 调用示例
```
用户问题："给张三发一封邮件，主题是会议通知"
调用：send_email(to="zhangsan@example.com", subject="会议通知", body="...")
```

### 注意事项
1. 确保邮箱地址格式正确
2. 邮件内容要清晰、礼貌
3. 发送前确认收件人信息
"""
    )
    
    # 测试使用新创建的 skill
    result = prompt_engine.render(
        template_name="agent_base",
        context={
            "role": "办公助手",
            "tools": [
                {"name": "send_email"}
            ],
            "user_level": "normal"
        },
        load_skills=True
    )
    
    print(result)
    print("\n")


def main():
    """主函数"""
    print("\n")
    print("🚀 提示词引擎测试开始")
    print("\n")
    
    # 运行所有测试
    test_basic_render()
    test_with_skills()
    test_partial_skills()
    test_list_skills()
    test_create_new_skill()
    
    print("=" * 80)
    print("✅ 所有测试完成")
    print("=" * 80)


if __name__ == "__main__":
    main()
