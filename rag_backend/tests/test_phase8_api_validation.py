"""
Phase 8: API 完整性验证
验证所有 API 端点正常工作，文档完整
"""

import sys
from pathlib import Path
import json
import uuid  # 修复：添加uuid导入

sys.path.insert(0, str(Path(__file__).parent))

from fastapi.testclient import TestClient
from app.main import app
from app.core.security import create_access_token


class APIValidationTester:
    """API 验证测试器"""
    
    def __init__(self):
        self.client = TestClient(app)
        self.tenant_id = "tenant_api_test"
        self.user_id = uuid.uuid4()  # 修复：使用UUID而不是整数
        self.token = None
        self.results = []
        
    def setup(self):
        """测试环境准备"""
        print("=" * 80)
        print("Phase 8: API 完整性验证")
        print("=" * 80)
        
        # 创建测试 token
        self.token = create_access_token(
            data={
                "sub": str(self.user_id),
                "tenant_id": self.tenant_id
            }
        )
        
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "X-Tenant-ID": self.tenant_id
        }
        
        print(f"✓ 测试租户: {self.tenant_id}")
        print(f"✓ 认证 Token 已创建")
        
    def test_health_check(self):
        """测试健康检查端点"""
        print("\n" + "=" * 80)
        print("测试 1: 健康检查")
        print("=" * 80)
        
        try:
            response = self.client.get("/health")
            
            assert response.status_code == 200, f"状态码错误: {response.status_code}"
            
            data = response.json()
            print(f"✓ 健康检查响应: {data}")
            
            self.results.append({
                "test": "健康检查",
                "endpoint": "/health",
                "status": "PASS",
                "status_code": response.status_code
            })
            
        except Exception as e:
            print(f"✗ 健康检查失败: {str(e)}")
            self.results.append({
                "test": "健康检查",
                "endpoint": "/health",
                "status": "FAIL",
                "error": str(e)
            })
            
    def test_docs_endpoint(self):
        """测试 API 文档端点"""
        print("\n" + "=" * 80)
        print("测试 2: API 文档")
        print("=" * 80)
        
        try:
            # 测试 Swagger UI
            response = self.client.get("/docs")
            assert response.status_code == 200, "Swagger UI 不可访问"
            print("✓ Swagger UI 可访问")
            
            # 测试 OpenAPI JSON
            response = self.client.get("/openapi.json")
            assert response.status_code == 200, "OpenAPI JSON 不可访问"
            
            openapi_spec = response.json()
            assert "paths" in openapi_spec, "OpenAPI 规范缺少 paths"
            assert "info" in openapi_spec, "OpenAPI 规范缺少 info"
            
            endpoint_count = len(openapi_spec["paths"])
            print(f"✓ OpenAPI 文档可访问")
            print(f"  API 端点数: {endpoint_count}")
            
            self.results.append({
                "test": "API 文档",
                "status": "PASS",
                "endpoint_count": endpoint_count
            })
            
        except Exception as e:
            print(f"✗ API 文档测试失败: {str(e)}")
            self.results.append({
                "test": "API 文档",
                "status": "FAIL",
                "error": str(e)
            })
            
    def test_knowledge_base_api(self):
        """测试知识库 API"""
        print("\n" + "=" * 80)
        print("测试 3: 知识库 API")
        print("=" * 80)
        
        try:
            # 测试创建知识库
            create_data = {
                "name": "API Test KB",
                "description": "Test knowledge base"
            }
            
            response = self.client.post(
                "/api/v1/knowledge/bases",
                json=create_data,
                headers=self.headers
            )
            
            if response.status_code == 200:
                kb_data = response.json()
                kb_id = kb_data.get("id")
                print(f"✓ 创建知识库成功: ID={kb_id}")
                
                # 测试查询知识库
                response = self.client.get(
                    f"/api/v1/knowledge/bases/{kb_id}",
                    headers=self.headers
                )
                
                assert response.status_code == 200, "查询知识库失败"
                print(f"✓ 查询知识库成功")
                
                # 测试列表查询
                response = self.client.get(
                    "/api/v1/knowledge/bases",
                    headers=self.headers
                )
                
                assert response.status_code == 200, "列表查询失败"
                print(f"✓ 列表查询成功")
                
                self.results.append({
                    "test": "知识库 API",
                    "status": "PASS",
                    "operations": ["create", "get", "list"]
                })
            else:
                print(f"⚠ 知识库 API 返回: {response.status_code}")
                self.results.append({
                    "test": "知识库 API",
                    "status": "PARTIAL",
                    "status_code": response.status_code
                })
                
        except Exception as e:
            print(f"✗ 知识库 API 测试失败: {str(e)}")
            self.results.append({
                "test": "知识库 API",
                "status": "FAIL",
                "error": str(e)
            })
            
    def test_error_handling(self):
        """测试错误处理"""
        print("\n" + "=" * 80)
        print("测试 4: 错误处理")
        print("=" * 80)
        
        error_tests = [
            {
                "name": "401 Unauthorized",
                "method": "get",
                "url": "/api/v1/knowledge/bases",
                "headers": {},  # 无认证
                "expected_status": 401
            },
            {
                "name": "404 Not Found",
                "method": "get",
                "url": "/api/v1/knowledge/bases/99999",
                "headers": self.headers,
                "expected_status": 404
            }
        ]
        
        passed_count = 0
        
        for test in error_tests:
            try:
                if test["method"] == "get":
                    response = self.client.get(test["url"], headers=test["headers"])
                elif test["method"] == "post":
                    response = self.client.post(test["url"], headers=test["headers"])
                
                if response.status_code == test["expected_status"]:
                    print(f"✓ {test['name']}: {response.status_code}")
                    passed_count += 1
                else:
                    print(f"✗ {test['name']}: 期望 {test['expected_status']}, 实际 {response.status_code}")
                    
            except Exception as e:
                print(f"✗ {test['name']}: {str(e)}")
        
        all_passed = passed_count == len(error_tests)
        
        self.results.append({
            "test": "错误处理",
            "status": "PASS" if all_passed else "PARTIAL",
            "passed": passed_count,
            "total": len(error_tests)
        })
        
    def test_audit_api(self):
        """测试审查 API"""
        print("\n" + "=" * 80)
        print("测试 5: 审查 API")
        print("=" * 80)
        
        try:
            # 测试审查任务列表
            response = self.client.get(
                "/api/v1/audit/tasks",
                headers=self.headers
            )
            
            if response.status_code == 200:
                print(f"✓ 审查任务列表 API 可访问")
                
                self.results.append({
                    "test": "审查 API",
                    "status": "PASS",
                    "status_code": response.status_code
                })
            else:
                print(f"⚠ 审查 API 返回: {response.status_code}")
                self.results.append({
                    "test": "审查 API",
                    "status": "PARTIAL",
                    "status_code": response.status_code
                })
                
        except Exception as e:
            print(f"✗ 审查 API 测试失败: {str(e)}")
            self.results.append({
                "test": "审查 API",
                "status": "FAIL",
                "error": str(e)
            })
            
    def print_summary(self):
        """打印测试摘要"""
        print("\n" + "=" * 80)
        print("API 验证摘要")
        print("=" * 80)
        
        total = len(self.results)
        passed = sum(1 for r in self.results if r["status"] == "PASS")
        partial = sum(1 for r in self.results if r["status"] == "PARTIAL")
        failed = total - passed - partial
        
        print(f"\n总测试数: {total}")
        print(f"通过: {passed}")
        print(f"部分通过: {partial}")
        print(f"失败: {failed}")
        
        print("\n详细结果:")
        for i, result in enumerate(self.results, 1):
            if result["status"] == "PASS":
                icon = "✓"
            elif result["status"] == "PARTIAL":
                icon = "⚠"
            else:
                icon = "✗"
            
            print(f"{i}. {icon} {result['test']}: {result['status']}")
            if result["status"] == "FAIL":
                print(f"   错误: {result.get('error', 'Unknown')}")
        
        # 保存结果
        with open("test_phase8_api_results.json", "w", encoding="utf-8") as f:
            json.dump(self.results, f, ensure_ascii=False, indent=2, default=str)
        print(f"\n✓ API 验证结果已保存到: test_phase8_api_results.json")


def main():
    """主测试函数"""
    tester = APIValidationTester()
    
    try:
        tester.setup()
        
        # 运行所有 API 测试
        tester.test_health_check()
        tester.test_docs_endpoint()
        tester.test_knowledge_base_api()
        tester.test_error_handling()
        tester.test_audit_api()
        
        # 打印摘要
        tester.print_summary()
        
    except Exception as e:
        print(f"\nAPI 验证执行失败: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
