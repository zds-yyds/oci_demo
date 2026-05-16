# OCI Manager — Oracle Cloud 多租户管理平台

基于 FastAPI + Vue 3 + PostgreSQL 构建的 Web 端 Oracle Cloud Infrastructure 管理工具，支持多用户、多租户，覆盖实例管理、抢机、账单监控、消息推送等核心场景。

## 功能特性

### 云账户管理
- 批量添加多个 OCI 租户配置（User OCID / Fingerprint / Tenancy OCID / 私钥 PEM）
- 支持为每个租户绑定多个 Region
- 连接测试（单区域 / 全区域）
- 用户可设置默认私钥，新建租户时自动复用

### 实例管理
- 列出租户下所有区域、所有 Compartment 的实例
- 一键开机 / 关机 / 强制关机 / 重启
- 删除实例（二次确认）
- **更改实例配置** — 修改实例名称、Shape 类型、OCPU 数量、内存大小（支持 Flex 类型动态调整）

### 抢机任务
- 可视化配置 ARM / AMD 实例规格（OCPU、内存、引导卷大小）
- 自定义抢机频率（秒级间隔）
- 实时查看日志和尝试次数
- 断点续抢（服务重启后自动恢复运行中的任务）
- 抢机成功自动通知

### 账单监控
- 实时拉取当月账单（OCI Usage API）
- 按日粒度展示消费趋势（ECharts 图表）
- 自动换算 CNY（CurrencyConverter）
- 历史账单记录

### 消息推送
- 邮件通知（SMTP，支持 QQ / 163 / Gmail 等）
- 企业微信 Webhook 推送
- 按用户独立配置，互不干扰

### Web SSH 终端
- 基于 WebSocket + Paramiko 的浏览器内 SSH 终端
- 支持密码 / 私钥认证（RSA / Ed25519 / ECDSA）
- 终端大小自适应（xterm.js + FitAddon）
- SSH 凭据持久化保存，快速连接

### 用户与权限
- 管理员 / 普通用户角色
- 管理员可创建子账户
- 各用户独立管理自己的云账户和任务
- JWT 认证

### OCI 子用户管理
- 查看租户下的 IAM 用户列表

---

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python 3.11 · FastAPI · SQLAlchemy (async) · OCI SDK · Paramiko |
| 前端 | Vue 3 · Element Plus · ECharts · xterm.js · Pinia · Vite |
| 数据库 | PostgreSQL 16 (asyncpg) |
| 部署 | Docker Compose · Nginx Proxy Manager (SSL + 反代) |

---

## 目录结构

```
├── backend/                # FastAPI 后端
│   ├── app/
│   │   ├── main.py             # 入口 + 生命周期（自动建库/建表/初始化）
│   │   ├── config.py           # 环境变量配置
│   │   ├── database.py         # 异步数据库引擎
│   │   ├── models.py           # SQLAlchemy 模型
│   │   ├── schemas.py          # Pydantic 请求/响应模型
│   │   ├── auth.py             # JWT 认证
│   │   ├── notify.py           # 通知模块（邮件 / 企业微信）
│   │   ├── oci_client.py       # OCI SDK 封装
│   │   ├── snipe_worker.py     # 抢机后台线程
│   │   └── routers/
│   │       ├── auth.py         # 登录 / Token
│   │       ├── users.py        # 用户管理
│   │       ├── tenants.py      # 云账户 CRUD
│   │       ├── instances.py    # 实例管理 + 更改配置
│   │       ├── snipe.py        # 抢机任务
│   │       ├── bills.py        # 账单查询
│   │       ├── notify.py       # 通知配置
│   │       ├── regions.py      # 区域字典
│   │       ├── oci_users.py    # OCI IAM 用户
│   │       ├── terminal.py     # WebSocket SSH
│   │       └── ssh_credentials.py  # SSH 凭据管理
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/               # Vue 3 前端
│   ├── src/
│   │   ├── views/              # 页面组件
│   │   ├── api/                # Axios 封装
│   │   ├── router/             # 路由
│   │   ├── stores/             # Pinia 状态
│   │   └── layouts/            # 布局
│   ├── package.json
│   ├── vite.config.js
│   └── Dockerfile
├── docker-compose.yml      # 一键部署编排
├── .env.example            # 环境变量模板
└── oci/config.prod         # OCI 配置参考
```

---

## 快速部署（Docker Compose）

### 1. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env`，修改以下关键项：

```env
SECRET_KEY=一串随机字符串
ADMIN_USERNAME=admin
ADMIN_PASSWORD=你的管理员密码
DB_PASSWORD=oci123
```

### 2. 一键启动

```bash
docker-compose up -d --build
```

启动后包含 4 个容器：

| 容器 | 说明 |
|------|------|
| oci-manager-db | PostgreSQL 数据库 |
| oci-manager-backend | FastAPI 后端 (8000) |
| oci-manager-frontend | Nginx 静态前端 (80) |
| oci-manager-npm | Nginx Proxy Manager (80/443/81) |

### 3. 配置反向代理 + HTTPS

1. 浏览器打开 `http://your-server-ip:81` 进入 NPM 管理面板
2. 默认账号：`admin@example.com` / `changeme`（首次登录强制修改）
3. 添加 Proxy Host：域名 → `oci-manager-frontend`，端口 `80`，开启 SSL（Let's Encrypt）
4. 再添加一个 Proxy Host：`npm.your-domain.com` → `oci-manager-npm`，端口 `81`，绑定 IP 白名单
5. 确认 HTTPS 访问正常后，删掉 `docker-compose.yml` 中的 `"81:81"` 行，重新 `docker-compose up -d`

**OCI Manager 默认账号：** `admin` / `admin123`（请立即修改密码）

---

## 本地开发

### 后端

```bash
cd backend
cp ../.env.example .env   # 编辑数据库连接等配置

# Conda 环境
conda create -n oci-manager python=3.11 -y
conda activate oci-manager
pip install -r requirements.txt

# 启动（自动建库建表）
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

> 数据库用户和库不需要手动创建，后端启动时会自动检查并创建。

### 前端

```bash
cd frontend
npm install
npm run dev
# 访问 http://localhost:5173
```

> Vite 开发服务器默认将 `/api` 请求代理到 `http://localhost:8000`。

---

## API 概览

| 模块 | 路径前缀 | 说明 |
|------|----------|------|
| 认证 | `/api/auth` | 登录、Token 刷新 |
| 用户 | `/api/users` | 用户 CRUD、默认密钥管理 |
| 云账户 | `/api/tenants` | 租户 CRUD、连接测试、导入导出 |
| 实例 | `/api/instances` | 列表、操作、更改配置、删除 |
| 抢机 | `/api/snipe` | 任务 CRUD、启动/停止 |
| 账单 | `/api/bills` | 当月账单、历史记录 |
| 通知 | `/api/notify` | 通知配置、测试发送 |
| 区域 | `/api/regions` | OCI 区域字典 |
| OCI 用户 | `/api/oci-users` | IAM 用户列表 |
| SSH 终端 | `/api/terminal` | WebSocket SSH |
| SSH 凭据 | `/api/ssh-credentials` | 凭据 CRUD |
| 健康检查 | `GET /api/health` | 服务状态 |

---

## 使用说明

### 添加云账户

1. 进入「云账户管理」→「添加账户」
2. 填写 OCI 配置信息（User OCID、Fingerprint、Tenancy OCID、选择 Region、私钥 PEM）
3. 点击「测试」验证连接

### 抢机

1. 进入「抢机任务」→「新建任务」
2. 选择云账户、配置规格（ARM 4C24G 推荐）
3. 填写 SSH 公钥（可选，留空使用用户默认公钥）
4. 点击「创建并启动」，实时查看日志

### 更改实例配置

1. 进入「实例管理」，找到目标实例卡片
2. 点击「更改配置」按钮
3. 可修改：实例名称、Shape 类型、OCPU 数量、内存大小
4. 对于 Flex 类型 Shape，OCPU/内存可在运行中调整；更换 Shape 需先关机

### 通知配置

**邮件（QQ 邮箱示例）：**
- SMTP 服务器：`smtp.qq.com`，端口：`587`
- 发件人：QQ 邮箱地址
- 授权码：QQ 邮箱 → 设置 → 账户 → 开启 SMTP → 获取授权码

**企业微信：**
- 在企业微信群 → 群机器人 → 添加机器人 → 复制 Webhook 地址

---

## License

MIT
