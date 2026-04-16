#!/usr/bin/env python3
# test_hybrid_simple.py

"""
简化的混合Agent测试
"""

import asyncio
import os
import sys
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
load_dotenv()

from app.services.hybrid_agent_service import hybrid_agent_service


async def test_simple_cases():
    """测试简单场景"""
    print("🧪 简化测试")
    print("=" * 40)
    
    test_cases = [
        ("工具链模式", "北京天气", "chain"),
        ("Agent模式", "人工智能的发展趋势", "agent"),
        ("自动路由", "上海天气怎么样", None),
    ]
    
    for name, question, mode in test_cases:
        print(f"\n🔍 {name}: {question}")
        
        try:
            answer = await hybrid_agent_service.chat(
                user_input=question,
                kb_id="test-kb-id",
                session_id=f"test-{name}",
                preferred_mode=mode
            )
            
            print(f"✅ 回答: {answer[:100]}...")
            
        except Exception as e:
            print(f"❌ 错误: {str(e)}")
    
    # 显示统计
    print("\n📊 执行统计:")
    stats = hybrid_agent_service.get_execution_statistics()
    for key, value in stats.items():
        if key.endswith('_executions') or key.endswith('_percentage'):
            print(f"   {key}: {value}")


if __name__ == "__main__":
    asyncio.run(test_simple_cases())