<div align="center">
  <img src="logo.png" width="150" alt="BiliWatch logo">
  <h1>BiliWatch · B 站分阶段看视频</h1>
  <p>先看 10 帧 + 字幕，再由模型自己决定看哪段 / 全片</p>
  <p>
    <strong>AstrBot</strong> ≥ 4.22 · <strong>License</strong> MIT ·
    <a href="README_en.md">English</a>
  </p>
</div>

---

## 这是什么

大多数 B 站插件只给模型**字幕**，或者按固定配置抽几张图；模型没有机会“先看看，再决定要不要细看”。

BiliWatch 把“看视频”拆成两次工具调用：

1. **`bili_watch_preview`**：抽 10 张关键帧 + 字幕，给模型一个整片概览；
2. **`bili_watch_more`**：模型觉得某段有意思，就传 `start` / `end` / `frames` 继续抽；想看全片就 `start=0, end=0`。

单次抽帧上限由配置 `max_frames` 控制；设为 `0` 表示允许返回视频的**全部快照**。

它不下载整段视频，不依赖 `ffmpeg` / `yt-dlp`，只读 B 站公开视频信息、官方快照拼版和字幕。

## 特性

- **两阶段、模型自选**：先预览，再决定是否细看、看哪段。
- **轻依赖**：只用 AstrBot 自带的 `aiohttp` / `Pillow` / `mcp`；不需要 ffmpeg、yt-dlp、浏览器。
- **不下载视频**：直接使用 B 站官方 `videoshot` 快照拼版，快速、省磁盘。
- **字幕可选**：配置 B 站 Cookie 后读取中文 / AI 字幕；没有字幕也能看画面。
- **上限可配**：`max_frames=0` 允许全部快照；也可以限制 20 / 40 / 60 张。
- **只读安全**：不评论、不发动态、不操作 B 站账号。
- **短缓存**：同一进程内快照/字幕缓存 5 分钟，减少连续 preview → more 的风控概率。

## 前置条件

| 条件 | 是否必需 | 说明 |
|---|---|---|
| AstrBot | 必需 | `>=4.22,<5`，实测 `4.29.1` |
| 支持图片输入的聊天模型 | 必需 | 插件把关键帧作为图片交给主模型；纯文本模型看不到画面 |
| B 站 Cookie | 可选，字幕推荐 | 放在 `bili_credential.json`；不配也能取快照，但字幕通常为空 |
| 网络 | 必需 | 能访问 `api.bilibili.com`、`i0.hdslb.com`、`aisubtitle.hdslb.com` |
| ffmpeg / yt-dlp | 不需要 | 本插件不下载视频 |
| 前置插件 | 无 | 不依赖其他 AstrBot 插件 |

> 如果你用 DeepSeek，建议使用支持视觉的 `deepseek-flash`（本项目实测环境）。模型不支持图片时，插件仍会返回图片，但模型无法理解画面。

### Cookie 文件格式

默认读取 `D:\bilibili-mcp\bili_credential.json`，也可以在插件配置里改路径：

```json
{
  "sessdata": "你的 SESSDATA",
  "bili_jct": "你的 bili_jct",
  "buvid3": "可选",
  "dedeuserid": "你的 DedeUserID"
}
```

可以复用 `adoresever/bilibili-mcp` 的凭证文件；也可以从浏览器登录 B 站后，在开发者工具 → Application → Cookies 里复制 `SESSDATA`、`bili_jct`、`DedeUserID`。

## 安装

### 插件市场（发布后）

在 AstrBot 插件市场搜索 **BiliWatch** / **B站分阶段看视频** 安装。

### 从 GitHub 手动安装

```bash
cd ~/.astrbot/data/plugins
git clone https://github.com/QKqiuku/astrbot_plugin_bili_watch.git
```

Windows 默认目录：

```text
C:\Users\<你>\.astrbot\data\plugins\astrbot_plugin_bili_watch
```

### 从 zip 安装

把 `astrbot_plugin_bili_watch.zip` 解压，确保最终目录里直接有 `main.py`：

```text
astrbot_plugin_bili_watch/
├── main.py
├── bili_core.py
├── metadata.yaml
├── _conf_schema.json
├── requirements.txt
├── README.md
├── README_en.md
├── LICENSE
├── CHANGELOG.md
└── logo.png
```

然后在 AstrBot 插件页点击 **重载插件**，或重启 AstrBot。

## 配置

在 AstrBot → 插件 → **BiliWatch · B站分阶段看视频** 中配置：

| 配置项 | 默认 | 说明 |
|---|---|---|
| `initial_frames` | `10` | 第一次概览抽多少帧；建议 6–10 |
| `max_frames` | `40` | 第二次续看单次上限；`0` = 允许全部快照 |
| `subtitle_max_chars` | `6000` | 字幕最多带多少字符；`0` = 不截断 |
| `credential_path` | `D:\bilibili-mcp\bili_credential.json` | B 站凭证路径 |

> 全量可能有一两百张甚至更多图片，视觉模型的上下文、费用和延迟都会明显增加。日常建议 `max_frames=20–40`；只有明确“整片过一遍”时才设 `0`。

## 使用

安装并启用后，在人格能力/工具里勾上：

- `bili_watch_preview`
- `bili_watch_more`

### 第一次：整体预览

对她说：

> 用 `bili_watch_preview` 看 BV1xrnz6gEVD 的画面和字幕，告诉我这视频在讲什么。

她会得到：

- 视频标题、时长、UP 主；
- 全片快照总帧数；
- 本次 10 个时间点的关键帧（图片）；
- 字幕（如果有）；
- 下一步提示：某段值得看就调用 `bili_watch_more`。

### 第二次：看某一段

> 用 `bili_watch_more` 看 BV1xrnz6gEVD 的 30–120 秒，抽 8 帧。

参数：

```text
bvid   = BV1xrnz6gEVD
start  = 30
end    = 120
frames = 8
```

### 第二次：看全片

> 用 `bili_watch_more` 看 BV1xrnz6gEVD 全片，最多 60 帧。

参数：

```text
bvid   = BV1xrnz6gEVD
start  = 0
end    = 0
frames = 60
```

`frames=0` 时使用配置的 `max_frames`；如果 `max_frames=0`，则允许返回全部快照。

### 模型会自己选吗？

会，但这是 **LLM 工具调用**，不是插件硬编码规则：

- 工具描述告诉模型“先 preview，再决定要不要 more”；
- preview 返回文本里有“下一步”提示；
- 模型根据画面 + 字幕自己判断要不要继续、看哪段；
- 插件只用 `max_frames` 做硬上限，不替模型选内容。

如果模型总是只看 10 帧，可以在人格/自由时间提示里加一句：

> 看视频先预览；只有出现明显剧情转折、想吐槽、想分享的片段，才继续抽帧细看。不要每片都全量。

## 工作原理

```mermaid
flowchart TB
  A[模型调用 bili_watch_preview] --> B[view API: 标题/时长/cid]
  B --> C[videoshot: 10x10 拼版 + 时间表]
  B --> D[player/v2: 字幕]
  C --> E[按时间均匀选 10 帧]
  E --> F[从拼版裁 160x90，放大 2 倍]
  D --> G[文本：元信息 + 字幕 + 下一步提示]
  F --> H[CallToolResult: TextContent + ImageContent...]
  G --> H
  H --> I[AstrBot 缓存图片并交给视觉模型]
  I --> J{模型判断}
  J -->|某段值得| K[bili_watch_more start/end/frames]
  J -->|没兴趣| L[不继续]
  K --> C
```

关键点：

- B 站 `videoshot` 按画面变化取帧，不是逐帧视频；每帧源图约 160×90。
- 插件把每帧放大 2 倍到 320×180，裁成 JPEG，放在 `CallToolResult` 的 `ImageContent` 里。
- AstrBot 的本地工具执行器会缓存 `ImageContent`，并把它交给视觉模型。
- 字幕来自 `x/player/v2` 的 `subtitle_url`，需要 B 站 Cookie。
- 快照和字幕在进程内缓存 5 分钟，避免 preview → more 重复请求。

## 限制

- **低分辨率**：快照源图 160×90，放大后也读不清屏幕小字；适合看场景、人物、动作，不适合 OCR。
- **不是逐帧**：B 站快照按画面变化抽样，快速动作、连续台词可能漏。
- **不是所有视频都有快照**：没有快照的视频会返回错误，可回退字幕。
- **不是所有视频都有字幕**：没有 AI 字幕/CC，或 Cookie 失效时字幕为空。
- **只支持 BV / 含 BV 的链接**：暂不解析 b23.tv 短链和 av 号。
- **默认只处理第一 P**：多 P 视频目前不传 `cid`；需要多 P 可自行扩展。
- **全量很重**：`max_frames=0` 可能返回数百张图，模型可能报图片数量/上下文超限。
- **B 站风控**：短时间高频请求可能返回 412 / -352；插件会对字幕重试一次并缓存，但请降低频率。
- **只读**：不评论、不发动态、不操作账号。

## 故障排查

### 插件加载失败

- 目录名必须是 `astrbot_plugin_bili_watch`；
- 目录里直接有 `main.py`，不是多套一层文件夹；
- AstrBot 版本 `>=4.22,<5`；
- 重载插件或重启 AstrBot；
- 查看 AstrBot 日志里的 `bili_watch` / `Traceback`。

### 她说“只看到字幕/没看到图”

- 确认人格工具里勾了 `bili_watch_preview`；
- 确认主模型支持图片输入；
- 看日志是否有：
  ```text
  Image returned and cached at path=...
  ```
- 如果只有文本、没有图片，可能是 AstrBot 版本过旧或工具返回被截断；把日志发出来。

### 没有字幕

- 检查 `credential_path` 是否存在；
- Cookie 可能过期，重新登录 B 站更新；
- 视频本身没有 AI 字幕/CC；
- B 站可能临时风控，降低频率后再试。

### “这个视频没有可用的快照拼版”

- 该视频没有 B 站视频快照；
- 换一个视频测试，或只用字幕。

### 图片太多/很慢

- 把 `max_frames` 调到 20–40；
- 不要设 `0`，除非明确要看全片；
- 缩小 `start/end` 范围再抽。

## 隐私与安全

- 只读取 B 站公开视频信息、快照和字幕；不写评论、不发动态。
- Cookie 只从本机配置路径读取，不会上传到本项目服务器（本项目没有服务器）。
- 关键帧和字幕会随 LLM 请求发送到你配置的模型提供商（例如 DeepSeek）；请自行确认其隐私政策。
- 不要把含 Cookie 的文件提交到 GitHub。

## 开发与测试

```bash
# 单元测试（纯离线，不需要 B 站网络）
python -m unittest discover -s tests -v

# 语法检查
python -m py_compile main.py bili_core.py
```

实测命令（需要网络与 Cookie）：

```python
import asyncio
from bili_core import prepare

async def main():
    pack = await prepare(
        "BV1xrnz6gEVD",
        r"D:\bilibili-mcp\bili_credential.json",
        initial=True,
        initial_frames=10,
        max_frames=10,
    )
    print(pack["total_frames"], len(pack["images"]), len(pack["subtitle"]))

asyncio.run(main())
```

项目结构：

```text
astrbot_plugin_bili_watch/
├── __init__.py          # Python 包标记，可以为空
├── main.py              # AstrBot Star、两个 LLM 工具
├── bili_core.py         # B 站 API、选帧、裁剪、字幕
├── _conf_schema.json    # 插件配置
├── metadata.yaml        # 插件市场元数据
├── tests/               # 离线单元测试
├── logo.png
├── README.md
├── README_en.md
├── LICENSE
└── CHANGELOG.md
```


## License

[MIT](LICENSE) © 2026 QKqiuku

---

[English README](README_en.md)
