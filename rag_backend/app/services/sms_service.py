"""
短信服务
提供短信发送功能
"""

import json
import logging
from typing import Optional, List

logger = logging.getLogger(__name__)


class SMSService:
    """
    短信服务
    
    支持多种短信网关（阿里云、腾讯云等）
    """

    def __init__(self):
        self.provider = None
        self.api_key = None
        self.api_secret = None
        self.signature = None
        self.enabled = False
        
        self._load_config()

    def _load_config(self):
        """加载短信配置"""
        try:
            from app.core.config import settings
            
            self.provider = getattr(settings, 'SMS_PROVIDER', None)
            self.api_key = getattr(settings, 'SMS_API_KEY', None)
            self.api_secret = getattr(settings, 'SMS_API_SECRET', None)
            self.signature = getattr(settings, 'SMS_SIGNATURE', '智能税务')
            
            self.enabled = bool(self.provider and self.api_key)
            
            if self.enabled:
                logger.info(f"✅ 短信服务已配置: {self.provider}")
            else:
                logger.warning("⚠️ 短信服务未配置，将使用模拟模式")
                
        except (ValueError, KeyError) as e:
            logger.warning(f"⚠️ 短信配置加载数据错误: {e}")
        except (OSError, IOError) as e:
            logger.warning(f"⚠️ 短信配置加载IO错误: {e}")
        except Exception as e:
            logger.warning(f"⚠️ 短信配置加载失败: {e}")

    async def send_sms(
        self,
        phone_number: str,
        message: str,
        template_id: Optional[str] = None,
        template_params: Optional[dict] = None
    ) -> bool:
        """
        发送短信
        
        Args:
            phone_number: 手机号
            message: 短信内容
            template_id: 模板ID（模板短信用）
            template_params: 模板参数
            
        Returns:
            是否发送成功
        """
        try:
            if not self.enabled:
                logger.info(f"📱 [模拟] 发送短信到: {phone_number}")
                logger.info(f"   内容: {message}")
                return True

            if not self._validate_phone_number(phone_number):
                logger.error(f"❌ 无效的手机号: {phone_number}")
                return False

            if self.provider == "aliyun":
                return await self._send_aliyun_sms(phone_number, message, template_id, template_params)
            elif self.provider == "tencent":
                return await self._send_tencent_sms(phone_number, message, template_id, template_params)
            else:
                return await self._send_generic_sms(phone_number, message)

        except (ValueError, KeyError) as e:
            logger.error(f"❌ 短信发送数据错误: {e}", exc_info=True)
            return False
        except (OSError, IOError) as e:
            logger.error(f"❌ 短信发送IO错误: {e}", exc_info=True)
            return False
        except Exception as e:
            logger.error(f"❌ 短信发送失败: {e}", exc_info=True)
            return False

    def _validate_phone_number(self, phone: str) -> bool:
        """验证手机号格式"""
        import re
        pattern = r'^1[3-9]\d{9}$'
        return bool(re.match(pattern, phone))

    async def _send_aliyun_sms(
        self,
        phone_number: str,
        message: str,
        template_id: Optional[str],
        template_params: Optional[dict]
    ) -> bool:
        """通过阿里云发送短信"""
        try:
            from aliyunsdkdysmsapi.request.v20170525 import SendSmsRequest
            from aliyunsdkcore.client import AcsClient
            
            client = AcsClient(self.api_key, self.api_secret, 'cn-hangzhou')
            
            if template_id:
                request = SendSmsRequest.SendSmsRequest()
                request.set_PhoneNumbers(phone_number)
                request.set_SignName(self.signature)
                request.set_TemplateCode(template_id)
                request.set_TemplateParam(json.dumps(template_params) if template_params else None)
            else:
                logger.warning("⚠️ 阿里云短信需要使用模板")
                return False
            
            response = client.do_action_with_exception(request)
            logger.info(f"✅ 阿里云短信发送成功: {phone_number}")
            return True
            
        except (ValueError, KeyError) as e:
            logger.error(f"❌ 阿里云短信发送数据错误: {e}")
            return False
        except (OSError, IOError) as e:
            logger.error(f"❌ 阿里云短信发送IO错误: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ 阿里云短信发送失败: {e}")
            return False

    async def _send_tencent_sms(
        self,
        phone_number: str,
        message: str,
        template_id: Optional[str],
        template_params: Optional[dict]
    ) -> bool:
        """通过腾讯云发送短信"""
        try:
            from qcloudsms_py import SmsMultiSender
            
            appid = self.api_key
            appkey = self.api_secret
            sender = SmsMultiSender(appid, appkey)
            
            if template_id:
                result = sender.send_with_param(
                    86,
                    phone_number,
                    template_id,
                    template_params or [],
                    sign=self.signature
                )
            else:
                logger.warning("⚠️ 腾讯云短信需要使用模板")
                return False
            
            if result.get('result') == 0:
                logger.info(f"✅ 腾讯云短信发送成功: {phone_number}")
                return True
            else:
                logger.error(f"❌ 腾讯云短信发送失败: {result}")
                return False
                
        except (ValueError, KeyError) as e:
            logger.error(f"❌ 腾讯云短信发送数据错误: {e}")
            return False
        except (OSError, IOError) as e:
            logger.error(f"❌ 腾讯云短信发送IO错误: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ 腾讯云短信发送失败: {e}")
            return False

    async def _send_generic_sms(self, phone_number: str, message: str) -> bool:
        """通用短信发送（HTTP API）"""
        try:
            import httpx
            
            if hasattr(self, 'api_url'):
                response = await httpx.AsyncClient().post(
                    self.api_url,
                    json={
                        "phone": phone_number,
                        "message": message,
                        "signature": self.signature
                    },
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    timeout=10.0
                )
                response.raise_for_status()
                logger.info(f"✅ 短信发送成功: {phone_number}")
                return True
            
            logger.warning("⚠️ 未配置短信API URL")
            return False
            
        except (ValueError, KeyError) as e:
            logger.error(f"❌ 短信发送数据错误: {e}")
            return False
        except (OSError, IOError) as e:
            logger.error(f"❌ 短信发送IO错误: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ 短信发送失败: {e}")
            return False

    async def send_batch_sms(
        self,
        phone_numbers: List[str],
        message: str,
        template_id: Optional[str] = None,
        template_params: Optional[dict] = None
    ) -> dict:
        """
        批量发送短信
        
        Args:
            phone_numbers: 手机号列表
            message: 短信内容
            template_id: 模板ID
            template_params: 模板参数
            
        Returns:
            发送结果统计
        """
        results = {
            "total": len(phone_numbers),
            "success": 0,
            "failed": 0,
            "failed_phones": []
        }
        
        for phone in phone_numbers:
            try:
                success = await self.send_sms(
                    phone_number=phone,
                    message=message,
                    template_id=template_id,
                    template_params=template_params
                )
                
                if success:
                    results["success"] += 1
                else:
                    results["failed"] += 1
                    results["failed_phones"].append(phone)
                    
            except (ValueError, KeyError) as e:
                logger.error(f"❌ 批量短信发送数据错误 ({phone}): {e}")
                results["failed"] += 1
            except (OSError, IOError) as e:
                logger.error(f"❌ 批量短信发送IO错误 ({phone}): {e}")
                results["failed"] += 1
            except Exception as e:
                logger.error(f"❌ 批量短信发送失败 ({phone}): {e}")
                results["failed"] += 1
                results["failed_phones"].append(phone)
        
        logger.info(f"📱 批量短信发送完成: 成功 {results['success']}/{results['total']}")
        return results


sms_service = SMSService()
