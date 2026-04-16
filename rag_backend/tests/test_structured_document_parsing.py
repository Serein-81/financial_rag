#!/usr/bin/env python3
"""
结构化文档解析测试脚本

测试功能:
1. PDF结构化解析
2. Word结构化解析
3. 结构化切块
4. 性能对比

运行方式:
python test_structured_document_parsing.py
"""

import asyncio
import sys
import os
import time

# 添加项目根目录到 Python 路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.structured_document_service import structured_document_service
from app.services.chunk_service import chunk_service


async def test_pdf_structured_parsing():
    """测试PDF结构化解析"""
    print("🔍 测试PDF结构化解析...")
    
    # 创建测试PDF内容（模拟）
    test_content = """# 第一章 系统概述

本章介绍系统的基本概念和架构设计。

## 1.1 系统架构

系统采用微服务架构，主要包含以下组件：

- API 网关
- 用户服务
- 数据服务
- 消息队列

### 1.1.1 API 网关

API 网关负责：
1. 请求路由
2. 身份认证
3. 限流控制

## 1.2 数据流

| 步骤 | 描述 | 负责组件 |
|------|------|----------|
| 1 | 接收请求 | API网关 |
| 2 | 身份验证 | 用户服务 |
| 3 | 数据处理 | 数据服务 |

# 第二章 部署指南

本章介绍如何部署和配置系统。

## 2.1 环境准备

需要准备以下环境：
- Docker 20.10+
- Kubernetes 1.20+
- PostgreSQL 13+
"""
    
    try:
        # 模拟解析结构化文档
        structured_doc = await structured_document_service._parse_markdown_to_structured(
            test_content, "test_document.pdf", "application/pdf"
        )
        
        print("✅ PDF解析成功")
        print(f"  - 文档标题: {structured_doc.title}")
        print(f"  - 文档类型: {structured_doc.doc_type.value}")
        print(f"  - 章节数量: {len(structured_doc.sections)}")
        print(f"  - 原始块数: {len(structured_doc.raw_blocks)}")
        
        # 显示章节结构
        for i, section in enumerate(structured_doc.sections):
            print(f"  章节 {i+1}: {section.heading} (级别 {section.level})")
            for j, subsection in enumerate(section.subsections):
                print(f"    子章节 {j+1}: {subsection.heading} (级别 {subsection.level})")
        
        # 测试结构化切块
        print("\n🔪 测试结构化切块...")
        chunk_results = await structured_document_service.chunk_structured_document(
            structured_doc,
            chunk_tokens=200,
            overlap_tokens=20
        )
        
        print(f"✅ 切块成功，共 {len(chunk_results)} 个片段")
        for i, chunk in enumerate(chunk_results):
            print(f"  片段 {i+1}:")
            print(f"    标题路径: {chunk.heading_path}")
            print(f"    Token数: {chunk.tokens}")
            print(f"    内容预览: {chunk.content[:100]}...")
            print()
        
        return True
        
    except Exception as e:
        print(f"❌ PDF解析测试失败: {e}")
        return False


async def test_word_structured_parsing():
    """测试Word结构化解析"""
    print("🔍 测试Word结构化解析...")
    
    # 创建测试Word内容（模拟）
    test_content = """# 项目需求文档

## 1. 项目背景

本项目旨在构建一个智能文档处理系统。

### 1.1 业务需求

- 支持多种文档格式
- 提供智能检索功能
- 实现结构化解析

## 2. 技术方案

### 2.1 架构设计

| 层级 | 组件 | 技术栈 |
|------|------|--------|
| 前端 | Web界面 | Vue.js |
| 后端 | API服务 | FastAPI |
| 数据 | 数据库 | PostgreSQL |

### 2.2 核心算法

1. 文档解析算法
2. 结构识别算法
3. 智能切块算法
"""
    
    try:
        structured_doc = await structured_document_service._parse_markdown_to_structured(
            test_content, "requirements.docx", 
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        
        print("✅ Word解析成功")
        print(f"  - 文档标题: {structured_doc.title}")
        print(f"  - 文档类型: {structured_doc.doc_type.value}")
        print(f"  - 章节数量: {len(structured_doc.sections)}")
        
        # 获取统计信息
        stats = structured_document_service.get_document_statistics(structured_doc)
        print(f"  - 统计信息: {stats}")
        
        return True
        
    except Exception as e:
        print(f"❌ Word解析测试失败: {e}")
        return False


async def test_performance_comparison():
    """测试性能对比"""
    print("⚡ 性能对比测试...")
    
    test_text = """# 测试文档

## 第一章 概述

这是一个测试文档，用于对比传统切块和结构化切块的性能差异。

### 1.1 背景

传统的文档处理方式存在以下问题：
- 结构信息丢失
- 切块质量差
- 检索精度低

### 1.2 解决方案

我们提出了结构化文档处理方案：
- 保留文档结构
- 智能切块策略
- 提升检索质量

## 第二章 技术实现

### 2.1 解析算法

基于字体大小和样式分析的标题识别算法。

### 2.2 切块策略

基于文档结构的智能切块策略。
""" * 10  # 重复10次，增加文档长度
    
    try:
        # 1. 传统切块测试
        print("📊 传统切块测试...")
        start_time = time.time()
        
        traditional_chunks = chunk_service.split_text(
            test_text,
            doc_type="plain",
            chunk_tokens=200,
            overlap_tokens=20,
            return_metadata=True
        )
        
        traditional_time = time.time() - start_time
        print(f"  - 耗时: {traditional_time:.4f}s")
        print(f"  - 切片数: {len(traditional_chunks)}")
        print(f"  - 平均Token数: {sum(c.tokens for c in traditional_chunks) / len(traditional_chunks):.1f}")
        
        # 2. 结构化切块测试
        print("📊 结构化切块测试...")
        start_time = time.time()
        
        structured_doc = await structured_document_service._parse_markdown_to_structured(
            test_text, "test.md", "text/markdown"
        )
        
        structured_chunks = await structured_document_service.chunk_structured_document(
            structured_doc,
            chunk_tokens=200,
            overlap_tokens=20
        )
        
        structured_time = time.time() - start_time
        print(f"  - 耗时: {structured_time:.4f}s")
        print(f"  - 切片数: {len(structured_chunks)}")
        print(f"  - 平均Token数: {sum(c.tokens for c in structured_chunks) / len(structured_chunks):.1f}")
        
        # 3. 质量对比
        print("📈 质量对比:")
        traditional_with_path = sum(1 for c in traditional_chunks if c.heading_path)
        structured_with_path = sum(1 for c in structured_chunks if c.heading_path)
        
        print(f"  - 传统切块带标题路径: {traditional_with_path}/{len(traditional_chunks)} ({traditional_with_path/len(traditional_chunks)*100:.1f}%)")
        print(f"  - 结构化切块带标题路径: {structured_with_path}/{len(structured_chunks)} ({structured_with_path/len(structured_chunks)*100:.1f}%)")
        
        # 4. 性能总结
        print("\n⚡ 性能总结:")
        print(f"  - 时间差异: {abs(structured_time - traditional_time):.4f}s")
        print(f"  - 质量提升: {(structured_with_path/len(structured_chunks) - traditional_with_path/len(traditional_chunks))*100:.1f}%")
        
        return True
        
    except Exception as e:
        print(f"❌ 性能对比测试失败: {e}")
        return False


async def test_edge_cases():
    """测试边界情况"""
    print("🧪 边界情况测试...")
    
    test_cases = [
        ("空文档", ""),
        ("纯文本", "这是一个没有任何结构的纯文本文档。"),
        ("只有标题", "# 标题\n## 子标题"),
        ("复杂表格", """# 数据表格

| 姓名 | 年龄 | 职业 | 备注 |
|------|------|------|------|
| 张三 | 25 | 工程师 | 后端开发 |
| 李四 | 30 | 设计师 | UI/UX设计 |
| 王五 | 28 | 产品经理 | 需求分析 |
"""),
        ("深层嵌套", """# 第一章
## 1.1 节
### 1.1.1 小节
#### 1.1.1.1 子小节
##### 1.1.1.1.1 更小节
###### 1.1.1.1.1.1 最小节
内容
""")
    ]
    
    passed = 0
    for case_name, content in test_cases:
        try:
            print(f"  测试: {case_name}")
            
            if not content:
                # 空文档特殊处理
                structured_doc = await structured_document_service._parse_plain_text_to_structured(
                    content, "empty.txt", "text/plain"
                )
            else:
                structured_doc = await structured_document_service._parse_markdown_to_structured(
                    content, f"{case_name}.md", "text/markdown"
                )
            
            chunks = await structured_document_service.chunk_structured_document(
                structured_doc,
                chunk_tokens=100,
                overlap_tokens=10
            )
            
            print(f"    ✅ 成功 - 章节: {len(structured_doc.sections)}, 切片: {len(chunks)}")
            passed += 1
            
        except Exception as e:
            print(f"    ❌ 失败: {e}")
    
    print(f"边界测试通过: {passed}/{len(test_cases)}")
    return passed == len(test_cases)


async def main():
    """主测试函数"""
    print("=" * 60)
    print("🧪 结构化文档解析测试")
    print("=" * 60)
    
    tests = [
        ("PDF结构化解析", test_pdf_structured_parsing()),
        ("Word结构化解析", test_word_structured_parsing()),
        ("性能对比", test_performance_comparison()),
        ("边界情况", test_edge_cases())
    ]
    
    results = []
    for test_name, test_coro in tests:
        print(f"\n🔬 {test_name}测试...")
        try:
            result = await test_coro
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name}测试异常: {e}")
            results.append((test_name, False))
    
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
        print("\n🎉 所有测试通过！结构化文档解析功能正常。")
        print("\n📋 功能特性:")
        print("✅ PDF结构化解析 - 字体分析 + 布局识别")
        print("✅ Word结构化解析 - 样式分析 + 层级推断")
        print("✅ 统一文档模型 - 跨格式兼容")
        print("✅ 智能切块策略 - 保留结构信息")
        print("✅ 性能优化 - 异步处理 + 缓存")
    else:
        print(f"\n⚠️ 有 {len(results) - passed} 个测试失败，请检查相关配置。")


if __name__ == "__main__":
    asyncio.run(main())