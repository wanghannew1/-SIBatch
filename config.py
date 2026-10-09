"""config.py — 仅存放基础设施配置。

这里只有「跑起来需要的环境值」：路径、监听地址、secret、允许的扩展名。
所有业务规则（减员原因映射、字典映射、单位信息、系统默认值、模板列定义）
一律存数据库、可在后台配置，不得写进本文件（见 T2/T4）。
"""

import os
import secrets

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# SQLite 数据库文件（仓库根目录）
DATABASE = os.path.join(BASE_DIR, "si_batch.db")

# 上传目录：前台导入的增员/减员 .xls 原始文件
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")

# 输出目录：生成的各类报盘文件
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")

# 局域网访问：监听所有网卡
HOST = "0.0.0.0"
PORT = 5000

# Flask session 签名密钥
SECRET_KEY = os.environ.get("SI_BATCH_SECRET_KEY") or secrets.token_hex(32)

# 上传文件允许的扩展名
ALLOWED_EXTENSIONS = {"xls", "xlsx"}

for _d in (UPLOAD_DIR, OUTPUT_DIR):
    os.makedirs(_d, exist_ok=True)