import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import ui_server
import esp32_tools


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

    def test_nerdminer_config_preserves_blank_passwords(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_file = Path(tmp) / "nerdminer-config.json"
            with mock.patch.object(ui_server, "NERDMINER_CONFIG_FILE", config_file):
                first = ui_server.write_nerdminer_config({
                    "SSID": "Lab WiFi",
                    "WifiPW": "secret-wifi",
                    "PoolUrl": "public-pool.io",
                    "PoolPort": "21496",
                    "PoolPassword": "x",
                    "BtcWallet": "bc1qexample",
                    "Timezone": "2",
                    "SaveStats": True,
                })
                self.assertEqual(first["values"]["WifiPW"], "")
                self.assertTrue(first["has_wifi_password"])

                second = ui_server.write_nerdminer_config({
                    "SSID": "Lab WiFi 2",
                    "WifiPW": "",
                    "PoolPassword": "",
                    "PoolPort": "3333",
                    "Timezone": "1",
                    "SaveStats": False,
                })
                raw = json.loads(config_file.read_text(encoding="utf-8"))

                self.assertEqual(raw["WifiPW"], "secret-wifi")
                self.assertEqual(raw["PoolPassword"], "x")
                self.assertEqual(raw["SSID"], "Lab WiFi 2")
                self.assertEqual(raw["PoolPort"], 3333)
                self.assertFalse(second["values"]["SaveStats"])

    def test_apply_nerdminer_config_posts_to_patched_device(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_file = Path(tmp) / "nerdminer-config.json"
            sent = {}

            def fake_urlopen(req, timeout):
                sent["url"] = req.full_url
                sent["timeout"] = timeout
                sent["body"] = json.loads(req.data.decode("utf-8"))
                return FakeResponse(b'{"ok":true,"saved":true,"restart":true}')

            with mock.patch.object(ui_server, "NERDMINER_CONFIG_FILE", config_file), \
                 mock.patch.object(ui_server.request, "urlopen", side_effect=fake_urlopen):
                result = ui_server.apply_nerdminer_config_to_device({
                    "DeviceUrl": "192.168.178.85",
                    "SSID": "Lab WiFi",
                    "WifiPW": "secret-wifi",
                    "PoolUrl": "public-pool.io",
                    "PoolPort": "21496",
                    "PoolPassword": "x",
                    "BtcWallet": "bc1qexample",
                    "Timezone": "2",
                    "SaveStats": True,
                })

            self.assertTrue(result["ok"])
            self.assertEqual(sent["url"], "http://192.168.178.85/api/config")
            self.assertEqual(sent["body"]["SSID"], "Lab WiFi")
            self.assertEqual(sent["body"]["BtcWallet"], "bc1qexample")
            self.assertTrue(sent["body"]["Restart"])
            self.assertNotIn("DeviceUrl", sent["body"])

    def test_nerdminer_firmware_api_patch_and_defaults_are_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "src"
            git_info = root / ".git" / "info"
            src.mkdir(parents=True)
            git_info.mkdir(parents=True)
            (git_info / "exclude").write_text("# local excludes\n", encoding="utf-8")
            (root / "platformio.ini").write_text("[env:test]\n", encoding="utf-8")
            (src / "NerdMinerV2.ino.cpp").write_text(
                '#include "monitor.h"\n'
                "void setup() {\n"
                "  /******** INIT WIFI ************/\n"
                "  init_WifiManager();\n"
                "}\n"
                "void loop() {\n"
                "  wifiManagerProcess(); // avoid delays() in loop when non-blocking and other long running code\n"
                "}\n",
                encoding="utf-8",
            )

            patch = esp32_tools.apply_nerdminer_config_api_patch(root)
            defaults = esp32_tools.write_nerdminer_firmware_defaults({
                "SSID": "Lab WiFi",
                "WifiPW": "secret-wifi",
                "PoolUrl": "public-pool.io",
                "PoolPort": 21496,
                "PoolPassword": "x",
                "BtcWallet": "bc1qexample",
                "Timezone": 2,
                "SaveStats": True,
            }, root)
            second_patch = esp32_tools.apply_nerdminer_config_api_patch(root)

            main_text = (src / "NerdMinerV2.ino.cpp").read_text(encoding="utf-8")
            local_header = (src / "config_api_local.h").read_text(encoding="utf-8")
            exclude_text = (git_info / "exclude").read_text(encoding="utf-8")

            self.assertTrue(patch["installed"])
            self.assertTrue(defaults["checks"]["local_defaults"])
            self.assertEqual(second_patch["changed"], [])
            self.assertIn('#include "config_api.h"', main_text)
            self.assertIn("applyConfigApiDefaults();", main_text)
            self.assertIn("setupConfigApi();", main_text)
            self.assertIn("configApiLoop();", main_text)
            self.assertIn('#define CONFIG_API_WIFI_SSID "Lab WiFi"', local_header)
            self.assertIn("src/config_api_local.h", exclude_text)

    def test_log_redaction_masks_tokens(self):
        line = "OPENAI_API_KEY=sk-secret123456789 PASSWORD hunter2"

        redacted = ui_server.redact_log_line(line)

        self.assertNotIn("sk-secret", redacted)
        self.assertNotIn("hunter2", redacted)

    def test_nerdminer_serial_logs_use_selected_port(self):
        with mock.patch.object(ui_server, "read_serial_log", return_value={
            "ok": True,
            "service": "nerdminer",
            "unit": "serial",
            "port": "/dev/ttyUSB0",
            "lines": ["NerdMiner v2 starting", "OPENAI_API_KEY=sk-secret123456789"],
            "message": "Captured 2 serial log line(s) from /dev/ttyUSB0.",
        }) as serial_log:
            payload = ui_server.service_logs("nerdminer", 20, port="/dev/ttyUSB0")

        serial_log.assert_called_once_with(port="/dev/ttyUSB0", seconds=3.5)
        self.assertEqual(payload["port"], "/dev/ttyUSB0")
        self.assertIn("NerdMiner v2 starting", payload["lines"][0])
        self.assertNotIn("sk-secret", "\n".join(payload["lines"]))


if __name__ == "__main__":
    unittest.main()
