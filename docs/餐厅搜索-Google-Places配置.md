# 餐厅搜索 - 数据源配置指南

## 免费方案（默认已启用）

**OpenStreetMap Overpass API** 已内置，**无需任何配置**即可使用：
- ✅ 完全免费，无 API Key
- ✅ 真实全球餐厅数据
- ⚠️ 电话覆盖率取决于 OSM 社区贡献，日本部分餐厅可能无电话

当 OSM 无结果时，会自动回退到 mock 示例数据。

---

## 付费方案（数据更全）

要获得**更完整的电话覆盖**，可配置 **Google Places API**。

## 一、获取 Google Places API Key

### 1. 创建 Google Cloud 项目

1. 打开 [Google Cloud Console](https://console.cloud.google.com/)
2. 点击顶部项目选择器 → **新建项目**
3. 输入项目名称（如 `ai-japanese-reservation`）→ 创建

### 2. 启用 Places API

1. 在左侧菜单选择 **API 和服务** → **库**
2. 搜索 **Places API**，点击进入
3. 点击 **启用**

> 提示：Places API 包含 Text Search 和 Place Details，一次启用即可。

### 3. 创建 API 密钥

1. 左侧菜单 **API 和服务** → **凭据**
2. 点击 **+ 创建凭据** → **API 密钥**
3. 复制生成的密钥（形如 `AIzaSy...`）

### 4. 限制 API 密钥（推荐）

1. 在凭据列表点击刚创建的 API 密钥
2. **API 限制**：选择「限制密钥」，勾选 **Places API**
3. **应用限制**：可选「HTTP 引荐来源」限制为你的域名

## 二、配置到项目

在项目根目录的 `.env` 文件中添加：

```env
GOOGLE_PLACES_API_KEY=AIzaSy你的密钥
```

## 三、费用说明

- Google Places API 按调用次数计费
- 新用户有免费额度（约 $200/月）
- 每次搜索：1 次 Text Search + 最多 5 次 Place Details ≈ 6 次调用
- 详见 [Places API 定价](https://developers.google.com/maps/billing-and-pricing/pricing#places)

## 四、验证

配置完成后重启应用，在搜索框输入餐厅名（如「神户牛铁板烧」「寿司 东京」），应能返回真实餐厅及电话。

## 五、方案对比

| 方案 | 费用 | 配置 | 电话覆盖率 |
|------|------|------|------------|
| **OpenStreetMap** | 免费 | 无需 | 中等（依赖社区） |
| **Google Places** | $200/月免费额度 | 需 API Key | 高 |
| **Mock** | 免费 | 无需 | 仅示例数据 |

## 六、国内访问说明

- **OpenStreetMap**：国内可访问
- **Google Places**：需代理/VPN，或改用高德/百度 POI API（需自行接入）
