import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bili_core import (  # noqa: E402
    cookie_header,
    extract_bvid,
    load_credential,
    select_frames,
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

    def test_invalid_range(self):
        with self.assertRaises(RuntimeError):
            select_frames(story(), start=20, end=10)

    def test_empty_range(self):
        with self.assertRaises(RuntimeError):
            select_frames(story(), start=999, end=1000)


if __name__ == "__main__":
    unittest.main()
