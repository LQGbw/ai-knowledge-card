#!/bin/bash
# 机器人守护脚本：检查进程是否存活，挂了自动重启
# 用法：每分钟由 cron 调用一次

PROJECT_DIR="/home/user/.doubao/agent_mode/workspace/ai-knowledge-card"
LOG_FILE="$PROJECT_DIR/bot.log"
PID_FILE="$PROJECT_DIR/bot.pid"

cd "$PROJECT_DIR" || exit 1

# 检查进程是否存活
if pgrep -f "run_bot.py" > /dev/null 2>&1; then
    # 进程存活，什么都不做
    exit 0
fi

# 进程挂了，重启
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 检测到机器人进程已退出，正在重启..." >> "$LOG_FILE"
nohup python3 run_bot.py >> "$LOG_FILE" 2>&1 &
NEW_PID=$!
echo "$NEW_PID" > "$PID_FILE"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 重启成功，新 PID: $NEW_PID" >> "$LOG_FILE"
