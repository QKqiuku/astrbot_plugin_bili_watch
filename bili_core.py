import asyncio
import io
import json
import re
import time
from pathlib import Path

import aiohttp
from PIL import Image as PILImage

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.bilibili.com/",
}

_HTTP_TIMEOUT = aiohttp.ClientTimeout(total=30)

# 同一个进程里短时间缓存快照/字幕，避免 preview -> more 之间重复请求触发 B 站风控。
_CACHE_TTL = 300.0
_CACHE_MAX = 50
_STORY_CACHE: dict[tuple[str, int], tuple[float, dict]] = {}
_SUB_CACHE: dict[tuple[str, int, int], tuple[float, str]] = {}


def extract_bvid(raw: str) -> str:
    m = re.search(r"BV[0-9A-Za-z]{10}", raw or "", re.IGNORECASE)
    if not m:
        raise RuntimeError("没找到 BV 号，请传 BV1xxxxxxxxx 或包含 BV 号的 B 站视频链接")
    return m.group(0)


def load_credential(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def cookie_header(cred: dict) -> str:
    parts = []
    if cred.get("sessdata"):
        parts.append(f"SESSDATA={cred['sessdata']}")
    if cred.get("bili_jct"):
        parts.append(f"bili_jct={cred['bili_jct']}")
    if cred.get("buvid3"):
        parts.append(f"buvid3={cred['buvid3']}")
    if cred.get("dedeuserid"):
        parts.append(f"DedeUserID={cred['dedeuserid']}")
    return "; ".join(parts)


def _headers(cred: dict) -> dict:
    h = dict(HEADERS)
    cookie = cookie_header(cred)
    if cookie:
        h["Cookie"] = cookie
    return h


def _sprite_url(url: str) -> str:
    return "https:" + url if url.startswith("//") else url


def _cache_set(cache: dict, key, value) -> None:
    cache[key] = (time.monotonic(), value)
    if len(cache) > _CACHE_MAX:
        oldest = min(cache, key=lambda k: cache[k][0])
        cache.pop(oldest, None)


async def _get_json(
    session: aiohttp.ClientSession,
    url: str,
    params: dict | None = None,
):
    async with session.get(url, params=params, timeout=_HTTP_TIMEOUT) as resp:
        return await resp.json(content_type=None)


async def fetch_video_info(session: aiohttp.ClientSession, bvid: str) -> dict:
    payload = await _get_json(
        session,
        "https://api.bilibili.com/x/web-interface/view",
        {"bvid": bvid},
    )
    if payload.get("code") != 0:
        raise RuntimeError(
            f"B站视频信息失败: {payload.get('code')} {payload.get('message')}"
        )
    data = payload.get("data") or {}
    return {
        "title": data.get("title", ""),
        "duration": int(data.get("duration") or 0),
        "cid": int(data.get("cid") or 0),
        "desc": (data.get("desc") or "")[:300],
        "owner": (data.get("owner") or {}).get("name", ""),
    }


async def fetch_storyboard(session: aiohttp.ClientSession, bvid: str, cid: int = 0) -> dict:
    key = (bvid, int(cid or 0))
    cached = _STORY_CACHE.get(key)
    if cached and time.monotonic() - cached[0] < _CACHE_TTL:
        return cached[1]
    params = {"bvid": bvid, "index": "1"}
    if cid:
        params["cid"] = str(cid)
    payload = await _get_json(
        session,
        "https://api.bilibili.com/x/player/videoshot",
        params,
    )
    if payload.get("code") != 0:
        raise RuntimeError(
            f"B站快照失败: {payload.get('code')} {payload.get('message')}"
        )
    data = payload.get("data") or {}
    if not data.get("image"):
        raise RuntimeError("这个视频没有可用的快照拼版")
    story = {
        "images": data.get("image") or [],
        "index": data.get("index") or [],
        "x_len": int(data.get("img_x_len") or 10),
        "y_len": int(data.get("img_y_len") or 10),
        "x_size": int(data.get("img_x_size") or 160),
        "y_size": int(data.get("img_y_size") or 90),
    }
    _cache_set(_STORY_CACHE, key, story)
    return story


async def fetch_subtitle(
    session: aiohttp.ClientSession,
    bvid: str,
    cid: int,
    max_chars: int = 6000,
) -> str:
    if not cid:
        return ""
    key = (bvid, int(cid), int(max_chars or 0))
    cached = _SUB_CACHE.get(key)
    if cached and time.monotonic() - cached[0] < _CACHE_TTL:
        return cached[1]
    try:
        payload = await _get_json(
            session,
            "https://api.bilibili.com/x/player/v2",
            {"bvid": bvid, "cid": cid},
        )
        if payload.get("code") != 0:
            # 偶发 412 / -352 时重试一次；字幕失败不应该让整次看视频失败
            await asyncio.sleep(0.4)
            payload = await _get_json(
                session,
                "https://api.bilibili.com/x/player/v2",
                {"bvid": bvid, "cid": cid},
            )
        if payload.get("code") != 0:
            return ""
        subs = ((payload.get("data") or {}).get("subtitle") or {}).get("subtitles") or []
        chosen = None
        for s in subs:
            if str(s.get("lan", "")).lower().startswith(("zh", "ai-zh")):
                chosen = s
                break
        if chosen is None and subs:
            chosen = subs[0]
        if not chosen or not chosen.get("subtitle_url"):
            return ""
        url = _sprite_url(str(chosen["subtitle_url"]))
        data = await _get_json(session, url)
        lines = []
        for item in data.get("body") or []:
            text = (item.get("content") or "").strip()
            if not text:
                continue
            try:
                sec = int(float(item.get("from") or 0))
            except Exception:
                sec = 0
            lines.append(f"[{sec // 60:02d}:{sec % 60:02d}] {text}")
        out = "\n".join(lines)
        if max_chars > 0 and len(out) > max_chars:
            out = out[:max_chars] + "\n…（字幕过长已截断）"
        return out
    except Exception:
        return ""


def _frame_times(story: dict) -> list[int]:
    index = story["index"]
    if len(index) > 1:
        return [int(x) for x in index[1:]]
    per = story["x_len"] * story["y_len"]
    return list(range(len(story["images"]) * per))


def select_frames(
    story: dict,
    start: int = 0,
    end: int = 0,
    count: int = 10,
    max_frames: int = 40,
) -> list[tuple[int, int]]:
    """Return [(frame_index, timestamp), ...] for the requested range/cap."""
    times = _frame_times(story)
    if not times:
        raise RuntimeError("快照时间表为空")

    start = max(0, int(start or 0))
    end = max(0, int(end or 0))
    if end > 0 and end <= start:
        raise RuntimeError("结束时间必须大于开始时间（end=0 表示到结尾）")

    candidates = [
        (n, t)
        for n, t in enumerate(times)
        if t >= start and (end <= 0 or t <= end)
    ]
    if not candidates:
        raise RuntimeError(f"在 {start}–{end or '结尾'} 秒内没有可用快照")

    requested = int(count or 0)
    cap = max(0, int(max_frames or 0))
    if requested <= 0:
        # 0 = 未指定：有上限就用上限，没有上限就全部
        requested = cap if cap > 0 else len(candidates)
    if cap > 0:
        requested = min(requested, cap)
    requested = min(requested, len(candidates))
    requested = max(1, requested)

    if requested == 1:
        return [candidates[len(candidates) // 2]]
    if requested >= len(candidates):
        return candidates
    return [
        candidates[round(i * (len(candidates) - 1) / (requested - 1))]
        for i in range(requested)
    ]


async def crop_frames(
    session: aiohttp.ClientSession,
    story: dict,
    picks: list[tuple[int, int]],
    scale: int = 2,
) -> list[bytes]:
    x_len = story["x_len"]
    y_len = story["y_len"]
    y_size = story["y_size"]
    x_size = story["x_size"]
    per_sprite = x_len * y_len
    sprite_indices = sorted(
        {
            n // per_sprite
            for n, _ in picks
            if (n // per_sprite) < len(story["images"])
        }
    )

    sem = asyncio.Semaphore(3)

    async def fetch_sprite(sprite_idx: int):
        async with sem:
            async with session.get(
                _sprite_url(story["images"][sprite_idx]),
                timeout=_HTTP_TIMEOUT,
            ) as resp:
                resp.raise_for_status()
                return sprite_idx, await resp.read()

    downloaded = await asyncio.gather(*(fetch_sprite(i) for i in sprite_indices))
    sprite_cache = dict(downloaded)

    out: list[bytes] = []
    for n, _t in picks:
        sprite_idx = n // per_sprite
        if sprite_idx not in sprite_cache:
            continue
        pos = n % per_sprite
        row, col = divmod(pos, x_len)
        sprite = PILImage.open(io.BytesIO(sprite_cache[sprite_idx])).convert("RGB")
        box = (
            col * x_size,
            row * y_size,
            (col + 1) * x_size,
            (row + 1) * y_size,
        )
        frame = sprite.crop(box)
        if scale > 1:
            frame = frame.resize(
                (x_size * scale, y_size * scale),
                PILImage.Resampling.LANCZOS,
            )
        buf = io.BytesIO()
        frame.save(buf, format="JPEG", quality=88)
        out.append(buf.getvalue())
    return out


async def prepare(
    bvid_raw: str,
    credential_path: str,
    initial: bool,
    start: int = 0,
    end: int = 0,
    frames: int = 0,
    max_frames: int = 40,
    initial_frames: int = 10,
    subtitle_max_chars: int = 6000,
) -> dict:
    bvid = extract_bvid(bvid_raw)
    cred = load_credential(credential_path)
    max_frames = max(0, int(max_frames or 0))
    subtitle_max_chars = max(0, int(subtitle_max_chars or 0))

    async with aiohttp.ClientSession(headers=_headers(cred)) as session:
        info = await fetch_video_info(session, bvid)
        story = await fetch_storyboard(session, bvid, info["cid"])
        total = len(_frame_times(story))

        if initial:
            count = max(1, int(initial_frames or 10))
            if max_frames > 0:
                count = min(count, max_frames)
            picks = select_frames(
                story,
                start=0,
                end=0,
                count=count,
                max_frames=count,
            )
        else:
            requested = int(frames or 0)
            if requested <= 0:
                requested = max_frames if max_frames > 0 else total
            picks = select_frames(
                story,
                start=start,
                end=end,
                count=requested,
                max_frames=max_frames,
            )

        subtitle = await fetch_subtitle(
            session, bvid, info["cid"], max_chars=subtitle_max_chars
        )
        images = await crop_frames(session, story, picks)

    return {
        "bvid": bvid,
        "info": info,
        "total_frames": total,
        "picks": picks,
        "images": images,
        "subtitle": subtitle,
    }
