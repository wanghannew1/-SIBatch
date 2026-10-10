#!/usr/bin/env bash
# run.sh — SI-Batch 一键启动脚本。
#
# 从任意工作目录执行均可：先定位脚本自身所在目录，再依次处理
#   1) .venv 缺失 -> 创建虚拟环境并安装 requirements.txt（本机 PEP668，必须 venv）
#   2) si_batch.db 缺失 -> init_db() + seed_data()（幂等）
#   3) exec .venv/bin/python app.py（监听 0.0.0.0:5000）
set -e

# ---- 定位脚本所在目录（兼容任意 cwd；readlink -f 兼容软链接调用） ----
SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
cd "$SCRIPT_DIR"

PY="$SCRIPT_DIR/.venv/bin/python"
DB_FILE="$SCRIPT_DIR/si_batch.db"

# ---- 1. venv / 依赖 ----
if [ ! -x "$PY" ]; then
    echo "[run.sh] 未检测到 .venv，创建虚拟环境并安装依赖…"
    python3 -m venv "$SCRIPT_DIR/.venv"
    "$SCRIPT_DIR/.venv/bin/pip" install --disable-pip-version-check -r "$SCRIPT_DIR/requirements.txt"
fi

# ---- 2. 数据库初始化（仅当库文件缺失；init_db/seed_data 均为幂等操作） ----
if [ ! -f "$DB_FILE" ]; then
    echo "[run.sh] 未检测到 si_batch.db，初始化表结构与种子数据…"
    "$PY" -c "import db; db.init_db(); db.seed_data()"
fi

# ---- 3. 启动（exec 替换当前 shell，Ctrl-C / kill 直接作用于 Flask 进程） ----
echo "[run.sh] 启动 SI-Batch：本机 http://127.0.0.1:5000 ，局域网 http://<服务器IP>:5000"
exec "$PY" app.py
