from __future__ import annotations

import base64
import re
from pathlib import Path

from mcp.types import CallToolResult, ImageContent, TextContent

from astrbot.api import star
from astrbot.api.event import AstrMessageEvent, filter

from .bili_core import prepare


class Main(star.Star):
    def __init__(self, context: star.Context, config: dict | None = None):
        super().__init__(context, config)
        self.config = config or {}

    def _cfg(self, key: str, default):
        return (self.config or {}).get(key, default)

    def _int_cfg(self, key: str, default: int, minimum: int = 0) -> int:
        try:
            value = int(self._cfg(key, default))
        except (TypeError, ValueError):
            value = default
        return max(minimum, value)

    def _credential_path(self) -> str:
        configured = str(self._cfg("credential_path", "") or "").strip()
        path = Path(configured).expanduser() if configured else Path("bili_credential.json")
        if path.is_absolute():
            return str(path)
        try:
            return str(
                (star.StarTools.get_data_dir("astrbot_plugin_bili_watch") / path).resolve()
            )
        except Exception:
            return str(
                Path("data/plugin_data/astrbot_plugin_bili_watch") / path
            )

    def _text_result(self, text: str, is_error: bool = False) -> CallToolResult:
        return CallToolResult(
            content=[TextContent(type="text", text=text)],
            isError=is_error,
        )

    def _result(self, text: str, images: list[bytes]) -> CallToolResult:
        content = [TextContent(type="text", text=text)]
        for data in images:
            content.append(
                ImageContent(
                    type="image",
                    data=base64.b64encode(data).decode("ascii"),
                    mimeType="image/jpeg",
                )
            )
        return CallToolResult(content=content)

    def _summary(self, pack: dict, mode: str) -> str:
        info = pack["info"]
        picks = pack["picks"]
        times = [t for _, t in picks]
        lines = [
            f"【视频】{info['title']}（{pack['bvid']}）",
            f"【时长】{info['duration'] // 60} 分 {info['duration'] % 60} 秒；UP 主：{info['owner']}",
            f"【分P】{info.get('page_count', 1)} P（本次只取第 1 P / 默认 cid）",
            f"【快照】共 {pack['total_frames']} 帧，覆盖到约 {pack.get('covered_sec', 0)} 秒；本次抽 {len(pack['images'])} 帧，时间点（秒）：{times}",
            f"【字幕对齐】{pack.get('cue_count', 0)} 条字幕 cue；smart 模式下会优先靠近对话/关键节点。",
        ]
        if mode == "preview":
            lines.append(
                "【下一步】这是整片概览。如果某一段值得细看，调用 "
                "`bili_watch_more(bvid, start, end, frames)`；已知字幕时间点也可以传 "
                "`at=\"30,90,150\"`；想看全片就 start=0、end=0。"
            )
            lines.append(
                "【提示】frames 会被配置里的 max_frames 限制；max_frames=0 表示允许全部快照。"
            )
        else:
            lines.append(
                f"【续看】本次只看 {times[0] if times else 0}–{times[-1] if times else 0} 秒；"
                "如果要更细，缩小 start/end 再抽一次。"
            )
        if pack["subtitle"]:
            lines.append("【字幕】\n" + pack["subtitle"])
        else:
            lines.append("【字幕】没有获取到字幕（可能没有 AI 字幕，或 B 站登录态无效）。")
        if mode == "more" and len(pack["images"]) >= pack["total_frames"]:
            lines.append("【注意】这次已经抽了全量快照，图片很多，阅读和费用都会明显增加。")
        return "\n".join(lines)

    @filter.llm_tool(name="bili_watch_preview")
    async def bili_watch_preview(self, event: AstrMessageEvent, bvid: str):
        """先看一个 B 站视频的整体画面和字幕：抽固定数量的关键帧（默认 10 张），并带上字幕，用于判断值不值得细看。

        Args:
            bvid(string): 视频 BV 号，例如 BV1os411H7wm
        """
        initial = self._int_cfg("initial_frames", 10, minimum=1)
        max_frames = self._int_cfg("max_frames", 40, minimum=0)
        if max_frames > 0:
            initial = min(initial, max_frames)
        try:
            pack = await prepare(
                bvid_raw=bvid,
                credential_path=self._credential_path(),
                initial=True,
                initial_frames=initial,
                max_frames=initial,
                subtitle_max_chars=self._int_cfg("subtitle_max_chars", 6000, minimum=0),
                frame_width=self._int_cfg("frame_width", 480, minimum=160),
                selection_mode=str(self._cfg("selection_mode", "smart")),
                avoid_dark=bool(self._cfg("avoid_dark", True)),
            )
            self.logger.info(
                "bili_watch_preview %s: %s/%s frames, subtitle=%s chars",
                pack["bvid"], len(pack["images"]), pack["total_frames"],
                len(pack["subtitle"]),
            )
            return self._result(self._summary(pack, "preview"), pack["images"])
        except Exception as e:
            self.logger.warning(f"bili_watch_preview 失败: {e}")
            return self._text_result(f"看视频概览失败：{e}", is_error=True)

    @filter.llm_tool(name="bili_watch_more")
    async def bili_watch_more(
        self,
        event: AstrMessageEvent,
        bvid: str,
        start: int = 0,
        end: int = 0,
        frames: int = 0,
        at: str = "",
    ):
        """在概览之后，对 B 站视频的某个时间段或全片继续抽帧细看。start/end 是秒，end=0 表示到结尾；frames=0 表示用配置里的 max_frames；at 可选，逗号分隔的秒数列表，指定时间点优先。

        Args:
            bvid(string): 视频 BV 号，例如 BV1os411H7wm
            start(number): 起始秒数，0 表示开头
            end(number): 结束秒数，0 表示结尾
            frames(number): 本次最多抽几帧，0 表示使用配置上限
            at(string): 可选，逗号分隔的时间点秒数，例如 "30,90,150"；填了就以它为准，忽略 start/end
        """
        at_values = []
        at_text = str(at or "").strip()
        if at_text:
            try:
                at_values = [
                    float(x)
                    for x in re.split(r"[,，\s]+", at_text)
                    if x.strip()
                ]
            except ValueError:
                return self._text_result("at 格式不对：请用逗号分隔的秒数，例如 30,90,150。", True)
            if not at_values:
                return self._text_result("at 是空的；要么不传，要么给 30,90,150。", True)

        start = max(0, int(start or 0))
        end = max(0, int(end or 0))
        if not at_values and end > 0 and end <= start:
            return self._text_result("结束时间必须大于开始时间（end=0 表示到结尾）。", True)
        max_frames = self._int_cfg("max_frames", 40, minimum=0)
        requested = int(frames or 0)
        if requested <= 0:
            requested = max_frames if max_frames > 0 else 0
        try:
            pack = await prepare(
                bvid_raw=bvid,
                credential_path=self._credential_path(),
                initial=False,
                start=start,
                end=end,
                frames=requested,
                max_frames=max_frames,
                subtitle_max_chars=self._int_cfg("subtitle_max_chars", 6000, minimum=0),
                at=at_values or None,
                frame_width=self._int_cfg("frame_width", 480, minimum=160),
                selection_mode=str(self._cfg("selection_mode", "smart")),
                avoid_dark=bool(self._cfg("avoid_dark", True)),
            )
            self.logger.info(
                "bili_watch_more %s: %s/%s frames, range=%s-%s",
                pack["bvid"], len(pack["images"]), pack["total_frames"], start, end,
            )
            return self._result(self._summary(pack, "more"), pack["images"])
        except Exception as e:
            self.logger.warning(f"bili_watch_more 失败: {e}")
            return self._text_result(f"继续看视频失败：{e}", is_error=True)
