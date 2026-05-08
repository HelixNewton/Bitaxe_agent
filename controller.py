#!/usr/bin/env python3
import argparse
import json
import logging
import os
import sys
import time
from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional
from urllib import error, parse, request


def app_base_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    return int(value) if value is not None else default


def env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    return float(value) if value is not None else default


def env_str(*names: str, default: Optional[str] = None) -> Optional[str]:
    for name in names:
        value = os.getenv(name)
        if value is not None and value.strip():
            return value.strip()
    return default


def env_path(*names: str, default_name: str) -> str:
    value = env_str(*names, default=default_name) or default_name
    if os.path.isabs(value):
        return value
    return os.path.join(app_base_dir(), value)


SENSITIVE_RAW_KEY_PARTS = {
    "cert",
    "coinbase",
    "hostname",
    "mac",
    "script",
    "ssid",
    "stratumurl",
    "stratumuser",
    "user",
}

SENSITIVE_RAW_KEYS = {
    "dnsserver",
    "fallbackstratumcert",
    "fallbackstratumurl",
    "fallbackstratumuser",
    "gateway",
    "hostname",
    "ip",
    "ipv4",
    "ipv6",
    "macaddr",
    "netmask",
    "scriptsig",
    "ssid",
    "stratumcert",
    "stratumurl",
    "stratumuser",
}


def ensure_parent_dir(path: str) -> None:
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)


def is_sensitive_key(key: str) -> bool:
    normalized = "".join(char for char in key.lower() if char.isalnum())
    if normalized in SENSITIVE_RAW_KEYS:
        return True
    if normalized.endswith("address") or normalized.endswith("addr"):
        return True
    return any(part in normalized for part in SENSITIVE_RAW_KEY_PARTS)


def sanitize_raw(value: Any, key: str = "") -> Any:
    if key and is_sensitive_key(key):
        return "[redacted]"
    if isinstance(value, dict):
        return {item_key: sanitize_raw(item_value, item_key) for item_key, item_value in value.items()}
    if isinstance(value, list):
        return [sanitize_raw(item) for item in value]
    return value


def redact_url(url: str) -> str:
    try:
        parsed = parse.urlsplit(url)
    except ValueError:
        return "[redacted]"
    if not parsed.scheme or not parsed.netloc:
        return "[redacted]"
    hostname = "miner.local"
    if parsed.port:
        hostname = f"{hostname}:{parsed.port}"
    return parse.urlunsplit((parsed.scheme, hostname, parsed.path, "", ""))


@dataclass
class Config:
    bitaxe_url: str
    miner_name: str = "Bitaxe"
    miner_api_profile: str = "axeos"
    info_path: str = "/api/system/info"
    asic_path: str = "/api/system/asic"
    settings_path: str = "/api/system"
    frequency_field: str = "frequency"
    voltage_field: str = "coreVoltage"
    fan_speed_field: str = "fanspeed"
    auto_fan_field: str = "autofanspeed"
    loop_seconds: int = 30
    mode: str = "rules"
    dry_run: bool = False
    auto_fan: bool = False
    min_frequency: int = 425
    max_frequency: int = 600
    absolute_max_frequency: int = 625
    freq_step: int = 25
    min_voltage: int = 1100
    max_voltage: int = 1300
    absolute_max_voltage: int = 1150
    voltage_step: int = 10
    target_temp_c: float = 58.0
    hot_temp_c: float = 64.0
    emergency_temp_c: float = 70.0
    absolute_max_emergency_temp_c: float = 70.0
    cool_temp_c: float = 52.0
    max_vr_temp_c: float = 90.0
    absolute_max_vr_temp_c: float = 75.0
    min_input_voltage_mv: int = 4800
    max_power_w: float = 18.0
    absolute_max_power_w: float = 18.0
    climb_power_ratio: float = 0.90
    min_fan_percent: int = 50
    max_fan_percent: int = 100
    step_cooldown_seconds: int = 180
    min_hashrate_gh: float = 0.0
    use_asic_options: bool = False
    max_error_percentage: float = 20.0
    max_domain_spread_percentage: float = 10.0
    critical_domain_spread_percentage: float = 18.0
    domain_spread_polls: int = 2
    learning_enabled: bool = True
    learning_min_samples: int = 3
    learning_bad_limit: int = 2
    learning_restore_margin: float = 0.03
    learning_efficiency_weight: float = 0.25
    adaptive_cooldown_enabled: bool = True
    adaptive_min_cooldown_seconds: int = 45
    adaptive_max_cooldown_seconds: int = 240
    adaptive_stable_samples: int = 8
    status_file: str = os.path.join(app_base_dir(), "status.json")
    learning_file: str = os.path.join(app_base_dir(), "learning.json")
    ai_api_url: Optional[str] = None
    ai_api_key: Optional[str] = None
    ai_model: Optional[str] = None

    @classmethod
    def from_env(cls) -> "Config":
        bitaxe_url = env_str("MINER_URL", "BITAXE_URL")
        if not bitaxe_url:
            raise SystemExit("MINER_URL or BITAXE_URL is required")
        return cls(
            bitaxe_url=bitaxe_url.rstrip("/"),
            miner_name=env_str("MINER_NAME", "BITAXE_NAME", default="Bitaxe") or "Bitaxe",
            miner_api_profile=env_str("MINER_API_PROFILE", "BITAXE_API_PROFILE", default="axeos") or "axeos",
            info_path=env_str("MINER_INFO_PATH", "BITAXE_INFO_PATH", default="/api/system/info") or "/api/system/info",
            asic_path=env_str("MINER_ASIC_PATH", "BITAXE_ASIC_PATH", default="/api/system/asic") or "/api/system/asic",
            settings_path=env_str("MINER_SETTINGS_PATH", "BITAXE_SETTINGS_PATH", default="/api/system") or "/api/system",
            frequency_field=env_str("MINER_FREQUENCY_FIELD", default="frequency") or "frequency",
            voltage_field=env_str("MINER_VOLTAGE_FIELD", default="coreVoltage") or "coreVoltage",
            fan_speed_field=env_str("MINER_FAN_SPEED_FIELD", default="fanspeed") or "fanspeed",
            auto_fan_field=env_str("MINER_AUTO_FAN_FIELD", default="autofanspeed") or "autofanspeed",
            loop_seconds=env_int("BITAXE_LOOP_SECONDS", 30),
            mode=os.getenv("BITAXE_MODE", "rules").strip().lower(),
            dry_run=env_bool("BITAXE_DRY_RUN", False),
            auto_fan=env_bool("BITAXE_AUTO_FAN", False),
            min_frequency=env_int("BITAXE_MIN_FREQUENCY", 425),
            max_frequency=env_int("BITAXE_MAX_FREQUENCY", 600),
            absolute_max_frequency=env_int("BITAXE_ABSOLUTE_MAX_FREQUENCY", 625),
            freq_step=env_int("BITAXE_FREQ_STEP", 25),
            min_voltage=env_int("BITAXE_MIN_VOLTAGE", 1100),
            max_voltage=env_int("BITAXE_MAX_VOLTAGE", 1300),
            absolute_max_voltage=env_int("BITAXE_ABSOLUTE_MAX_VOLTAGE", 1150),
            voltage_step=env_int("BITAXE_VOLTAGE_STEP", 10),
            target_temp_c=env_float("BITAXE_TARGET_TEMP_C", 58.0),
            hot_temp_c=env_float("BITAXE_HOT_TEMP_C", 64.0),
            emergency_temp_c=env_float("BITAXE_EMERGENCY_TEMP_C", 70.0),
            absolute_max_emergency_temp_c=env_float("BITAXE_ABSOLUTE_MAX_EMERGENCY_TEMP_C", 70.0),
            cool_temp_c=env_float("BITAXE_COOL_TEMP_C", 52.0),
            max_vr_temp_c=env_float("BITAXE_MAX_VR_TEMP_C", 90.0),
            absolute_max_vr_temp_c=env_float("BITAXE_ABSOLUTE_MAX_VR_TEMP_C", 75.0),
            min_input_voltage_mv=env_int("BITAXE_MIN_INPUT_VOLTAGE_MV", 4800),
            max_power_w=env_float("BITAXE_MAX_POWER_W", 18.0),
            absolute_max_power_w=env_float("BITAXE_ABSOLUTE_MAX_POWER_W", 18.0),
            climb_power_ratio=env_float("BITAXE_CLIMB_POWER_RATIO", 0.90),
            min_fan_percent=env_int("BITAXE_MIN_FAN_PERCENT", 50),
            max_fan_percent=env_int("BITAXE_MAX_FAN_PERCENT", 100),
            step_cooldown_seconds=env_int("BITAXE_STEP_COOLDOWN_SECONDS", 180),
            min_hashrate_gh=env_float("BITAXE_MIN_HASHRATE_GH", 0.0),
            use_asic_options=env_bool("BITAXE_USE_ASIC_OPTIONS", False),
            max_error_percentage=env_float("BITAXE_MAX_ERROR_PERCENTAGE", 20.0),
            max_domain_spread_percentage=env_float("BITAXE_MAX_DOMAIN_SPREAD_PERCENTAGE", 10.0),
            critical_domain_spread_percentage=env_float("BITAXE_CRITICAL_DOMAIN_SPREAD_PERCENTAGE", 18.0),
            domain_spread_polls=env_int("BITAXE_DOMAIN_SPREAD_POLLS", 2),
            learning_enabled=env_bool("BITAXE_LEARNING_ENABLED", True),
            learning_min_samples=env_int("BITAXE_LEARNING_MIN_SAMPLES", 3),
            learning_bad_limit=env_int("BITAXE_LEARNING_BAD_LIMIT", 2),
            learning_restore_margin=env_float("BITAXE_LEARNING_RESTORE_MARGIN", 0.03),
            learning_efficiency_weight=env_float("BITAXE_LEARNING_EFFICIENCY_WEIGHT", 0.25),
            adaptive_cooldown_enabled=env_bool("BITAXE_ADAPTIVE_COOLDOWN_ENABLED", True),
            adaptive_min_cooldown_seconds=env_int("BITAXE_ADAPTIVE_MIN_COOLDOWN_SECONDS", 45),
            adaptive_max_cooldown_seconds=env_int("BITAXE_ADAPTIVE_MAX_COOLDOWN_SECONDS", 240),
            adaptive_stable_samples=env_int("BITAXE_ADAPTIVE_STABLE_SAMPLES", 8),
            status_file=env_path("MINER_STATUS_FILE", "BITAXE_STATUS_FILE", default_name="status.json"),
            learning_file=env_path("MINER_LEARNING_FILE", "BITAXE_LEARNING_FILE", default_name="learning.json"),
            ai_api_url=os.getenv("AI_API_URL", "https://api.openai.com/v1/responses"),
            ai_api_key=os.getenv("AI_API_KEY") or os.getenv("OPENAI_API_KEY"),
            ai_model=os.getenv("AI_MODEL"),
        )

    def __post_init__(self) -> None:
        self.absolute_max_frequency = min(self.absolute_max_frequency, 625)
        self.absolute_max_voltage = min(self.absolute_max_voltage, 1150)
        self.absolute_max_emergency_temp_c = min(self.absolute_max_emergency_temp_c, 70.0)
        self.absolute_max_vr_temp_c = min(self.absolute_max_vr_temp_c, 75.0)
        self.absolute_max_power_w = min(self.absolute_max_power_w, 18.0)
        self.max_frequency = min(self.max_frequency, self.absolute_max_frequency)
        self.max_voltage = min(self.max_voltage, self.absolute_max_voltage)
        self.emergency_temp_c = min(self.emergency_temp_c, self.absolute_max_emergency_temp_c)
        self.max_vr_temp_c = min(self.max_vr_temp_c, self.absolute_max_vr_temp_c)
        self.max_power_w = min(self.max_power_w, self.absolute_max_power_w)
        self.climb_power_ratio = max(0.50, min(0.99, self.climb_power_ratio))
        self.min_frequency = min(self.min_frequency, self.max_frequency)
        self.min_voltage = min(self.min_voltage, self.max_voltage)
        self.hot_temp_c = min(self.hot_temp_c, self.emergency_temp_c)
        self.target_temp_c = min(self.target_temp_c, self.hot_temp_c)
        self.cool_temp_c = min(self.cool_temp_c, self.target_temp_c)


@dataclass
class MinerState:
    temperature_c: float
    vr_temperature_c: float
    frequency_mhz: int
    voltage_mv: int
    frequency_options: Any
    voltage_options: Any
    fan_percent: int
    hashrate_gh: float
    hashrate_10m_gh: float
    error_percentage: float
    domain_spread_percentage: float
    offline_domain_count: int
    power_w: float
    input_voltage_mv: int
    raw: Dict[str, Any]


@dataclass
class LearningRecord:
    frequency_mhz: int
    voltage_mv: int
    samples: int = 0
    stable_samples: int = 0
    unstable_samples: int = 0
    best_hashrate_gh: float = 0.0
    avg_hashrate_gh: float = 0.0
    best_hashrate_10m_gh: float = 0.0
    avg_hashrate_10m_gh: float = 0.0
    best_efficiency_gh_per_w: float = 0.0
    avg_efficiency_gh_per_w: float = 0.0
    best_score: float = 0.0
    avg_score: float = 0.0
    min_score: float = 0.0
    max_total_penalty: float = 0.0
    max_temperature_c: float = 0.0
    max_power_w: float = 0.0
    max_error_percentage: float = 0.0
    max_domain_spread_percentage: float = 0.0
    last_seen_at: str = ""
    last_unstable_at: str = ""

    @property
    def key(self) -> str:
        return f"{self.frequency_mhz}:{self.voltage_mv}"


def get_first_number(data: Dict[str, Any], *keys: str, default: float = 0.0) -> float:
    for key in keys:
        if key in data and data[key] not in (None, ""):
            try:
                return float(data[key])
            except (TypeError, ValueError):
                continue
    return default


def clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def parse_int_list(value: Any) -> list[int]:
    if not isinstance(value, list):
        return []
    out = []
    for item in value:
        try:
            out.append(int(item))
        except (TypeError, ValueError):
            continue
    return sorted(set(out))


def parse_domain_metrics(data: Dict[str, Any]) -> tuple[float, int]:
    domains = data.get("hashrateMonitor", {}).get("asics", [{}])[0].get("domains", [])
    if not isinstance(domains, list):
        return 0.0, 0
    numeric_domains: list[float] = []
    for item in domains:
        try:
            numeric_domains.append(float(item))
        except (TypeError, ValueError):
            numeric_domains.append(0.0)
    if not numeric_domains:
        return 0.0, 0
    active_domains = [value for value in numeric_domains if value > 0]
    offline_count = len(numeric_domains) - len(active_domains)
    if not active_domains:
        return 100.0, offline_count
    average = sum(active_domains) / len(active_domains)
    weakest = min(active_domains)
    spread = ((average - weakest) / average) * 100 if average > 0 else 0.0
    return spread, offline_count


def prev_setting(current: int, minimum: int, step: int, options: list[int], use_options: bool) -> int:
    if use_options and options:
        allowed = [value for value in options if minimum <= value < current]
        return allowed[-1] if allowed else max(minimum, min(options))
    return clamp(current - step, minimum, current)


def next_setting(current: int, maximum: int, step: int, options: list[int], use_options: bool) -> int:
    if use_options and options:
        allowed = [value for value in options if current < value <= maximum]
        return allowed[0] if allowed else min(maximum, max(options))
    return clamp(current + step, current, maximum)


def efficiency_gh_per_w(state: MinerState) -> float:
    return state.hashrate_10m_gh / state.power_w if state.power_w > 0 else 0.0


def performance_metrics(state: MinerState, config: Config) -> Dict[str, float]:
    stable_hashrate = state.hashrate_10m_gh or state.hashrate_gh
    efficiency = efficiency_gh_per_w(state)
    power_ratio = state.power_w / config.max_power_w if config.max_power_w and state.power_w else 0.0
    temp_ratio = state.temperature_c / config.hot_temp_c if config.hot_temp_c else 1.0
    fan_ratio = state.fan_percent / config.max_fan_percent if config.max_fan_percent else 1.0
    error_ratio = state.error_percentage / config.max_error_percentage if config.max_error_percentage else 1.0
    domain_ratio = (
        state.domain_spread_percentage / config.max_domain_spread_percentage
        if config.max_domain_spread_percentage
        else 1.0
    )
    base_score = stable_hashrate + (efficiency * config.learning_efficiency_weight)
    power_penalty = max(0.0, power_ratio - 0.92) * stable_hashrate * 2.0
    temp_penalty = max(0.0, temp_ratio - 0.90) * 120.0
    fan_penalty = max(0.0, fan_ratio - 0.85) * 80.0
    error_penalty = max(0.0, error_ratio - 0.20) * 80.0
    domain_penalty = max(0.0, domain_ratio - 0.70) * 100.0
    total_penalty = power_penalty + temp_penalty + fan_penalty + error_penalty + domain_penalty
    return {
        "stable_hashrate_gh": stable_hashrate,
        "efficiency_gh_per_w": efficiency,
        "base_score": base_score,
        "power_penalty": power_penalty,
        "temperature_penalty": temp_penalty,
        "fan_penalty": fan_penalty,
        "error_penalty": error_penalty,
        "domain_spread_penalty": domain_penalty,
        "total_penalty": total_penalty,
        "score": base_score - total_penalty,
    }


def performance_score(state: MinerState, config: Config) -> float:
    return performance_metrics(state, config)["score"]


class LearningStore:
    def __init__(self, path: str):
        self.path = path
        self.records: Dict[str, LearningRecord] = {}
        self.load()

    def load(self) -> None:
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            for item in data.get("records", []):
                record = LearningRecord(**item)
                self.records[record.key] = record
        except Exception as exc:
            logging.warning("failed to load learning file %s: %s", self.path, exc)

    def save(self) -> None:
        payload = {
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "records": [asdict(record) for record in self.records.values()],
        }
        tmp_path = f"{self.path}.tmp"
        ensure_parent_dir(self.path)
        with open(tmp_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
        os.replace(tmp_path, self.path)

    def record(self, state: MinerState, stable: bool, config: Config) -> LearningRecord:
        key = f"{state.frequency_mhz}:{state.voltage_mv}"
        record = self.records.get(key)
        if record is None:
            record = LearningRecord(frequency_mhz=state.frequency_mhz, voltage_mv=state.voltage_mv)
            self.records[key] = record
        record.samples += 1
        if stable:
            record.stable_samples += 1
        else:
            record.unstable_samples += 1
            record.last_unstable_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        previous_total = record.samples - 1
        efficiency = efficiency_gh_per_w(state)
        metrics = performance_metrics(state, config)
        score = metrics["score"]
        record.avg_hashrate_gh = (
            ((record.avg_hashrate_gh * previous_total) + state.hashrate_gh) / record.samples
            if record.samples
            else state.hashrate_gh
        )
        record.avg_hashrate_10m_gh = (
            ((record.avg_hashrate_10m_gh * previous_total) + state.hashrate_10m_gh) / record.samples
            if record.samples
            else state.hashrate_10m_gh
        )
        record.avg_efficiency_gh_per_w = (
            ((record.avg_efficiency_gh_per_w * previous_total) + efficiency) / record.samples
            if record.samples
            else efficiency
        )
        record.avg_score = (
            ((record.avg_score * previous_total) + score) / record.samples
            if record.samples
            else score
        )
        record.best_hashrate_gh = max(record.best_hashrate_gh, state.hashrate_gh)
        record.best_hashrate_10m_gh = max(record.best_hashrate_10m_gh, state.hashrate_10m_gh)
        record.best_efficiency_gh_per_w = max(record.best_efficiency_gh_per_w, efficiency)
        record.best_score = max(record.best_score, score)
        record.min_score = score if record.samples == 1 else min(record.min_score, score)
        record.max_total_penalty = max(record.max_total_penalty, metrics["total_penalty"])
        record.max_temperature_c = max(record.max_temperature_c, state.temperature_c)
        record.max_power_w = max(record.max_power_w, state.power_w)
        record.max_error_percentage = max(record.max_error_percentage, state.error_percentage)
        record.max_domain_spread_percentage = max(record.max_domain_spread_percentage, state.domain_spread_percentage)
        record.last_seen_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        return record

    def get(self, frequency_mhz: int, voltage_mv: int) -> Optional[LearningRecord]:
        return self.records.get(f"{frequency_mhz}:{voltage_mv}")

    def best_stable(self, config: Config) -> Optional[LearningRecord]:
        max_unstable_rate = 0.20
        candidates = [
            record
            for record in self.records.values()
            if record.stable_samples >= config.learning_min_samples
            and (record.unstable_samples / max(1, record.samples)) <= max_unstable_rate
            and config.min_frequency <= record.frequency_mhz <= config.max_frequency
            and config.min_voltage <= record.voltage_mv <= config.max_voltage
            and record.max_power_w <= config.max_power_w
            and record.max_temperature_c < config.hot_temp_c
            and record.max_error_percentage < config.max_error_percentage
            and record.max_domain_spread_percentage < config.critical_domain_spread_percentage
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda record: (record.avg_score, record.best_score, record.avg_hashrate_10m_gh, record.frequency_mhz))

    def is_bad_candidate(self, frequency_mhz: int, voltage_mv: int, config: Config) -> bool:
        record = self.get(frequency_mhz, voltage_mv)
        return bool(record and record.unstable_samples >= config.learning_bad_limit and record.stable_samples == 0)

    def summary(self, config: Config) -> Dict[str, Any]:
        best = self.best_stable(config)
        return {
            "enabled": config.learning_enabled,
            "record_count": len(self.records),
            "best_stable": asdict(best) if best else None,
            "bad_candidates": [
                asdict(record)
                for record in self.records.values()
                if record.unstable_samples >= config.learning_bad_limit and record.stable_samples == 0
            ],
        }


class MinerClient:
    def __init__(self, base_url: str, info_path: str, asic_path: str, settings_path: str, timeout: int = 10):
        self.base_url = base_url.rstrip("/")
        self.info_path = info_path
        self.asic_path = asic_path
        self.settings_path = settings_path
        self.timeout = timeout

    def _request(self, method: str, path: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        body = None
        headers = {}
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = request.Request(f"{self.base_url}{path}", data=body, headers=headers, method=method)
        with request.urlopen(req, timeout=self.timeout) as response:
            text = response.read().decode("utf-8")
            return json.loads(text) if text else {}

    def get_info(self) -> Dict[str, Any]:
        return self._request("GET", self.info_path)

    def get_asic(self) -> Dict[str, Any]:
        return self._request("GET", self.asic_path)

    def patch_system(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._request("PATCH", self.settings_path, payload)


class AiAdvisor:
    def __init__(self, config: Config):
        self.url = config.ai_api_url
        self.api_key = config.ai_api_key
        self.model = config.ai_model

    def extract_output_text(self, data: Dict[str, Any]) -> str:
        if data.get("output_text"):
            return str(data["output_text"]).strip()
        chunks: list[str] = []
        for item in data.get("output", []):
            if not isinstance(item, dict):
                continue
            for content in item.get("content", []):
                if not isinstance(content, dict):
                    continue
                text = content.get("text")
                if text:
                    chunks.append(str(text))
        return "".join(chunks).strip()

    def decide(self, state: MinerState, config: Config, learning: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if not self.api_key or not self.model:
            raise RuntimeError("AI mode requires AI_API_KEY and AI_MODEL")

        safe_config = asdict(config)
        safe_config.pop("ai_api_key", None)
        metrics = performance_metrics(state, config)
        prompt = {
            "task": f"Recommend the next tuning action for {config.miner_name}.",
            "rules": {
                "return_json_only": True,
                "allowed_actions": ["hold", "raise_freq", "lower_freq", "raise_voltage", "lower_voltage", "set_fan"],
                "one_step_limit": True,
                "prefer_cooling_over_performance": True,
            },
            "config": safe_config,
            "state": {
                "temperature_c": state.temperature_c,
                "vr_temperature_c": state.vr_temperature_c,
                "frequency_mhz": state.frequency_mhz,
                "voltage_mv": state.voltage_mv,
                "fan_percent": state.fan_percent,
                "hashrate_gh": state.hashrate_gh,
                "hashrate_10m_gh": state.hashrate_10m_gh,
                "efficiency_gh_per_w": efficiency_gh_per_w(state),
                "performance_score": metrics["score"],
                "score_penalty": metrics["total_penalty"],
                "power_w": state.power_w,
                "input_voltage_mv": state.input_voltage_mv,
                "error_percentage": state.error_percentage,
                "domain_spread_percentage": state.domain_spread_percentage,
                "offline_domain_count": state.offline_domain_count,
            },
            "learning": learning or {},
            "response_schema": {
                "action": "hold|raise_freq|lower_freq|raise_voltage|lower_voltage|set_fan",
                "reason": "short string",
                "target_fan_percent": "integer or null",
            },
        }

        payload = {
            "model": self.model,
            "input": [
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "input_text",
                            "text": "You are a conservative hardware tuning controller. Respond with JSON only.",
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": json.dumps(prompt)}],
                },
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                            "name": "miner_tuning_action",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "action": {
                                "type": "string",
                                "enum": ["hold", "raise_freq", "lower_freq", "raise_voltage", "lower_voltage", "set_fan"],
                            },
                            "reason": {"type": "string"},
                            "target_fan_percent": {
                                "anyOf": [
                                    {"type": "integer"},
                                    {"type": "null"},
                                ]
                            },
                        },
                        "required": ["action", "reason", "target_fan_percent"],
                        "additionalProperties": False,
                    },
                }
            },
        }
        req = request.Request(
            self.url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with request.urlopen(req, timeout=30) as response:
            text = response.read().decode("utf-8")
            data = json.loads(text)
        raw = self.extract_output_text(data)
        if not raw:
            raise RuntimeError(f"AI response did not contain output_text: {text}")
        return json.loads(raw)


class Controller:
    def __init__(self, config: Config):
        self.config = config
        self.client = MinerClient(config.bitaxe_url, config.info_path, config.asic_path, config.settings_path)
        self.ai = AiAdvisor(config) if config.mode == "openai" else None
        self.learning = LearningStore(config.learning_file)
        self.last_change_at = 0.0
        self.last_applied: Dict[str, Any] = {}
        self.last_state: Optional[MinerState] = None
        self.last_decision: Optional[Dict[str, Any]] = None
        self.last_error: Optional[str] = None
        self.domain_spread_breach_count = 0
        self.domain_spread_critical_count = 0

    def is_state_stable(self, state: MinerState) -> bool:
        if state.temperature_c >= self.config.hot_temp_c:
            return False
        if state.vr_temperature_c >= self.config.max_vr_temp_c:
            return False
        if state.input_voltage_mv and state.input_voltage_mv < self.config.min_input_voltage_mv:
            return False
        if state.power_w and state.power_w > self.config.max_power_w:
            return False
        if state.error_percentage >= self.config.max_error_percentage:
            return False
        if state.offline_domain_count > 0:
            return False
        if state.domain_spread_percentage >= self.config.max_domain_spread_percentage:
            return False
        return True

    def record_learning(self, state: MinerState) -> None:
        if not self.config.learning_enabled:
            return
        stable = self.is_state_stable(state)
        record = self.learning.record(state, stable, self.config)
        self.learning.save()
        logging.info(
            "learning freq=%sMHz volt=%smV stable=%s samples=%s best_hash=%.2fGH best_score=%.2f",
            record.frequency_mhz,
            record.voltage_mv,
            stable,
            record.samples,
            record.best_hashrate_gh,
            record.best_score,
        )

    def parse_state(self, info: Dict[str, Any], asic: Dict[str, Any]) -> MinerState:
        merged = dict(info)
        merged.update(asic)
        temp = get_first_number(merged, "temp", "temperature", "ASIC_temp", "asic_temp", default=0.0)
        vr_temp = get_first_number(merged, "vrTemp", "vr_temp", "voltage_regulator_temp", default=0.0)
        freq = int(get_first_number(merged, "frequency", "freq", default=0.0))
        volt = int(get_first_number(merged, "coreVoltage", "core_voltage", "asic_voltage", default=0.0))
        frequency_options = parse_int_list(merged.get("frequencyOptions"))
        voltage_options = parse_int_list(merged.get("voltageOptions"))
        fan = int(get_first_number(merged, "fanSpeed", "fan_speed", "fanspeed", default=0.0))
        hashrate = get_first_number(
            merged,
            "hashRate_1m",
            "hashRate",
            "hashrate",
            "hashRate1m",
            "hashrate1m",
            "hashRateGH",
            default=0.0,
        )
        hashrate_10m = get_first_number(merged, "hashRate_10m", "hashrate_10m", "hashRate10m", "hashrate10m", default=hashrate)
        error_percentage = get_first_number(merged, "errorPercentage", "error_percentage", default=0.0)
        domain_spread_percentage, offline_domain_count = parse_domain_metrics(merged)
        power = get_first_number(merged, "power", "power_w", "powerDraw", default=0.0)
        input_mv = int(get_first_number(merged, "voltage", "inputVoltage", "input_voltage", default=0.0))
        return MinerState(
            temperature_c=temp,
            vr_temperature_c=vr_temp,
            frequency_mhz=freq,
            voltage_mv=volt,
            frequency_options=frequency_options,
            voltage_options=voltage_options,
            fan_percent=fan,
            hashrate_gh=hashrate,
            hashrate_10m_gh=hashrate_10m,
            error_percentage=error_percentage,
            domain_spread_percentage=domain_spread_percentage,
            offline_domain_count=offline_domain_count,
            power_w=power,
            input_voltage_mv=input_mv,
            raw=merged,
        )

    def build_patch(self, *, frequency: Optional[int] = None, voltage: Optional[int] = None, fan_percent: Optional[int] = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {}
        if frequency is not None:
            payload[self.config.frequency_field] = clamp(int(frequency), self.config.min_frequency, self.config.max_frequency)
        if voltage is not None:
            payload[self.config.voltage_field] = clamp(int(voltage), self.config.min_voltage, self.config.max_voltage)
        if fan_percent is not None:
            payload[self.config.fan_speed_field] = clamp(int(fan_percent), self.config.min_fan_percent, self.config.max_fan_percent)
            payload[self.config.auto_fan_field] = False
        elif self.config.auto_fan:
            payload[self.config.auto_fan_field] = True
        return payload

    def headroom(self, state: MinerState) -> Dict[str, float]:
        return {
            "temperature": state.temperature_c / self.config.hot_temp_c if self.config.hot_temp_c else 1.0,
            "vr_temperature": state.vr_temperature_c / self.config.max_vr_temp_c if self.config.max_vr_temp_c else 1.0,
            "power": state.power_w / self.config.max_power_w if self.config.max_power_w and state.power_w else 0.0,
            "error": state.error_percentage / self.config.max_error_percentage if self.config.max_error_percentage else 1.0,
            "domain_spread": state.domain_spread_percentage / self.config.max_domain_spread_percentage if self.config.max_domain_spread_percentage else 1.0,
        }

    def adaptive_cooldown_seconds(self, state: Optional[MinerState] = None) -> int:
        base = self.config.step_cooldown_seconds
        if not self.config.adaptive_cooldown_enabled or state is None:
            return base

        headroom = self.headroom(state)
        if (
            not self.is_state_stable(state)
            or headroom["temperature"] >= 0.96
            or headroom["vr_temperature"] >= 0.96
            or headroom["power"] >= 0.95
            or headroom["error"] >= 0.50
            or headroom["domain_spread"] >= 0.75
        ):
            return max(base, self.config.adaptive_max_cooldown_seconds)

        record = self.learning.get(state.frequency_mhz, state.voltage_mv)
        has_stable_history = bool(record and record.stable_samples >= self.config.adaptive_stable_samples)
        if (
            has_stable_history
            and state.temperature_c <= self.config.cool_temp_c
            and headroom["power"] <= 0.88
            and headroom["error"] <= 0.25
            and headroom["domain_spread"] <= 0.50
        ):
            return min(base, self.config.adaptive_min_cooldown_seconds)

        return base

    def can_change(self, state: Optional[MinerState] = None) -> bool:
        return (time.time() - self.last_change_at) >= self.adaptive_cooldown_seconds(state)

    def desired_fan(self, state: MinerState) -> Optional[int]:
        if self.config.auto_fan:
            return None
        if state.temperature_c >= self.config.hot_temp_c or state.vr_temperature_c >= self.config.max_vr_temp_c - 5:
            return self.config.max_fan_percent
        if state.temperature_c >= self.config.target_temp_c:
            return clamp(self.config.min_fan_percent + 20, self.config.min_fan_percent, self.config.max_fan_percent)
        return self.config.min_fan_percent

    def update_domain_spread_tracking(self, state: MinerState) -> None:
        if state.offline_domain_count > 0 or state.domain_spread_percentage >= self.config.critical_domain_spread_percentage:
            self.domain_spread_critical_count += 1
        else:
            self.domain_spread_critical_count = 0
        if state.offline_domain_count > 0 or state.domain_spread_percentage >= self.config.max_domain_spread_percentage:
            self.domain_spread_breach_count += 1
        else:
            self.domain_spread_breach_count = 0

    def learned_restore_decision(self, state: MinerState, fan: Optional[int]) -> Optional[Dict[str, Any]]:
        if not self.config.learning_enabled or not self.can_change(state) or not self.is_state_stable(state):
            return None
        best = self.learning.best_stable(self.config)
        if not best:
            return None
        if best.frequency_mhz == state.frequency_mhz and best.voltage_mv == state.voltage_mv:
            return None
        current_score = performance_score(state, self.config)
        if current_score >= best.best_score * (1.0 - self.config.learning_restore_margin):
            return None
        if best.frequency_mhz != state.frequency_mhz:
            target_freq = (
                next_setting(
                    state.frequency_mhz,
                    min(best.frequency_mhz, self.config.max_frequency),
                    self.config.freq_step,
                    state.frequency_options,
                    self.config.use_asic_options,
                )
                if best.frequency_mhz > state.frequency_mhz
                else prev_setting(
                    state.frequency_mhz,
                    max(best.frequency_mhz, self.config.min_frequency),
                    self.config.freq_step,
                    state.frequency_options,
                    self.config.use_asic_options,
                )
            )
            return {
                "reason": "learning restore toward best stable frequency",
                "patch": self.build_patch(frequency=target_freq, fan_percent=fan),
            }
        if best.voltage_mv != state.voltage_mv:
            target_voltage = (
                next_setting(
                    state.voltage_mv,
                    min(best.voltage_mv, self.config.max_voltage),
                    self.config.voltage_step,
                    state.voltage_options,
                    self.config.use_asic_options,
                )
                if best.voltage_mv > state.voltage_mv
                else prev_setting(
                    state.voltage_mv,
                    max(best.voltage_mv, self.config.min_voltage),
                    self.config.voltage_step,
                    state.voltage_options,
                    self.config.use_asic_options,
                )
            )
            return {
                "reason": "learning restore toward best stable voltage",
                "patch": self.build_patch(voltage=target_voltage, fan_percent=fan),
            }
        return None

    def decide_rules(self, state: MinerState) -> Dict[str, Any]:
        fan = self.desired_fan(state)
        self.update_domain_spread_tracking(state)
        if state.frequency_mhz > self.config.max_frequency:
            return {
                "reason": "frequency above configured ceiling",
                "patch": self.build_patch(
                    frequency=self.config.max_frequency,
                    fan_percent=fan,
                ),
            }

        if state.voltage_mv > self.config.max_voltage:
            return {
                "reason": "voltage above configured ceiling",
                "patch": self.build_patch(
                    voltage=self.config.max_voltage,
                    fan_percent=fan,
                ),
            }

        if self.domain_spread_critical_count >= self.config.domain_spread_polls:
            return {
                "reason": "domain instability critical; strong rollback",
                "patch": self.build_patch(
                    frequency=prev_setting(
                        prev_setting(
                            state.frequency_mhz,
                            self.config.min_frequency,
                            self.config.freq_step,
                            state.frequency_options,
                            self.config.use_asic_options,
                        ),
                        self.config.min_frequency,
                        self.config.freq_step,
                        state.frequency_options,
                        self.config.use_asic_options,
                    ),
                    fan_percent=self.config.max_fan_percent if not self.config.auto_fan else fan,
                ),
            }

        if self.domain_spread_breach_count >= self.config.domain_spread_polls:
            return {
                "reason": "domain instability elevated; rollback frequency",
                "patch": self.build_patch(
                    frequency=prev_setting(
                        state.frequency_mhz,
                        self.config.min_frequency,
                        self.config.freq_step,
                        state.frequency_options,
                        self.config.use_asic_options,
                    ),
                    fan_percent=fan,
                ),
            }

        if state.error_percentage >= self.config.max_error_percentage * 1.5:
            return {
                "reason": "hardware error rate critical; strong rollback",
                "patch": self.build_patch(
                    frequency=prev_setting(
                        prev_setting(
                            state.frequency_mhz,
                            self.config.min_frequency,
                            self.config.freq_step,
                            state.frequency_options,
                            self.config.use_asic_options,
                        ),
                        self.config.min_frequency,
                        self.config.freq_step,
                        state.frequency_options,
                        self.config.use_asic_options,
                    ),
                    fan_percent=fan,
                ),
            }

        if state.error_percentage >= self.config.max_error_percentage:
            return {
                "reason": "hardware error rate high; rollback frequency",
                "patch": self.build_patch(
                    frequency=prev_setting(
                        state.frequency_mhz,
                        self.config.min_frequency,
                        self.config.freq_step,
                        state.frequency_options,
                        self.config.use_asic_options,
                    ),
                    fan_percent=fan,
                ),
            }

        if state.temperature_c >= self.config.emergency_temp_c or state.vr_temperature_c >= self.config.max_vr_temp_c:
            return {
                "reason": "emergency thermal rollback",
                "patch": self.build_patch(
                    frequency=prev_setting(
                        prev_setting(
                            state.frequency_mhz,
                            self.config.min_frequency,
                            self.config.freq_step,
                            state.frequency_options,
                            self.config.use_asic_options,
                        ),
                        self.config.min_frequency,
                        self.config.freq_step,
                        state.frequency_options,
                        self.config.use_asic_options,
                    ),
                    voltage=prev_setting(
                        prev_setting(
                            state.voltage_mv,
                            self.config.min_voltage,
                            self.config.voltage_step,
                            state.voltage_options,
                            self.config.use_asic_options,
                        ),
                        self.config.min_voltage,
                        self.config.voltage_step,
                        state.voltage_options,
                        self.config.use_asic_options,
                    ),
                    fan_percent=self.config.max_fan_percent,
                ),
            }

        if state.input_voltage_mv and state.input_voltage_mv < self.config.min_input_voltage_mv:
            return {
                "reason": "input voltage too low",
                "patch": self.build_patch(
                    frequency=prev_setting(
                        state.frequency_mhz,
                        self.config.min_frequency,
                        self.config.freq_step,
                        state.frequency_options,
                        self.config.use_asic_options,
                    ),
                    voltage=prev_setting(
                        state.voltage_mv,
                        self.config.min_voltage,
                        self.config.voltage_step,
                        state.voltage_options,
                        self.config.use_asic_options,
                    ),
                    fan_percent=fan,
                ),
            }

        if state.power_w and state.power_w > self.config.max_power_w:
            return {
                "reason": "power above configured ceiling",
                "patch": self.build_patch(
                    frequency=prev_setting(
                        state.frequency_mhz,
                        self.config.min_frequency,
                        self.config.freq_step,
                        state.frequency_options,
                        self.config.use_asic_options,
                    ),
                    fan_percent=self.config.max_fan_percent,
                ),
            }

        if state.temperature_c >= self.config.hot_temp_c:
            return {
                "reason": "hot; cooling down",
                "patch": self.build_patch(
                    frequency=prev_setting(
                        state.frequency_mhz,
                        self.config.min_frequency,
                        self.config.freq_step,
                        state.frequency_options,
                        self.config.use_asic_options,
                    ),
                    fan_percent=self.config.max_fan_percent,
                ),
            }

        if not self.can_change(state):
            return {"reason": "cooldown window active", "patch": self.build_patch(fan_percent=fan)}

        learned_restore = self.learned_restore_decision(state, fan)
        if learned_restore:
            return learned_restore

        climb_power_gate = self.config.max_power_w * self.config.climb_power_ratio
        if state.temperature_c <= self.config.cool_temp_c and state.power_w < climb_power_gate:
            next_freq = next_setting(
                state.frequency_mhz,
                self.config.max_frequency,
                self.config.freq_step,
                state.frequency_options,
                self.config.use_asic_options,
            )
            if self.config.learning_enabled and self.learning.is_bad_candidate(next_freq, state.voltage_mv, self.config):
                return {"reason": "learning hold; next frequency candidate was previously unstable", "patch": self.build_patch(fan_percent=fan)}
            if next_freq > state.frequency_mhz:
                return {
                    "reason": "cool and below power ceiling; raise frequency",
                    "patch": self.build_patch(
                        frequency=next_freq,
                        fan_percent=fan,
                    ),
                }
            next_voltage = next_setting(
                state.voltage_mv,
                self.config.max_voltage,
                self.config.voltage_step,
                state.voltage_options,
                self.config.use_asic_options,
            )
            if next_voltage > state.voltage_mv and state.hashrate_gh < self.config.min_hashrate_gh:
                return {
                    "reason": "cool but below hashrate floor; raise voltage",
                    "patch": self.build_patch(
                        voltage=next_voltage,
                        fan_percent=fan,
                    ),
                }

        if state.temperature_c > self.config.target_temp_c and state.frequency_mhz > self.config.min_frequency:
            return {
                "reason": "above target temp; lower frequency",
                "patch": self.build_patch(
                    frequency=prev_setting(
                        state.frequency_mhz,
                        self.config.min_frequency,
                        self.config.freq_step,
                        state.frequency_options,
                        self.config.use_asic_options,
                    ),
                    fan_percent=fan,
                ),
            }

        return {"reason": "hold", "patch": self.build_patch(fan_percent=fan)}

    def decide_ai(self, state: MinerState) -> Dict[str, Any]:
        assert self.ai is not None
        guard = self.decide_rules(state)
        guard_reason = guard.get("reason", "")
        ai_allowed_reasons = {
            "hold",
            "cooldown window active",
            "learning hold; next frequency candidate was previously unstable",
        }
        if guard_reason not in ai_allowed_reasons and not guard_reason.startswith("cool and below"):
            guard["reason"] = f"safety guard before ai: {guard_reason}"
            return guard

        try:
            action = self.ai.decide(state, self.config, self.learning.summary(self.config))
        except Exception as exc:
            logging.warning("ai advisor failed; using local rules: %s", exc)
            guard["reason"] = f"ai advisor unavailable; local rules: {guard_reason}"
            return guard
        fan = self.desired_fan(state)
        name = action.get("action", "hold")
        target_fan = action.get("target_fan_percent")
        if target_fan is not None and not self.config.auto_fan:
            fan = clamp(int(target_fan), self.config.min_fan_percent, self.config.max_fan_percent)

        patch = self.build_patch(fan_percent=fan)
        if name == "raise_freq" and self.can_change(state):
            next_freq = next_setting(
                state.frequency_mhz,
                self.config.max_frequency,
                self.config.freq_step,
                state.frequency_options,
                self.config.use_asic_options,
            )
            if self.config.learning_enabled and self.learning.is_bad_candidate(next_freq, state.voltage_mv, self.config):
                return {"reason": "learning blocked ai frequency raise; candidate was previously unstable", "patch": patch}
            patch = self.build_patch(
                frequency=next_freq,
                fan_percent=fan,
            )
        elif name == "lower_freq":
            prev_freq = prev_setting(
                state.frequency_mhz,
                self.config.min_frequency,
                self.config.freq_step,
                state.frequency_options,
                self.config.use_asic_options,
            )
            patch = self.build_patch(
                frequency=prev_freq,
                fan_percent=fan,
            )
        elif name == "raise_voltage" and self.can_change(state):
            next_voltage = next_setting(
                state.voltage_mv,
                self.config.max_voltage,
                self.config.voltage_step,
                state.voltage_options,
                self.config.use_asic_options,
            )
            patch = self.build_patch(
                voltage=next_voltage,
                fan_percent=fan,
            )
        elif name == "lower_voltage":
            prev_voltage = prev_setting(
                state.voltage_mv,
                self.config.min_voltage,
                self.config.voltage_step,
                state.voltage_options,
                self.config.use_asic_options,
            )
            patch = self.build_patch(
                voltage=prev_voltage,
                fan_percent=fan,
            )
        return {"reason": action.get("reason", "ai decision"), "patch": patch}

    def apply(self, decision: Dict[str, Any]) -> None:
        patch = {k: v for k, v in decision["patch"].items() if v is not None}
        if patch == self.last_applied:
            logging.info("no-op: %s", decision["reason"])
            return
        logging.info("decision=%s patch=%s", decision["reason"], patch)
        if self.config.dry_run:
            self.last_applied = patch
            return
        if patch:
            self.client.patch_system(patch)
            self.last_applied = patch
            if self.config.frequency_field in patch or self.config.voltage_field in patch:
                self.last_change_at = time.time()

    def write_status(self) -> None:
        next_change_at = None
        if self.last_change_at:
            next_change_at = self.last_change_at + self.adaptive_cooldown_seconds(self.last_state)
        state = asdict(self.last_state) if self.last_state else None
        if state and "raw" in state:
            state["raw"] = sanitize_raw(state["raw"])
        status = {
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "config": {
                "bitaxe_url": redact_url(self.config.bitaxe_url),
                "miner_name": self.config.miner_name,
                "miner_api_profile": self.config.miner_api_profile,
                "info_path": self.config.info_path,
                "asic_path": self.config.asic_path,
                "settings_path": self.config.settings_path,
                "frequency_field": self.config.frequency_field,
                "voltage_field": self.config.voltage_field,
                "fan_speed_field": self.config.fan_speed_field,
                "auto_fan_field": self.config.auto_fan_field,
                "mode": self.config.mode,
                "dry_run": self.config.dry_run,
                "loop_seconds": self.config.loop_seconds,
                "min_frequency": self.config.min_frequency,
                "max_frequency": self.config.max_frequency,
                "absolute_max_frequency": self.config.absolute_max_frequency,
                "freq_step": self.config.freq_step,
                "min_voltage": self.config.min_voltage,
                "max_voltage": self.config.max_voltage,
                "absolute_max_voltage": self.config.absolute_max_voltage,
                "voltage_step": self.config.voltage_step,
                "target_temp_c": self.config.target_temp_c,
                "hot_temp_c": self.config.hot_temp_c,
                "emergency_temp_c": self.config.emergency_temp_c,
                "absolute_max_emergency_temp_c": self.config.absolute_max_emergency_temp_c,
                "cool_temp_c": self.config.cool_temp_c,
                "max_vr_temp_c": self.config.max_vr_temp_c,
                "absolute_max_vr_temp_c": self.config.absolute_max_vr_temp_c,
                "min_input_voltage_mv": self.config.min_input_voltage_mv,
                "max_power_w": self.config.max_power_w,
                "absolute_max_power_w": self.config.absolute_max_power_w,
                "climb_power_ratio": self.config.climb_power_ratio,
                "max_error_percentage": self.config.max_error_percentage,
                "max_domain_spread_percentage": self.config.max_domain_spread_percentage,
                "critical_domain_spread_percentage": self.config.critical_domain_spread_percentage,
                "domain_spread_polls": self.config.domain_spread_polls,
                "learning_enabled": self.config.learning_enabled,
                "learning_min_samples": self.config.learning_min_samples,
                "learning_bad_limit": self.config.learning_bad_limit,
                "learning_restore_margin": self.config.learning_restore_margin,
                "learning_efficiency_weight": self.config.learning_efficiency_weight,
                "adaptive_cooldown_enabled": self.config.adaptive_cooldown_enabled,
                "adaptive_min_cooldown_seconds": self.config.adaptive_min_cooldown_seconds,
                "adaptive_max_cooldown_seconds": self.config.adaptive_max_cooldown_seconds,
                "adaptive_stable_samples": self.config.adaptive_stable_samples,
                "min_fan_percent": self.config.min_fan_percent,
                "max_fan_percent": self.config.max_fan_percent,
                "step_cooldown_seconds": self.config.step_cooldown_seconds,
                "use_asic_options": self.config.use_asic_options,
            },
            "last_applied": self.last_applied,
            "last_decision": self.last_decision,
            "last_error": self.last_error,
            "last_change_at_epoch": self.last_change_at if self.last_change_at else None,
            "next_change_at_epoch": next_change_at,
            "active_cooldown_seconds": self.adaptive_cooldown_seconds(self.last_state),
            "performance_score": performance_score(self.last_state, self.config) if self.last_state else None,
            "performance_metrics": performance_metrics(self.last_state, self.config) if self.last_state else None,
            "efficiency_gh_per_w": efficiency_gh_per_w(self.last_state) if self.last_state else None,
            "headroom": self.headroom(self.last_state) if self.last_state else None,
            "climb_power_gate_w": self.config.max_power_w * self.config.climb_power_ratio,
            "learning": self.learning.summary(self.config),
            "state": state,
        }
        tmp_path = f"{self.config.status_file}.tmp"
        ensure_parent_dir(self.config.status_file)
        with open(tmp_path, "w", encoding="utf-8") as handle:
            json.dump(status, handle, indent=2)
        os.replace(tmp_path, self.config.status_file)

    def run(self) -> None:
        while True:
            try:
                info = self.client.get_info()
                asic = self.client.get_asic()
                state = self.parse_state(info, asic)
                self.last_state = state
                self.record_learning(state)
                logging.info(
                    "state temp=%.1fC vr=%.1fC freq=%sMHz volt=%smV fan=%s%% hash=%.2fGH err=%.2f%% spread=%.2f%% offline=%s power=%.2fW vin=%smV",
                    state.temperature_c,
                    state.vr_temperature_c,
                    state.frequency_mhz,
                    state.voltage_mv,
                    state.fan_percent,
                    state.hashrate_gh,
                    state.error_percentage,
                    state.domain_spread_percentage,
                    state.offline_domain_count,
                    state.power_w,
                    state.input_voltage_mv,
                )
                decision = self.decide_ai(state) if self.config.mode == "openai" else self.decide_rules(state)
                self.last_decision = decision
                self.last_error = None
                self.apply(decision)
            except error.HTTPError as exc:
                self.last_error = f"http error: {exc}"
                logging.error("http error: %s", exc)
            except error.URLError as exc:
                self.last_error = f"connection error: {exc}"
                logging.error("connection error: %s", exc)
            except Exception as exc:
                self.last_error = f"controller error: {exc}"
                logging.exception("controller error: %s", exc)
            try:
                self.write_status()
            except Exception:
                logging.exception("failed to write status file")
            time.sleep(self.config.loop_seconds)


def main() -> int:
    parser = argparse.ArgumentParser(description="Guarded Bitaxe pilot")
    parser.add_argument("--once", action="store_true", help="run one iteration and exit")
    args = parser.parse_args()

    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(message)s",
    )
    controller = Controller(Config.from_env())
    if args.once:
        info = controller.client.get_info()
        asic = controller.client.get_asic()
        state = controller.parse_state(info, asic)
        controller.last_state = state
        controller.record_learning(state)
        logging.info("state=%s", state)
        decision = controller.decide_ai(state) if controller.config.mode == "openai" else controller.decide_rules(state)
        controller.last_decision = decision
        logging.info("decision=%s", decision)
        if not controller.config.dry_run:
            controller.apply(decision)
        controller.write_status()
        return 0
    controller.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
