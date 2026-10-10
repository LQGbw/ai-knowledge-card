#!/bin/bash
# 机器人守护进程：无限循环运行机器人，挂了立刻自动重启
# 用法：nohup bash run_guardian.sh > guardian.log 2>&1 &

PROJECT_DIR="/home/user/.doubao/agent_mode/workspace/ai-knowledge-card"
LOG_FILE="$PROJECT_DIR/bot.log"

cd "$PROJECT_DIR" || exit 1

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 守护进程启动，开始托管机器人" >> "$LOG_FILE"

while true; do
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 启动机器人..." >> "$LOG_FILE"
    python3 run_bot.py >> "$LOG_FILE" 2>&1
    EXIT_CODE=$?
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 机器人退出（退出码 $EXIT_CODE），2秒后自动重启..." >> "$LOG_FILE"
    sleep 2
done
