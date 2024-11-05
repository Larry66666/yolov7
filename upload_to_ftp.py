from ftplib import FTP
import os

def upload_to_ftp(filepath, server, username, password, ftp_dir):
    # 连接到 FTP 服务器
    ftp = FTP()
    try:
        ftp.connect(server, 21)  # 默认 FTP 端口是 21
        ftp.login(username, password)  # 登录
        print(f"成功登录到 FTP 服务器 {server}")
        ftp.set_pasv(False)

        # 打开调试信息
        ftp.set_debuglevel(2)

        # 进入根目录，确认路径是否正确
        ftp.cwd('/')  # 确保进入根目录
        print(f"进入根目录成功，当前目录：{ftp.pwd()}")

        # 切换到目标目录
        try:
            ftp.cwd(ftp_dir)  # 切换到目标目录
            print(f"成功切换到目录 {ftp_dir}")
        except Exception as e:
            print(f"切换到目录 {ftp_dir} 时出错: {e}")
            return

        # 打开本地文件并上传
        with open(filepath, 'rb') as file:
            filename = os.path.basename(filepath)
            ftp.storbinary(f"STOR {filename}", file)  # 上传文件
            print(f"文件 {filename} 上传成功！")

    except Exception as e:
        print(f"FTP 上传失败: {e}")
    finally:
        ftp.quit()  # 退出 FTP 连接