"""模拟投注存储测试。"""

import json
import os
import tempfile
import unittest

from web import bet_store


class TestBetStore(unittest.TestCase):
    def setUp(self) -> None:
        self._fd, self._path = tempfile.mkstemp(suffix=".sqlite3")
        os.close(self._fd)
        self._old = os.environ.get("SIM_BET_DB")
        os.environ["SIM_BET_DB"] = self._path

    def tearDown(self) -> None:
        if self._old is None:
            os.environ.pop("SIM_BET_DB", None)
        else:
            os.environ["SIM_BET_DB"] = self._old
        os.unlink(self._path)

    def test_create_slip_and_settle(self) -> None:
        sels = [
            {
                "selection_id": "x-nspf-3",
                "fixture_id": "fid1",
                "market": "nspf",
                "handicap": "",
                "outcome": "3",
                "odds": 2.0,
                "matchnum": "T1",
            }
        ]
        with bet_store.connect() as conn:
            sid = bet_store.get_or_create_default_session(conn)
            slip_id = bet_store.create_slip(
                conn, sid, "2026-01-01", sels, ["单关"], [], multiplier=1, stake_per_line=2.0
            )
            bet_store.set_result(conn, "fid1", 1, 0)
            bet_store.settle_slip(conn, slip_id)
            row = conn.execute("SELECT * FROM slips WHERE id=?", (slip_id,)).fetchone()
        self.assertEqual(row["status"], "settled")
        sub = json.loads(row["subbets_json"])
        self.assertTrue(sub[0]["won"])


if __name__ == "__main__":
    unittest.main()
