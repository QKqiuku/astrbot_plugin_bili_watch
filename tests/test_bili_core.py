import io
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image as PILImage

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bili_core import (  # noqa: E402
    _normalize_index,
    cookie_header,
    crop_frames,
    extract_bvid,
    load_credential,
    select_frames,
    select_smart_frames,
)


def story():
    return {
        "images": ["sprite-0.jpg", "sprite-1.jpg"],
        "index": [0, 0, 10, 20, 30, 40],
        "x_len": 2,
        "y_len": 2,
        "x_size": 160,
        "y_size": 90,
    }


class BiliWatchCoreTests(unittest.TestCase):
    def test_extract_bvid_from_plain_and_url(self):
        self.assertEqual(extract_bvid("BV1os411H7wm"), "BV1os411H7wm")
        self.assertEqual(
            extract_bvid("看看 https://www.bilibili.com/video/BV1xrnz6gEVD?p=1"),
            "BV1xrnz6gEVD",
        )
        self.assertEqual(extract_bvid("bv1os411h7wm"), "bv1os411h7wm")

    def test_extract_bvid_invalid(self):
        with self.assertRaises(RuntimeError):
            extract_bvid("https://www.bilibili.com/video/av123")

    def test_cookie_header(self):
        cookie = cookie_header(
            {
                "sessdata": "s",
                "bili_jct": "j",
                "buvid3": "b",
                "dedeuserid": "d",
            }
        )
        self.assertIn("SESSDATA=s", cookie)
        self.assertIn("bili_jct=j", cookie)
        self.assertIn("buvid3=b", cookie)
        self.assertIn("DedeUserID=d", cookie)

    def test_load_credential_missing_and_valid(self):
        self.assertEqual(load_credential(str(ROOT / "does-not-exist.json")), {})
        with (
            patch.object(Path, "exists", return_value=True),
            patch.object(Path, "read_text", return_value=json.dumps({"sessdata": "x"})),
        ):
            self.assertEqual(load_credential("x.json"), {"sessdata": "x"})

    def test_select_evenly(self):
        picks = select_frames(story(), count=3, max_frames=40)
        self.assertEqual(picks, [(0, 0), (2, 20), (4, 40)])

    def test_select_segment(self):
        picks = select_frames(story(), start=10, end=20, count=0, max_frames=0)
        self.assertEqual(picks, [(1, 10), (2, 20)])

    def test_select_all_when_no_cap(self):
        picks = select_frames(story(), count=0, max_frames=0)
        self.assertEqual(picks, [(0, 0), (1, 10), (2, 20), (3, 30), (4, 40)])

    def test_select_cap(self):
        picks = select_frames(story(), count=99, max_frames=2)
        self.assertEqual(picks, [(0, 0), (4, 40)])

    def test_select_at(self):
        picks = select_frames(story(), at=[12, 38], max_frames=10)
        self.assertEqual(picks, [(1, 10), (4, 40)])

    def test_smart_selection_uses_cues_and_count(self):
        cues = [
            {"start": 11, "end": 12, "text": "关键点 A"},
            {"start": 31, "end": 32, "text": "关键点 B"},
        ]
        picks = select_smart_frames(
            story(), cues, count=3, max_frames=3,
        )
        self.assertEqual(len(picks), 3)
        self.assertEqual(picks, sorted(picks, key=lambda x: x[1]))
        # 至少有一个选帧落在字幕节点附近（10/30 秒）
        self.assertTrue(any(abs(t - 10) <= 10 or abs(t - 30) <= 10 for _, t in picks))

    def test_smart_selection_without_cues_still_works(self):
        picks = select_smart_frames(story(), [], count=5, max_frames=5)
        self.assertEqual(len(picks), 5)
        self.assertEqual(picks, sorted(picks, key=lambda x: x[1]))

    def test_crop_frames_avoids_black_tile(self):
        class Resp:
            def __init__(self, data):
                self.data = data

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            def raise_for_status(self):
                pass

            async def read(self):
                return self.data

        class Session:
            def get(self, *args, **kwargs):
                return Resp(sprite_bytes)

        sheet = PILImage.new("RGB", (320, 90), (0, 0, 0))
        sheet.paste(PILImage.new("RGB", (160, 90), (240, 240, 240)), (160, 0))
        buf = io.BytesIO()
        sheet.save(buf, format="JPEG")
        sprite_bytes = buf.getvalue()

        frame_story = {
            "images": ["//fake/sprite.jpg"],
            "index": [0, 0, 10],
            "x_len": 2,
            "y_len": 1,
            "x_size": 160,
            "y_size": 90,
        }
        import asyncio

        images, used = asyncio.run(
            crop_frames(
                Session(),
                frame_story,
                [(0, 0)],
                width=160,
                avoid_dark=True,
                avoid_similar=True,
            )
        )
        self.assertEqual(len(images), 1)
        self.assertEqual(used, [(1, 10)])

    def test_normalize_ms_index(self):
        index = [0, 0, 8000, 14000]
        self.assertEqual(_normalize_index(index, duration=20), [0, 0, 8, 14])
        index = [0, {"timestamp": 0}, {"timestamp": 8000}]
        self.assertEqual(_normalize_index(index, duration=10), [0, 0, 8])

    def test_invalid_range(self):
        with self.assertRaises(RuntimeError):
            select_frames(story(), start=20, end=10)

    def test_empty_range(self):
        with self.assertRaises(RuntimeError):
            select_frames(story(), start=999, end=1000)


if __name__ == "__main__":
    unittest.main()
