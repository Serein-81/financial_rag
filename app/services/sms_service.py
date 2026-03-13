# app/services/sms_service.py

"""
短信服务

使用阿里云短信服务发送验证码
"""

import random
import string
import json
import logging
from typing import Dict, Optional

try:
    from aliyunsdkcore.client import AcsClient
    from aliyunsdkcore.request import CommonRequest
    ALIYUN_SDK_AVAILABLE = True
except ImportError:
    ALIYUN_SDK_AVAILABLE = False
    logging.warning("⚠️ 阿里云SDK未安装，短信功能将使用模拟模式")

from app.core.config import settings
from app.services.redis_service import redis_service

logger = logging.getLogger(__name__)


class SMSService:
    """短信服务类"""
    
    def __init__(self):
        """初始化阿里云短信客户端"""
        if ALIYUN_SDK_AVAILABLE and settings.ALIYUN_ACCESS_KEY_ID:
            try:
                self.client = AcsClient(
                    settings.ALIYUN_ACCESS_KEY_ID,
                    settings.ALIYUN_ACCESS_KEY_SECRET,
                    'cn-hangzhou'
                )
                logger.info("✅ 阿里云短信服务初始化成功")
            except Exception as e:
                logger.error(f"❌ 阿里云短信服务初始化失败: {e}")
                self.client = None
        else:
            self.client = None
            logger.warning("⚠️ 阿里云短信服务未配置，将使用模拟模式")
    
    def generate_code(self, length: int = 6) -> str:
        """生成随机验证码"""
        return ''.join(random.choices(string.digits, k=length))
    
    def check_send_limit(self, phone: str) -> Dict[str, any]:
        """
        检查发送频率限制
        - 1小时内只能发送1次
        - 每日最多发送3次
        """
        # 检查1小时内是否已发送
        limit_key = f"sms:limit:{phone}"
        if redis_service.exists(limit_key):
            return {
                "can_send": False,
                "reason": "发送过于频繁，请1小时后再试"
            }
        
        # 检查每日发送次数
        daily_key = f"sms:daily:{phone}"
        daily_count = redis_service.get(daily_key)
        if daily_count and int(daily_count) >= settings.SMS_DAILY_LIMIT:
            return {
                "can_send": False,
                "reason": f"今日发送次数已达上限（{settings.SMS_DAILY_LIMIT}次）"
            }
        
        return {"can_send": True}
    
    async def send_verification_code(self, phone: str) -> Dict[str, any]:
        """发送验证码"""
        # 1. 检查发送限制
        limit_check = self.check_send_limit(phone)
        if not limit_check["can_send"]:
            logger.warning(f"发送限制: {phone} - {limit_check['reason']}")
            return {
                "success": False,
                "message": limit_check["reason"]
            }
        
        # 2. 生成验证码
        code = self.generate_code(settings.SMS_CODE_LENGTH)
        logger.info(f"生成验证码: {phone} -> {code}")
        
        # 3. 存储验证码到Redis
        code_key = f"sms:code:{phone}"
        redis_service.set_with_expire(
            code_key, 
            code, 
            settings.SMS_CODE_EXPIRE
        )
        
        # 4. 设置发送频率限制（1小时）
        limit_key = f"sms:limit:{phone}"
        redis_service.set_with_expire(
            limit_key, 
            "1", 
            settings.SMS_SEND_INTERVAL
        )
        
        # 5. 更新每日发送次数
        daily_key = f"sms:daily:{phone}"
        count = redis_service.incr(daily_key)
        if count == 1:
            redis_service.expire(daily_key, 86400)  # 24小时
        
        # 6. 调用阿里云短信API
        if self.client:
            try:
                request = CommonRequest()
                request.set_accept_format('json')
                request.set_domain('dysmsapi.aliyuncs.com')
                request.set_method('POST')
                request.set_protocol_type('https')
                request.set_version('2017-05-25')
                request.set_action_name('SendSms')
                
                request.add_query_param('PhoneNumbers', phone)
                request.add_query_param('SignName', settings.ALIYUN_SMS_SIGN_NAME)
                request.add_query_param('TemplateCode', settings.ALIYUN_SMS_TEMPLATE_CODE)
                # 短信认证服务模板需要 code 和 min 两个参数
                request.add_query_param('TemplateParam', json.dumps({
                    "code": code,
                    "min": str(settings.SMS_CODE_EXPIRE // 60)  # 转换为分钟
                }))
                
                response = self.client.do_action_with_exception(request)
                result = json.loads(response)
                
                if result.get('Code') == 'OK':
                    logger.info(f"✅ 短信发送成功: {phone}")
                    return {
                        "success": True,
                        "message": "验证码发送成功",
                        "expire_seconds": settings.SMS_CODE_EXPIRE
                    }
                else:
                    logger.error(f"❌ 短信发送失败: {result.get('Message')}")
                    # 发送失败，删除Redis中的验证码和限制
                    redis_service.delete(code_key)
                    redis_service.delete(limit_key)
                    return {
                        "success": False,
                        "message": f"发送失败: {result.get('Message')}"
                    }
            
            except Exception as e:
                logger.error(f"❌ 短信发送异常: {e}")
                # 发送失败，删除Redis中的验证码和限制
                redis_service.delete(code_key)
                redis_service.delete(limit_key)
                return {
                    "success": False,
                    "message": f"短信发送异常: {str(e)}"
                }
        else:
            # 模拟模式：直接返回成功，验证码打印到日志
            logger.warning(f"📱 [模拟模式] 验证码: {phone} -> {code}")
            print(f"\n{'='*50}")
            print(f"📱 短信验证码（模拟模式）")
            print(f"手机号: {phone}")
            print(f"验证码: {code}")
            print(f"有效期: {settings.SMS_CODE_EXPIRE}秒")
            print(f"{'='*50}\n")
            
            return {
                "success": True,
                "message": "验证码发送成功（模拟模式，请查看控制台）",
                "expire_seconds": settings.SMS_CODE_EXPIRE,
                "debug_code": code  # 仅在开发模式下返回
            }
    
    def verify_code(self, phone: str, code: str) -> Dict[str, any]:
        """验证验证码"""
        code_key = f"sms:code:{phone}"
        stored_code = redis_service.get(code_key)
        
        if not stored_code:
            logger.warning(f"验证码不存在或已过期: {phone}")
            return {
                "valid": False,
                "message": "验证码已过期或不存在"
            }
        
        if stored_code != code:
            logger.warning(f"验证码错误: {phone} - 输入:{code}, 正确:{stored_code}")
            return {
                "valid": False,
                "message": "验证码错误"
            }
        
        # 验证成功，删除验证码
        redis_service.delete(code_key)
        logger.info(f"✅ 验证码验证成功: {phone}")
        
        return {
            "valid": True,
            "message": "验证成功"
        }


# 创建全局实例
sms_service = SMSService()