"""法律网站 - 生产模式启动脚本（Waitress 高性能 WSGI）"""
import sys
import os

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

os.chdir(os.path.dirname(os.path.abspath(__file__)))
os.environ['PYTHONIOENCODING'] = 'utf-8'

from waitress import serve
from app import app, init_database

print("=" * 50)
print("   云律师团队 - 生产模式启动")
print("   前台: http://localhost:5000")
print("   后台: http://localhost:5000/admin")
print("=" * 50)

init_database()

serve(app, host='0.0.0.0', port=5000, threads=4, channel_timeout=120)
