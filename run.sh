#!/usr/bin/env bash
# 校园每日快讯 · 一键启动
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  echo "首次运行：创建虚拟环境并安装依赖…"
  python3 -m venv .venv
  .venv/bin/python -m pip install -q --upgrade pip
  .venv/bin/python -m pip install -q -r requirements.txt
fi

exec .venv/bin/python app.py
