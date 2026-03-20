# Credentials Guide for Non-Technical Users

在使用本 Skill 进行 Section 2（官方视频评论分析）的数据采集时，我们需要获取平台的数据。为了绕过反爬机制并获取完整数据，你需要提供你的专属凭证（YouTube API Key 或 Bilibili Cookie）。

本指南专为非技术背景用户编写，只需按照以下步骤“照猫画虎”即可完成配置。

---

## 1. 如何获取 Bilibili (B站) Cookie？

B站的反爬机制非常严格。为了稳定抓取评论，你需要用自己的B站账号登录，并把浏览器里的“身份证明”（Cookie）提取出来保存为本地文件。

### 提取步骤：

1. **登录B站**：在电脑浏览器（推荐使用 Chrome 或 Edge）中打开 [Bilibili主页](https://www.bilibili.com/) 并登录你的账号。
2. **打开开发者工具**：
   - Windows/Linux：按键盘上的 `F12` 键，或者右键点击网页空白处选择“检查 (Inspect)”。
   - Mac：按 `Cmd + Option + I`。
3. **找到 Cookie 面板**：
   - 在弹出的开发者工具窗口顶部，找到 **Application (应用)** 标签页（如果没看到，点击顶部的 `>>` 展开更多选项）。
   - 在左侧侧边栏中，找到 **Storage (存储)** -> **Cookies**，然后点击展开的 `https://www.bilibili.com`。
4. **寻找关键字段**：
   在右侧的表格中，你需要找到以下几个 Name（名称）对应的值（Value）。双击 Value 单元格即可复制里面的长字符串：
   - `SESSDATA` （核心身份凭证，千万不要泄露给他人！）
   - `bili_jct`
   - `DedeUserID`
   - `buvid3`
   - `buvid4` （如果没有 buvid4 可以不填）

### 创建 cookie.json 文件：

在你的电脑上（最好是这个项目文件夹里）新建一个文本文件，命名为 `bilibili_cookie.json`，将你复制的值按照以下格式填入（保留英文双引号和格式）：

```json
{
  "SESSDATA": "填入你复制的SESSDATA值",
  "bili_jct": "填入你复制的bili_jct值",
  "DedeUserID": "填入你复制的DedeUserID值",
  "buvid3": "填入你复制的buvid3值"
}
```

**如何使用？**
在让 Agent 跑脚本时，指定这个文件即可，例如：`--cookie-file "bilibili_cookie.json"`。

---

## 2. 如何获取 YouTube API Key？

与 B 站不同，YouTube 官方提供了合法公开的数据接口（API）。你需要去谷歌云平台申请一把“免费钥匙”（API Key）。

### 申请步骤：

1. **登录 Google Cloud Console**：打开 [Google Cloud 控制台](https://console.cloud.google.com/)，用你的 Google 账号登录。
2. **创建一个新项目**：
   - 点击页面顶部左上角的“选择项目 (Select a project)”下拉菜单。
   - 在弹出的窗口右上角点击 **新建项目 (New Project)**。
   - 随便起个名字（比如 `Game-Research`），点击创建。
3. **启用 YouTube Data API v3**：
   - 确保当前处于你刚创建的项目下。
   - 在左侧菜单中找到 **API 和服务 (APIs & Services)** -> **库 (Library)**。
   - 在搜索框中输入 `YouTube Data API v3`，点击搜索结果中的第一个。
   - 点击蓝色的 **启用 (Enable)** 按钮。
4. **生成 API Key**：
   - 启用后，页面会跳转。在左侧菜单点击 **凭据 (Credentials)**。
   - 点击页面顶部的 **+ 创建凭据 (+ CREATE CREDENTIALS)**，选择 **API 密钥 (API key)**。
   - 此时会弹出一个窗口，里面有一串很长的字符（类似 `AIzaSy...`），这就是你的 API Key！点击复制图标把它保存下来。

**如何使用？**
在让 Agent 跑脚本时，直接把这串字符告诉它，或者在命令中加上 `--api-key "你的API_KEY"`。

> **注意**：YouTube API 每天有免费额度（通常是 10,000 点/天），对于日常单个游戏抓取评论完全足够，注意不要将其公开泄露在网上。

---

## 3. 给 Agent 的最简单回复格式

如果 Agent 提示你缺少凭证，不需要理解命令行参数，也不需要自己写脚本。
你只需要直接复制下面模板，填好后发给 Agent：

```text
YouTube API Key: <粘贴这里，没有就写 None>
Bilibili SESSDATA: <粘贴这里，没有就写 None>
Bilibili bili_jct: <粘贴这里，没有就写 None>
Bilibili DedeUserID: <粘贴这里，没有就写 None>
Bilibili buvid3: <粘贴这里，没有就写 None>
Bilibili buvid4: <可选，没有就写 None>
```

### 最低要求

- 如果你只提供 **YouTube API Key**，Agent 就可以先跑 YouTube 评论分析。
- 如果你只提供 **Bilibili Cookie**，Agent 就可以先跑 B 站评论分析。
- 如果两边都提供，Agent 就可以一起跑并做更完整的 Section 2 分析。

### 安全提醒

- `SESSDATA` 和 `YouTube API Key` 都属于敏感凭证，不要发到公开群聊、文档或代码仓库。
- 只在受信任的内部 Agent 工作流里提供这些值。
- 如果担心风险，可以先只给其中一个平台的凭证，先跑单平台版本。
