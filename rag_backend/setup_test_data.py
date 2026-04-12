"""
添加财务测试数据脚本
"""

import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.db.session import AsyncSessionLocal
from app.models.user_financial_data import UserFinancialData
from datetime import date
import uuid


async def add_test_data():
    """添加测试数据"""
    
    print("=" * 60)
    print("添加财务测试数据")
    print("=" * 60)
    
    # 测试用的租户ID
    test_tenant_id = "default"
    
    # 首先查找或创建一个测试用户
    from app.models.user import User
    
    async with AsyncSessionLocal() as session:
        try:
            # 尝试查找已有的用户
            from sqlalchemy import select
            result = await session.execute(
                select(User).where(User.phone == "13800138000").limit(1)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                # 尝试通过租户ID查找
                result = await session.execute(
                    select(User).where(User.tenant_id == test_tenant_id).limit(1)
                )
                user = result.scalar_one_or_none()
                
                if not user:
                    print("[INFO] 未找到测试用户，创建一个...")
                    # 创建一个测试用户
                    user = User(
                        id=uuid.uuid4(),
                        username="test_user",
                        email="test@example.com",
                        phone="13800138001",  # 使用不同的电话号码避免冲突
                        hashed_password="$2b$12$dummy.hash.for.testing.purposes.only",  # 测试用哈希密码
                        tenant_id=test_tenant_id,
                        is_active=True
                    )
                    session.add(user)
                    await session.commit()
                    await session.refresh(user)
                    print(f"[OK] 测试用户创建成功: {user.id}")
                else:
                    print(f"[INFO] 使用已有租户用户: {user.id}")
            else:
                print(f"[INFO] 使用已有用户: {user.id} (通过电话号码)")
            
            # 添加测试财务数据
            print("\n[1] 添加Q1季度数据...")
            q1_data = UserFinancialData(
                user_id=user.id,
                tenant_id=test_tenant_id,
                fiscal_year=2024,
                period_type="quarterly",
                period_start=date(2024, 1, 1),
                period_end=date(2024, 3, 31),
                total_revenue=1000000.0,
                taxable_sales=850000.0,
                tax_free_sales=150000.0,
                total_expenses=700000.0,
                deductible_expenses=600000.0,
                non_deductible_expenses=100000.0,
                input_tax=78000.0,
                output_tax=110500.0,
                vat_rate=0.13,
                taxable_income=300000.0,
                corporate_tax_rate=0.25,
                is_small_enterprise=False,
                total_payroll=200000.0,
                special_deductions=50000.0,
                total_invoices=50,
                input_invoice_count=30,
                output_invoice_count=20,
                data_status="confirmed",
                is_current=True,
                data_source="manual",
                notes="2024年第一季度财务数据"
            )
            session.add(q1_data)
            await session.commit()
            print(f"[OK] Q1数据添加成功")
            
            print("\n[2] 添加Q2季度数据...")
            q2_data = UserFinancialData(
                user_id=user.id,
                tenant_id=test_tenant_id,
                fiscal_year=2024,
                period_type="quarterly",
                period_start=date(2024, 4, 1),
                period_end=date(2024, 6, 30),
                total_revenue=1200000.0,
                taxable_sales=1000000.0,
                tax_free_sales=200000.0,
                total_expenses=800000.0,
                deductible_expenses=700000.0,
                non_deductible_expenses=100000.0,
                input_tax=91000.0,
                output_tax=130000.0,
                vat_rate=0.13,
                taxable_income=400000.0,
                corporate_tax_rate=0.25,
                is_small_enterprise=False,
                total_payroll=250000.0,
                special_deductions=50000.0,
                total_invoices=60,
                input_invoice_count=35,
                output_invoice_count=25,
                data_status="confirmed",
                is_current=True,
                data_source="manual",
                notes="2024年第二季度财务数据"
            )
            session.add(q2_data)
            await session.commit()
            print(f"[OK] Q2数据添加成功")
            
            print("\n[3] 添加年度汇总数据...")
            yearly_data = UserFinancialData(
                user_id=user.id,
                tenant_id=test_tenant_id,
                fiscal_year=2024,
                period_type="yearly",
                period_start=date(2024, 1, 1),
                period_end=date(2024, 12, 31),
                total_revenue=4500000.0,
                taxable_sales=3800000.0,
                tax_free_sales=700000.0,
                total_expenses=3000000.0,
                deductible_expenses=2600000.0,
                non_deductible_expenses=400000.0,
                input_tax=338000.0,
                output_tax=494000.0,
                vat_rate=0.13,
                taxable_income=1500000.0,
                corporate_tax_rate=0.25,
                is_small_enterprise=False,
                total_payroll=1000000.0,
                special_deductions=200000.0,
                total_invoices=250,
                input_invoice_count=150,
                output_invoice_count=100,
                data_status="draft",
                is_current=True,
                data_source="manual",
                notes="2024年全年财务数据（汇总）"
            )
            session.add(yearly_data)
            await session.commit()
            print(f"[OK] 年度数据添加成功")
            
            print("\n" + "=" * 60)
            print("[OK] 测试数据添加完成！")
            print("=" * 60)
            print(f"  - 租户ID: {test_tenant_id}")
            print(f"  - 用户ID: {user.id}")
            print(f"  - 数据记录: 3条")
            print(f"  - 包括: Q1、Q2、年度汇总")
            
        except Exception as e:
            print(f"\n[FAIL] 添加数据失败: {str(e)}")
            import traceback
            traceback.print_exc()
            await session.rollback()


if __name__ == "__main__":
    asyncio.run(add_test_data())
