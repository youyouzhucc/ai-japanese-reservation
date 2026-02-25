# AI 日语电话预约系统

AI 自动致电日本餐厅完成日语预约，支持预约下单、支付、AI 电话、短信通知全流程。

## 功能

1. **预约支付下单**：填写餐厅名称、电话、预约人信息、预约时间（半小时间隔）、人数、备注，生成预约单
2. **预约单据**：状态为「预约中」，支持查询
3. **AI 打电话**：根据预约信息用日语致电餐厅完成预约
4. **完成预约**：返回成功/失败，更新预约单状态，发送短信通知预约人

## 技术栈

- 后端：Python 3.10+ / FastAPI / SQLAlchemy
- 前端：HTML + CSS + JavaScript
- 数据库：SQLite（可换 MySQL/PostgreSQL）
- 可选：Twilio（电话 + 短信）、阿里云短信

## 快速开始

```bash
# 1. 进入项目目录
cd ai-japanese-reservation

# 2. 创建虚拟环境（推荐）
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 复制环境变量（可选，模拟模式无需配置）
cp .env.example .env

# 5. 启动服务
python main.py
# 或
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

浏览器访问：http://localhost:8000

## Railway 一键部署

1. 打开 [Railway](https://railway.app) 并登录
2. **New Project** → **Deploy from GitHub repo** → 选择 `ai-japanese-reservation`
3. 部署会自动使用 `Dockerfile` 构建，无需额外配置
4. 部署完成后，在 **Settings** → **Networking** → **Generate Domain**
   - **端口填 8080**（Railway 默认）
   - 点击 Generate Domain
5. 访问生成的域名（如 `xxx.up.railway.app`）即可使用

## 配置说明

| 变量 | 说明 | 默认 |
|------|------|------|
| `DATABASE_URL` | 数据库连接 | sqlite+aiosqlite:///./reservations.db |
| `PAYMENT_MODE` | 支付模式 | mock（模拟） |
| `TWILIO_*` | Twilio 电话/短信 | 留空则模拟 |
| `ALIYUN_*` | 阿里云短信 | 留空则模拟 |

**模拟模式**：不配置 Twilio/阿里云时，AI 电话延迟 5 秒后自动成功，短信打印到控制台。

## 项目结构

```
ai-japanese-reservation/
├── main.py           # FastAPI 入口
├── config.py         # 配置
├── models.py         # 数据模型
├── schemas.py        # API 模型
├── services/         # 业务服务
│   ├── payment.py    # 支付
│   ├── ai_phone.py   # AI 电话
│   └── sms.py       # 短信
├── static/           # 前端
│   ├── index.html
│   ├── style.css
│   └── app.js
├── requirements.txt
├── .env.example
└── README.md
```

## API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/reservations | 创建预约 |
| POST | /api/pay | 支付并触发 AI 电话 |
| GET | /api/reservations/{order_no} | 查询预约 |
| GET | /api/reservations | 预约列表 |
| POST | /api/callback/call | AI 通话完成回调 |

---

## 如何上传到 GitHub

### 方式一：新建仓库后推送

1. **在 GitHub 创建新仓库**
   - 打开 https://github.com/new
   - 仓库名如：`ai-japanese-reservation`
   - 选择 Public，不勾选「Add a README」

2. **在本地初始化并推送**

```bash
cd ai-japanese-reservation

# 初始化 Git（若尚未初始化）
git init

# 添加所有文件
git add .

# 提交
git commit -m "feat: AI 日语电话预约系统初始版本"

# 添加远程仓库（替换为你的 GitHub 用户名和仓库名）
git remote add origin https://github.com/你的用户名/ai-japanese-reservation.git

# 推送到 main 分支
git branch -M main
git push -u origin main
```

3. **若已有 GitHub 仓库**

```bash
git remote add origin https://github.com/你的用户名/仓库名.git
git push -u origin main
```

### 方式二：使用 SSH

```bash
git remote add origin git@github.com:你的用户名/ai-japanese-reservation.git
git push -u origin main
```

### 注意事项

- `.env` 已在 `.gitignore` 中，不会被提交（保护密钥）
- 首次推送前确认 `git status`，避免提交敏感文件
- 若项目在 mothership 子目录下，可单独为 `ai-japanese-reservation` 建仓库并推送
