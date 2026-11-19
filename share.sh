#!/usr/bin/env bash
# 校园每日快讯 · 一键公网分享
# 用法：在终端里运行 ./share.sh，看到公网链接后把它发给别人即可。
# 停止：按 Ctrl+C（只停止公网分享，不影响本机 http://127.0.0.1:7878 的使用）。
set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"
LOG="/tmp/campus-news-tunnel.log"

echo "[1/2] 检查本地服务..."
if ! curl -s -o /dev/null --max-time 3 http://127.0.0.1:7878/; then
  echo "      本地服务未运行，正在启动..."
  nohup .venv/bin/python app.py > /tmp/campus-news.log 2>&1 &
  sleep 3
  if ! curl -s -o /dev/null --max-time 3 http://127.0.0.1:7878/; then
    echo "      启动失败，请查看 /tmp/campus-news.log"; exit 1
  fi
fi
echo "      本地服务正常"

echo "[2/2] 建立公网隧道（localhost.run）..."
: > "$LOG"
ssh -o StrictHostKeyChecking=no -o ServerAliveInterval=60 -o ServerAliveCountMax=3 \
    -R 80:localhost:7878 nokey@localhost.run > "$LOG" 2>&1 &
SSH_PID=$!
trap 'echo; echo "已停止公网分享（本地服务仍在运行）"; kill $SSH_PID 2>/dev/null || true' EXIT

URL=""
for i in $(seq 1 40); do
  URL=$(grep -oE 'https://[a-z0-9]+\.app\.lhr\.life' "$LOG" | head -1 || true)
  if [ -n "$URL" ]; then break; fi
  if ! kill -0 $SSH_PID 2>/dev/null; then
    echo "      隧道进程退出，日志："; cat "$LOG"; exit 1
  fi
  sleep 1
done

if [ -z "$URL" ]; then
  echo "      未能获取公网链接，请查看日志：$LOG"; exit 1
fi

echo
echo "============================================================"
echo "  公网链接：$URL"
echo "  访问口令：$(cat data/access_token 2>/dev/null || echo '(未设置)')"
echo "------------------------------------------------------------"
echo "  把链接发给别人即可打开；写操作（抓取/生成Word/改配置）"
echo "  第一次会弹出输入框，填上面的口令即可。"
echo "  电脑需保持开机、这个终端窗口保持打开。"
echo "  注意：免费链接每次重启会变，重跑脚本后请把新链接发给大家。"
echo "============================================================"
echo

wait $SSH_PID
