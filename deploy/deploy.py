"""部署到 OpenCloudOS 香港服务器"""
import paramiko, os, sys
from pathlib import Path

HOST = '43.135.112.189'
KEY_PATH = r'C:\Users\ynlvs\.ssh\ynlawyers_key'
PROJECT = Path(r'C:\Users\ynlvs\Desktop\法律网站1')
REMOTE = '/var/www/ynlawyers'
EXCLUDE = ['__pycache__', '.secret_key', '*.pyc', 'deploy/upload_and_deploy.py']

key = paramiko.Ed25519Key.from_private_key_file(KEY_PATH)
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username='root', pkey=key, timeout=30)
sftp = ssh.open_sftp()
print('=== 已连接服务器 ===\n')

# ---- Step 1: Install dependencies ----
print('[1/5] 安装依赖...')
for cmd in [
    'dnf install -y python3-pip 2>&1 | tail -5',
    'mkdir -p /var/www/ynlawyers',
]:
    _, out, err = ssh.exec_command(cmd, timeout=60)
    o = out.read().decode() + err.read().decode()
    print(f'  {o.strip()[:200]}')

# ---- Step 2: Upload files ----
print('\n[2/5] 上传文件...')

def mkdir_remote(path):
    try: sftp.mkdir(path)
    except: pass

for d in ['templates', 'static', 'static/css', 'static/js', 'static/img', 'static/uploads', 'deploy']:
    mkdir_remote(f'{REMOTE}/{d}')

uploaded = 0
def upload_dir(local, remote):
    global uploaded
    for item in Path(local).iterdir():
        name = str(item.name)
        if any(e.replace('*','') in name if '*' in e else e in str(item) for e in EXCLUDE):
            continue
        rpath = f'{remote}/{item.name}'
        if item.is_file():
            sftp.put(str(item), rpath)
            uploaded += 1
        elif item.is_dir():
            try: sftp.mkdir(rpath)
            except: pass
            upload_dir(str(item), rpath)

for item in ['app.py', 'run.py', 'requirements.txt', 'legal.db', 'templates', 'static', 'deploy']:
    local = PROJECT / item
    if not local.exists(): continue
    if local.is_file():
        sftp.put(str(local), f'{REMOTE}/{item}')
        uploaded += 1
        print(f'  {item}')
    else:
        upload_dir(str(local), f'{REMOTE}/{item}')
        print(f'  {item}/')

sftp.close()
print(f'  共 {uploaded} 个文件')

# ---- Step 3: Install Python packages ----
print('\n[3/5] 安装 Python 包...')
_, out, err = ssh.exec_command(f'cd {REMOTE} && pip3 install -r requirements.txt 2>&1 | tail -5', timeout=120)
print('  ' + (out.read().decode() + err.read().decode()).strip())

# ---- Step 4: Configure Nginx ----
print('\n[4/5] 配置 Nginx...')

nginx_conf = '''server {
    listen 80;
    server_name lawyer01.com www.lawyer01.com;

    client_max_body_size 10M;

    location /static/ {
        alias /var/www/ynlawyers/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}'''

_, out, err = ssh.exec_command(f"cat > /etc/nginx/conf.d/ynlawyers.conf << 'NGINX_EOF'\n{nginx_conf}\nNGINX_EOF", timeout=10)
e = err.read().decode()
if e: print(f'  ERROR: {e[:200]}')

for cmd in [
    'nginx -t 2>&1',
    'systemctl reload nginx 2>&1',
]:
    _, out, err = ssh.exec_command(cmd, timeout=10)
    print(f'  {cmd}: {(out.read().decode()+err.read().decode()).strip()}')

# ---- Step 5: Systemd service ----
print('\n[5/5] 配置服务并启动...')

service = '''[Unit]
Description=ynlawyers Legal Website
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/var/www/ynlawyers
ExecStart=/usr/bin/python3 /var/www/ynlawyers/run.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target'''

_, out, err = ssh.exec_command(f"cat > /etc/systemd/system/ynlawyers.service << 'SVC_EOF'\n{service}\nSVC_EOF", timeout=10)
for cmd in [
    'systemctl daemon-reload',
    'systemctl enable ynlawyers 2>&1',
    'systemctl restart ynlawyers 2>&1',
    'sleep 2',
    'systemctl status ynlawyers --no-pager -l 2>&1 | head -15',
    'curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:5000/ 2>&1',
]:
    _, out, err = ssh.exec_command(cmd, timeout=10)
    print(f'  {(out.read().decode()+err.read().decode()).strip()}')

ssh.close()

print('\n========================================')
print('  部署完成！')
print('  前台: http://lawyer01.com')
print('  后台: http://lawyer01.com/admin')
print('  账号: admin / admin123')
print('========================================')
