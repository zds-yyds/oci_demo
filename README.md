# OCI Manager — Oracle Cloud 多租户管理平台

## 功能特性

- **多租户管理**：支持添加多个 OCI 云账户，独立管理
- **抢机任务**：可视化配置 ARM/AMD 实例抢机，实时查看日志和尝试次数
- **实例控制**：面板一键开机 / 关机 / 重启
- **账单监控**：实时拉取当月账单，图表展示每日消费趋势（自动换算 CNY）
- **消息推送**：支持邮件（SMTP）和企业微信 Webhook 双通道推送
- **用户管理**：管理员可创建多个子账户，各自管理自己的云账户

## 快速部署（Docker）

### 1. 克隆并配置

```bash
cp .env.example .env
# 编辑 .env，修改管理员密码和 SECRET_KEY
```

### 2. 一键启动

```bash
docker-compose up -d --build
```

### 3. 访问

浏览器打开 `http://your-server-ip:8080`

默认账号：`admin` / `admin123`（请立即修改密码）

---

## 使用说明

### 添加云账户

1. 进入「云账户管理」→「添加账户」
2. 填写 OCI 配置信息（User OCID、Fingerprint、Tenancy OCID、Region、私钥 PEM）
3. 点击「测试」验证连接

### 抢机

1. 进入「抢机任务」→「新建任务」
2. 选择云账户、配置规格（ARM 4C24G 推荐）
3. 填写 SSH 公钥（可选）
4. 点击「创建并启动」，实时查看日志

### 通知配置

**邮件（QQ邮箱示例）：**
- SMTP 服务器：`smtp.qq.com`，端口：`587`
- 发件人：QQ邮箱地址
- 授权码：QQ邮箱 → 设置 → 账户 → 开启 SMTP → 获取授权码

**企业微信：**
- 在企业微信群 → 群机器人 → 添加机器人 → 复制 Webhook 地址

---

## 目录结构

```
├── backend/          # FastAPI 后端
│   ├── app/
│   │   ├── main.py       # 入口
│   │   ├── models.py     # 数据库模型
│   │   ├── schemas.py    # Pydantic 模型
│   │   ├── auth.py       # JWT 认证
│   │   ├── notify.py     # 通知模块（邮件/企业微信）
│   │   ├── oci_client.py # OCI SDK 封装
│   │   ├── snipe_worker.py # 抢机后台线程
│   │   └── routers/      # API 路由
│   └── Dockerfile
├── frontend/         # Vue 3 + Element Plus 前端
│   └── Dockerfile
├── docker-compose.yml
└── .env.example
```

## 本地开发（不用 Docker）

### 1. 配置环境变量

```bash
# 把示例文件复制到 backend/ 目录下
cp .env.example backend/.env
```

编辑 `backend/.env`，主要改这几项：

```env
PG_ROOT_USER=postgres        # 你本地 postgres 超级用户名
PG_ROOT_PASSWORD=postgres    # 对应密码
DB_PASSWORD=oci123           # 自定义 oci 用户密码
SECRET_KEY=随便一串随机字符串
```

> 数据库用户和库不需要手动创建，后端启动时会自动检查并创建。

### 2. 启动后端（Conda）

```bash
cd backend

conda create -n oci-manager python=3.11 -y
conda activate oci-manager
pip install -r requirements.txt

uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

**PyCharm 配置：**
- Working Directory → `backend/`
- Script → `uvicorn`
- Parameters → `app.main:app --reload`
- Environment Variables → 留空（自动从 `backend/.env` 读取）

### 3. 启动前端

```bash
cd frontend
npm install
npm run dev
# 访问 http://localhost:5173
```

> `.env` 里的 `PORT=8080` 只给 Docker Nginx 用，本地开发无效。
> 前端 Vite 默认跑 5173，后端固定 8000，`/api` 请求由 Vite 自动代理转发。
