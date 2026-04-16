"""
PolicyNotificationAgent API 测试脚本

用于快速测试 PolicyNotificationAgent 的各个 API 端点
使用方法: python tests/test_policy_agent_api.py
"""

import asyncio
from typing import Dict, Any
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.policy_notification_agent_service import get_agent_service
from app.services.policy_notification_agent_service import PolicyNotificationAgentService


class PolicyAgentAPITester:
    """PolicyNotificationAgent API 测试器"""
    
    def __init__(self):
        self.service: PolicyNotificationAgentService = None
        self.test_data = self._load_test_data()
    
    def _load_test_data(self) -> Dict[str, Any]:
        """加载测试数据"""
        return {
            "policy": {
                "policy_id": "POL-TAX-2024-001",
                "title": "关于进一步支持高新技术企业发展的税收优惠政策",
                "content": """为深入实施创新驱动发展战略，进一步支持高新技术企业创新发展，现就有关税收优惠政策公告如下：

一、减按税率征收企业所得税
国家需要重点扶持的高新技术企业，减按15%的税率征收企业所得税。

二、研发费用加计扣除
企业开展研发活动中实际发生的研发费用，未形成无形资产计入当期损益的，在按规定据实扣除的基础上，再按照实际发生额的100%在税前加计扣除。

三、技术转让所得减免
一个纳税年度内，居民企业技术转让所得不超过500万元的部分，免征企业所得税；超过500万元的部分，减半征收企业所得税。

四、适用范围
本政策适用于经认定的高新技术企业，以及符合条件的科技型中小企业。""",
                "source": "manual",
                "priority": "high"
            },
            "enterprise": {
                "enterprise_id": "ENT-TECH-2024",
                "enterprise_name": "北京科技创新有限公司",
                "industry": "信息技术",
                "region": "北京",
                "scale": "medium",
                "tax_types": ["增值税", "企业所得税"],
                "qualifications": ["高新技术企业", "软件企业"]
            },
            "policies": [
                {
                    "policy_id": "POL-TAX-001",
                    "title": "高新技术企业税收优惠",
                    "content": "国家需要重点扶持的高新技术企业，减按15%的税率征收企业所得税。研发费用可加计扣除100%。",
                    "priority": "high"
                },
                {
                    "policy_id": "POL-INNOV-002",
                    "title": "企业研发费用补贴",
                    "content": "对符合条件的企业研发费用，按实际支出的30%给予补贴，单个企业最高补贴500万元。",
                    "priority": "high"
                },
                {
                    "policy_id": "POL-TALENT-003",
                    "title": "高端人才引进奖励",
                    "content": "对引进海外留学人才和国内博士后的企业，给予每人20万元奖励。",
                    "priority": "medium"
                },
                {
                    "policy_id": "POL-DIGITAL-004",
                    "title": "数字化转型扶持",
                    "content": "支持中小企业数字化转型，购买数字化服务可获得50%的补贴。",
                    "priority": "medium"
                }
            ]
        }
    
    async def initialize(self):
        """初始化服务"""
        print("🔄 正在初始化 PolicyNotificationAgent 服务...")
        self.service = get_agent_service()
        
        if self.service.use_llm:
            print(f"✅ 服务初始化完成 - 使用 LLM: {self.service.agent.llm_adapter.__class__.__name__}")
        else:
            print("✅ 服务初始化完成 - 使用规则引擎模式")
    
    async def test_status(self):
        """测试智能体状态"""
        print("\n" + "="*60)
        print("📊 测试 1: 获取智能体状态")
        print("="*60)
        
        try:
            status = {
                "status": "healthy",
                "use_llm": self.service.use_llm,
                "llm_provider": self.service.agent.llm_adapter.__class__.__name__ if self.service.use_llm else None,
                "agent_capabilities": {
                    "policy_understanding": True,
                    "semantic_matching": self.service.use_llm,
                    "personalized_generation": self.service.use_llm,
                    "fallback_mode": not self.service.use_llm
                },
                "match_weights": self.service.agent.match_weights if self.service.agent else None
            }
            
            print("\n✅ 智能体状态:")
            print(f"   - 状态: {status['status']}")
            print(f"   - 使用 LLM: {status['use_llm']}")
            print(f"   - LLM 提供商: {status['llm_provider']}")
            print(f"   - 政策理解: {'✅' if status['agent_capabilities']['policy_understanding'] else '❌'}")
            print(f"   - 语义匹配: {'✅' if status['agent_capabilities']['semantic_matching'] else '❌'}")
            print(f"   - 个性化生成: {'✅' if status['agent_capabilities']['personalized_generation'] else '❌'}")
            print(f"   - 回退模式: {'✅' if status['agent_capabilities']['fallback_mode'] else '❌'}")
            
            return status
            
        except Exception as e:
            print(f"\n❌ 测试失败: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    async def test_match(self):
        """测试政策-企业匹配"""
        print("\n" + "="*60)
        print("🔍 测试 2: 政策-企业匹配")
        print("="*60)
        
        try:
            print(f"\n📝 匹配政策: {self.test_data['policy']['title']}")
            print(f"🏢 匹配企业: {self.test_data['enterprise']['enterprise_name']}")
            print("\n⏳ 正在进行匹配，请稍候...")
            
            match_result = await self.service.match_policy_for_enterprise(
                policy=self.test_data['policy'],
                enterprise_profile=self.test_data['enterprise']
            )
            
            print("\n✅ 匹配结果:")
            print(f"   - 总匹配度: {match_result['match_score']*100:.1f}%")
            print(f"   - 语义匹配: {match_result['semantic_score']*100:.1f}%")
            print(f"   - 行业匹配: {match_result['industry_score']*100:.1f}%")
            print(f"   - 地区匹配: {match_result['region_score']*100:.1f}%")
            print(f"   - 规模匹配: {match_result['scale_score']*100:.1f}%")
            print(f"   - 紧急度: {match_result['urgency_score']*100:.1f}%")
            print(f"   - 使用 LLM: {'✅' if match_result['use_llm'] else '❌'}")
            
            print("\n📌 匹配理由:")
            for i, reason in enumerate(match_result['reasons'], 1):
                print(f"   {i}. {reason}")
            
            return match_result
            
        except Exception as e:
            print(f"\n❌ 测试失败: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    async def test_notification(self):
        """测试通知生成"""
        print("\n" + "="*60)
        print("📝 测试 3: 生成个性化通知")
        print("="*60)
        
        try:
            print("\n📝 正在生成通知...")
            
            match_result = await self.test_match()
            if not match_result:
                print("⚠️ 跳过通知生成测试（匹配测试失败）")
                return None
            
            notification = await self.service.generate_notification(
                policy=self.test_data['policy'],
                enterprise_profile=self.test_data['enterprise'],
                match_result=match_result
            )
            
            print("\n✅ 通知生成完成:")
            print(f"   - 标题: {notification['title']}")
            print(f"   - 紧急度: {notification['urgency_level']}")
            print(f"   - 使用 LLM: {'✅' if notification['use_llm'] else '❌'}")
            
            print("\n📋 通知内容:")
            print(f"   {notification['content'][:200]}...")
            
            print("\n🎯 关键要点:")
            for i, point in enumerate(notification['key_points'], 1):
                print(f"   {i}. {point}")
            
            print("\n✅ 行动步骤:")
            for i, step in enumerate(notification['action_steps'], 1):
                print(f"   {i}. {step}")
            
            if notification.get('deadline'):
                print(f"\n⏰ 截止日期: {notification['deadline']}")
            
            return notification
            
        except Exception as e:
            print(f"\n❌ 测试失败: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    async def test_prioritize(self):
        """测试政策优先级排序"""
        print("\n" + "="*60)
        print("📊 测试 4: 政策优先级排序")
        print("="*60)
        
        try:
            print(f"\n📝 正在排序 {len(self.test_data['policies'])} 个政策...")
            
            prioritized = await self.service.prioritize_policies(
                policies=self.test_data['policies'],
                enterprise_profile=self.test_data['enterprise']
            )
            
            print(f"\n✅ 排序完成 - {len(prioritized)} 个政策")
            print("\n📊 优先级排序结果:")
            
            for i, policy in enumerate(prioritized, 1):
                print(f"\n   {i}. {policy.get('title', '未知')}")
                print(f"      - 政策ID: {policy.get('policy_id', 'N/A')}")
                print(f"      - 优先级: {policy.get('priority', 'N/A')}")
                print(f"      - 匹配度: {policy.get('match_score', 0)*100:.1f}%")
            
            return prioritized
            
        except Exception as e:
            print(f"\n❌ 测试失败: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    async def test_full_flow(self):
        """测试完整流程"""
        print("\n" + "="*60)
        print("🧪 测试 5: 完整流程测试")
        print("="*60)
        
        import time
        
        try:
            print("\n⏳ 正在运行完整流程测试...")
            print(f"   - 处理 {len(self.test_data['policies'])} 个政策")
            print(f"   - 企业: {self.test_data['enterprise']['enterprise_name']}")
            
            start_time = time.time()
            
            matches = []
            notifications = []
            
            for policy in self.test_data['policies']:
                print(f"\n   📝 处理政策: {policy['title']}")
                
                match_result = await self.service.match_policy_for_enterprise(
                    policy=policy,
                    enterprise_profile=self.test_data['enterprise']
                )
                matches.append(match_result)
                print(f"      ✅ 匹配完成: {match_result['match_score']*100:.1f}%")
                
                notification = await self.service.generate_notification(
                    policy=policy,
                    enterprise_profile=self.test_data['enterprise'],
                    match_result=match_result
                )
                notifications.append(notification)
                print("      ✅ 通知生成完成")
                
                await asyncio.sleep(0.5)
            
            prioritized = await self.service.prioritize_policies(
                policies=self.test_data['policies'],
                enterprise_profile=self.test_data['enterprise']
            )
            
            processing_time = time.time() - start_time
            
            print("\n✅ 完整流程测试完成:")
            print(f"   - 处理政策数: {len(self.test_data['policies'])}")
            print(f"   - 生成匹配数: {len(matches)}")
            print(f"   - 生成通知数: {len(notifications)}")
            print(f"   - 处理耗时: {processing_time:.2f}秒")
            print(f"   - 使用 LLM: {'✅' if self.service.use_llm else '❌'}")
            print(f"   - LLM 提供商: {self.service.agent.llm_adapter.__class__.__name__ if self.service.use_llm else 'N/A'}")
            
            return {
                "enterprise_id": self.test_data['enterprise']['enterprise_id'],
                "policies_processed": len(self.test_data['policies']),
                "matches": matches,
                "notifications": notifications,
                "prioritized_policies": prioritized,
                "use_llm": self.service.use_llm,
                "llm_provider": self.service.agent.llm_adapter.__class__.__name__ if self.service.use_llm else "fallback",
                "processing_time": processing_time
            }
            
        except Exception as e:
            print(f"\n❌ 测试失败: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    async def run_all_tests(self):
        """运行所有测试"""
        print("\n" + "🎯"*30)
        print("🧪 PolicyNotificationAgent 完整测试套件")
        print("🎯"*30)
        
        await self.initialize()
        
        await self.test_status()
        await self.test_match()
        await self.test_notification()
        await self.test_prioritize()
        await self.test_full_flow()
        
        print("\n" + "="*60)
        print("🎉 所有测试完成！")
        print("="*60)


async def main():
    """主函数"""
    tester = PolicyAgentAPITester()
    await tester.run_all_tests()


if __name__ == "__main__":
    print("\n🚀 启动 PolicyNotificationAgent API 测试...")
    print("⚠️  注意: 此测试直接调用服务层，不需要 HTTP 服务器\n")
    
    asyncio.run(main())
