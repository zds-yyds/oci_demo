"""统一通知模块：支持邮件 + 企业微信 Webhook"""
import smtplib
import httpx
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import Optional, List
import logging

logger = logging.getLogger(__name__)


def send_email(
    smtp_server: str,
    smtp_port: int,
    sender_email: str,
    sender_password: str,
    receiver_email: str,
    subject: str,
    body: str,
    attachment_paths: Optional[List[str]] = None,
) -> bool:
    try:
        message = MIMEMultipart()
        message["From"] = sender_email
        message["To"] = receiver_email
        message["Subject"] = subject
        message.attach(MIMEText(body, "plain", "utf-8"))

        if attachment_paths:
            for path in attachment_paths:
                try:
                    with open(path, "rb") as f:
                        part = MIMEBase("application", "octet-stream")
                        part.set_payload(f.read())
                        encoders.encode_base64(part)
                        part.add_header(
                            "Content-Disposition",
                            f"attachment; filename={path.split('/')[-1]}",
                        )
                        message.attach(part)
                except Exception as e:
                    logger.warning(f"附件 {path} 添加失败: {e}")

        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, receiver_email, message.as_string())
        logger.info("邮件发送成功")
        return True
    except Exception as e:
        logger.error(f"邮件发送失败: {e}")
        return False


def send_wecom(webhook_url: str, content: str) -> bool:
    """企业微信机器人 Webhook 推送"""
    try:
        payload = {
            "msgtype": "text",
            "text": {"content": content},
        }
        resp = httpx.post(webhook_url, json=payload, timeout=10)
        data = resp.json()
        if data.get("errcode") == 0:
            logger.info("企业微信消息发送成功")
            return True
        else:
            logger.error(f"企业微信发送失败: {data}")
            return False
    except Exception as e:
        logger.error(f"企业微信发送异常: {e}")
        return False


async def dispatch_notify(db, owner_id: int, subject: str, body: str):
    """根据用户配置自动分发通知"""
    from sqlalchemy import select
    from app.models import NotifyConfig

    result = await db.execute(
        select(NotifyConfig).where(
            NotifyConfig.owner_id == owner_id,
            NotifyConfig.is_active == True,
        )
    )
    configs = result.scalars().all()

    for cfg in configs:
        if cfg.notify_type == "email" and cfg.sender_email:
            send_email(
                smtp_server=cfg.smtp_server,
                smtp_port=cfg.smtp_port,
                sender_email=cfg.sender_email,
                sender_password=cfg.sender_password,
                receiver_email=cfg.receiver_email,
                subject=subject,
                body=body,
            )
        elif cfg.notify_type == "wecom" and cfg.wecom_webhook:
            send_wecom(cfg.wecom_webhook, f"【{subject}】\n{body}")
