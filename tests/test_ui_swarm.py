import tempfile
import unittest
from pathlib import Path
from unittest import mock

import ui_server


class FakeResponse:
    def __init__(self, body: bytes, content_type: str = "application/json"):
        self.body = body
        self.headers = {"Content-Type": content_type}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self, _size=-1):
        return self.body


class SwarmConfigTests(unittest.TestCase):
    def test_add_and_remove_swarm_miner(self):
        with tempfile.TemporaryDirectory() as tmp:
            swarm_file = Path(tmp) / "swarm.json"
            with mock.patch.object(ui_server, "SWARM_FILE", swarm_file):
                miner = ui_server.add_swarm_miner({
                    "name": "Desk Miner",
                    "url": "192.168.1.50",
                    "api_profile": "nerdminer",
                })

                self.assertEqual(miner["url"], "http://192.168.1.50")
                self.assertEqual(miner["api_profile"], "nerdminer")
                self.assertEqual(len(ui_server.read_swarm_config()), 2)

                result = ui_server.remove_swarm_miner({"id": miner["id"]})

                self.assertTrue(result["ok"])
                remaining = ui_server.read_swarm_config()
                self.assertEqual(len(remaining), 1)
                self.assertEqual(remaining[0]["id"], "primary")

    def test_primary_miner_cannot_be_removed(self):
        with self.assertRaises(ValueError):
            ui_server.remove_swarm_miner({"id": "primary"})

    def test_nerdminer_live_probe_normalizes_json_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            status_file = Path(tmp) / "missing.json"
            miner = {
                "id": "esp32",
                "name": "ESP32 NerdMiner",
                "url": "http://192.168.178.85",
                "api_profile": "nerdminer",
                "status_file": str(status_file),
            }
            ui_server.LIVE_PROBE_CACHE.clear()
            payload = b'{"currentHashRate": 62.5, "temp": 45, "completedShares": 2, "valids": 1}'

            with mock.patch.object(ui_server.request, "urlopen", return_value=FakeResponse(payload)):
                summary = ui_server.summarize_miner(miner)

            self.assertTrue(summary["online"])
            self.assertFalse(summary["stale"])
            self.assertEqual(summary["temperature_c"], 45.0)
            self.assertAlmostEqual(summary["hashrate_gh"], 0.0000625)
            self.assertEqual(summary["last_error"], None)

    def test_nerdminer_live_probe_reports_reachable_without_telemetry(self):
        with tempfile.TemporaryDirectory() as tmp:
            status_file = Path(tmp) / "missing.json"
            miner = {
                "id": "esp32",
                "name": "ESP32 NerdMiner",
                "url": "http://192.168.178.85",
                "api_profile": "nerdminer",
                "status_file": str(status_file),
            }
            ui_server.LIVE_PROBE_CACHE.clear()

            with mock.patch.object(ui_server.request, "urlopen", return_value=FakeResponse(b"<html>NerdMiner</html>", "text/html")):
                summary = ui_server.summarize_miner(miner)

            self.assertTrue(summary["online"])
            self.assertIn("does not expose live stats", summary["last_error"])


if __name__ == "__main__":
    unittest.main()
