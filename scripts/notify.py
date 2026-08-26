# -*- coding: utf-8 -*-
"""共享邮件通知模块；未配置 SMTP 时静默跳过，发送失败不抛异常。"""
from __future__ import annotations

import os
import smtplib
from email.header import Header
from email.mime.text import MIMEText


def send_email(subject: str, body: str) -> bool:
    """通过 SMTP 发送通知邮件；未配置时静默跳过。"""
    host = os.environ.get("SMTP_HOST", "")
    user = os.environ.get("SMTP_USER", "")
    password = os.environ.get("SMTP_PASS", "")
    to_addr = os.environ.get("MAIL_TO", "")
    if not all([host, user, password, to_addr]):
        print("ℹ️  未配置 SMTP，跳过邮件通知")
        return False

    raw_port = (os.environ.get("SMTP_PORT") or "").strip() or "465"
    port = int(raw_port)
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = Header(subject, "utf-8")
    msg["From"] = user
    msg["To"] = to_addr

    try:
        with smtplib.SMTP_SSL(host, port, timeout=30) as server:
            server.login(user, password)
            server.sendmail(user, [to_addr], msg.as_string())
        print(f"✅ 已发送通知邮件至 {to_addr}")
        return True
    except Exception as e:
        print(f"⚠️  邮件发送失败（不影响主流程）: {e}")
        return False
