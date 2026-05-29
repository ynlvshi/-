"""部署脚本：上传文件到香港服务器并执行部署"""
import paramiko
import os
import sys
from pathlib import Path

HOST = "43.135.112.189"
USER = "a4c3799d"
PASSWORD = "f23022d2"
PROJECT_DIR = Path(r"C:\Users\ynlvs\Desktop\法律网站1")
REMOTE_DIR = "/var/www/ynlawyers"

# 要上传的文件/目录
INCLUDE = [
    "app.py", "run.py", "requirements.txt", "legal.db",
    "templates", "static", "deploy"
]

# 要排除的文件
EXCLUDE = ["__pycache__", ".secret_key", "*.pyc"]


def should_skip(path):
    for ex in EXCLUDE:
        if ex.startswith("*"):
            if path.endswith(ex[1:]):
                return True
        elif ex in str(path):
            return True
    return False


def upload_directory(sftp, local_dir, remote_dir):
    """递归上传目录"""
    local_path = Path(local_dir)
    for item in local_path.iterdir():
        if should_skip(str(item)):
            continue
        remote_path = f"{remote_dir}/{item.name}"
        if item.is_file():
            print(f"  [FILE] {item.name}")
            sftp.put(str(item), remote_path)
        elif item.is_dir():
            print(f"  [DIR]  {item.name}/")
            try:
                sftp.mkdir(remote_path)
            except IOError:
                pass
            upload_directory(sftp, str(item), remote_path)


def main():
    print(f"=== 连接服务器 {HOST}... ===")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    sftp = ssh.open_sftp()
    print("已连接！\n")

    # ---- 创建目录 ----
    print("=== 创建远程目录 ===")
    for subdir in ["", "templates", "static", "static/css", "static/js", "static/img", "static/uploads", "deploy"]:
        path = f"{REMOTE_DIR}/{subdir}" if subdir else REMOTE_DIR
        try:
            sftp.mkdir(path)
            print(f"  创建: {path}")
        except IOError:
            pass

    # ---- 上传文件 ----
    print("\n=== 上传文件 ===")
    for item in INCLUDE:
        local_item = PROJECT_DIR / item
        if not local_item.exists():
            print(f"  [跳过] {item} (不存在)")
            continue
        remote_path = f"{REMOTE_DIR}/{item}"
        if local_item.is_file():
            print(f"  [FILE] {item}")
            sftp.put(str(local_item), remote_path)
        elif local_item.is_dir():
            print(f"  [DIR]  {item}/")
            upload_directory(sftp, str(local_item), remote_path)

    sftp.close()

    # ---- 执行部署 ----
    print("\n=== 开始远程部署 ===")
    commands = [
        "apt-get update -y",
        "apt-get install -y python3 python3-pip python3-venv nginx",
        f"cd {REMOTE_DIR} && pip3 install --break-system-packages -r requirements.txt",
        f"cp {REMOTE_DIR}/deploy/ynlawyers-nginx.conf /etc/nginx/sites-available/lawyer01.com",
        f"ln -sf /etc/nginx/sites-available/lawyer01.com /etc/nginx/sites-enabled/",
        "rm -f /etc/nginx/sites-enabled/default",
        "nginx -t && systemctl reload nginx",
        f"cp {REMOTE_DIR}/deploy/ynlawyers.service /etc/systemd/system/",
        "systemctl daemon-reload",
        "systemctl enable ynlawyers",
        "systemctl restart ynlawyers",
        "sleep 2 && systemctl status ynlawyers --no-pager | head -15",
    ]

    for cmd in commands:
        print(f"\n>>> {cmd}")
        stdin, stdout, stderr = ssh.exec_command(cmd, timeout=120)
        out = stdout.read().decode()
        err = stderr.read().decode()
        if out:
            print(out[:500])
        if err:
            print("STDERR:", err[:300])

    ssh.close()
    print("\n=== 部署完成！===")
    print("  前台: http://lawyer01.com")
    print("  后台: http://lawyer01.com/admin")


if __name__ == "__main__":
    main()
