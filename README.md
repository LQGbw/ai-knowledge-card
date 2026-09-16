# AI 新词播客采集器

这是 AI 知识卡项目的第一步：从一组可信播客中发现新单集、保存 Show Notes 和音频来源，并为后续术语识别保留证据。

当前版本刻意不做音频转写、术语生成、推荐和自动发布。采集到的单集只是后续研究与审核的原始证据。

## 能做什么

- 通过播客 RSS 增量发现新单集
- 保存节目、单集、Show Notes 和音频地址
- 使用 SQLite 保存来源、内容指纹与同步时间
- 同一单集不会重复入库，Show Notes 变化时会更新
- RSS 暂不可用的节目会保留在来源表中，等待后续补充采集方式

## 开始使用

要求 Python 3.11 或更高版本。安装一次项目依赖：

```bash
python3 -m pip install -e .
python3 -m podcast_collector sync
python3 -m podcast_collector list --limit 20
```

默认数据库位于 `data/podcasts.sqlite3`。可以通过参数修改：

```bash
python3 -m podcast_collector --database data/custom.sqlite3 sync
```

## 节目配置

节目配置位于 `config/podcasts.json`：

```json
[
  {
    "id": "example-podcast",
    "name": "Example Podcast",
    "platform_url": "https://example.com/podcast",
    "feed_url": "https://example.com/podcast.xml",
    "language": "zh-CN",
    "authority": "expert_interview",
    "enabled": true
  }
]
```

`authority` 用于描述节目在证据链中的主要角色：

- `first_hand`：提出者、项目团队或当事人直接表达
- `expert_interview`：包含一线嘉宾访谈，需要区分主播与嘉宾观点
- `secondary_digest`：转译或整理型内容，需要继续回溯原始来源

## 数据边界

采集器只保存节目公开元数据、Show Notes 和音频引用。后续做音频转写前，需要确认平台规则、节目授权和合理使用边界；面向用户发布时不应重新分发完整音频或完整逐字稿。

## 生成知识卡草稿

项目内已经提供一批基于当前标题和简介整理的草稿：

```bash
python3 -m podcast_collector import-cards data/card_drafts.json
python3 -m podcast_collector cards --limit 20
```

自动生成使用 OpenAI Responses API 的结构化输出。配置 API 密钥后运行：

```bash
export OPENAI_API_KEY="你的密钥"
python3 -m podcast_collector generate --per-podcast 5 --max-cards 10
```

默认模型是 `gpt-5.4-mini`，也可以通过 `--model` 或 `OPENAI_MODEL` 修改。生成器只把标题和 Show Notes 发送给模型，并设置 `store=false`；不会发送、下载或转写音频。

所有生成结果默认状态为 `draft`。每张卡必须绑定有效单集，而且术语或别名必须实际出现在引用材料中，否则会被过滤。

## 测试

```bash
python3 -m unittest discover -s tests -v
```

## 飞书机器人：AI 概念骰子

第一版机器人使用飞书 WebSocket 长连接。它在这台电脑上运行，不需要购买服务器或配置公网回调地址；电脑休眠或程序退出后，机器人会暂时离线。

机器人会只读 data/podcasts.sqlite3 中已有的知识卡，把收藏单独保存在 data/feishu_bot.sqlite3，支持这些消息：

- 今日卡组：显示当天六个带暗示的话题
- 1 到 6：先显示骰子过程，再揭晓对应概念
- 骰子、抽一个、换一个：掷骰后随机揭晓一张
- 收藏、取消收藏、我的收藏：管理个人知识盒
- 帮助：重新显示玩法

每次抽取都会生成一张新的知识卡，之前抽到的卡会继续留在飞书会话里。点击知识卡底部的“查看收藏”，或直接发送“我的收藏”，可以打开个人知识盒。

### 1. 在飞书开放平台创建应用

打开 https://open.feishu.cn/app ，创建一个企业自建应用，并添加“机器人”能力。然后：

1. 在“凭证与基础信息”中取得 App ID 和 App Secret。
2. 在“权限管理”中开通 im:message 和 im:message:send_as_bot。
3. 在“事件与回调 → 事件配置”中选择“使用长连接接收事件”，添加接收消息事件 im.message.receive_v1。
4. 切换到旁边的“回调配置”，选择“使用长连接接收回调”，再添加卡片回传交互 card.action.trigger。不要选择带“旧”字样的 card.action.trigger_v1。
5. 创建版本并发布，把应用的可用范围设为你自己即可。

飞书后台的栏目名称可能会随版本微调，但应始终选择长连接，而不是填写公网回调地址。

### 2. 在本机填写凭证

把 .env.example 复制为 .env，只在本机填写：

    LARK_APP_ID=你的应用ID
    LARK_APP_SECRET=你的应用密钥

不要把真实密钥发到聊天或提交到代码仓库。.gitignore 已排除 .env。

### 3. 启动

安装项目后运行：

    python3 -m feishu_bot

看到“AI 概念骰子已连接”后，在飞书中找到这个机器人并发送“今日卡组”。
