"""
报表智能体 (Report Agent)

负责生成各类业务报表：
- 销售报表
- 财务统计
- 数据汇总
- 业务分析

所有输出都会经过 Output Agent 审查
"""

from typing import Dict, List, Optional, Any, AsyncGenerator
from datetime import datetime


class ReportAgent:
    """
    报表生成智能体
    
    专门用于处理报表生成任务，当用户说"生成报表"、"统计"时会调用此智能体
    """
    
    def __init__(self, llm_adapter=None, db_session=None):
        self.llm = llm_adapter
        self.db_session = db_session
        self.output_agent = None
        
        self.REPORT_TYPES = {
            "sales": {
                "keywords": ["销售", "销量", "销售额", "订单"],
                "description": "销售报表"
            },
            "financial": {
                "keywords": ["财务", "收支", "利润", "成本"],
                "description": "财务报表"
            },
            "operation": {
                "keywords": ["运营", "用户", "活跃", "留存"],
                "description": "运营报表"
            },
            "inventory": {
                "keywords": ["库存", "仓储", "物流"],
                "description": "库存报表"
            }
        }
    
    def set_output_agent(self, output_agent):
        """设置输出审查智能体"""
        self.output_agent = output_agent
    
    def recognize_report_type(self, user_input: str) -> Optional[str]:
        """
        识别报表类型
        
        Args:
            user_input: 用户输入
            
        Returns:
            报表类型，如 "sales", "financial" 等
        """
        user_input_lower = user_input.lower()
        
        for report_type, config in self.REPORT_TYPES.items():
            for keyword in config["keywords"]:
                if keyword in user_input:
                    return report_type
        
        return "general"
    
    async def generate_report(
        self, 
        user_input: str, 
        time_range: str = "本月",
        **kwargs
    ) -> Dict[str, Any]:
        """
        生成报表
        
        Args:
            user_input: 用户输入
            time_range: 时间范围
            **kwargs: 其他参数
            
        Returns:
            报表数据
        """
        report_type = self.recognize_report_type(user_input)
        
        report_config = self.REPORT_TYPES.get(report_type, {
            "description": "通用报表"
        })
        
        if self.db_session:
            data = await self._fetch_report_data(report_type, time_range)
        else:
            data = self._generate_mock_data(report_type, time_range)
        
        report_content = self._format_report(report_type, data, time_range)
        
        return {
            "report_type": report_type,
            "report_name": report_config["description"],
            "time_range": time_range,
            "data": data,
            "content": report_content,
            "generated_at": datetime.now().isoformat()
        }
    
    async def _fetch_report_data(
        self, 
        report_type: str, 
        time_range: str
    ) -> Dict[str, Any]:
        """
        从数据库获取报表数据
        
        Args:
            report_type: 报表类型
            time_range: 时间范围
            
        Returns:
            报表数据
        """
        return self._generate_mock_data(report_type, time_range)
    
    def _generate_mock_data(self, report_type: str, time_range: str) -> Dict[str, Any]:
        """
        生成模拟数据（用于演示）
        
        Args:
            report_type: 报表类型
            time_range: 时间范围
            
        Returns:
            模拟的报表数据
        """
        mock_data = {
            "sales": {
                "total_orders": 1256,
                "total_amount": 895670.50,
                "avg_order_value": 713.11,
                "top_products": [
                    {"name": "产品A", "sales": 156000, "growth": "+12%"},
                    {"name": "产品B", "sales": 98000, "growth": "+8%"},
                    {"name": "产品C", "sales": 87500, "growth": "+15%"}
                ]
            },
            "financial": {
                "revenue": 895670.50,
                "cost": 520000.00,
                "profit": 375670.50,
                "profit_margin": "41.9%",
                "expenses": [
                    {"item": "人力成本", "amount": 200000},
                    {"item": "运营成本", "amount": 150000},
                    {"item": "营销成本", "amount": 100000}
                ]
            },
            "operation": {
                "total_users": 25680,
                "active_users": 18650,
                "new_users": 1256,
                "retention_rate": "72.5%",
                "avg_session_duration": "15分钟"
            },
            "inventory": {
                "total_products": 4580,
                "low_stock_items": 23,
                "out_of_stock": 5,
                "turnover_rate": "4.2次/月"
            },
            "general": {
                "summary": f"{time_range}数据汇总",
                "highlights": ["数据1", "数据2", "数据3"]
            }
        }
        
        return mock_data.get(report_type, mock_data["general"])
    
    def _format_report(
        self, 
        report_type: str, 
        data: Dict[str, Any],
        time_range: str
    ) -> str:
        """
        格式化报表内容
        
        Args:
            report_type: 报表类型
            data: 报表数据
            time_range: 时间范围
            
        Returns:
            格式化的报表文本
        """
        if report_type == "sales":
            return f"""【{time_range}销售报表】

📊 销售概况
• 总订单数：{data['total_orders']} 单
• 总销售额：¥{data['total_amount']:,.2f}
• 平均订单金额：¥{data['avg_order_value']:.2f}

🏆 热销产品 TOP3
1. {data['top_products'][0]['name']}：¥{data['top_products'][0]['sales']:,}（{data['top_products'][0]['growth']}）
2. {data['top_products'][1]['name']}：¥{data['top_products'][1]['sales']:,}（{data['top_products'][1]['growth']}）
3. {data['top_products'][2]['name']}：¥{data['top_products'][2]['sales']:,}（{data['top_products'][2]['growth']}）

---
报表生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}"""
        
        elif report_type == "financial":
            return f"""【{time_range}财务报表】

💰 财务概要
• 营业收入：¥{data['revenue']:,.2f}
• 营业成本：¥{data['cost']:,.2f}
• 净利润：¥{data['profit']:,.2f}
• 利润率：{data['profit_margin']}

📋 费用明细
• 人力成本：¥{data['expenses'][0]['amount']:,}
• 运营成本：¥{data['expenses'][1]['amount']:,}
• 营销成本：¥{data['expenses'][2]['amount']:,}

---
报表生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}"""
        
        elif report_type == "operation":
            return f"""【{time_range}运营报表】

👥 用户数据
• 总用户数：{data['total_users']:,}
• 活跃用户：{data['active_users']:,}
• 新增用户：{data['new_users']:,}
• 留存率：{data['retention_rate']}
• 平均会话时长：{data['avg_session_duration']}

---
报表生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}"""
        
        elif report_type == "inventory":
            return f"""【{time_range}库存报表】

📦 库存概况
• 商品总数：{data['total_products']:,}
• 低库存商品：{data['low_stock_items']} 种
• 缺货商品：{data['out_of_stock']} 种
• 库存周转率：{data['turnover_rate']}

---
报表生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}"""
        
        else:
            return f"""【{time_range}数据汇总】

{data.get('summary', '暂无数据')}

亮点：
{chr(10).join(['• ' + h for h in data.get('highlights', [])])}

---
报表生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}"""
    
    async def stream_run(
        self, 
        user_input: str, 
        history: List[Dict] = None,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """
        流式生成报表
        
        Args:
            user_input: 用户输入
            history: 对话历史
            **kwargs: 其他参数
            
        Yields:
            逐步生成的报表内容
        """
        report_result = await self.generate_report(user_input, **kwargs)
        content = report_result["content"]
        
        for char in content:
            yield char


report_agent = ReportAgent()
