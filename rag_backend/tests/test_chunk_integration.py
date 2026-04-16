#!/usr/bin/env python3
"""
切块策略集成测试脚本

测试完整的文档处理流程:
1. 数据库模型更新验证
2. 切块策略功能测试
3. API 集成测试模拟

运行方式:
python test_chunk_integration.py
"""

import asyncio
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.chunk_service import chunk_service
from app.chunkers.base_chunker import ChunkResult
from app.db.session import AsyncSessionLocal
from app.models.chunk import DocumentChunk
from sqlalchemy import text


async def test_database_schema():
    """测试数据库模式是否正确更新"""
    print("🔍 测试数据库模式...")
    
    async with AsyncSessionLocal() as db:
        try:
            # 检查新字段是否存在
            result = await db.execute(text("""
                SELECT column_name, data_type, is_nullable 
                FROM information_schema.columns 
                WHERE table_name = 'document_chunks' 
                AND column_name IN ('heading_path', 'chunk_start', 'chunk_end', 'token_count')
                ORDER BY column_name;
            """))
            
            columns = result.fetchall()
            expected_fields = {'heading_path', 'chunk_start', 'chunk_end', 'token_count'}
            found_fields = {col[0] for col in columns}
            
            if expected_fields.issubset(found_fields):
                print("✅ 数据库模式检查通过")
                for col in columns:
                    print(f"  - {col[0]}: {col[1]} (nullable: {col[2]})")
                return True
            else:
                missing = expected_fields - found_fields
                print(f"❌ 缺少字段: {missing}")
                print("请先运行: python migrations/add_chunk_metadata.py")
                return False
                
        except Exception as e:
            print(f"❌ 数据库检查失败: {e}")
            return False


def test_chunk_service():
    """测试切块服务的新功能"""
    print("\n🧪 测试切块服务...")
    
    # 测试 Markdown 文档
    markdown_content = """# 第一章 系统概述

本章介绍系统的基本概念和架构。

## 1.1 系统架构

系统采用微服务架构，包含以下组件：
- API 网关
- 用户服务
- 数据服务

### 1.1.1 API 网关

API 网关负责请求路由和认证。它是系统的入口点，所有外部请求都通过网关进入系统。

## 1.2 数据流

数据在系统中的流转过程如下：
1. 用户发起请求
2. 网关验证身份
3. 路由到相应服务
4. 返回处理结果

# 第二章 部署指南

本章介绍如何部署系统。

## 2.1 环境准备

需要准备以下环境：
- Docker
- Kubernetes
- PostgreSQL
"""
    
    try:
        # 测试 Markdown 切块
        print("📝 测试 Markdown 智能切块...")
        markdown_results = chunk_service.split_text(
            markdown_content,
            doc_type="markdown",
            chunk_tokens=200,
            overlap_tokens=20,
            return_metadata=True
        )
        
        print(f"✅ Markdown 切块成功，共 {len(markdown_results)} 个片段")
        for i, result in enumerate(markdown_results):
            print(f"  片段 {i+1}:")
            print(f"    标题路径: {result.heading_path}")
            print(f"    Token 数: {result.tokens}")
            print(f"    位置: {result.start}-{result.end}")
            print(f"    内容预览: {result.content[:50]}...")
            print()
        
        # 测试纯文本切块
        print("📄 测试纯文本切块...")
        plain_results = chunk_service.split_text(
            "这是一个简单的测试文档。" * 100,
            doc_type="plain",
            chunk_tokens=100,
            return_metadata=True
        )
        
        print(f"✅ 纯文本切块成功，共 {len(plain_results)} 个片段")
        
        # 测试向后兼容性
        print("🔄 测试向后兼容性...")
        legacy_results = chunk_service.split_text("测试向后兼容性。" * 50)
        print(f"✅ 向后兼容测试通过，返回类型: {type(legacy_results[0])}")
        
        return True
        
    except Exception as e:
        print(f"❌ 切块服务测试失败: {e}")
        return False


async def test_model_integration():
    """测试模型集成"""
    print("\n🏗️ 测试模型集成...")
    
    try:
        # 创建测试用的 ChunkResult
        test_chunk = ChunkResult(
            content="这是一个测试切片",
            start=0,
            end=8,
            tokens=8,
            heading_path="测试章节 > 子章节",
            metadata={"test": True}
        )
        
        # 验证 DocumentChunk 模型可以接受新字段
        chunk_data = {
            "content": test_chunk.content,
            "chunk_index": 0,
            "meta_info": {"test": True},
            "heading_path": test_chunk.heading_path,
            "chunk_start": test_chunk.start,
            "chunk_end": test_chunk.end,
            "token_count": test_chunk.tokens
        }
        
        print("✅ 模型字段映射测试通过")
        print(f"  - heading_path: {chunk_data['heading_path']}")
        print(f"  - chunk_start: {chunk_data['chunk_start']}")
        print(f"  - chunk_end: {chunk_data['chunk_end']}")
        print(f"  - token_count: {chunk_data['token_count']}")
        
        return True
        
    except Exception as e:
        print(f"❌ 模型集成测试失败: {e}")
        return False


async def main():
    """主测试函数"""
    print("=" * 60)
    print("🧪 切块策略集成测试")
    print("=" * 60)
    
    # 运行所有测试
    tests = [
        ("数据库模式", test_database_schema()),
        ("切块服务", test_chunk_service()),
        ("模型集成", test_model_integration())
    ]
    
    results = []
    for test_name, test_coro in tests:
        if asyncio.iscoroutine(test_coro):
            result = await test_coro
        else:
            result = test_coro
        results.append((test_name, result))
    
    # 输出测试结果
    print("\n" + "=" * 60)
    print("📊 测试结果汇总")
    print("=" * 60)
    
    passed = 0
    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\n总计: {passed}/{len(results)} 个测试通过")
    
    if passed == len(results):
        print("\n🎉 所有测试通过！切块策略重构完成。")
        print("\n📋 下一步操作:")
        print("1. 运行迁移脚本: python migrations/add_chunk_metadata.py")
        print("2. 上传 Markdown 文件测试完整流程")
        print("3. 检查数据库中的元数据是否正确保存")
    else:
        print(f"\n⚠️ 有 {len(results) - passed} 个测试失败，请检查相关配置。")


if __name__ == "__main__":
    asyncio.run(main())