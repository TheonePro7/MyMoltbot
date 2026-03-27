"""Web 应用冒烟测试。"""

import unittest

from web.app import app


class TestWebApp(unittest.TestCase):
    def setUp(self) -> None:
        self.client = app.test_client()

    def test_index_ok(self) -> None:
        # 使用本地 JSON，避免 CI 依赖外网 500
        r = self.client.get("/?source=file")
        self.assertEqual(r.status_code, 200)
        self.assertIn("足彩赔率分析", r.data.decode("utf-8"))

    def test_health(self) -> None:
        r = self.client.get("/health")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json(), {"ok": True})

    def test_history_invalid_page_defaults_to_first(self) -> None:
        r = self.client.get("/history?page=abc")
        self.assertEqual(r.status_code, 200)


if __name__ == "__main__":
    unittest.main()
