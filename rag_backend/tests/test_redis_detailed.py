"""
详细的Redis连接测试

尝试各种可能的Redis配置
"""

import asyncio
import redis.asyncio as redis


async def test_redis_configurations():
    """测试各种Redis配置"""
    
    print("🔍 详细Redis连接测试")
    print("=" * 50)
    
    # 测试配置列表
    configs = [
        {"name": "无密码", "password": None},
        {"name": "空密码", "password": ""},
        {"name": "默认密码redis", "password": "redis"},
        {"name": "数据库密码", "password": "REDACTED_PG_PASSWORD"},
        {"name": "常见密码123456", "password": "123456"},
        {"name": "常见密码password", "password": "password"},
        {"name": "常见密码admin", "password": "admin"},
    ]
    
    for i, config in enumerate(configs, 1):
        print(f"\n{i}. 测试配置: {config['name']}")
        
        try:
            redis_client = redis.Redis(
                host="localhost",
                port=6379,
                db=0,
                password=config['password'],
                decode_responses=True,
                socket_connect_timeout=5
            )
            
            # 测试连接
            await redis_client.ping()
            print(f"   ✅ 连接成功！")
            
            # 测试读写
            await redis_client.set("test_key", "test_value", ex=5)
            value = await redis_client.get("test_key")
            
            if value == "test_value":
                print(f"   ✅ 读写测试成功！")
                print(f"   💡 正确的Redis配置:")
                print(f"      REDIS_HOST=localhost")
                print(f"      REDIS_PORT=6379")
                print(f"      REDIS_DB=0")
                print(f"      REDIS_PASSWORD={config['password'] or ''}")
                
                await redis_client.delete("test_key")
                await redis_client.close()
                return config['password']
            else:
                print(f"   ⚠️ 连接成功但读写失败")
            
            await redis_client.close()
            
        except redis.AuthenticationError:
            print(f"   ❌ 认证失败")
        except redis.ConnectionError as e:
            print(f"   ❌ 连接失败: {e}")
        except Exception as e:
            print(f"   ❌ 其他错误: {e}")
    
    print(f"\n❌ 所有配置都失败了")
    print(f"\n💡 可能的解决方案:")
    print(f"   1. 检查Redis是否正确启动")
    print(f"   2. 查看Redis启动日志中的密码信息")
    print(f"   3. 检查redis.conf文件中的requirepass设置")
    print(f"   4. 尝试使用redis-cli连接测试")
    
    return None


async def update_env_with_correct_password(password):
    """更新.env文件中的Redis密码"""
    
    try:
        # 读取.env文件
        with open('.env', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 替换Redis密码
        lines = content.split('\n')
        updated_lines = []
        
        for line in lines:
            if line.startswith('REDIS_PASSWORD='):
                updated_lines.append(f'REDIS_PASSWORD={password or ""}')
                print(f"✅ 已更新.env文件中的REDIS_PASSWORD")
            else:
                updated_lines.append(line)
        
        # 写回文件
        with open('.env', 'w', encoding='utf-8') as f:
            f.write('\n'.join(updated_lines))
        
        return True
        
    except Exception as e:
        print(f"❌ 更新.env文件失败: {e}")
        return False


async def main():
    """主函数"""
    
    # 测试各种配置
    correct_password = await test_redis_configurations()
    
    if correct_password is not None:
        print(f"\n🎉 找到正确的Redis配置！")
        
        # 更新.env文件
        if await update_env_with_correct_password(correct_password):
            print(f"✅ 配置已更新到.env文件")
            print(f"🚀 现在可以重新运行API测试了")
        else:
            print(f"⚠️ 请手动更新.env文件中的REDIS_PASSWORD={correct_password or ''}")
    else:
        print(f"\n❌ 未找到正确的Redis配置")
        print(f"\n🔧 手动检查方法:")
        print(f"   1. 打开新的命令提示符")
        print(f"   2. 切换到 D:\\redis 目录")
        print(f"   3. 运行: redis-cli.exe")
        print(f"   4. 如果提示输入密码，记录下正确的密码")
        print(f"   5. 或者查看redis.conf文件中的requirepass设置")


if __name__ == "__main__":
    asyncio.run(main())