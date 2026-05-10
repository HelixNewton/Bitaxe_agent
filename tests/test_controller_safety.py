import json
import os
import tempfile
import unittest

from controller import Config, Controller, LearningStore, MinerState, performance_metrics


def _make_state(**overrides) -> MinerState:
    defaults = dict(
        temperature_c=50.0,
        vr_temperature_c=60.0,
        frequency_mhz=500,
        voltage_mv=1100,
        frequency_options=[],
        voltage_options=[],
        fan_percent=60,
        hashrate_gh=500.0,
        hashrate_10m_gh=490.0,
        error_percentage=0.0,
        domain_spread_percentage=0.0,
        offline_domain_count=0,
        power_w=15.0,
        input_voltage_mv=5000,
        raw={},
    )
    defaults.update(overrides)
    return MinerState(**defaults)


class ControllerSafetyTests(unittest.TestCase):
    def make_controller(self, **overrides):
        learning = tempfile.NamedTemporaryFile(delete=False, suffix=".json")
        learning.write(b"{}")
        learning.close()
        config = Config(bitaxe_url="http://miner.local", learning_file=learning.name, **overrides)
        return Controller(config)

    # ------------------------------------------------------------------ #
    # Existing tests                                                       #
    # ------------------------------------------------------------------ #

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

    # ------------------------------------------------------------------ #
    # Config validation                                                    #
    # ------------------------------------------------------------------ #

    def test_config_post_init_clamps_frequency_ceiling(self):
        config = Config(bitaxe_url="http://miner.local", max_frequency=700, absolute_max_frequency=625)
        self.assertEqual(config.max_frequency, 625)

    def test_config_post_init_clamps_voltage_ceiling(self):
        config = Config(bitaxe_url="http://miner.local", max_voltage=1300, absolute_max_voltage=1150)
        self.assertEqual(config.max_voltage, 1150)

    def test_config_post_init_clamps_emergency_temp(self):
        config = Config(bitaxe_url="http://miner.local", emergency_temp_c=80.0, absolute_max_emergency_temp_c=70.0)
        self.assertEqual(config.emergency_temp_c, 70.0)

    def test_config_temp_ordering_is_enforced(self):
        # Setting cool > target > hot is corrected by __post_init__
        config = Config(
            bitaxe_url="http://miner.local",
            cool_temp_c=70.0,
            target_temp_c=60.0,
            hot_temp_c=50.0,
        )
        self.assertLessEqual(config.cool_temp_c, config.target_temp_c)
        self.assertLessEqual(config.target_temp_c, config.hot_temp_c)

    # ------------------------------------------------------------------ #
    # LearningStore robustness                                             #
    # ------------------------------------------------------------------ #

    def test_learning_store_survives_invalid_json(self):
        with tempfile.NamedTemporaryFile(delete=False, mode="w", suffix=".json") as f:
            f.write("NOT_JSON{{{{")
            path = f.name
        try:
            store = LearningStore(path)
            self.assertEqual(len(store.records), 0)
        finally:
            os.unlink(path)

    def test_learning_store_ignores_unknown_fields(self):
        record = {
            "frequency_mhz": 500,
            "voltage_mv": 1100,
            "samples": 5,
            "stable_samples": 4,
            "unstable_samples": 1,
            "unknown_future_field": "should_be_ignored",
        }
        with tempfile.NamedTemporaryFile(delete=False, mode="w", suffix=".json") as f:
            json.dump({"records": [record]}, f)
            path = f.name
        try:
            store = LearningStore(path)
            self.assertEqual(len(store.records), 1)
            rec = store.get(500, 1100)
            self.assertIsNotNone(rec)
            self.assertEqual(rec.samples, 5)
        finally:
            os.unlink(path)

    def test_learning_store_skips_malformed_record_keeps_good_ones(self):
        records = [
            {"frequency_mhz": 500, "voltage_mv": 1100, "samples": 3, "stable_samples": 3, "unstable_samples": 0},
            {"frequency_mhz": "BAD", "voltage_mv": None},  # invalid — missing required int
        ]
        with tempfile.NamedTemporaryFile(delete=False, mode="w", suffix=".json") as f:
            json.dump({"records": records}, f)
            path = f.name
        try:
            store = LearningStore(path)
            # Only the valid record should load
            self.assertEqual(len(store.records), 1)
        finally:
            os.unlink(path)

    # ------------------------------------------------------------------ #
    # Domain spread counter decay                                          #
    # ------------------------------------------------------------------ #

    def test_domain_spread_counter_decays_on_clean_poll(self):
        controller = self.make_controller()
        # Trigger two breach polls
        breach_state = _make_state(domain_spread_percentage=99.0)
        controller.update_domain_spread_tracking(breach_state)
        controller.update_domain_spread_tracking(breach_state)
        self.assertEqual(controller.domain_spread_breach_count, 2)

        # One clean poll should decay by 1, not reset to 0
        clean_state = _make_state(domain_spread_percentage=0.0)
        controller.update_domain_spread_tracking(clean_state)
        self.assertEqual(controller.domain_spread_breach_count, 1)

    def test_domain_spread_counter_does_not_go_below_zero(self):
        controller = self.make_controller()
        clean_state = _make_state(domain_spread_percentage=0.0)
        for _ in range(5):
            controller.update_domain_spread_tracking(clean_state)
        self.assertEqual(controller.domain_spread_breach_count, 0)
        self.assertEqual(controller.domain_spread_critical_count, 0)

    # ------------------------------------------------------------------ #
    # Power penalty clamping                                               #
    # ------------------------------------------------------------------ #

    def test_power_penalty_is_clamped(self):
        config = Config(bitaxe_url="http://miner.local", max_power_w=15.0)
        # Extreme over-power (power_ratio >> 1)
        state = _make_state(power_w=150.0, hashrate_10m_gh=500.0)
        metrics = performance_metrics(state, config)
        # Penalty must not exceed 3× the stable hashrate
        self.assertLessEqual(metrics["power_penalty"], 500.0 * 3.0)


if __name__ == "__main__":
    unittest.main()
