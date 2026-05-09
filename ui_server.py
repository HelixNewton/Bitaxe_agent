#!/usr/bin/env python3
from concurrent.futures import ThreadPoolExecutor, as_completed
import ipaddress
import json
import os
import subprocess
import sys
import time
from functools import lru_cache
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib import error, request
from urllib.parse import urlparse

from esp32_tools import esp32_status
from miner_adapters import get_adapter


def app_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def resource_base_dir() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return app_base_dir()


BASE_DIR = app_base_dir()
status_file_value = os.getenv("MINER_STATUS_FILE") or os.getenv("BITAXE_STATUS_FILE") or "status.json"
STATUS_FILE = Path(status_file_value)
if not STATUS_FILE.is_absolute():
    STATUS_FILE = BASE_DIR / STATUS_FILE
swarm_file_value = os.getenv("MINER_SWARM_FILE") or "swarm.json"
SWARM_FILE = Path(swarm_file_value)
if not SWARM_FILE.is_absolute():
    SWARM_FILE = BASE_DIR / SWARM_FILE
ENV_FILE = BASE_DIR / ".env"
ASSETS_DIR = resource_base_dir() / "assets"
HOST = os.getenv("MINER_UI_HOST") or os.getenv("BITAXE_UI_HOST", "0.0.0.0")
PORT = int(os.getenv("MINER_UI_PORT") or os.getenv("BITAXE_UI_PORT", "8787"))

EDITABLE_KEYS = {
    "MINER_NAME",
    "MINER_URL",
    "MINER_API_PROFILE",
    "MINER_INFO_PATH",
    "MINER_ASIC_PATH",
    "MINER_SETTINGS_PATH",
    "MINER_RESTART_PATH",
    "MINER_FREQUENCY_FIELD",
    "MINER_VOLTAGE_FIELD",
    "MINER_FAN_SPEED_FIELD",
    "MINER_AUTO_FAN_FIELD",
    "MINER_STATUS_FILE",
    "MINER_LEARNING_FILE",
    "MINER_SWARM_FILE",
    "MINER_UI_HOST",
    "MINER_UI_PORT",
    "BITAXE_URL",
    "BITAXE_RESTART_PATH",
    "BITAXE_MODE",
    "BITAXE_DRY_RUN",
    "BITAXE_AUTO_FAN",
    "BITAXE_LOOP_SECONDS",
    "BITAXE_MIN_FREQUENCY",
    "BITAXE_MAX_FREQUENCY",
    "BITAXE_ABSOLUTE_MAX_FREQUENCY",
    "BITAXE_FREQ_STEP",
    "BITAXE_MIN_VOLTAGE",
    "BITAXE_MAX_VOLTAGE",
    "BITAXE_ABSOLUTE_MAX_VOLTAGE",
    "BITAXE_VOLTAGE_STEP",
    "BITAXE_TARGET_TEMP_C",
    "BITAXE_HOT_TEMP_C",
    "BITAXE_EMERGENCY_TEMP_C",
    "BITAXE_ABSOLUTE_MAX_EMERGENCY_TEMP_C",
    "BITAXE_COOL_TEMP_C",
    "BITAXE_MAX_VR_TEMP_C",
    "BITAXE_ABSOLUTE_MAX_VR_TEMP_C",
    "BITAXE_MIN_INPUT_VOLTAGE_MV",
    "BITAXE_MAX_POWER_W",
    "BITAXE_ABSOLUTE_MAX_POWER_W",
    "BITAXE_CLIMB_POWER_RATIO",
    "BITAXE_MAX_ERROR_PERCENTAGE",
    "BITAXE_MAX_DOMAIN_SPREAD_PERCENTAGE",
    "BITAXE_CRITICAL_DOMAIN_SPREAD_PERCENTAGE",
    "BITAXE_DOMAIN_SPREAD_POLLS",
    "BITAXE_LEARNING_ENABLED",
    "BITAXE_LEARNING_MIN_SAMPLES",
    "BITAXE_LEARNING_BAD_LIMIT",
    "BITAXE_LEARNING_RESTORE_MARGIN",
    "BITAXE_LEARNING_EFFICIENCY_WEIGHT",
    "BITAXE_ADAPTIVE_COOLDOWN_ENABLED",
    "BITAXE_ADAPTIVE_MIN_COOLDOWN_SECONDS",
    "BITAXE_ADAPTIVE_MAX_COOLDOWN_SECONDS",
    "BITAXE_ADAPTIVE_STABLE_SAMPLES",
    "BITAXE_MIN_FAN_PERCENT",
    "BITAXE_MAX_FAN_PERCENT",
    "BITAXE_STEP_COOLDOWN_SECONDS",
    "BITAXE_USE_ASIC_OPTIONS",
}

CONFIG_RANGES = {
    "MINER_UI_PORT": (1, 65535),
    "BITAXE_LOOP_SECONDS": (5, 3600),
    "BITAXE_MIN_FREQUENCY": (300, 800),
    "BITAXE_MAX_FREQUENCY": (300, 800),
    "BITAXE_ABSOLUTE_MAX_FREQUENCY": (300, 800),
    "BITAXE_FREQ_STEP": (1, 100),
    "BITAXE_MIN_VOLTAGE": (800, 1400),
    "BITAXE_MAX_VOLTAGE": (800, 1400),
    "BITAXE_ABSOLUTE_MAX_VOLTAGE": (800, 1400),
    "BITAXE_VOLTAGE_STEP": (1, 100),
    "BITAXE_TARGET_TEMP_C": (40, 85),
    "BITAXE_HOT_TEMP_C": (45, 90),
    "BITAXE_EMERGENCY_TEMP_C": (50, 95),
    "BITAXE_ABSOLUTE_MAX_EMERGENCY_TEMP_C": (50, 95),
    "BITAXE_COOL_TEMP_C": (30, 85),
    "BITAXE_MAX_VR_TEMP_C": (40, 100),
    "BITAXE_ABSOLUTE_MAX_VR_TEMP_C": (40, 100),
    "BITAXE_MIN_INPUT_VOLTAGE_MV": (4000, 6000),
    "BITAXE_MAX_POWER_W": (5, 30),
    "BITAXE_ABSOLUTE_MAX_POWER_W": (5, 30),
    "BITAXE_CLIMB_POWER_RATIO": (0.5, 0.99),
    "BITAXE_MAX_ERROR_PERCENTAGE": (0, 100),
    "BITAXE_MAX_DOMAIN_SPREAD_PERCENTAGE": (0, 100),
    "BITAXE_CRITICAL_DOMAIN_SPREAD_PERCENTAGE": (0, 100),
    "BITAXE_DOMAIN_SPREAD_POLLS": (1, 20),
    "BITAXE_LEARNING_MIN_SAMPLES": (1, 1000),
    "BITAXE_LEARNING_BAD_LIMIT": (1, 1000),
    "BITAXE_LEARNING_RESTORE_MARGIN": (0, 1),
    "BITAXE_LEARNING_EFFICIENCY_WEIGHT": (0, 1),
    "BITAXE_ADAPTIVE_MIN_COOLDOWN_SECONDS": (1, 3600),
    "BITAXE_ADAPTIVE_MAX_COOLDOWN_SECONDS": (1, 7200),
    "BITAXE_ADAPTIVE_STABLE_SAMPLES": (1, 1000),
    "BITAXE_MIN_FAN_PERCENT": (0, 100),
    "BITAXE_MAX_FAN_PERCENT": (0, 100),
    "BITAXE_STEP_COOLDOWN_SECONDS": (1, 7200),
}

BOOLEAN_KEYS = {
    "BITAXE_DRY_RUN",
    "BITAXE_AUTO_FAN",
    "BITAXE_USE_ASIC_OPTIONS",
    "BITAXE_LEARNING_ENABLED",
    "BITAXE_ADAPTIVE_COOLDOWN_ENABLED",
}

MODE_VALUES = {"rules", "openai"}
PROFILE_VALUES = {"axeos", "generic-json", "futurebit", "braiins", "esp32", "nerdminer"}
LIVE_PROBE_TTL_SECONDS = 12
LIVE_PROBE_TIMEOUT_SECONDS = 0.8
LIVE_PROBE_CACHE: dict[str, tuple[float, dict]] = {}
NERDMINER_PROBE_PATHS = ("/api/status", "/status", "/api", "/")
GENERIC_PROBE_PATHS = ("/api/system/info", "/api/status", "/status", "/api", "/")


def sanitize_env_value(key: str, value: str) -> str:
    cleaned = value.strip()
    if any(char in cleaned for char in ("\x00", "\n", "\r")):
        raise ValueError(f"{key} cannot contain line breaks")
    if any(char in cleaned for char in (";", "&", "|", "`", "$", "<", ">")):
        raise ValueError(f"{key} contains an unsupported shell-control character")
    return cleaned


def validate_config_value(key: str, value: str) -> None:
    if key in BOOLEAN_KEYS and value.strip().lower() not in {"1", "0", "true", "false", "yes", "no", "on", "off"}:
        raise ValueError(f"{key} must be a boolean")
    if key == "BITAXE_MODE" and value.strip().lower() not in MODE_VALUES:
        raise ValueError(f"{key} must be one of: {', '.join(sorted(MODE_VALUES))}")
    if key == "MINER_API_PROFILE" and value.strip().lower() not in PROFILE_VALUES:
        raise ValueError(f"{key} must be one of: {', '.join(sorted(PROFILE_VALUES))}")
    if key in CONFIG_RANGES:
        try:
            number = float(value)
        except ValueError as exc:
            raise ValueError(f"{key} must be a number") from exc
        lower, upper = CONFIG_RANGES[key]
        if number < lower or number > upper:
            raise ValueError(f"{key} must be between {lower} and {upper}")


def parse_env_file() -> dict[str, str]:
    values: dict[str, str] = {}
    if not ENV_FILE.exists():
        return values
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        if not line or line.lstrip().startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def write_env_file(updates: dict[str, str]) -> dict[str, str]:
    existing = parse_env_file()
    validated: dict[str, str] = {}
    for key, value in updates.items():
        cleaned = sanitize_env_value(key, value)
        validate_config_value(key, cleaned)
        validated[key] = cleaned
    existing.update(validated)
    lines = [f"{key}={value}" for key, value in existing.items()]
    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return validated


def read_status() -> dict:
    if not STATUS_FILE.exists():
        return {"status": "waiting_for_controller"}
    return json.loads(STATUS_FILE.read_text(encoding="utf-8"))


def read_json_file(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def display_miner_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.hostname:
        return parsed.hostname
    return url.replace("http://", "").replace("https://", "").split("/", 1)[0]


def read_swarm_config() -> list[dict]:
    if not SWARM_FILE.exists():
        config = parse_env_file()
        return [{
            "id": "primary",
            "name": config.get("MINER_NAME") or "Primary Miner",
            "url": config.get("MINER_URL") or config.get("BITAXE_URL") or "",
            "api_profile": config.get("MINER_API_PROFILE") or "axeos",
            "status_file": str(STATUS_FILE),
        }]
    payload = read_json_file(SWARM_FILE)
    miners = payload.get("miners", [])
    if not isinstance(miners, list):
        raise ValueError("swarm.json must contain a miners list")
    return miners


def write_swarm_config(miners: list[dict]) -> None:
    SWARM_FILE.write_text(json.dumps({"miners": miners}, indent=2) + "\n", encoding="utf-8")


def add_swarm_miner(payload: dict) -> dict:
    url = str(payload.get("url") or "").strip().rstrip("/")
    if not url:
        raise ValueError("url is required")
    if not url.startswith(("http://", "https://")):
        url = f"http://{url}"
    name = str(payload.get("name") or display_miner_url(url) or "Miner").strip()
    miner_id = "".join(char.lower() if char.isalnum() else "-" for char in name).strip("-") or "miner"
    miners = read_swarm_config()
    existing_ids = {str(miner.get("id")) for miner in miners}
    base_id = miner_id
    counter = 2
    while miner_id in existing_ids:
        miner_id = f"{base_id}-{counter}"
        counter += 1
    status_name = f"status-{miner_id}.json"
    api_profile = str(payload.get("api_profile") or "axeos").strip().lower()
    if api_profile not in PROFILE_VALUES:
        raise ValueError(f"api_profile must be one of: {', '.join(sorted(PROFILE_VALUES))}")
    miner = {
        "id": miner_id,
        "name": name,
        "url": url,
        "api_profile": api_profile,
        "status_file": str(payload.get("status_file") or status_name),
    }
    miners.append(miner)
    write_swarm_config(miners)
    return miner


def remove_swarm_miner(payload: dict) -> dict:
    miner_id = str(payload.get("id") or "").strip()
    if not miner_id:
        raise ValueError("id is required")
    if miner_id == "primary":
        raise ValueError("primary miner cannot be removed from the fleet")
    miners = read_swarm_config()
    kept = [miner for miner in miners if str(miner.get("id")) != miner_id]
    if len(kept) == len(miners):
        raise ValueError(f"miner {miner_id} was not found")
    write_swarm_config(kept)
    return {"ok": True, "removed": miner_id}


def resolve_status_file(path_value: str) -> Path:
    path = Path(path_value)
    if not path.is_absolute():
        path = BASE_DIR / path
    return path


def normalize_base_url(url: str) -> str:
    cleaned = str(url or "").strip().rstrip("/")
    if cleaned and not cleaned.startswith(("http://", "https://")):
        cleaned = f"http://{cleaned}"
    return cleaned


def probe_paths_for_profile(profile: str) -> tuple[str, ...]:
    if profile in {"nerdminer", "esp32"}:
        return NERDMINER_PROBE_PATHS
    return GENERIC_PROBE_PATHS


def probe_live_miner(miner: dict) -> dict | None:
    profile = str(miner.get("api_profile") or "generic-json").strip().lower()
    base_url = normalize_base_url(str(miner.get("url") or ""))
    if not base_url:
        return None
    cache_key = f"{profile}:{base_url}"
    cached = LIVE_PROBE_CACHE.get(cache_key)
    if cached and time.time() - cached[0] < LIVE_PROBE_TTL_SECONDS:
        return dict(cached[1])

    adapter = get_adapter(profile)
    fallback: dict | None = None
    for path in probe_paths_for_profile(profile):
        url = f"{base_url}{path}"
        req = request.Request(url, method="GET")
        req.add_header("Connection", "close")
        try:
            with request.urlopen(req, timeout=LIVE_PROBE_TIMEOUT_SECONDS) as response:
                body = response.read(65536)
                content_type = response.headers.get("Content-Type", "")
        except Exception as exc:
            fallback = {
                "online": False,
                "stale": True,
                "last_error": f"live probe failed: {exc}",
            }
            continue

        text = body.decode("utf-8", errors="ignore").strip()
        if text:
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                data = None
            if isinstance(data, dict):
                normalized = adapter.normalize(data, {})
                result = {
                    "online": True,
                    "stale": False,
                    "status_age_seconds": 0.0,
                    "temperature_c": normalized.get("temperature_c") or None,
                    "hashrate_gh": normalized.get("hashrate_gh") or None,
                    "power_w": normalized.get("power_w") or None,
                    "frequency_mhz": normalized.get("frequency_mhz") or None,
                    "domain_spread_percentage": normalized.get("domain_spread_percentage") or None,
                    "last_error": None,
                    "probe_source": path,
                }
                LIVE_PROBE_CACHE[cache_key] = (time.time(), result)
                return dict(result)

        readable_type = content_type.split(";", 1)[0] or "HTTP"
        fallback = {
            "online": True,
            "stale": False,
            "status_age_seconds": 0.0,
            "last_error": f"Device is reachable, but stock NerdMiner does not expose live stats over HTTP ({readable_type}).",
            "probe_source": path,
        }
        break

    if fallback:
        LIVE_PROBE_CACHE[cache_key] = (time.time(), fallback)
        return dict(fallback)
    return None


def summarize_miner(miner: dict) -> dict:
    status_path = resolve_status_file(str(miner.get("status_file") or "status.json"))
    profile = str(miner.get("api_profile") or "axeos").strip().lower()
    summary = {
        "id": str(miner.get("id") or miner.get("name") or status_path.stem),
        "name": str(miner.get("name") or "Miner"),
        "url": display_miner_url(str(miner.get("url") or "")),
        "api_profile": profile,
        "status_file": str(status_path),
        "online": False,
        "stale": True,
        "status_age_seconds": None,
        "temperature_c": None,
        "hashrate_gh": None,
        "power_w": None,
        "frequency_mhz": None,
        "domain_spread_percentage": None,
        "last_error": None,
    }
    if not status_path.exists():
        live = probe_live_miner(miner)
        if live:
            summary.update(live)
            return summary
        summary["last_error"] = "status file missing"
        return summary
    age_seconds = max(0.0, time.time() - status_path.stat().st_mtime)
    summary["status_age_seconds"] = round(age_seconds, 3)
    summary["stale"] = age_seconds > 120
    try:
        status = read_json_file(status_path)
    except Exception as exc:
        summary["last_error"] = f"status read failed: {exc}"
        return summary
    state = status.get("state") or {}
    config = status.get("config") or {}
    summary.update({
        "online": bool(state) and not summary["stale"],
        "temperature_c": state.get("temperature_c"),
        "hashrate_gh": state.get("hashrate_gh"),
        "power_w": state.get("power_w"),
        "frequency_mhz": state.get("frequency_mhz"),
        "domain_spread_percentage": state.get("domain_spread_percentage"),
        "mode": config.get("mode"),
        "dry_run": config.get("dry_run"),
        "last_error": status.get("last_error"),
    })
    if summary["stale"] and profile in {"nerdminer", "esp32", "generic-json"}:
        live = probe_live_miner(miner)
        if live:
            summary.update(live)
    return summary


def swarm_status() -> dict:
    miners = [summarize_miner(miner) for miner in read_swarm_config()]
    online = [miner for miner in miners if miner.get("online")]
    total_hashrate = sum(float(miner.get("hashrate_gh") or 0) for miner in miners)
    total_power = sum(float(miner.get("power_w") or 0) for miner in miners)
    hottest = max((float(miner.get("temperature_c") or 0) for miner in miners), default=0.0)
    return {
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "swarm_file": str(SWARM_FILE),
        "miners": miners,
        "summary": {
            "total_miners": len(miners),
            "online_miners": len(online),
            "total_hashrate_gh": total_hashrate,
            "total_power_w": total_power,
            "hottest_temperature_c": hottest,
            "efficiency_gh_per_w": total_hashrate / total_power if total_power > 0 else None,
        },
    }


def discover_miners() -> dict:
    config = parse_env_file()
    base_url = config.get("MINER_URL") or config.get("BITAXE_URL")
    if not base_url:
        return {"devices": [], "message": "MINER_URL or BITAXE_URL is not configured."}
    parsed = urlparse(base_url if "://" in base_url else f"http://{base_url}")
    if not parsed.hostname:
        return {"devices": [], "message": "Unable to detect subnet from configured miner URL."}
    info_path = config.get("MINER_INFO_PATH") or "/api/system/info"
    if not info_path.startswith("/"):
        info_path = f"/{info_path}"
    try:
        network = ipaddress.ip_network(f"{parsed.hostname}/24", strict=False)
    except ValueError as exc:
        return {"devices": [], "message": f"Subnet scan unavailable: {exc}"}

    known_hosts = {
        display_miner_url(str(miner.get("url") or ""))
        for miner in read_swarm_config()
    }

    def probe(host: str) -> dict | None:
        url = f"http://{host}{info_path}"
        req = request.Request(url, method="GET")
        req.add_header("Connection", "close")
        try:
            with request.urlopen(req, timeout=0.35) as response:
                text = response.read(65536).decode("utf-8", errors="ignore")
                data = json.loads(text) if text else {}
        except Exception:
            return None
        bitaxe_signals = ("axeOSVersion", "ASICModel", "deviceModel", "frequency", "voltage")
        if not any(key in data for key in bitaxe_signals):
            return None
        return {
            "name": str(data.get("hostname") or data.get("deviceModel") or f"Bitaxe {host}"),
            "url": f"http://{host}",
            "api_profile": "axeos",
            "version": data.get("axeOSVersion") or data.get("version"),
            "registered": host in known_hosts,
        }

    devices: list[dict] = []
    hosts = [str(host) for host in network.hosts()]
    with ThreadPoolExecutor(max_workers=48) as pool:
        future_map = {pool.submit(probe, host): host for host in hosts}
        for future in as_completed(future_map):
            result = future.result()
            if result:
                devices.append(result)
    devices.sort(key=lambda item: item["url"])
    return {
        "devices": devices,
        "message": f"Found {len(devices)} Bitaxe-like device(s) on {network}.",
    }


def update_status() -> dict:
    def run_git(args: list[str], timeout: int = 12) -> subprocess.CompletedProcess:
        return subprocess.run(["git", *args], cwd=BASE_DIR, capture_output=True, text=True, check=False, timeout=timeout)

    current = run_git(["rev-parse", "--short", "HEAD"])
    branch = run_git(["branch", "--show-current"])
    upstream = run_git(["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"])
    result = {
        "current": current.stdout.strip() if current.returncode == 0 else "unknown",
        "branch": branch.stdout.strip() if branch.returncode == 0 else "unknown",
        "upstream": upstream.stdout.strip() if upstream.returncode == 0 else "",
        "update_available": False,
        "behind": 0,
        "ahead": 0,
        "message": "No upstream configured.",
    }
    if upstream.returncode != 0:
        return result
    fetch = run_git(["fetch", "--quiet"], timeout=30)
    if fetch.returncode != 0:
        result["message"] = fetch.stderr.strip() or "git fetch failed"
        return result
    counts = run_git(["rev-list", "--left-right", "--count", "HEAD...@{u}"])
    if counts.returncode != 0:
        result["message"] = counts.stderr.strip() or "unable to compare with upstream"
        return result
    ahead, behind = [int(part) for part in counts.stdout.strip().split()]
    result.update({
        "ahead": ahead,
        "behind": behind,
        "update_available": behind > 0,
        "message": "Update available." if behind > 0 else "Already up to date.",
    })
    return result


def health_status() -> dict:
    payload = {
        "ok": True,
        "ui": "running",
        "status_file": str(STATUS_FILE),
        "status_exists": STATUS_FILE.exists(),
    }
    if STATUS_FILE.exists():
        age_seconds = max(0.0, time.time() - STATUS_FILE.stat().st_mtime)
        payload["status_age_seconds"] = round(age_seconds, 3)
        payload["controller_fresh"] = age_seconds <= 120
    else:
        payload["ok"] = False
        payload["controller_fresh"] = False
    return payload


def read_asset(path: str) -> tuple[bytes, str]:
    relative = path.removeprefix("/assets/")
    candidate = (ASSETS_DIR / relative).resolve()
    if not str(candidate).startswith(str(ASSETS_DIR.resolve())) or not candidate.is_file():
        raise FileNotFoundError(path)
    suffix = candidate.suffix.lower()
    content_type = "text/plain; charset=utf-8"
    if suffix == ".css":
        content_type = "text/css; charset=utf-8"
    elif suffix == ".js":
        content_type = "application/javascript; charset=utf-8"
    elif suffix == ".json":
        content_type = "application/json; charset=utf-8"
    return candidate.read_bytes(), content_type


@lru_cache(maxsize=64)
def read_asset_cached(path: str) -> tuple[bytes, str]:
    return read_asset(path)


def post_json(url: str, max_retries: int = 2) -> dict:
    req = request.Request(url, data=b"", method="POST")
    req.add_header("Connection", "close")
    for attempt in range(max_retries + 1):
        try:
            with request.urlopen(req, timeout=5) as response:
                text = response.read().decode("utf-8")
                return json.loads(text) if text else {"ok": True}
        except error.HTTPError as exc:
            text = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"HTTP {exc.code}: {text or exc.reason}") from exc
        except (TimeoutError, error.URLError) as exc:
            if attempt >= max_retries:
                raise RuntimeError(f"miner request failed after {max_retries + 1} attempts: {exc}") from exc
            time.sleep(0.5 * (attempt + 1))
    return {"ok": True}


def restart_controller_service() -> dict:
    result = subprocess.run(
        ["systemctl", "restart", "bitaxe-agent"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "failed to restart controller")
    return {"ok": True}


def restart_bitaxe() -> dict:
    config = parse_env_file()
    bitaxe_url = config.get("MINER_URL") or config.get("BITAXE_URL")
    if not bitaxe_url:
        raise RuntimeError("MINER_URL or BITAXE_URL is not configured")
    restart_path = config.get("MINER_RESTART_PATH") or config.get("BITAXE_RESTART_PATH") or "/api/system/restart"
    if not restart_path.startswith("/"):
        restart_path = f"/{restart_path}"
    return post_json(f"{bitaxe_url.rstrip('/')}{restart_path}")


def html() -> str:
    return """<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
  <meta name=\"theme-color\" content=\"#0d1218\">
  <meta name=\"description\" content=\"Bitaxe Agent dashboard for guarded miner tuning and telemetry\">
  <title>Bitaxe Agent</title>
  <link rel=\"icon\" type=\"image/svg+xml\" href=\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Crect width='100' height='100' rx='20' fill='%230d1218'/%3E%3Ctext x='50' y='58' text-anchor='middle' font-size='34' font-family='Arial' font-weight='700' fill='%2300ff9c'%3EBA%3C/text%3E%3C/svg%3E\">
  <link rel=\"stylesheet\" href=\"/assets/dashboard.css\">
  <link rel=\"stylesheet\" href=\"/assets/dashboard-polish.css\">
  <link rel=\"stylesheet\" href=\"/assets/dashboard-redesign.css?v=20260509-flow\">
</head>
<body>
  <div class=\"app-shell\">
    <aside class=\"sidebar\">
      <div class=\"brand-mark\">BA</div>
      <nav class=\"nav\">
        <a class=\"nav-link active\" href=\"#summarySec\" data-nav=\"summarySec\"><span class=\"nav-label\">Overview</span></a>
        <a class=\"nav-link\" href=\"#statsSec\" data-nav=\"statsSec\"><span class=\"nav-label\">Metrics</span></a>
        <a class=\"nav-link\" href=\"#trendsSec\" data-nav=\"trendsSec\"><span class=\"nav-label\">Trends</span></a>
        <a class=\"nav-link\" href=\"#swarmSec\" data-nav=\"swarmSec\"><span class=\"nav-label\">Fleet</span></a>
        <a class=\"nav-link\" href=\"#esp32Sec\" data-nav=\"esp32Sec\"><span class=\"nav-label\">ESP32</span></a>
        <a class=\"nav-link\" href=\"#domainsSec\" data-nav=\"domainsSec\"><span class=\"nav-label\">ASICs</span></a>
        <a class=\"nav-link\" href=\"#configSec\" data-nav=\"configSec\"><span class=\"nav-label\">Settings</span></a>
      </nav>
      <div class=\"sidebar-meta\">Bitaxe Agent</div>
    </aside>

    <main class=\"workspace\">
      <header class=\"topbar\">
        <div class=\"search-wrap\">
          <input id=\"sectionSearch\" type=\"search\" placeholder=\"Search sections, metrics, or controls\">
        </div>
        <div class=\"profile\">
          <div class=\"avatar\">OP</div>
          <div class=\"profile-copy\">
            <strong>Operations Console</strong>
            <span id=\"updatedAt\">Waiting for telemetry</span>
          </div>
        </div>
      </header>

      <section id=\"summarySec\" class=\"section-card panel\">
        <div class=\"panel-body\">
          <div class=\"hero-grid\">
            <div>
              <div class=\"eyebrow\">Live Miner Control</div>
              <h1 class=\"heading-xl\">Bitaxe Agent Dashboard</h1>
              <p class=\"summary-copy\" id=\"heroText\">Synchronizing controller state, thermals, tuning limits, and live miner telemetry.</p>
              <div class=\"summary-strip\">
                <span id=\"health\" class=\"status-pill ok\"><span class=\"pulse\"></span><span>Online</span></span>
                <span class=\"chip\" id=\"modeChip\">Mode: -</span>
                <span class=\"chip\" id=\"dryRunChip\">Dry Run: -</span>
                <span class=\"chip\" id=\"fanChip\">Fan: -</span>
                <span class=\"chip\" id=\"stabilityChip\">Stability: -</span>
                <span class=\"chip\" id=\"domainGuardChip\">Domain Guard: -</span>
                <span class=\"chip\" id=\"updatedChip\">Updated: -</span>
              </div>
            </div>
            <div class=\"panel\">
              <div class=\"panel-body\">
                <div class=\"section-head\">
                  <div>
                    <div class=\"eyebrow\">Recommended Action</div>
                    <h2 class=\"heading-md\" id=\"decisionReason\">Loading decision</h2>
                  </div>
                </div>
                <div class=\"decision-text\" id=\"decisionPatch\">Waiting for the controller to choose the safest next step.</div>
                <div class=\"decision-hint\" id=\"decisionHint\">The controller will describe why it is holding, climbing, or rolling back.</div>
                <div class=\"decision-actions\" style=\"margin-top:16px;\">
                  <button type=\"button\" class=\"btn-secondary\" id=\"applySafeBtn\">Apply Safe Rails</button>
                  <button type=\"button\" class=\"btn-secondary\" id=\"restartControllerBtn\">Restart Controller</button>
                  <button type=\"button\" class=\"btn-danger\" id=\"restartMinerBtn\">Restart Miner</button>
                </div>
                <div class=\"panel-copy\" id=\"actionMessage\">No operator action pending.</div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section id=\"statsSec\" class=\"section-card\">
        <div class=\"stat-grid\" id=\"overview\"></div>
      </section>

      <section id=\"swarmSec\" class=\"section-card\">
        <div class=\"panel swarm-panel\">
          <div class=\"panel-body\">
            <div class=\"section-head\">
              <div>
                <div class=\"eyebrow\">Swarm Control</div>
                <h2 class=\"heading-md\">Fleet Overview</h2>
              </div>
              <button type=\"button\" class=\"btn-secondary\" id=\"checkUpdatesBtn\">Check Updates</button>
            </div>
            <div class=\"swarm-summary\">
              <div><span class=\"mini-label\">Online</span><strong id=\"swarmOnline\">-</strong></div>
              <div><span class=\"mini-label\">Hashrate</span><strong id=\"swarmHashrate\">-</strong></div>
              <div><span class=\"mini-label\">Power</span><strong id=\"swarmPower\">-</strong></div>
              <div><span class=\"mini-label\">Efficiency</span><strong id=\"swarmEfficiency\">-</strong></div>
            </div>
            <form id=\"swarmAddForm\" class=\"swarm-add-form\">
              <input name=\"name\" placeholder=\"Nickname\">
              <input name=\"url\" placeholder=\"Miner IP or URL\">
              <select name=\"api_profile\">
                <option value=\"axeos\">AxeOS / Bitaxe</option>
                <option value=\"nerdminer\">NerdMiner / ESP32</option>
                <option value=\"esp32\">Generic ESP32 Miner</option>
                <option value=\"generic-json\">Generic JSON</option>
                <option value=\"futurebit\">FutureBit</option>
                <option value=\"braiins\">Braiins</option>
              </select>
              <button type=\"submit\" class=\"btn-secondary\">Add Device</button>
              <button type=\"button\" class=\"btn-secondary\" id=\"rescanNetworkBtn\">Rescan Network</button>
            </form>
            <div id=\"discoveryNotice\" class=\"decision-hint hidden\">No new devices found yet.</div>
            <div id=\"swarmGrid\" class=\"swarm-grid\"></div>
            <div class=\"update-strip\" id=\"updateStrip\">
              <span class=\"mini-label\">Updates</span>
              <strong id=\"updateStatus\">Not checked yet</strong>
              <span id=\"updateDetails\" class=\"muted\">Use Check Updates to compare this checkout with GitHub.</span>
            </div>
          </div>
        </div>
      </section>

      <section id=\"trendsSec\" class=\"section-card\">
        <div class=\"status-grid\">
          <div class=\"panel\">
            <div class=\"panel-body\">
              <div class=\"section-head\">
                <div>
                  <div class=\"eyebrow\">Trend Analysis</div>
                  <h2 class=\"heading-md\">Thermal And Power History</h2>
                </div>
                <div class=\"toolbar-group\">
                  <select id=\"refreshSelect\">
                    <option value=\"2000\">2s</option>
                    <option value=\"5000\" selected>5s</option>
                    <option value=\"10000\">10s</option>
                    <option value=\"15000\">15s</option>
                  </select>
                  <label class=\"toggle\"><input type=\"checkbox\" id=\"showHashrateToggle\" checked> Hashrate</label>
                  <label class=\"toggle\"><input type=\"checkbox\" id=\"showTempToggle\" checked> Temp</label>
                  <label class=\"toggle\"><input type=\"checkbox\" id=\"showPowerToggle\" checked> Power</label>
                  <button type=\"button\" class=\"btn-secondary\" id=\"pauseRefreshBtn\">Pause Refresh</button>
                  <button type=\"button\" class=\"btn-secondary\" id=\"copyStatusBtn\">Copy Status JSON</button>
                </div>
              </div>
              <div class=\"chart-shell\">
                <svg id=\"historyChart\" viewBox=\"0 0 960 280\" preserveAspectRatio=\"none\"></svg>
                <div id=\"chartTooltip\" class=\"chart-tooltip hidden\">-</div>
              </div>
              <div class=\"legend\">
                <span class=\"hashrate\">Hashrate</span>
                <span class=\"temp\">Temperature</span>
                <span class=\"power\">Power</span>
              </div>
              <div class=\"chart-latest\">
                <span id=\"latestHashrate\">Hashrate -</span>
                <span id=\"latestTemp\">Temp -</span>
                <span id=\"latestPower\">Power -</span>
              </div>
            </div>
          </div>
            <div class=\"headroom-grid\">
            <div class=\"panel meter-card efficiency-panel\">
              <div class=\"panel-body\">
                <div class=\"section-head\">
                  <div>
                    <div class=\"eyebrow\">Efficiency</div>
                    <h2 class=\"heading-md\" id=\"efficiencyNow\">-</h2>
                  </div>
                </div>
                <div class=\"efficiency-controls\">
                  <label><span>$/kWh</span><input id=\"energyCostInput\" type=\"number\" min=\"0\" step=\"0.01\" value=\"0.15\"></label>
                  <label><span>Target J/TH</span><input id=\"targetEfficiencyInput\" type=\"number\" min=\"1\" step=\"0.1\" value=\"20\"></label>
                  <label><span>Unit</span><select id=\"efficiencyUnitSelect\"><option value=\"jth\">J/TH</option><option value=\"ghw\">GH/W</option></select></label>
                </div>
                <div class=\"efficiency-result\">
                  <strong id=\"dailyCostValue\">-</strong>
                  <span>projected daily energy cost</span>
                </div>
                <p class=\"panel-copy\" id=\"efficiencyAdvice\">Waiting for power and hashrate.</p>
              </div>
            </div>
            <div class=\"panel meter-card\">
              <div class=\"panel-body\">
                <div class=\"section-head\">
                  <div>
                    <div class=\"eyebrow\">Thermal Headroom</div>
                    <h2 class=\"heading-md\" id=\"thermalLabel\">-</h2>
                  </div>
                </div>
                <div class=\"bar\" id=\"thermalBar\"><span style=\"width:0%\"></span></div>
                <p class=\"panel-copy\" id=\"thermalHint\">Awaiting thermal telemetry.</p>
              </div>
            </div>
            <div class=\"panel meter-card\">
              <div class=\"panel-body\">
                <div class=\"section-head\">
                  <div>
                    <div class=\"eyebrow\">Power Headroom</div>
                    <h2 class=\"heading-md\" id=\"powerLabel\">-</h2>
                  </div>
                </div>
                <div class=\"bar\" id=\"powerBar\"><span style=\"width:0%\"></span></div>
                <p class=\"panel-copy\" id=\"powerHint\">Awaiting power telemetry.</p>
              </div>
            </div>
            <div class=\"panel meter-card\">
              <div class=\"panel-body\">
                <div class=\"section-head\">
                  <div>
                    <div class=\"eyebrow\">Next Tuning Window</div>
                    <h2 class=\"heading-md\" id=\"nextStepCountdown\">-</h2>
                  </div>
                  <span class=\"chip\" id=\"tuningLabel\">-</span>
                </div>
                <p class=\"panel-copy\" id=\"nextStepAt\">Waiting for controller timing.</p>
                <p class=\"panel-copy\" id=\"nextStepHint\">Cooldown and climb gates will appear here.</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section id=\"domainsSec\" class=\"section-card\">
        <div class=\"detail-grid\">
          <div class=\"panel\">
            <div class=\"panel-body\">
              <div class=\"section-head\">
                <div>
                  <div class=\"eyebrow\">ASIC Domains</div>
                  <h2 class=\"heading-md\">Per-Domain Stability</h2>
                </div>
              </div>
              <div id=\"domainAlert\" class=\"decision-hint\">Waiting for per-domain telemetry.</div>
              <div id=\"domainGrid\" class=\"domain-grid\"></div>
            </div>
          </div>

          <div class=\"panel\">
            <div class=\"panel-body\">
              <div class=\"section-head\">
                <div>
                  <div class=\"eyebrow\">Tuning Profile</div>
                  <h2 class=\"heading-md\">Preset Control</h2>
                </div>
              </div>
              <div class=\"advisor-card\" id=\"profileAdvisor\">
                <div>
                  <div class=\"eyebrow\">Profile Advisor</div>
                  <h3 id=\"advisorTitle\">Waiting for learning data</h3>
                  <p id=\"advisorText\">The controller will compare learned stability, thermal headroom, power, and domain spread.</p>
                </div>
                <span class=\"advisor-badge\" id=\"advisorBadge\">Sync</span>
              </div>
              <div id=\"presetStatus\" class=\"decision-hint\">Computing saved profile alignment.</div>
              <div class=\"preset-grid\">
                <div class=\"preset\" data-preset-card=\"cool\">
                  <div class=\"eyebrow\">Cool</div>
                  <p>Stability-first rails with tighter thermals and reduced power demand.</p>
                  <button type=\"button\" class=\"btn-secondary\" data-preset=\"cool\">Apply Cool</button>
                </div>
                <div class=\"preset\" data-preset-card=\"balanced\">
                  <div class=\"eyebrow\">Balanced</div>
                  <p>Moderate climb behavior with rollback logic tuned for daily operation.</p>
                  <button type=\"button\" class=\"btn-secondary\" data-preset=\"balanced\">Apply Balanced</button>
                </div>
                <div class=\"preset\" data-preset-card=\"performance\">
                  <div class=\"eyebrow\">Performance</div>
                  <p>Higher throughput ceiling for test conditions with wider thermal allowance.</p>
                  <button type=\"button\" data-preset=\"performance\">Apply Performance</button>
                </div>
              </div>
            </div>
          </div>

          <div class=\"panel\">
            <div class=\"panel-body\">
              <div class=\"section-head\">
                <div>
                  <div class=\"eyebrow\">Deep Telemetry</div>
                  <h2 class=\"heading-md\">Operational Signals</h2>
                </div>
              </div>
              <div class=\"deep-grid\">
                <div class=\"mini-card\"><div class=\"mini-label\">Error Percentage</div><div class=\"stat-value\" id=\"errorValue\">-</div><div class=\"muted\">Hardware error rate</div></div>
                <div class=\"mini-card\"><div class=\"mini-label\">Expected Hashrate</div><div class=\"stat-value\" id=\"expectedValue\">-</div><div class=\"muted\">Theoretical throughput</div></div>
                <div class=\"mini-card\"><div class=\"mini-label\">Best Difficulty</div><div class=\"stat-value\" id=\"bestDiffValue\">-</div><div class=\"muted\" id=\"bestDiffSubvalue\">-</div></div>
                <div class=\"mini-card\"><div class=\"mini-label\">Solo Block Odds</div><div class=\"stat-value\" id=\"soloOddsValue\">-</div><div class=\"muted\" id=\"soloOddsSubvalue\">Network difficulty odds</div></div>
                <div class=\"mini-card\"><div class=\"mini-label\">Response Time</div><div class=\"stat-value\" id=\"responseValue\">-</div><div class=\"muted\">Controller API latency</div></div>
                <div class=\"mini-card\"><div class=\"mini-label\">Status Freshness</div><div class=\"stat-value\" id=\"statusFreshnessValue\">-</div><div class=\"muted\" id=\"statusFreshnessSubvalue\">Controller write age</div></div>
                <div class=\"mini-card\"><div class=\"mini-label\">Advanced Health</div><div class=\"stat-value\" id=\"advancedHealthValue\">-</div><div class=\"muted\" id=\"advancedHealthSubvalue\">Controller health</div></div>
                <div class=\"mini-card\"><div class=\"mini-label\">Climb Eligibility</div><div class=\"stat-value\" id=\"climbValue\">-</div><div class=\"muted\" id=\"climbSubvalue\">Power and guardrail gate</div></div>
                <div class=\"mini-card\"><div class=\"mini-label\">Decisions</div><div class=\"stat-value\" id=\"decisionCountValue\">-</div><div class=\"muted\" id=\"decisionCountSubvalue\">Runtime decisions</div></div>
                <div class=\"mini-card\"><div class=\"mini-label\">Guardrail Ratios</div><div class=\"stat-value\" id=\"guardrailValue\">-</div><div class=\"muted\" id=\"guardrailSubvalue\">Power / domain / error</div></div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section id=\"esp32Sec\" class=\"section-card\">
        <div class=\"panel\">
          <div class=\"panel-body\">
            <div class=\"section-head\">
              <div>
                <div class=\"eyebrow\">ESP32 Firmware</div>
                <h2 class=\"heading-md\">NerdMiner Tools</h2>
              </div>
              <button type=\"button\" class=\"btn-secondary\" id=\"esp32RefreshBtn\">Refresh ESP32 Tools</button>
            </div>
            <div id=\"esp32Status\" class=\"decision-hint\">Checking for NerdMiner_v2 workspace and serial ports.</div>
            <div class=\"deep-grid esp32-grid\">
              <div class=\"mini-card\"><div class=\"mini-label\">Workspace</div><div class=\"stat-value\" id=\"esp32RootValue\">-</div><div class=\"muted\" id=\"esp32RootHint\">Set NERDMINER_ROOT if needed.</div></div>
              <div class=\"mini-card\"><div class=\"mini-label\">Serial Ports</div><div class=\"stat-value\" id=\"esp32PortsValue\">-</div><div class=\"muted\" id=\"esp32PortsHint\">Connect an ESP32 miner by USB.</div></div>
              <div class=\"mini-card\"><div class=\"mini-label\">Build Targets</div><div class=\"stat-value\" id=\"esp32EnvsValue\">-</div><div class=\"muted\" id=\"esp32EnvsHint\">PlatformIO environments from NerdMiner_v2.</div></div>
              <div class=\"mini-card\"><div class=\"mini-label\">Firmware Files</div><div class=\"stat-value\" id=\"esp32BundlesValue\">-</div><div class=\"muted\" id=\"esp32BundlesHint\">Prebuilt .bin bundles found.</div></div>
            </div>
          </div>
        </div>
      </section>

      <section id=\"configSec\" class=\"section-card\">
        <div class=\"lower-grid\">
          <div class=\"panel\">
            <div class=\"panel-body\">
              <div class=\"section-head\">
                <div>
                  <div class=\"eyebrow\">System Detail</div>
                  <h2 class=\"heading-md\">Runtime Summary</h2>
                </div>
              </div>
              <div id=\"details\" class=\"info-grid\"></div>
              <div class=\"toolbar\">
                <div class=\"toolbar-group\">
                  <span class=\"chip\" id=\"fanStripChip\">Fan: -</span>
                  <span class=\"chip\" id=\"modeStripChip\">Mode: -</span>
                </div>
              </div>
              <div class=\"panel\" style=\"margin-top:14px;\">
                <div class=\"panel-body\">
                  <div class=\"section-head\">
                    <div>
                      <div class=\"eyebrow\">Activity Feed</div>
                      <h2 class=\"heading-md\">Recent Operator Events</h2>
                    </div>
                  </div>
                  <div id=\"activityLog\" class=\"activity-log\"></div>
                </div>
              </div>
            </div>
          </div>

          <div class=\"panel\">
            <div class=\"panel-body\">
              <div class=\"section-head\">
                <div>
                  <div class=\"eyebrow\">Configuration</div>
                  <h2 class=\"heading-md\">Control Rails</h2>
                </div>
              </div>
              <form id=\"configForm\" class=\"config-grid\"></form>
              <div class=\"save-row\">
                <button type=\"submit\" form=\"configForm\">Save Config</button>
                <span id=\"saveMessage\" class=\"muted\"></span>
              </div>
              <div class=\"panel\" style=\"margin-top:14px;\">
                <div class=\"panel-body\">
                  <div class=\"section-head\">
                    <div>
                      <div class=\"eyebrow\">Payload</div>
                      <h2 class=\"heading-md\">Decision Snapshot</h2>
                    </div>
                  </div>
                  <pre id=\"decision\">Loading...</pre>
                  <div class=\"section-head\" style=\"margin-top:14px;\">
                    <div>
                      <div class=\"eyebrow\">Raw Status</div>
                      <h2 class=\"heading-md\">Controller JSON</h2>
                    </div>
                  </div>
                  <pre id=\"raw\"></pre>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>
    </main>
  </div>

  <script src=\"/assets/dashboard-app.js?v=20260509-app\"></script>
</body>
</html>"""


class Handler(BaseHTTPRequestHandler):
    def _send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, body: str) -> None:
        encoded = body.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/":
            self._send_html(html())
            return
        if path.startswith("/assets/"):
            try:
                body, content_type = read_asset_cached(path)
            except FileNotFoundError:
                self._send_json({"error": "not found"}, status=404)
                return
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "public, max-age=3600")
            self.end_headers()
            self.wfile.write(body)
            return
        if path == "/api/status":
            self._send_json(read_status())
            return
        if path == "/api/swarm":
            self._send_json(swarm_status())
            return
        if path == "/api/discover":
            self._send_json(discover_miners())
            return
        if path == "/api/update-check":
            self._send_json(update_status())
            return
        if path == "/api/esp32/status":
            self._send_json(esp32_status())
            return
        if path in {"/health", "/api/health"}:
            health = health_status()
            self._send_json(health, status=200 if health.get("ok") else 503)
            return
        if path == "/api/config":
            self._send_json(parse_env_file())
            return
        self._send_json({"error": "not found"}, status=404)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length).decode("utf-8")
            payload = json.loads(raw or "{}")
            if path == "/api/config":
                updates: dict[str, str] = {}
                for key, value in payload.items():
                    if key in EDITABLE_KEYS:
                        updates[key] = str(value)
                validated = write_env_file(updates)
                self._send_json({"ok": True, "updated": validated})
                return
            if path == "/api/swarm":
                miner = add_swarm_miner(payload)
                self._send_json({"ok": True, "miner": miner})
                return
            if path == "/api/swarm/remove":
                self._send_json(remove_swarm_miner(payload))
                return
            if path == "/api/action":
                action = payload.get("action")
                if action == "restart-controller":
                    self._send_json(restart_controller_service())
                    return
                if action == "restart-miner":
                    self._send_json(restart_bitaxe())
                    return
                self._send_json({"error": "unknown action"}, status=400)
                return
            self._send_json({"error": "not found"}, status=404)
        except Exception as exc:
            self._send_json({"error": str(exc)}, status=400)

    def log_message(self, format: str, *args) -> None:
        return


def create_server() -> ThreadingHTTPServer:
    return ThreadingHTTPServer((HOST, PORT), Handler)


def main() -> int:
    server = create_server()
    print(f"Bitaxe UI listening on http://{HOST}:{PORT}")
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
