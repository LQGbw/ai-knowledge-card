#!/bin/bash
# AI知识卡 - 云电脑一键部署脚本
set -e

cd "$(dirname "$0")"

echo "=== 1/3 检查 Python 版本 ==="
python3 --version

echo ""
echo "=== 2/3 安装项目依赖 ==="
python3 -m pip install -e . --quiet

echo ""
echo "=== 3/3 验证安装 ==="
python3 -c "import podcast_collector, feishu_bot; print('模块导入成功')"

echo ""
echo "=== 部署完成 ==="
echo "启动飞书机器人：python3 -m feishu_bot"
echo "手动采集播客：python3 -m podcast_collector sync"
echo "查看知识卡列表：python3 -m podcast_collector cards --limit 20"
