from __future__ import annotations

from typing import Any, Dict, Protocol


def get_first_number(data: Dict[str, Any], *keys: str, default: float = 0.0) -> float:
    for key in keys:
        value = data.get(key)
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return default


def parse_int_list(value: Any) -> list[int]:
    if isinstance(value, list):
        result = []
        for item in value:
            try:
                result.append(int(item))
            except (TypeError, ValueError):
                continue
        return result
    if isinstance(value, str):
        return parse_int_list([item.strip() for item in value.split(",")])
    return []


def parse_domain_metrics(data: Dict[str, Any]) -> tuple[float, int]:
    monitor = data.get("hashrateMonitor") or {}
    asics = monitor.get("asics") if isinstance(monitor, dict) else None
    if not asics:
        domains = data.get("domains") or data.get("hashRateDomains") or []
    else:
        domains = asics[0].get("domains", []) if isinstance(asics[0], dict) else []
    values = []
    offline = 0
    for item in domains or []:
        try:
            number = float(item)
        except (TypeError, ValueError):
            continue
        if number <= 0:
            offline += 1
        else:
            values.append(number)
    if len(values) < 2:
        return 0.0, offline
    average = sum(values) / len(values)
    if average <= 0:
        return 0.0, offline
    return ((max(values) - min(values)) / average) * 100.0, offline


class MinerAdapter(Protocol):
    profile: str

    def merge_payloads(self, info: Dict[str, Any], asic: Dict[str, Any]) -> Dict[str, Any]:
        ...

    def normalize(self, info: Dict[str, Any], asic: Dict[str, Any]) -> Dict[str, Any]:
        ...


class BaseAdapter:
    profile = "generic-json"

    def merge_payloads(self, info: Dict[str, Any], asic: Dict[str, Any]) -> Dict[str, Any]:
        merged = dict(info)
        merged.update(asic)
        return merged

    def normalize(self, info: Dict[str, Any], asic: Dict[str, Any]) -> Dict[str, Any]:
        merged = self.merge_payloads(info, asic)
        hashrate = get_first_number(
            merged,
            "hashRate_1m",
            "hashRate",
            "hashrate",
            "hashRate1m",
            "hashrate1m",
            "hashRateGH",
            "ghs",
            default=0.0,
        )
        domain_spread, offline_domains = parse_domain_metrics(merged)
        return {
            "temperature_c": get_first_number(merged, "temp", "temperature", "ASIC_temp", "asic_temp", default=0.0),
            "vr_temperature_c": get_first_number(merged, "vrTemp", "vr_temp", "voltage_regulator_temp", default=0.0),
            "frequency_mhz": int(get_first_number(merged, "frequency", "freq", default=0.0)),
            "voltage_mv": int(get_first_number(merged, "coreVoltage", "core_voltage", "asic_voltage", default=0.0)),
            "frequency_options": parse_int_list(merged.get("frequencyOptions")),
            "voltage_options": parse_int_list(merged.get("voltageOptions")),
            "fan_percent": int(get_first_number(merged, "fanSpeed", "fan_speed", "fanspeed", default=0.0)),
            "hashrate_gh": hashrate,
            "hashrate_10m_gh": get_first_number(merged, "hashRate_10m", "hashrate_10m", "hashRate10m", "hashrate10m", default=hashrate),
            "error_percentage": get_first_number(merged, "errorPercentage", "error_percentage", default=0.0),
            "domain_spread_percentage": domain_spread,
            "offline_domain_count": offline_domains,
            "power_w": get_first_number(merged, "power", "power_w", "powerDraw", default=0.0),
            "input_voltage_mv": int(get_first_number(merged, "voltage", "inputVoltage", "input_voltage", default=0.0)),
            "raw": merged,
        }


class AxeOSAdapter(BaseAdapter):
    profile = "axeos"


class NerdMinerAdapter(BaseAdapter):
    profile = "nerdminer"

    def normalize(self, info: Dict[str, Any], asic: Dict[str, Any]) -> Dict[str, Any]:
        normalized = super().normalize(info, asic)
        raw = normalized["raw"]
        khs = get_first_number(raw, "hashrate_kh", "hashRateKH", "KHs", "khs", default=0.0)
        if khs and not normalized["hashrate_gh"]:
            normalized["hashrate_gh"] = khs / 1_000_000.0
            normalized["hashrate_10m_gh"] = normalized["hashrate_gh"]
        return normalized


class Esp32Adapter(NerdMinerAdapter):
    profile = "esp32"


ADAPTERS = {
    "axeos": AxeOSAdapter(),
    "generic-json": BaseAdapter(),
    "futurebit": BaseAdapter(),
    "braiins": BaseAdapter(),
    "nerdminer": NerdMinerAdapter(),
    "esp32": Esp32Adapter(),
}


def get_adapter(profile: str | None) -> MinerAdapter:
    return ADAPTERS.get((profile or "axeos").strip().lower(), ADAPTERS["generic-json"])
