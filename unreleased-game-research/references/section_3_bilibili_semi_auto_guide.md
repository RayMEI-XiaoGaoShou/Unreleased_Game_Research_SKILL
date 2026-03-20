# Section 3 Bilibili Semi-Automatic Guide

这份指引给不懂技术的同事用。你的目标只有一件事：把 B站游戏详情页里已经成功返回评论正文的请求信息交给 Agent。

Agent 需要的不是复杂代码，而是你从浏览器里复制出来的 3 到 5 条信息。照着下面做就行。

---

## 1. 你要打开哪个页面？

打开目标游戏的 B站游戏详情页，例如：

- `https://www.biligame.com/detail/?id=107079`

先正常登录你的 B站账号，再继续下面步骤。

---

## 2. 如何找到 Agent 需要的请求？

1. 在页面里按 `F12` 打开开发者工具。
2. 点顶部的 `Network`。
3. 勾选 `Preserve log`。
4. 刷新页面。
5. 在过滤框里输入 `comment`。
6. 在请求列表里优先找这两个：
   - `recommend?game_base_id=...`
   - `page?game_base_id=...`
7. 先点 `recommend`，再点右侧的 `Response`。
8. 如果你在 `Response` 里能看到这些字段，就说明找对了：
   - `user_name`
   - `content`
   - `up_count`
   - `reply_count`
9. 再点 `page`，确认它的 `Response` 里也有评论正文。

如果这两个请求里都能看到评论正文，就可以继续下一步。

---

## 3. 你到底要复制什么？

你需要从浏览器里把找到的请求“以 cURL 格式”复制出来。

具体做法：
1. 在 `Network` 里右键点击那个 `recommend?...` 或 `page?...` 请求。
2. 选择 **Copy** -> **Copy as cURL (bash)**（注意必须选带 bash 的那个）。
3. 把剪贴板里的那一长串代码，原封不动地发给 Agent。

如果你找到了多个请求（比如一个 recommend，一个 page），把它们各自 `Copy as cURL (bash)` 后，分行粘贴给 Agent 就行。Agent 会自动把里面的 URL、Cookie、Referer 提取出来。

---

## 4. 最简单的回复模板

你不需要自己写脚本，也不需要手动拼接字段。直接把 cURL 贴进来：

```text
Biligame Page URL: <可选：如果 cURL 里没带 Referer，在这里补上页面地址>
<把你复制的 cURL 文本直接粘贴在这里，可以有多段>
```

---

## 5. 如果 `page` 请求没有看到怎么办？

先把页面往下滚到评论区。

如果有分页按钮、排序按钮，点一下，再看 `Network` 里有没有新的 `page?...` 请求。

如果还是没有，先把 `recommend` 那条请求给 Agent。这样通常也能先抓到一批高价值热评。

---

## 6. 常见错误

- 只截图，不复制文字：不够，Agent 最好拿到可复制文本。
- 复制了页面地址，但没复制 `Request URL`：不够。
- 复制了 `Response`，但没复制 `Cookie`：很多时候不够。
- 复制错请求：必须是能在 `Response` 里看到评论正文的 `recommend` 或 `page`。
- 只给 `summary`：通常不够，因为它经常只有评分和评论总数。

---

## 7. 安全提醒

- `Cookie` 属于敏感信息，不要发到公开群聊、公共文档或代码仓库。
- 只在受信任的内部 Agent 工作流里提供。
- 如果担心风险，可以临时开一个专门用于研究抓取的账号。

---

## 8. Agent 的最低要求

最理想：

- 页面地址（可选）
- 至少一个 `recommend` 或 `page` 请求的 cURL (bash) 文本

最低可启动：

- 至少一个 `recommend` 请求的 cURL (bash) 文本（必须带 Cookie）

这样 Agent 通常就能先抓到一批热评，后面再补分页评论。
