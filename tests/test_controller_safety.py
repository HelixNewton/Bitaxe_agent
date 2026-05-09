import unittest
import tempfile

from controller import Config, Controller


class ControllerSafetyTests(unittest.TestCase):
    def make_controller(self, **overrides):
        learning = tempfile.NamedTemporaryFile(delete=False)
        learning.write(b"{}")
        learning.close()
        config = Config(bitaxe_url="http://miner.local", learning_file=learning.name, **overrides)
        return Controller(config)

    def test_build_patch_clamps_frequency_voltage_and_fan(self):
        controller = self.make_controller(
            min_frequency=500,
            max_frequency=525,
            min_voltage=1000,
            max_voltage=1100,
            min_fan_percent=25,
            max_fan_percent=90,
        )

        patch = controller.build_patch(frequency=700, voltage=1200, fan_percent=100)

        self.assertEqual(patch["frequency"], 525)
        self.assertEqual(patch["coreVoltage"], 1100)
        self.assertEqual(patch["fanspeed"], 90)
        self.assertFalse(patch["autofanspeed"])

    def test_nerdminer_profile_converts_khs_to_ghs(self):
        controller = self.make_controller(miner_api_profile="nerdminer")

        state = controller.parse_state({"hashrate_kh": 75000, "temperature": 41}, {})

        self.assertAlmostEqual(state.hashrate_gh, 0.075)
        self.assertEqual(state.temperature_c, 41)


if __name__ == "__main__":
    unittest.main()
