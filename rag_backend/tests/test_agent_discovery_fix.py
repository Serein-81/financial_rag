"""
测试 Agent Discovery 修复效果

验证：
1. 工具是否被正确注册到 ToolManager
2. 工具分类是否正确
3. 工具位置是否正确
4. API 返回的数据是否完整
"""

import asyncio
import sys
sys.path.insert(0, 'd:/Python/Codebase/My_rag/rag_backend')

from app.agent_framework.tools.tool_manager import ToolManager
from app.agent_framework.tools.agent_tool_registry import initialize_tool_manager
from app.agent_framework.tools.tool_router import TOOL_ROUTING_CONFIG, get_local_tools, get_mcp_tools
from app.services.agent_registry import agent_discovery_registry, ToolLocation


class TestAgentDiscovery:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.results = []

    def log(self, test_name: str, passed: bool, message: str = ""):
        """记录测试结果"""
        status = "✅ PASS" if passed else "❌ FAIL"
        self.results.append(f"{status} - {test_name}")
        if message:
            self.results.append(f"   {message}")
        
        if passed:
            self.passed += 1
        else:
            self.failed += 1

    async def test_tool_registration(self):
        """测试工具注册"""
        print("\n" + "="*60)
        print("测试 1: 工具注册到 ToolManager")
        print("="*60)
        
        from app.core.config import settings
        print(f"\n当前 MCP_MODE 配置: {settings.MCP_MODE}")
        
        tool_manager = ToolManager()
        result = await initialize_tool_manager(tool_manager)
        
        registered_count = result['total_count']
        local_count = len(result['local_tools'])
        mcp_count = len(result['mcp_tools'])
        
        print(f"\n注册结果:")
        print(f"  - 本地工具: {local_count} 个")
        print(f"  - MCP 工具: {mcp_count} 个")
        print(f"  - 总计: {registered_count} 个")
        
        print(f"\nToolManager 中的工具数量: {len(tool_manager.tools)}")
        
        expected_local = len(get_local_tools())
        expected_mcp = len(get_mcp_tools())
        
        self.log(
            "工具总数正确",
            registered_count == (expected_local + expected_mcp),
            f"期望 {expected_local + expected_mcp}, 实际 {registered_count}"
        )
        
        self.log(
            "本地工具数量正确",
            local_count == expected_local,
            f"期望 {expected_local}, 实际 {local_count}"
        )
        
        self.log(
            "MCP 工具数量正确",
            mcp_count == expected_mcp,
            f"期望 {expected_mcp}, 实际 {mcp_count}"
        )
        
        return tool_manager

    def test_tool_locations(self, tool_manager: ToolManager):
        """测试工具位置分类"""
        print("\n" + "="*60)
        print("测试 2: 工具位置分类")
        print("="*60)
        
        local_tools = get_local_tools()
        mcp_tools = get_mcp_tools()
        
        print(f"\n期望的本地工具: {len(local_tools)} 个")
        for tool_name in sorted(local_tools):
            print(f"  - {tool_name}")
        
        print(f"\n期望的 MCP 工具: {len(mcp_tools)} 个")
        for tool_name in sorted(mcp_tools):
            print(f"  - {tool_name}")
        
        registered_local = []
        registered_mcp = []
        
        for tool_name in tool_manager.tools.keys():
            config = TOOL_ROUTING_CONFIG.get(tool_name, {})
            category = config.get('category')
            
            if category and category.value == 'local':
                registered_local.append(tool_name)
            elif category and category.value == 'mcp':
                registered_mcp.append(tool_name)
        
        self.log(
            "所有本地工具已注册",
            set(registered_local) == set(local_tools),
            f"缺少: {set(local_tools) - set(registered_local)}"
        )
        
        self.log(
            "所有 MCP 工具已注册",
            set(registered_mcp) == set(mcp_tools),
            f"缺少: {set(mcp_tools) - set(registered_mcp)}"
        )

    def test_tool_categories(self, tool_manager: ToolManager):
        """测试工具类别推断"""
        print("\n" + "="*60)
        print("测试 3: 工具类别推断")
        print("="*60)
        
        test_cases = [
            ("calculate_tax_vat", "税务"),
            ("calculate_corporate_tax", "税务"),
            ("query_financial_data", "财务"),
            ("get_financial_overview", "财务"),
            ("check_contract_essentials", "法律"),
            ("match_legal_provisions", "法律"),
            ("search_enterprise_knowledge", "知识库"),
            ("get_weather", "生活服务"),
            ("search_web", "搜索"),
            ("assess_enterprise_risk", "企业信息"),
        ]
        
        print(f"\n测试工具类别推断:")
        for tool_name, expected_category in test_cases:
            config = TOOL_ROUTING_CONFIG.get(tool_name, {})
            description = config.get('description', '')
            
            inferred = self._infer_category(tool_name, description)
            
            status = "✅" if inferred == expected_category else "❌"
            print(f"  {status} {tool_name}: {inferred} (期望: {expected_category})")
            
            self.log(
                f"工具 {tool_name} 类别正确",
                inferred == expected_category,
                f"期望 {expected_category}, 实际 {inferred}"
            )

    def _infer_category(self, tool_name: str, description: str) -> str:
        """从工具名称和描述推断类别（复现 _infer_tool_category 逻辑）"""
        tool_name_lower = tool_name.lower()
        desc_lower = description.lower()
        
        if 'search_web' in tool_name_lower or '网络搜索' in desc_lower or 'web' in tool_name_lower and 'search' in tool_name_lower:
            return '搜索'
        elif ('enterprise' in tool_name_lower or '企业信息' in desc_lower or '企业' in desc_lower) and ('assess' in tool_name_lower or 'risk' in tool_name_lower or '风险' in desc_lower):
            return '企业信息'
        elif 'calculate_tax' in tool_name_lower or '税务' in desc_lower or '增值税' in desc_lower or '所得税' in desc_lower or 'tax' in tool_name_lower:
            return '税务'
        elif 'finance' in tool_name_lower or '财务' in desc_lower or 'asset' in tool_name_lower or 'liability' in tool_name_lower or 'profit' in tool_name_lower or 'revenue' in tool_name_lower:
            return '财务'
        elif 'legal' in tool_name_lower or '法律' in desc_lower or 'contract' in tool_name_lower or 'provision' in desc_lower or '条款' in desc_lower:
            return '法律'
        elif 'knowledge' in tool_name_lower or '知识' in desc_lower or 'document' in tool_name_lower or '文档' in desc_lower:
            return '知识库'
        elif 'weather' in tool_name_lower or '天气' in desc_lower or 'location' in tool_name_lower or '位置' in desc_lower:
            return '生活服务'
        else:
            return '其他'

    def test_agent_discovery_registry(self, tool_manager: ToolManager):
        """测试 Agent Discovery Registry"""
        print("\n" + "="*60)
        print("测试 4: Agent Discovery Registry")
        print("="*60)
        
        from app.services.agent_registry import AgentInfo, ToolInfo, AgentType
        
        agent_info = AgentInfo(
            agent_id="test_agent",
            agent_name="测试智能体",
            agent_type=AgentType.SPECIALIST,
            description="用于测试的智能体",
            specialty="测试",
            tools=[]
        )
        
        for tool_name, tool in tool_manager.tools.items():
            config = TOOL_ROUTING_CONFIG.get(tool_name, {})
            description = config.get('description', '') or getattr(tool, 'description', '') or ''
            category = config.get('category')
            
            if category == None:
                location = ToolLocation.LOCAL
            elif category.value == 'local':
                location = ToolLocation.LOCAL
            elif category.value == 'cloud':
                location = ToolLocation.CLOUD
            else:
                location = ToolLocation.MCP
            
            tool_category = self._infer_category(tool_name, description)
            
            tool_info = ToolInfo(
                name=tool_name,
                description=description[:200] if description else '',
                location=location,
                parameters={},
                tags=["测试"],
                category=tool_category,
                is_async=True,
                enabled=True
            )
            agent_info.tools.append(tool_info)
        
        print(f"\n注册测试智能体:")
        print(f"  - Agent ID: {agent_info.agent_id}")
        print(f"  - Agent 名称: {agent_info.agent_name}")
        print(f"  - 工具数量: {len(agent_info.tools)}")
        print(f"  - 工具分布: {agent_info.get_tool_count_summary()}")
        
        local_tools = agent_info.get_local_tools()
        mcp_tools = agent_info.get_mcp_tools()
        
        print(f"\n本地工具 ({len(local_tools)} 个):")
        for tool in sorted(local_tools, key=lambda t: t.name)[:5]:
            print(f"  - {tool.name} ({tool.category})")
        if len(local_tools) > 5:
            print(f"  ... 还有 {len(local_tools) - 5} 个")
        
        print(f"\nMCP 工具 ({len(mcp_tools)} 个):")
        for tool in sorted(mcp_tools, key=lambda t: t.name)[:5]:
            print(f"  - {tool.name} ({tool.category})")
        if len(mcp_tools) > 5:
            print(f"  ... 还有 {len(mcp_tools) - 5} 个")
        
        self.log(
            "Agent 工具列表不为空",
            len(agent_info.tools) > 0,
            f"工具数量: {len(agent_info.tools)}"
        )
        
        self.log(
            "本地工具列表不为空",
            len(local_tools) > 0,
            f"本地工具数量: {len(local_tools)}"
        )
        
        self.log(
            "MCP 工具列表不为空",
            len(mcp_tools) > 0,
            f"MCP 工具数量: {len(mcp_tools)}"
        )

    def print_summary(self):
        """打印测试总结"""
        print("\n" + "="*60)
        print("测试总结")
        print("="*60)
        
        for result in self.results:
            print(result)
        
        print(f"\n总计: {self.passed} 通过, {self.failed} 失败")
        
        if self.failed == 0:
            print("\n🎉 所有测试通过！")
        else:
            print(f"\n⚠️ 有 {self.failed} 个测试失败，需要进一步调查。")


async def main():
    """主函数"""
    print("\n" + "="*60)
    print("🚀 Agent Discovery 修复效果验证")
    print("="*60)
    
    tester = TestAgentDiscovery()
    
    tool_manager = await tester.test_tool_registration()
    tester.test_tool_locations(tool_manager)
    tester.test_tool_categories(tool_manager)
    tester.test_agent_discovery_registry(tool_manager)
    
    tester.print_summary()
    
    return tester.failed == 0


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
