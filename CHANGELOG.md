# Changelog

## 0.2.0 — 2026-10-26

- 新增 `selection_mode=smart`：按字幕 cue 节点 + 时间覆盖选帧，不再纯等间隔。
- 新增 `avoid_dark`：裁到接近全黑的镜头时，尝试前后 1–3 个快照换一张可看的。
- 画面签名去重：连续两帧几乎一样时尝试相邻帧，减少重复画面。
- 字幕对齐：返回 `cue_count`，并在提示里说明选帧会靠近字幕节点。
- 保留 `selection_mode=even` 作为回退；没有字幕时 smart 自动退回时间覆盖。
- 新增说明：本插件听不到 BGM/语气，音频理解需要独立 ASR 方案。

## 0.1.1 — 2026-10-26

- `credential_path` 默认值改为 `bili_credential.json`，相对路径解析到 `data/plugin_data/astrbot_plugin_bili_watch/`，不再写死 Windows 绝对路径。
- 去掉 `sys.path.insert`，`main.py` 使用纯相对导入 `from .bili_core import prepare`。
- 保留绝对路径配置兼容：老用户填 `D:\...` 仍然有效。

## 0.1.0 — 2026-10-25

- 首个版本。
- 新增 `bili_watch_preview`：10 帧 + 字幕概览。
- 新增 `bili_watch_more`：按 `start` / `end` / `frames` 继续抽帧，支持全片。
- 抽帧上限由 `max_frames` 控制，`0` 表示允许全部快照。
- 使用 B 站官方 videoshot 快照拼版，不下载视频、不依赖 ffmpeg / yt-dlp。
- 支持 B 站 Cookie 获取 AI 字幕；字幕失败不阻断画面预览。
- 快照/字幕 5 分钟进程内缓存，降低连续 preview → more 的风控概率。
