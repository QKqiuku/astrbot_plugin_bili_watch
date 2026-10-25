# Changelog

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
