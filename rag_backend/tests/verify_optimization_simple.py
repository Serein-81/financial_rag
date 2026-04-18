#!/usr/bin/env python3
"""
快速验证优化后的 policy_agent.py 代码
"""

import sys
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

def test_imports():
    try:
        from app.api.v1.endpoints.policy_agent import (
            _create_enterprise_profile,
            _policy_input_to_dict,
            MAX_POLICIES_PER_REQUEST,
            MAX_POLICY_CONTENT_LENGTH,
            PolicyInput,
            EnterpriseProfileInput,
        )
        print("[OK] All imports successful")
        return True
    except Exception as e:
        print(f"[FAIL] Import failed: {e}")
        return False

def test_constants():
    try:
        from app.api.v1.endpoints.policy_agent import MAX_POLICIES_PER_REQUEST, MAX_POLICY_CONTENT_LENGTH
        assert MAX_POLICIES_PER_REQUEST == 100
        assert MAX_POLICY_CONTENT_LENGTH == 50000
        print("[OK] Constants defined correctly")
        return True
    except Exception as e:
        print(f"[FAIL] Constants test failed: {e}")
        return False

def test_helper_functions():
    try:
        from app.api.v1.endpoints.policy_agent import _create_enterprise_profile, _policy_input_to_dict, EnterpriseProfileInput, PolicyInput
        
        enterprise_input = EnterpriseProfileInput(
            enterprise_id="ent_123",
            enterprise_name="Test Enterprise",
            industry="Technology",
            region="Shenzhen",
            scale="Medium",
            tax_types=["VAT"],
            qualifications=["HighTech"]
        )
        
        profile = _create_enterprise_profile(enterprise_input)
        assert profile.enterprise_id == "ent_123"
        assert profile.industry == "Technology"
        
        policy_input = PolicyInput(
            policy_id="pol_789",
            title="Tax Incentive",
            content="Details",
            priority="high"
        )
        
        policy_dict = _policy_input_to_dict(policy_input)
        assert policy_dict["policy_id"] == "pol_789"
        assert policy_dict["priority"] == "high"
        
        print("[OK] Helper functions work correctly")
        return True
    except Exception as e:
        print(f"[FAIL] Helper functions test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_pydantic_models():
    try:
        from app.api.v1.endpoints.policy_agent import PolicyInput, EnterpriseProfileInput
        
        policy = PolicyInput(
            policy_id="test_001",
            title="Test",
            content="Content",
            priority="medium"
        )
        assert policy.source == "manual"
        
        enterprise = EnterpriseProfileInput(
            enterprise_id="ent_001",
            enterprise_name="Enterprise",
            industry="Manufacturing",
            region="Shanghai",
            scale="Small"
        )
        assert enterprise.tax_types == []
        assert enterprise.qualifications == []
        
        print("[OK] Pydantic models validated successfully")
        return True
    except Exception as e:
        print(f"[FAIL] Pydantic models test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("=" * 60)
    print("Verify policy_agent.py optimization results")
    print("=" * 60)
    
    results = []
    
    print("\n1. Test imports...")
    results.append(test_imports())
    
    print("\n2. Test constants...")
    results.append(test_constants())
    
    print("\n3. Test helper functions...")
    results.append(test_helper_functions())
    
    print("\n4. Test Pydantic models...")
    results.append(test_pydantic_models())
    
    print("\n" + "=" * 60)
    if all(results):
        print("SUCCESS: All tests passed! Optimization implemented.")
        print("=" * 60)
        return 0
    else:
        print("FAILURE: Some tests failed. Please check errors.")
        print("=" * 60)
        return 1

if __name__ == "__main__":
    sys.exit(main())
