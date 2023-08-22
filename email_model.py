import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# 发件人和收件人邮箱地址
sender_email = "1535726542@qq.com"
receiver_email = "1535726542@qq.com"  # 接收者的邮箱地址

# 发件人邮箱的SMTP服务器地址和端口号（针对Gmail）
smtp_server = "smtp.qq.com"
smtp_port = 587

# 发件人邮箱的登录信息,这里是qq邮箱的授权码
sender_password = "crxwuybpftozgfea"

# 创建邮件内容
subject_succeed = "(^o^)实例创建成功！！！"
body_succeed = "恭喜创建成功！！！"

subject_fail = "创建失败(╯︵╰),出现未知错误。。。"
body_fail = "由于出现了意外错误，进程被意外终止。\t错误代码:"


def email_send(subject, body):
    message = MIMEMultipart()
    message["From"] = sender_email
    message["To"] = receiver_email
    message["Subject"] = subject
    message.attach(MIMEText(body, "plain"))
    # 连接到SMTP服务器并发送邮件
    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()  # 启用TLS加密

            # 登录到发件人邮箱
            server.login(sender_email, sender_password)

            # 发送邮件
            server.sendmail(sender_email, receiver_email, message.as_string())
            print("邮件发送成功！")

    except Exception as e:
        print("邮件发送失败:", str(e))


# email_send(subject_fail, body_fail)
