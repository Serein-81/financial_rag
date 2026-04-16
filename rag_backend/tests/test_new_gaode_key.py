"""
测试新的高德地图API Key

用于验证重新创建的应用和Key是否正常工作
"""

import asyncio
import httpx
import sys


async def test_new_gaode_key(api_key):
    """测试新的高德API Key"""
    
    print("🔑 测试新的高德地图API Key")
    print("=" * 50)
    print(f"API Key: {api_key}")
    print(f"Key长度: {len(api_key)} 字符")
    
    if len(api_key) != 32:
        print("⚠️ 警告: API Key长度不是标准的32位")
    
    # 测试基础API
    test_cases = [
        {
            "name": "地理编码",
            "url": "https://restapi.amap.com/v3/geocode/geo",
            "params": {"address": "北京市", "key": api_key}
        },
        {
            "name": "IP定位",
            "url": "https://restapi.amap.com/v3/ip",
            "params": {"key": api_key}
        }
    ]
    
    success_count = 0
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        for i, test in enumerate(test_cases, 1):
            print(f"\n{i}. 测试{test['name']}API")
            print(f"   URL: {test['url']}")
            
            try:
                response = await client.get(test['url'], params=test['params'])
                print(f"   状态码: {response.status_code}")
                
                if response.status_code == 200:
                    data = response.json()
                    print(f"   响应: {data}")
                    
                    if data.get("status") == "1":
                        print(f"   ✅ {test['name']}API调用成功！")
                        success_count += 1
                    else:
                        error_info = data.get("info", "未知错误")
                        error_code = data.get("infocode", "未知")
                        print(f"   ❌ API错误: {error_info} (代码: {error_code})")
                        
                        # 错误分析
                        if error_code == "10001":
                            print("   💡 分析: API Key无效")
                        elif error_code == "10009":
                            print("   💡 分析: 平台配置问题或服务未开通")
                        elif error_code == "10003":
                            print("   💡 分析: 请求来源未授权")
                else:
                    print(f"   ❌ HTTP错误: {response.status_code}")
                    
            except Exception as e:
                print(f"   ❌ 请求异常: {e}")
    
    print("\n" + "=" * 50)
    print("📊 测试结果")
    print("=" * 50)
    print(f"成功: {success_count}/{len(test_cases)}")
    
    if success_count == len(test_cases):
        print("🎉 所有API测试通过！新Key配置正确")
        return True
    elif success_count > 0:
        print("⚠️ 部分API可用，可能需要开通更多服务")
        return True
    else:
        print("❌ 所有API测试失败，请检查Key和应用配置")
        return False


async def update_env_file(api_key):
    """更新.env文件中的API Key"""
    try:
        # 读取现有.env文件
        with open('.env', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 替换高德API Key
        lines = content.split('\n')
        updated_lines = []
        
        for line in lines:
            if line.startswith('GAODE_API_KEY='):
                updated_lines.append(f'GAODE_API_KEY={api_key}')
                print("✅ 已更新.env文件中的GAODE_API_KEY")
            else:
                updated_lines.append(line)
        
        # 写回文件
        with open('.env', 'w', encoding='utf-8') as f:
            f.write('\n'.join(updated_lines))
        
        return True
        
    except Exception as e:
        print(f"❌ 更新.env文件失败: {e}")
        return False


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("使用方法: python test_new_gaode_key.py <新的API_KEY>")
        print("示例: python test_new_gaode_key.py abc123def456...")
        sys.exit(1)
    
    new_api_key = sys.argv[1].strip()
    
    if len(new_api_key) < 20:
        print("❌ API Key长度太短，请检查是否完整")
        sys.exit(1)
    
    async def main():
        # 测试新Key
        success = await test_new_gaode_key(new_api_key)
        
        if success:
            # 更新.env文件
            if await update_env_file(new_api_key):
                print("\n🎉 配置更新完成！可以重新运行API测试")
            else:
                print(f"\n⚠️ 请手动更新.env文件中的GAODE_API_KEY={new_api_key}")
        else:
            print("\n❌ 新Key测试失败，请检查应用配置")
    
    asyncio.run(main())