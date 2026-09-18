# 福三和 CRM

本地 EspoCRM 环境，使用 Docker Compose 运行。

## 当前版本

- EspoCRM: `10.0.8-apache`
- MariaDB: `11.4`

镜像标签固定在 `compose.yaml` 中，升级时修改标签并提交 Git，便于审查和回溯。

## 启动

```bash
cp .env.example .env
# 编辑 .env，替换密码
docker compose up -d
```

打开 <http://localhost:8080>，使用 `.env` 中的管理员账号登录。

## 常用命令

```bash
make ps       # 查看容器状态
make logs     # 跟踪日志
make restart  # 重启
make down     # 停止，保留数据
```

## 数据和密码

- CRM 数据保存在 Docker 卷 `fusanhe-crm_espocrm-data`。
- 服务端自定义保存在 `fusanhe-crm_espocrm-custom`，客户端自定义保存在 `fusanhe-crm_espocrm-custom-client`。
- 数据库保存在 Docker 卷 `fusanhe-crm_db-data`。
- `.env` 包含本地密码，已被 Git 忽略。
- `docker compose down` 会保留数据；`docker compose down -v` 会删除所有数据。

## 升级流程

1. 先备份数据库和 `espocrm-data` 卷。
2. 修改 `compose.yaml` 中的 EspoCRM 镜像标签。
3. 运行 `docker compose pull && docker compose up -d`。
4. 检查页面、容器状态和日志。
5. 验证通过后提交版本变更。
