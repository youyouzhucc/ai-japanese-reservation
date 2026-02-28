# AI 日语电话接入指南

支付成功后，系统会通过 **Twilio** 拨打餐厅电话，接通后由 **OpenAI Realtime API** 驱动的 AI 用日语与店员对话，完成预约。

## 架构概览

```
用户支付成功 → 易付通回调 → 发起 Twilio 外呼
                              ↓
Twilio 拨打餐厅 → 接通 → 请求 /api/twiml/{order_no}
                              ↓
返回 TwiML（连接 WebSocket）→ wss://你的域名/media-stream?order_no=xxx
                              ↓
Twilio Media Stream ←→ 本服务 WebSocket ←→ OpenAI Realtime API
（餐厅语音）              （音频桥接）         （AI 日语对话）
```

## 前置条件

1. **Twilio 账号**：https://www.twilio.com 注册并购买可外呼的号码
2. **OpenAI API Key**：需开通 Realtime API 权限（GPT-4o Realtime）
3. **公网 HTTPS 服务**：Railway 等部署后需有固定域名

## 配置步骤

### 1. Twilio 配置

在 Twilio 控制台获取：

- `TWILIO_ACCOUNT_SID`
- `TWILIO_AUTH_TOKEN`
- `TWILIO_PHONE_NUMBER`（如 `+81xxxxxxxxxx`，日本号码需开通相应能力）

### 2. OpenAI 配置

- 在 https://platform.openai.com 创建 API Key
- 确认账号已开通 **Realtime API**（gpt-realtime 模型）
- 设置 `OPENAI_API_KEY`

### 3. 公网地址

- `APP_BASE_URL`：如 `https://ai-japanese-reservation-production.up.railway.app`
- 若未设置，会从 `QIUFK_NOTIFY_URL` 自动推导（去掉 `/api/qiufk/notify` 路径）

### 4. Railway 环境变量示例

```env
# Twilio
TWILIO_ACCOUNT_SID=ACxxxxxxxx
TWILIO_AUTH_TOKEN=xxxxxxxx
TWILIO_PHONE_NUMBER=+81xxxxxxxxxx

# OpenAI Realtime
OPENAI_API_KEY=sk-xxx

# 公网地址（或由 QIUFK_NOTIFY_URL 推导）
APP_BASE_URL=https://ai-japanese-reservation-production.up.railway.app
```

## 调试接口

- `GET /api/ai-phone-status`：检查 Twilio、OpenAI、APP_BASE_URL 是否配置完整

## 流程说明

1. **支付成功**：易付通回调 `/api/qiufk/notify`，更新订单状态为「预约中」，触发 `initiate_call`
2. **发起通话**：`ai_phone.py` 调用 Twilio API，`url` 指向 `/api/twiml/{order_no}`
3. **接通后**：Twilio 请求 TwiML URL，返回 `<Connect><Stream url="wss://.../media-stream?order_no=xxx">`
4. **Media Stream**：Twilio 与我们的 WebSocket 建立连接，音频双向流转
5. **OpenAI 桥接**：`ai_voice_stream.py` 将 Twilio 音频转发到 OpenAI Realtime，AI 用日语与店员对话
6. **状态回调**：通话结束 Twilio 回调 `/api/twilio/status`，更新订单为成功/失败，并发送短信

## 注意事项

- **日语支持**：Realtime API 支持多语言，系统提示词已配置为日语预约场景
- **电话格式**：餐厅电话需含国家/地区码（如日本 `+81`）
- **费用**：Twilio 按分钟计费，OpenAI Realtime 按使用量计费
- **模拟模式**：未配置 Twilio 时，系统走模拟模式（5 秒后返回，不实际拨打电话）

## 参考

- [Twilio Media Streams](https://www.twilio.com/docs/voice/media-streams)
- [OpenAI Realtime API](https://platform.openai.com/docs/guides/realtime)
- [Twilio + OpenAI Realtime 官方示例](https://www.twilio.com/en-us/blog/voice-ai-assistant-openai-realtime-api-python)
