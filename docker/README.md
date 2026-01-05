# Docker 部署文件

本目录包含 vibe-blog 的 Docker 部署配置。

## 文件说明

- **docker-compose.yml** - Docker Compose 配置文件，定义后端和 Nginx 服务
- **nginx.conf** - Nginx 反向代理配置，用于生产环境

## 快速开始

从项目根目录运行：

```bash
# 开发环境（仅启动后端）
docker compose -f docker/docker-compose.yml up -d backend

# 生产环境（启动后端 + Nginx）
docker compose -f docker/docker-compose.yml up -d
```

## 详细文档

完整的部署指南请参考 `docs/DOCKER_DEPLOY.md`

## 常用命令

```bash
# 查看日志
docker compose -f docker/docker-compose.yml logs -f backend

# 停止服务
docker compose -f docker/docker-compose.yml down

# 重启服务
docker compose -f docker/docker-compose.yml restart backend
```
