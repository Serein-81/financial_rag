"""
企业画像同步测试脚本
用于验证企业画像是否能正确同步到租户设置
"""

import asyncio
import logging
from typing import Dict, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_sync():
    """测试企业画像同步"""
    
    print("=" * 60)
    print("🧪 开始测试企业画像同步功能")
    print("=" * 60)
    
    try:
        from app.services.policy_retrieval_service import PolicyRetrievalService
        
        service = PolicyRetrievalService()
        
        test_profiles = [
            {
                "enterprise_id": "test_tenant_001",
                "name": "测试企业A",
                "industry": "软件开发",
                "region": "北京市",
                "scale": "小型企业",
                "tax_types": ["企业所得税", "增值税"]
            },
            {
                "enterprise_id": "test_tenant_002",
                "name": "测试企业B",
                "industry": "制造业",
                "region": "上海市",
                "scale": "中型企业",
                "tax_types": ["增值税", "消费税"]
            }
        ]
        
        for idx, profile in enumerate(test_profiles, 1):
            print(f"\n📋 测试 {idx}: {profile['name']}")
            print("-" * 60)
            
            try:
                await service._sync_enterprise_profile_to_settings(
                    profile["enterprise_id"],
                    profile
                )
                print(f"✅ 同步完成")
            except Exception as e:
                print(f"❌ 同步失败: {e}")
                import traceback
                traceback.print_exc()
        
        print("\n" + "=" * 60)
        print("✅ 测试完成")
        print("=" * 60)
        
    except Exception as e:
        logger.error(f"测试失败: {e}", exc_info=True)
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_sync())
