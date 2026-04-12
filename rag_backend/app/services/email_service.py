"""
邮件服务
提供邮件发送功能
"""

import logging
from typing import Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)


class EmailService:
    """
    邮件服务
    
    支持 SMTP 邮件发送
    """

    def __init__(self):
        self.smtp_host = None
        self.smtp_port = 587
        self.smtp_user = None
        self.smtp_password = None
        self.from_email = None
        self.enabled = False
        
        self._load_config()

    def _load_config(self):
        """加载邮件配置"""
        try:
            from app.core.config import settings
            
            self.smtp_host = getattr(settings, 'SMTP_HOST', None)
            self.smtp_port = getattr(settings, 'SMTP_PORT', 587)
            self.smtp_user = getattr(settings, 'SMTP_USER', None)
            self.smtp_password = getattr(settings, 'SMTP_PASSWORD', None)
            self.from_email = getattr(settings, 'SMTP_FROM_EMAIL', self.smtp_user)
            
            self.enabled = bool(self.smtp_host and self.smtp_user)
            
            if self.enabled:
                logger.info(f"✅ 邮件服务已配置: {self.smtp_host}:{self.smtp_port}")
            else:
                logger.warning("⚠️ 邮件服务未配置，将使用模拟模式")
                
        except (ValueError, KeyError) as e:
            logger.warning(f"⚠️ 邮件配置加载数据错误: {e}")
        except (OSError, IOError) as e:
            logger.warning(f"⚠️ 邮件配置加载IO错误: {e}")
        except Exception as e:
            logger.warning(f"⚠️ 邮件配置加载失败: {e}")

    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: Optional[str] = None,
        text_content: Optional[str] = None,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None
    ) -> bool:
        """
        发送邮件
        
        Args:
            to_email: 收件人邮箱
            subject: 邮件主题
            html_content: HTML 内容
            text_content: 纯文本内容
            cc: 抄送列表
            bcc: 密送列表
            
        Returns:
            是否发送成功
        """
        try:
            if not self.enabled:
                logger.info(f"📧 [模拟] 发送邮件到: {to_email}")
                logger.info(f"   主题: {subject}")
                return True

            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
            from email.header import Header

            msg = MIMEMultipart('alternative')
            msg['From'] = Header(self.from_email)
            msg['To'] = Header(to_email)
            msg['Subject'] = Header(subject, 'utf-8')
            msg['Date'] = datetime.now().strftime('%a, %d %b %Y %H:%M:%S %z')

            if cc:
                msg['Cc'] = ','.join(cc)
            
            if text_content:
                msg.attach(MIMEText(text_content, 'plain', 'utf-8'))
            
            if html_content:
                msg.attach(MIMEText(html_content, 'html', 'utf-8'))

            recipients = [to_email]
            if cc:
                recipients.extend(cc)
            if bcc:
                recipients.extend(bcc)

            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.sendmail(self.from_email, recipients, msg.as_string())

            logger.info(f"✅ 邮件发送成功: {to_email}")
            return True

        except (ValueError, KeyError) as e:
            logger.error(f"❌ 邮件发送数据错误: {e}", exc_info=True)
            return False
        except (OSError, IOError) as e:
            logger.error(f"❌ 邮件发送IO错误: {e}", exc_info=True)
            return False
        except Exception as e:
            logger.error(f"❌ 邮件发送失败: {e}", exc_info=True)
            return False

    async def send_batch_emails(
        self,
        recipients: List[str],
        subject: str,
        html_content: Optional[str] = None,
        text_content: Optional[str] = None
    ) -> dict:
        """
        批量发送邮件
        
        Args:
            recipients: 收件人列表
            subject: 邮件主题
            html_content: HTML 内容
            text_content: 纯文本内容
            
        Returns:
            发送结果统计
        """
        results = {
            "total": len(recipients),
            "success": 0,
            "failed": 0,
            "failed_emails": []
        }
        
        for email in recipients:
            try:
                success = await self.send_email(
                    to_email=email,
                    subject=subject,
                    html_content=html_content,
                    text_content=text_content
                )
                
                if success:
                    results["success"] += 1
                else:
                    results["failed"] += 1
                    results["failed_emails"].append(email)
                    
            except (ValueError, KeyError) as e:
                logger.error(f"❌ 批量邮件发送数据错误 ({email}): {e}")
                results["failed"] += 1
            except (OSError, IOError) as e:
                logger.error(f"❌ 批量邮件发送IO错误 ({email}): {e}")
                results["failed"] += 1
            except Exception as e:
                logger.error(f"❌ 批量邮件发送失败 ({email}): {e}")
                results["failed"] += 1
                results["failed_emails"].append(email)
        
        logger.info(f"📧 批量邮件发送完成: 成功 {results['success']}/{results['total']}")
        return results


email_service = EmailService()
