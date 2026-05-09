import tempfile
import unittest
from pathlib import Path
from unittest import mock

import ui_server


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


if __name__ == "__main__":
    unittest.main()
