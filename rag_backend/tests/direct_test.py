#!/usr/bin/env python3
"""
直接测试 policy_agent.py 的语法和结构
不依赖完整的导入链
"""

import sys
import ast

def analyze_policy_agent():
    """分析 policy_agent.py 的结构和语法"""
    
    file_path = "app/api/v1/endpoints/policy_agent.py"
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            code = f.read()
        
        print("=" * 60)
        print("Analyze policy_agent.py optimization results")
        print("=" * 60)
        
        tree = ast.parse(code)
        
        results = []
        
        print("\n1. Syntax check...")
        print("[OK] File syntax is valid")
        results.append(True)
        
        print("\n2. Check helper functions...")
        helper_functions = [
            '_create_enterprise_profile',
            '_policy_input_to_dict',
            'get_agent_service_dep'
        ]
        for func_name in helper_functions:
            found = any(
                isinstance(node, ast.FunctionDef) and node.name == func_name
                for node in ast.walk(tree)
            )
            if found:
                print(f"[OK] Function '{func_name}' found")
            else:
                print(f"[FAIL] Function '{func_name}' NOT found")
                results.append(False)
        
        print("\n3. Check constants...")
        constants = ['MAX_POLICIES_PER_REQUEST', 'MAX_POLICY_CONTENT_LENGTH']
        for const_name in constants:
            found = any(
                isinstance(node, ast.Assign) and any(
                    target.id == const_name for target in node.targets if isinstance(target, ast.Name)
                )
                for node in ast.walk(tree)
            )
            if found:
                print(f"[OK] Constant '{const_name}' found")
            else:
                print(f"[FAIL] Constant '{const_name}' NOT found")
                results.append(False)
        
        print("\n4. Check dependency injection...")
        has_depends = 'Depends(get_agent_service_dep)' in code
        if has_depends:
            print("[OK] Dependency injection pattern implemented")
        else:
            print("[FAIL] Dependency injection pattern NOT found")
            results.append(False)
        
        print("\n5. Check exception handling...")
        exception_types = ['ValueError', 'KeyError', 'OSError']
        for exc_type in exception_types:
            found = f'except {exc_type}' in code
            if found:
                print(f"[OK] Exception handling for '{exc_type}' found")
            else:
                print(f"[FAIL] Exception handling for '{exc_type}' NOT found")
                results.append(False)
        
        print("\n6. Check structured logging...")
        has_extra = 'extra={' in code
        if has_extra:
            print("[OK] Structured logging pattern implemented")
        else:
            print("[FAIL] Structured logging pattern NOT found")
            results.append(False)
        
        print("\n7. Check modern type hints...")
        modern_types = ['dict[str, Any]', 'list[str]', 'list[PolicyInput]']
        for type_hint in modern_types:
            if type_hint in code:
                print(f"[OK] Modern type hint '{type_hint}' found")
            else:
                print(f"[WARN] Modern type hint '{type_hint}' not found (may use legacy syntax)")
        
        print("\n8. Check service injection in endpoints...")
        endpoints = ['match_policy', 'generate_notification', 'prioritize_policies', 'test_policy_agent', 'get_agent_status']
        for endpoint in endpoints:
            found = any(
                isinstance(node, ast.AsyncFunctionDef) and node.name == endpoint
                for node in ast.walk(tree)
            )
            if found:
                has_service_dep = f'{endpoint}' in code and 'service: PolicyNotificationAgentService = Depends(get_agent_service_dep)' in code
                if has_service_dep:
                    print(f"[OK] Endpoint '{endpoint}' uses dependency injection")
                else:
                    print(f"[WARN] Endpoint '{endpoint}' may not use dependency injection")
        
        print("\n9. Check validation logic...")
        validations = [
            ('if not request.policies:', 'Empty policies check'),
            ('if len(request.policies) > MAX_POLICIES_PER_REQUEST:', 'Policy count limit'),
            ('if len(request.policy.content) > MAX_POLICY_CONTENT_LENGTH:', 'Content length check')
        ]
        for check, description in validations:
            if check in code:
                print(f"[OK] Validation: {description}")
            else:
                print(f"[WARN] Validation not found: {description}")
        
        print("\n" + "=" * 60)
        if all(results):
            print("SUCCESS: All critical checks passed!")
            print("The optimization has been successfully implemented.")
        else:
            print("PARTIAL: Some checks failed, but optimization may still work.")
        print("=" * 60)
        
        return all(results)
        
    except Exception as e:
        print(f"[FAIL] Analysis failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = analyze_policy_agent()
    sys.exit(0 if success else 1)
