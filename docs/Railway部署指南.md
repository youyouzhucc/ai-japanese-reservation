# Railway 部署指南

## 一、前置准备

1. 注册 [Railway](https://railway.app) 账号（支持 GitHub 登录）
2. 确保项目已推送到 GitHub：`https://github.com/youyouzhucc/ai-japanese-reservation`

---

## 二、部署步骤

### 1. 创建新项目

1. 登录 [Railway Dashboard](https://railway.app/dashboard)
2. 点击 **New Project**
3. 选择 **Deploy from GitHub repo**
4. 授权 Railway 访问你的 GitHub，选择仓库 `ai-japanese-reservation`
5. Railway 会自动检测到 `Procfile` 和 `requirements.txt`，开始构建

### 2. 配置数据库（必做，否则数据会丢失）

Railway 文件系统是**临时的**，使用默认 SQLite 时，**每次 redeploy 或重启后预约/用户数据会全部丢失**。

**务必添加 PostgreSQL：**

1. 在 Railway 项目内点击 **+ New** → **Database** → **PostgreSQL**
2. Railway 会自动创建数据库并注入 `DATABASE_URL` 环境变量到你的 Service
3. 在 **Variables** 中确认存在 `DATABASE_URL`（格式类似 `postgresql://...`）
4. 点击 **Deploy** 或 **Redeploy** 使新变量生效

项目已内置 PostgreSQL 支持（`config.py` 会自动将 `postgresql://` 转为 `postgresql+asyncpg://`），无需手动修改。

**若 DATABASE_URL 未自动注入**：点击你的 Web Service → **Variables** → **Add Variable** → 从 PostgreSQL 服务选择 `DATABASE_URL` 引用。

### 3. 环境变量（可选）

在 **Variables** 中可配置：

| 变量名 | 说明 | 默认 |
|-------|------|------|
| `DATABASE_URL` | 数据库连接（PostgreSQL 由 Railway 自动注入） | SQLite |
| `PAYMENT_MODE` | 支付模式 | `mock` |
| `TWILIO_*` | Twilio 电话/短信（真实模式需配置） | - |
| `ALIYUN_*` | 阿里云短信（国内可选） | - |

**快速体验**：不配置任何变量即可运行（模拟模式）。

### 4. 生成公网域名

1. 点击你的 **Service**
2. 打开 **Settings** → **Networking** → **Generate Domain**
3. Railway 会分配一个 `xxx.railway.app` 域名

### 5. 部署完成

- **预约页面**：`https://你的域名.railway.app/`
- **管理后台**：`https://你的域名.railway.app/admin`

---

## 三、PostgreSQL 支持（可选）

项目已内置 PostgreSQL 支持。添加 Railway 的 PostgreSQL 插件后，`config.py` 会自动将 `postgresql://` 转为 `postgresql+asyncpg://`，无需手动修改 `DATABASE_URL`。

---

## 四、常见问题

### 构建失败

- 确认 `requirements.txt` 和 `Procfile` 存在
- 查看 Railway 构建日志排查错误

### 应用启动后 502

- 检查 `Procfile` 中 `$PORT` 是否正确（Railway 会注入）
- 确认 `uvicorn` 监听 `0.0.0.0`

### 环境变量未生效（如阿里云短信配置后仍显示未设置）

1. **点击 Deploy 保存**：在 Variables 页添加/修改变量后，若出现 **Deploy** 按钮，必须点击它才能保存并触发部署，否则变量不会生效
2. **确认 Environment**：变量需加在正确的 Environment（通常为 Production）
3. **确认 Service**：变量需加在实际运行应用的那个 Service 上
4. **Redeploy**：修改变量后，在 Deployments 页点击 Redeploy 确保新变量被注入
5. **验证**：部署完成后访问 `/api/auth/sms-status` 检查 `env_in_process` 是否全为 `true`

### 数据丢失

- SQLite 在 Railway 上会随容器重启而清空
- 生产环境务必使用 PostgreSQL

---

## 五、费用说明

- Railway 提供 **$5/月** 免费额度
- 超出后按用量计费（CPU、内存、流量等）
- 详见 [Railway Pricing](https://railway.app/pricing)
