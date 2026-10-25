# Changelog

## 0.1.0 — 2026-10-25

- 首个版本。
- 新增 `bili_watch_preview`：10 帧 + 字幕概览。
- 新增 `bili_watch_more`：按 `start` / `end` / `frames` 继续抽帧，支持全片。
- 抽帧上限由 `max_frames` 控制，`0` 表示允许全部快照。
- 使用 B 站官方 videoshot 快照拼版，不下载视频、不依赖 ffmpeg / yt-dlp。
- 支持 B 站 Cookie 获取 AI 字幕；字幕失败不阻断画面预览。
- 快照/字幕 5 分钟进程内缓存，降低连续 preview → more 的风控概率。
