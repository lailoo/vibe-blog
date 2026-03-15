#!/bin/bash
# vibe-blog 服务重部署脚本
# 用法: ./redeploy.sh [backend|frontend|all]
# 默认: all

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DEPLOY_TARGET="${1:-all}"

echo "🔄 开始重部署 vibe-blog 服务..."
echo "📁 项目目录: $PROJECT_DIR"
echo "🎯 部署目标: $DEPLOY_TARGET"

# 进入项目目录
cd "$PROJECT_DIR"

# 拉取最新代码
echo "📥 拉取最新代码..."
git pull

# 停止现有容器
echo "🛑 停止现有容器..."
docker compose -f docker/docker-compose.yml down

# 根据目标选择构建
case $DEPLOY_TARGET in
  backend)
    echo "🚀 重新构建并启动后端..."
    docker compose -f docker/docker-compose.yml up -d --build backend
    ;;
  frontend)
    echo "🚀 重新构建并启动前端..."
    docker compose -f docker/docker-compose.yml up -d --build frontend
    ;;
  all|*)
    echo "🚀 重新构建并启动所有服务..."
    docker compose -f docker/docker-compose.yml up -d --build
    ;;
esac

echo ""
echo "✅ 重部署完成！"
echo ""
echo "📊 容器状态:"
docker compose -f docker/docker-compose.yml ps
echo ""
echo "📝 查看日志: docker compose -f docker/docker-compose.yml logs -f"
echo "🌐 访问地址: http://localhost (通过 Nginx)"
echo "🔧 后端直连: http://localhost:5000"
echo "🎨 前端直连: http://localhost:3000"
