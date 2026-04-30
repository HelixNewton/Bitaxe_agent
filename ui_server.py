#!/usr/bin/env python3
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
    "MINER_STATUS_FILE",
    "MINER_LEARNING_FILE",
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
</head>
<body>
  <div class=\"app-shell\">
    <aside class=\"sidebar\">
      <div class=\"brand-mark\">BA</div>
      <nav class=\"nav\">
        <a class=\"nav-link active\" href=\"#summarySec\" data-nav=\"summarySec\"><span class=\"nav-label\">SM</span></a>
        <a class=\"nav-link\" href=\"#statsSec\" data-nav=\"statsSec\"><span class=\"nav-label\">KP</span></a>
        <a class=\"nav-link\" href=\"#trendsSec\" data-nav=\"trendsSec\"><span class=\"nav-label\">TR</span></a>
        <a class=\"nav-link\" href=\"#domainsSec\" data-nav=\"domainsSec\"><span class=\"nav-label\">DM</span></a>
        <a class=\"nav-link\" href=\"#configSec\" data-nav=\"configSec\"><span class=\"nav-label\">CF</span></a>
      </nav>
      <div class=\"sidebar-meta\">Bitaxe Command Deck</div>
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
              <div class=\"eyebrow\">Cybernetic Control Plane</div>
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
                    <div class=\"eyebrow\">Agent Intent</div>
                    <h2 class=\"heading-md\" id=\"decisionReason\">Loading decision</h2>
                  </div>
                </div>
                <div class=\"decision-text mono\" id=\"decisionPatch\">-</div>
                <div class=\"decision-hint\" id=\"decisionHint\">The controller will describe why it is holding, climbing, or rolling back.</div>
                <div class=\"decision-actions\" style=\"margin-top:16px;\">
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
                  <button type=\"button\" class=\"btn-secondary\" id=\"pauseRefreshBtn\">Pause Refresh</button>
                  <button type=\"button\" class=\"btn-secondary\" id=\"copyStatusBtn\">Copy Status JSON</button>
                </div>
              </div>
              <div class=\"chart-shell\">
                <svg id=\"historyChart\" viewBox=\"0 0 960 280\" preserveAspectRatio=\"none\"></svg>
              </div>
              <div class=\"legend\">
                <span class=\"temp\">Temperature</span>
                <span class=\"freq\">Frequency</span>
                <span class=\"power\">Power</span>
              </div>
            </div>
          </div>
          <div class=\"headroom-grid\">
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
                <div class=\"mini-card\"><div class=\"mini-label\">Response Time</div><div class=\"stat-value\" id=\"responseValue\">-</div><div class=\"muted\">Controller API latency</div></div>
                <div class=\"mini-card\"><div class=\"mini-label\">Advanced Health</div><div class=\"stat-value\" id=\"advancedHealthValue\">-</div><div class=\"muted\" id=\"advancedHealthSubvalue\">Controller health</div></div>
                <div class=\"mini-card\"><div class=\"mini-label\">Climb Eligibility</div><div class=\"stat-value\" id=\"climbValue\">-</div><div class=\"muted\" id=\"climbSubvalue\">Power and guardrail gate</div></div>
                <div class=\"mini-card\"><div class=\"mini-label\">Decisions</div><div class=\"stat-value\" id=\"decisionCountValue\">-</div><div class=\"muted\" id=\"decisionCountSubvalue\">Runtime decisions</div></div>
                <div class=\"mini-card\"><div class=\"mini-label\">Guardrail Ratios</div><div class=\"stat-value\" id=\"guardrailValue\">-</div><div class=\"muted\" id=\"guardrailSubvalue\">Power / domain / error</div></div>
              </div>
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
                  <span class=\"chip\" id=\"fanChip\">Fan: -</span>
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

  <script>
    const editable = [
      "MINER_NAME", "MINER_URL", "MINER_API_PROFILE", "MINER_INFO_PATH", "MINER_ASIC_PATH", "MINER_SETTINGS_PATH", "MINER_RESTART_PATH",
      "MINER_STATUS_FILE", "MINER_LEARNING_FILE", "MINER_UI_HOST", "MINER_UI_PORT",
      \"BITAXE_URL\", \"BITAXE_MODE\", \"BITAXE_DRY_RUN\", \"BITAXE_AUTO_FAN\", \"BITAXE_LOOP_SECONDS\",
      \"BITAXE_MIN_FREQUENCY\", \"BITAXE_MAX_FREQUENCY\", \"BITAXE_ABSOLUTE_MAX_FREQUENCY\", \"BITAXE_FREQ_STEP\", \"BITAXE_MIN_VOLTAGE\",
      \"BITAXE_MAX_VOLTAGE\", \"BITAXE_ABSOLUTE_MAX_VOLTAGE\", \"BITAXE_VOLTAGE_STEP\", \"BITAXE_TARGET_TEMP_C\", \"BITAXE_HOT_TEMP_C\",
      \"BITAXE_EMERGENCY_TEMP_C\", \"BITAXE_ABSOLUTE_MAX_EMERGENCY_TEMP_C\", \"BITAXE_COOL_TEMP_C\", \"BITAXE_MAX_VR_TEMP_C\",
      \"BITAXE_ABSOLUTE_MAX_VR_TEMP_C\", \"BITAXE_MIN_INPUT_VOLTAGE_MV\", \"BITAXE_MAX_POWER_W\", \"BITAXE_ABSOLUTE_MAX_POWER_W\",
      \"BITAXE_CLIMB_POWER_RATIO\",
      \"BITAXE_MAX_ERROR_PERCENTAGE\", \"BITAXE_MAX_DOMAIN_SPREAD_PERCENTAGE\", \"BITAXE_CRITICAL_DOMAIN_SPREAD_PERCENTAGE\",
      \"BITAXE_DOMAIN_SPREAD_POLLS\", \"BITAXE_LEARNING_ENABLED\", \"BITAXE_LEARNING_MIN_SAMPLES\", \"BITAXE_LEARNING_BAD_LIMIT\",
      \"BITAXE_LEARNING_RESTORE_MARGIN\", \"BITAXE_LEARNING_EFFICIENCY_WEIGHT\", \"BITAXE_ADAPTIVE_COOLDOWN_ENABLED\",
      \"BITAXE_ADAPTIVE_MIN_COOLDOWN_SECONDS\", \"BITAXE_ADAPTIVE_MAX_COOLDOWN_SECONDS\", \"BITAXE_ADAPTIVE_STABLE_SAMPLES\",
      \"BITAXE_MIN_FAN_PERCENT\", \"BITAXE_MAX_FAN_PERCENT\",
      \"BITAXE_STEP_COOLDOWN_SECONDS\", \"BITAXE_USE_ASIC_OPTIONS\"
    ];
    const groups = {
      \"Miner\": [\"MINER_NAME\", \"MINER_URL\", \"MINER_API_PROFILE\", \"MINER_INFO_PATH\", \"MINER_ASIC_PATH\", \"MINER_SETTINGS_PATH\", \"MINER_RESTART_PATH\", \"MINER_STATUS_FILE\", \"MINER_LEARNING_FILE\", \"MINER_UI_HOST\", \"MINER_UI_PORT\"],
      \"Control\": [\"BITAXE_URL\", \"BITAXE_MODE\", \"BITAXE_DRY_RUN\", \"BITAXE_AUTO_FAN\", \"BITAXE_LOOP_SECONDS\"],
      \"Frequency\": [\"BITAXE_MIN_FREQUENCY\", \"BITAXE_MAX_FREQUENCY\", \"BITAXE_ABSOLUTE_MAX_FREQUENCY\", \"BITAXE_FREQ_STEP\", \"BITAXE_USE_ASIC_OPTIONS\"],
      \"Voltage\": [\"BITAXE_MIN_VOLTAGE\", \"BITAXE_MAX_VOLTAGE\", \"BITAXE_ABSOLUTE_MAX_VOLTAGE\", \"BITAXE_VOLTAGE_STEP\"],
      \"Thermal\": [\"BITAXE_TARGET_TEMP_C\", \"BITAXE_HOT_TEMP_C\", \"BITAXE_EMERGENCY_TEMP_C\", \"BITAXE_ABSOLUTE_MAX_EMERGENCY_TEMP_C\", \"BITAXE_COOL_TEMP_C\", \"BITAXE_MAX_VR_TEMP_C\", \"BITAXE_ABSOLUTE_MAX_VR_TEMP_C\"],
      \"Power And Stability\": [\"BITAXE_MIN_INPUT_VOLTAGE_MV\", \"BITAXE_MAX_POWER_W\", \"BITAXE_ABSOLUTE_MAX_POWER_W\", \"BITAXE_CLIMB_POWER_RATIO\", \"BITAXE_MAX_ERROR_PERCENTAGE\", \"BITAXE_MAX_DOMAIN_SPREAD_PERCENTAGE\", \"BITAXE_CRITICAL_DOMAIN_SPREAD_PERCENTAGE\", \"BITAXE_DOMAIN_SPREAD_POLLS\", \"BITAXE_LEARNING_ENABLED\", \"BITAXE_LEARNING_MIN_SAMPLES\", \"BITAXE_LEARNING_BAD_LIMIT\", \"BITAXE_LEARNING_RESTORE_MARGIN\", \"BITAXE_LEARNING_EFFICIENCY_WEIGHT\", \"BITAXE_ADAPTIVE_COOLDOWN_ENABLED\", \"BITAXE_ADAPTIVE_MIN_COOLDOWN_SECONDS\", \"BITAXE_ADAPTIVE_MAX_COOLDOWN_SECONDS\", \"BITAXE_ADAPTIVE_STABLE_SAMPLES\", \"BITAXE_MIN_FAN_PERCENT\", \"BITAXE_MAX_FAN_PERCENT\", \"BITAXE_STEP_COOLDOWN_SECONDS\"]
    };
    const presets = {
      cool: {
        BITAXE_MAX_FREQUENCY: \"525\",
        BITAXE_MAX_VOLTAGE: \"1060\",
        BITAXE_COOL_TEMP_C: \"61\",
        BITAXE_MAX_POWER_W: \"15.5\",
        BITAXE_MAX_ERROR_PERCENTAGE: \"10\",
        BITAXE_STEP_COOLDOWN_SECONDS: \"240\"
      },
      balanced: {
        BITAXE_MAX_FREQUENCY: \"535\",
        BITAXE_MAX_VOLTAGE: \"1090\",
        BITAXE_COOL_TEMP_C: \"63\",
        BITAXE_MAX_POWER_W: \"16.5\",
        BITAXE_MAX_ERROR_PERCENTAGE: \"20\",
        BITAXE_STEP_COOLDOWN_SECONDS: \"180\"
      },
      performance: {
        BITAXE_MAX_FREQUENCY: \"575\",
        BITAXE_MAX_VOLTAGE: \"1125\",
        BITAXE_COOL_TEMP_C: \"64\",
        BITAXE_MAX_POWER_W: \"17.5\",
        BITAXE_MAX_ERROR_PERCENTAGE: \"25\",
        BITAXE_STEP_COOLDOWN_SECONDS: \"120\"
      }
    };
    const historyBuffer = [];
    const activityLog = [];
    const maxHistoryPoints = 60;
    const maxActivityItems = 18;
    let refreshIntervalMs = 5000;
    let refreshTimer = null;
    let refreshPaused = false;
    let chartVisible = false;
    let lastConfigSignature = \"\";
    let lastOverviewSignature = \"\";
    let reconnectAttempts = 0;

    const dom = {
      overview: document.getElementById(\"overview\"),
      health: document.getElementById(\"health\"),
      heroText: document.getElementById(\"heroText\"),
      updatedAt: document.getElementById(\"updatedAt\"),
      updatedChip: document.getElementById(\"updatedChip\"),
      modeChip: document.getElementById(\"modeChip\"),
      modeStripChip: document.getElementById(\"modeStripChip\"),
      dryRunChip: document.getElementById(\"dryRunChip\"),
      fanChip: document.getElementById(\"fanChip\"),
      stabilityChip: document.getElementById(\"stabilityChip\"),
      domainGuardChip: document.getElementById(\"domainGuardChip\"),
      decisionReason: document.getElementById(\"decisionReason\"),
      decisionPatch: document.getElementById(\"decisionPatch\"),
      decisionHint: document.getElementById(\"decisionHint\"),
      actionMessage: document.getElementById(\"actionMessage\"),
      historyChart: document.getElementById(\"historyChart\"),
      thermalLabel: document.getElementById(\"thermalLabel\"),
      thermalBar: document.getElementById(\"thermalBar\"),
      thermalHint: document.getElementById(\"thermalHint\"),
      powerLabel: document.getElementById(\"powerLabel\"),
      powerBar: document.getElementById(\"powerBar\"),
      powerHint: document.getElementById(\"powerHint\"),
      nextStepCountdown: document.getElementById(\"nextStepCountdown\"),
      nextStepAt: document.getElementById(\"nextStepAt\"),
      nextStepHint: document.getElementById(\"nextStepHint\"),
      tuningLabel: document.getElementById(\"tuningLabel\"),
      domainAlert: document.getElementById(\"domainAlert\"),
      domainGrid: document.getElementById(\"domainGrid\"),
      profileAdvisor: document.getElementById(\"profileAdvisor\"),
      advisorTitle: document.getElementById(\"advisorTitle\"),
      advisorText: document.getElementById(\"advisorText\"),
      advisorBadge: document.getElementById(\"advisorBadge\"),
      presetStatus: document.getElementById(\"presetStatus\"),
      details: document.getElementById(\"details\"),
      errorValue: document.getElementById(\"errorValue\"),
      expectedValue: document.getElementById(\"expectedValue\"),
      bestDiffValue: document.getElementById(\"bestDiffValue\"),
      bestDiffSubvalue: document.getElementById(\"bestDiffSubvalue\"),
      responseValue: document.getElementById(\"responseValue\"),
      advancedHealthValue: document.getElementById(\"advancedHealthValue\"),
      advancedHealthSubvalue: document.getElementById(\"advancedHealthSubvalue\"),
      climbValue: document.getElementById(\"climbValue\"),
      climbSubvalue: document.getElementById(\"climbSubvalue\"),
      decisionCountValue: document.getElementById(\"decisionCountValue\"),
      decisionCountSubvalue: document.getElementById(\"decisionCountSubvalue\"),
      guardrailValue: document.getElementById(\"guardrailValue\"),
      guardrailSubvalue: document.getElementById(\"guardrailSubvalue\"),
      configForm: document.getElementById(\"configForm\"),
      saveMessage: document.getElementById(\"saveMessage\"),
      decision: document.getElementById(\"decision\"),
      raw: document.getElementById(\"raw\"),
      activityLog: document.getElementById(\"activityLog\"),
      refreshSelect: document.getElementById(\"refreshSelect\"),
      pauseRefreshBtn: document.getElementById(\"pauseRefreshBtn\"),
      search: document.getElementById(\"sectionSearch\")
    };

    function prettyBool(value) {
      return String(value) === \"true\" || value === true ? \"On\" : \"Off\";
    }

    function formatKey(key) {
      return key.replace(\"BITAXE_\", \"\").replaceAll(\"_\", \" \");
    }

    function formatSeconds(totalSeconds) {
      const seconds = Math.max(0, Math.floor(totalSeconds));
      const minutes = Math.floor(seconds / 60);
      const remain = seconds % 60;
      return `${minutes}m ${remain}s`;
    }

    function formatCompactNumber(value) {
      const number = Number(value) || 0;
      if (number >= 1e9) return `${(number / 1e9).toFixed(2)} G`;
      if (number >= 1e6) return `${(number / 1e6).toFixed(2)} M`;
      if (number >= 1e3) return `${(number / 1e3).toFixed(2)} K`;
      return `${number.toFixed(0)}`;
    }

    function formatPercent(value) {
      const number = Number(value) || 0;
      return `${number.toFixed(4)}%`;
    }

    function formatRatio(value) {
      const number = Number(value);
      return Number.isFinite(number) ? `${(number * 100).toFixed(1)}%` : \"-\";
    }

    async function fetchJson(path, options = {}, retries = 2) {
      for (let attempt = 0; attempt <= retries; attempt += 1) {
        try {
          const response = await fetch(path, options);
          if (!response.ok) throw new Error(await response.text());
          reconnectAttempts = 0;
          return response.json();
        } catch (error) {
          if (attempt >= retries) throw error;
          await new Promise((resolve) => setTimeout(resolve, 500 * (attempt + 1)));
        }
      }
      throw new Error(\"request failed\");
    }

    async function postAction(action) {
      return fetchJson(\"/api/action\", {
        method: \"POST\",
        headers: { \"Content-Type\": \"application/json\" },
        body: JSON.stringify({ action })
      });
    }

    function pushActivity(title, text) {
      activityLog.unshift({ title, text, at: new Date().toLocaleTimeString() });
      while (activityLog.length > maxActivityItems) activityLog.pop();
      dom.activityLog.innerHTML = activityLog.map((item) => `
        <div class=\"activity-item\">
          <strong>${item.title}</strong>
          <div>${item.text}</div>
          <div class=\"muted\">${item.at}</div>
        </div>
      `).join(\"\");
    }

    function addHistoryPoint(state) {
      if (!state || typeof state.temperature_c !== \"number\") return;
      historyBuffer.push({
        temp: Number(state.temperature_c) || 0,
        freq: Number(state.frequency_mhz) || 0,
        power: Number(state.power_w) || 0
      });
      while (historyBuffer.length > maxHistoryPoints) historyBuffer.shift();
    }

    function normalizeSeries(values, width, height, padding) {
      if (!values.length) return \"\";
      const min = Math.min(...values);
      const max = Math.max(...values);
      const span = max - min || 1;
      return values.map((value, index) => {
        const x = padding + ((width - padding * 2) * index / Math.max(1, values.length - 1));
        const y = height - padding - (((value - min) / span) * (height - padding * 2));
        return `${x.toFixed(2)},${y.toFixed(2)}`;
      }).join(\" \");
    }

    function renderHistoryChart() {
      if (!chartVisible) return;
      if (!historyBuffer.length) {
        dom.historyChart.innerHTML = \"\";
        return;
      }
      const width = 960;
      const height = 280;
      const padding = 18;
      const tempPoints = normalizeSeries(historyBuffer.map((point) => point.temp), width, height, padding);
      const freqPoints = normalizeSeries(historyBuffer.map((point) => point.freq), width, height, padding);
      const powerPoints = normalizeSeries(historyBuffer.map((point) => point.power), width, height, padding);
      const grid = [0.2, 0.4, 0.6, 0.8].map((ratio) => {
        const y = (height * ratio).toFixed(2);
        return `<line x1=\"0\" y1=\"${y}\" x2=\"${width}\" y2=\"${y}\" stroke=\"rgba(0,255,156,.08)\" stroke-width=\"1\" />`;
      }).join(\"\");
      dom.historyChart.innerHTML = `
        ${grid}
        <polyline fill=\"none\" stroke=\"#33ffaf\" stroke-width=\"3\" stroke-linecap=\"round\" stroke-linejoin=\"round\" points=\"${tempPoints}\"></polyline>
        <polyline fill=\"none\" stroke=\"#39e5ff\" stroke-width=\"3\" stroke-linecap=\"round\" stroke-linejoin=\"round\" points=\"${freqPoints}\"></polyline>
        <polyline fill=\"none\" stroke=\"#ffd166\" stroke-width=\"3\" stroke-linecap=\"round\" stroke-linejoin=\"round\" points=\"${powerPoints}\"></polyline>
      `;
    }

    function setBar(node, ratio, variant) {
      node.className = `bar ${variant || \"\"}`.trim();
      node.querySelector(\"span\").style.width = `${Math.max(0, Math.min(100, ratio))}%`;
    }

    function healthState(temp, target, emergency, lastError) {
      if (lastError) return { className: \"status-pill hot\", label: \"Controller Error\" };
      if (temp >= emergency) return { className: \"status-pill hot\", label: \"Emergency Thermal\" };
      if (temp >= target) return { className: \"status-pill warn\", label: \"Thermal Watch\" };
      return { className: \"status-pill ok\", label: \"Online\" };
    }

    function explainTuning(state, status) {
      const temp = Number(state.temperature_c) || 0;
      const power = Number(state.power_w) || 0;
      const cool = Number(status.config?.cool_temp_c) || 0;
      const powerGate = (Number(status.config?.max_power_w) || 0) * 0.9;
      const err = Number(state.error_percentage) || 0;
      const errCap = Number(status.config?.max_error_percentage) || 0;
      if (errCap && err >= errCap) return `Holding because error rate ${err.toFixed(2)}% is above the ${errCap}% guardrail.`;
      if (temp <= cool && power < powerGate) return \"The miner is inside the climb window and can step up when cooldown allows.\";
      if (temp > cool) return `Holding because temperature ${temp.toFixed(1)}C is above the cool threshold of ${cool}C.`;
      return `Holding because power draw ${power.toFixed(2)}W is above the climb gate of ${powerGate.toFixed(2)}W.`;
    }

    function getDomainGuardState(state, status) {
      const spread = Number(state.domain_spread_percentage) || 0;
      const offline = Number(state.offline_domain_count) || 0;
      const maxSpread = Number(status.config?.max_domain_spread_percentage) || 0;
      const criticalSpread = Number(status.config?.critical_domain_spread_percentage) || 0;
      if (offline > 0 || (criticalSpread && spread >= criticalSpread)) return { label: \"Rollback Armed\", className: \"chip hot\" };
      if (maxSpread && spread >= maxSpread) return { label: \"Watch\", className: \"chip warn\" };
      return { label: \"Stable\", className: \"chip ok\" };
    }

    function renderOverview(state, status) {
      const expected = Number(state.raw?.expectedHashrate) || 0;
      const next = [
        { label: \"Temp\", value: state.temperature_c?.toFixed?.(1) ?? \"-\", suffix: \"C\", sub: `Target ${status.config?.target_temp_c ?? \"-\"}C` },
        { label: \"Hashrate\", value: state.hashrate_gh?.toFixed?.(1) ?? \"-\", suffix: \" GH/s\", sub: `Expected ${expected ? expected.toFixed(1) : \"-\"} GH/s` },
        { label: \"Power\", value: state.power_w?.toFixed?.(2) ?? \"-\", suffix: \" W\", sub: `Cap ${status.config?.max_power_w ?? \"-\"} W` },
        { label: \"Frequency\", value: state.frequency_mhz ?? \"-\", suffix: \" MHz\", sub: `Range ${status.config?.min_frequency ?? \"-\"}-${status.config?.max_frequency ?? \"-\"}` }
      ];
      const signature = JSON.stringify(next);
      if (signature === lastOverviewSignature) return;
      lastOverviewSignature = signature;
      dom.overview.innerHTML = next.map((item) => `
        <div class=\"panel stat-card\">
          <div class=\"panel-body\">
            <div class=\"eyebrow\">${item.label}</div>
            <div class=\"stat-value\">${item.value}${item.suffix}</div>
            <div class=\"stat-foot\"><span>${item.sub}</span><span class=\"chip ok\">Live</span></div>
          </div>
        </div>
      `).join(\"\");
    }

    function renderDomains(state) {
      const domains = state.raw?.hashrateMonitor?.asics?.[0]?.domains || [];
      if (!domains.length) {
        dom.domainAlert.textContent = \"Domain telemetry is not available yet.\";
        dom.domainGrid.innerHTML = `<div class=\"domain-card\"><div class=\"muted\">No domain data in the current payload.</div></div>`;
        return;
      }
      const numeric = domains.map((value) => Number(value) || 0);
      const active = numeric.filter((value) => value > 0);
      const offline = numeric.length - active.length;
      const average = active.length ? active.reduce((sum, value) => sum + value, 0) / active.length : 0;
      const weakest = active.length ? Math.min(...active) : 0;
      const spread = average > 0 ? ((average - weakest) / average) * 100 : 0;
      if (offline > 0) {
        dom.domainAlert.textContent = `${offline} domain ${offline === 1 ? \"is\" : \"are\"} offline. Stability rollback risk is active.`;
      } else if (spread >= 18) {
        dom.domainAlert.textContent = `Domain imbalance is critical at ${spread.toFixed(1)}%. The weakest lane is materially underperforming.`;
      } else if (spread >= 10) {
        dom.domainAlert.textContent = `Domain spread is elevated at ${spread.toFixed(1)}%. Watch for a developing weak lane.`;
      } else {
        dom.domainAlert.textContent = `Domain spread is stable at ${spread.toFixed(1)}% across ${numeric.length} active lanes.`;
      }
      dom.domainGrid.innerHTML = numeric.map((value, index) => {
        const deviation = average > 0 ? ((average - value) / average) * 100 : 0;
        const isOffline = value <= 0;
        const stateClass = isOffline ? \"hot\" : deviation >= 18 ? \"hot\" : deviation >= 10 ? \"warn\" : \"\";
        const stateText = isOffline ? \"offline\" : deviation >= 18 ? \"weak\" : deviation >= 10 ? \"watch\" : \"healthy\";
        return `
          <div class=\"domain-card ${isOffline ? \"offline\" : stateClass}\">
            <div class=\"mini-label\">Domain ${index + 1}</div>
            <div class=\"domain-value\">${value.toFixed(1)}</div>
            <div class=\"muted\">GH/s</div>
            <div class=\"domain-state ${stateClass}\">${stateText}</div>
          </div>
        `;
      }).join(\"\");
    }

    function presetDistance(config, preset) {
      return Object.entries(preset).reduce((score, [key, value]) => {
        if (String(config[key] ?? \"\") === String(value)) return score;
        return score + 1;
      }, 0);
    }

    function renderPresetStatus(config) {
      const candidates = Object.entries(presets).map(([name, preset]) => ({ name, distance: presetDistance(config, preset) }));
      candidates.sort((a, b) => a.distance - b.distance);
      const active = candidates[0];
      document.querySelectorAll(\"[data-preset-card]\").forEach((card) => {
        card.classList.toggle(\"active\", card.dataset.presetCard === active.name);
      });
      const total = Object.keys(presets[active.name]).length;
      const matched = total - active.distance;
      dom.presetStatus.textContent = active.distance === 0
        ? `Current preset: ${active.name}. Saved config exactly matches the profile.`
        : `Closest preset: ${active.name}. ${matched}/${total} profile fields match the saved rails.`;
    }

    function renderProfileAdvisor(state, status) {
      const temp = Number(state.temperature_c);
      const power = Number(state.power_w);
      const fan = Number(state.fan_percent);
      const spread = Number(state.domain_spread_percentage);
      const maxSpread = Number(status.config?.max_domain_spread_percentage) || 12;
      const target = Number(status.config?.target_temp_c) || 65;
      const powerCap = Number(status.config?.max_power_w) || 16.5;
      const best = status.learning?.best_stable;
      let tone = \"ok\";
      let title = \"Hold Balanced\";
      let text = \"Learning data says the miner is inside daily operating rails. Keep collecting samples.\";
      let badge = \"Balanced\";

      if (!Number.isFinite(temp) || !Number.isFinite(power)) {
        tone = \"sync\";
        title = \"Waiting for telemetry\";
        text = \"The advisor will activate once status.json includes live temperature, power, and learning data.\";
        badge = \"Sync\";
      } else if (spread >= maxSpread || fan >= 98 || temp >= target || power >= powerCap * 0.96) {
        tone = \"warn\";
        title = \"Cooling Headroom Tight\";
        text = `Hold or step down if this persists. Fan ${Number.isFinite(fan) ? fan.toFixed(0) : \"-\"}%, temp ${temp.toFixed(1)}C, domain spread ${Number.isFinite(spread) ? spread.toFixed(1) : \"-\"}%.`;
        badge = \"Watch\";
      } else if (best && Number(best.frequency_mhz) <= Number(state.frequency_mhz || 0)) {
        tone = \"ok\";
        title = \"Best Learned Range\";
        text = `Best stable target is ${best.frequency_mhz} MHz / ${best.voltage_mv} mV with ${Number(best.best_hashrate_gh || 0).toFixed(1)} GH/s observed.`;
        badge = \"Learned\";
      } else if (temp < target - 4 && power < powerCap * 0.9 && spread < maxSpread * 0.75) {
        tone = \"boost\";
        title = \"Room to Test Upward\";
        text = \"Thermal, power, and domain spread are clean enough for one cautious step after cooldown.\";
        badge = \"Test\";
      }

      dom.profileAdvisor.className = `advisor-card ${tone}`;
      dom.advisorTitle.textContent = title;
      dom.advisorText.textContent = text;
      dom.advisorBadge.textContent = badge;
    }

    function renderConfig(config) {
      const signature = JSON.stringify(config);
      if (signature === lastConfigSignature) return;
      lastConfigSignature = signature;
      dom.configForm.innerHTML = Object.entries(groups).map(([title, keys]) => `
        <div class=\"config-group\">
          <h3>${title}</h3>
          <div class=\"config-grid\">
            ${keys.map((key) => `
              <label>
                <span class=\"mini-label mono\">${formatKey(key)}</span>
                <input name=\"${key}\" value=\"${config[key] ?? \"\"}\">
              </label>
            `).join(\"\")}
          </div>
        </div>
      `).join(\"\");
      dom.configForm.onsubmit = async (event) => {
        event.preventDefault();
        const payload = {};
        for (const key of editable) payload[key] = dom.configForm.elements[key].value;
        try {
          await fetchJson(\"/api/config\", {
            method: \"POST\",
            headers: { \"Content-Type\": \"application/json\" },
            body: JSON.stringify(payload)
          });
          dom.saveMessage.textContent = \"Saved. Restart the controller to apply immediately.\";
          pushActivity(\"Config\", \"Control rails were written to .env.\");
          lastConfigSignature = \"\";
          await refresh();
        } catch (error) {
          dom.saveMessage.textContent = error.message;
        }
      };
    }

    function renderInfoRows(state, status, config) {
      const best = status.learning?.best_stable;
      const health = status.health || {};
      const metrics = status.metrics || {};
      const guardrails = status.guardrails || {};
      const rows = [
        [\"Voltage\", `${state.voltage_mv ?? \"-\"} mV`],
        [\"Fan\", `${state.fan_percent ?? \"-\"}%`],
        [\"Input Voltage\", `${state.input_voltage_mv ?? \"-\"} mV`],
        [\"Mode\", `${status.config?.mode ?? \"-\"}`],
        [\"Auto Fan\", prettyBool(config.BITAXE_AUTO_FAN)],
        [\"Dry Run\", prettyBool(status.config?.dry_run)],
        [\"Error Limit\", `${status.config?.max_error_percentage ?? \"-\"}%`],
        [\"Domain Spread Limit\", `${status.config?.max_domain_spread_percentage ?? \"-\"}%`],
        [\"Climb Power Gate\", status.climb_power_gate_w ? `${status.climb_power_gate_w.toFixed(2)} W` : \"-\"],
        [\"Learning\", prettyBool(status.config?.learning_enabled)],
        [\"Best Learned\", best ? `${best.frequency_mhz} MHz / ${best.voltage_mv} mV / ${best.best_hashrate_gh.toFixed(1)} GH/s` : \"none yet\"],
        [\"Efficiency\", status.efficiency_gh_per_w ? `${status.efficiency_gh_per_w.toFixed(2)} GH/W` : \"-\"],
        [\"Score\", status.performance_score ? `${status.performance_score.toFixed(2)}` : \"-\"],
        [\"Score Penalty\", status.performance_metrics?.total_penalty ? `${status.performance_metrics.total_penalty.toFixed(2)}` : \"0.00\"],
        [\"Can Climb\", guardrails.can_climb === undefined ? \"-\" : prettyBool(guardrails.can_climb)],
        [\"Power Gate\", guardrails.can_climb_by_power === undefined ? \"-\" : prettyBool(guardrails.can_climb_by_power)],
        [\"Health\", health.status || (status.last_error ? \"degraded\" : \"healthy\")],
        [\"Decisions\", metrics.total_decisions ?? \"-\"],
        [\"Error Rate\", metrics.error_rate === undefined ? \"-\" : `${(Number(metrics.error_rate) * 100).toFixed(2)}%`],
        [\"Active Cooldown\", `${status.active_cooldown_seconds ?? status.config?.step_cooldown_seconds ?? \"-\"} s`],
        [\"Cooldown\", `${status.config?.step_cooldown_seconds ?? \"-\"} s`],
        [\"Last Error\", `${status.last_error || \"none\"}`]
      ];
      dom.details.innerHTML = rows.map(([label, value]) => `
        <div class=\"info-row\">
          <span class=\"mini-label\">${label}</span>
          <strong>${value}</strong>
        </div>
      `).join(\"\");
    }

    function applyLiveText(node, value) {
      if (node.textContent === value) return;
      node.textContent = value;
      node.classList.remove(\"updated\");
      void node.offsetWidth;
      node.classList.add(\"updated\");
      setTimeout(() => node.classList.remove(\"updated\"), 220);
    }

    async function applyPreset(name) {
      const preset = presets[name];
      if (!preset) return;
      setActionMessage(`Applying ${name} preset...`);
      try {
        await fetchJson(\"/api/config\", {
          method: \"POST\",
          headers: { \"Content-Type\": \"application/json\" },
          body: JSON.stringify(preset)
        });
        setActionMessage(`${name} preset saved. Restart the controller to apply immediately.`);
        pushActivity(\"Preset\", `${name} preset saved to the control rails.`);
        lastConfigSignature = \"\";
        await refresh();
      } catch (error) {
        setActionMessage(error.message, true);
      }
    }

    function setActionMessage(message, isError = false) {
      dom.actionMessage.textContent = message;
      dom.actionMessage.style.color = isError ? \"var(--hot)\" : \"var(--soft)\";
    }

    function scheduleRefresh() {
      if (refreshTimer) clearInterval(refreshTimer);
      if (!refreshPaused) refreshTimer = setInterval(refresh, refreshIntervalMs);
    }

    async function refresh() {
      let status;
      let config;
      try {
        [status, config] = await Promise.all([fetchJson(\"/api/status\"), fetchJson(\"/api/config\")]);
      } catch (error) {
        reconnectAttempts += 1;
        dom.health.className = \"status-pill hot\";
        dom.health.innerHTML = `<span class=\"pulse\"></span><span>Connection Lost</span>`;
        dom.updatedAt.textContent = `Retrying dashboard connection (${reconnectAttempts})`;
        setActionMessage(\"Lost connection to the UI server. Retrying...\", true);
        return;
      }
      if (dom.actionMessage.textContent.startsWith(\"Lost connection\")) {
        setActionMessage(\"Dashboard connection restored.\");
      }
      const state = status.state || {};
      const decision = status.last_decision || {};
      const expected = Number(state.raw?.expectedHashrate) || 0;
      const ratio = expected > 0 ? ((Number(state.hashrate_gh) || 0) / expected) * 100 : 0;
      const health = healthState(Number(state.temperature_c) || 0, Number(status.config?.target_temp_c) || 60, Number(status.config?.emergency_temp_c) || 68, status.last_error);
      const domainGuard = getDomainGuardState(state, status);
      const thermalRatio = (Number(state.temperature_c) || 0) && status.config?.emergency_temp_c ? ((Number(state.temperature_c) || 0) / Number(status.config.emergency_temp_c)) * 100 : 0;
      const powerRatio = (Number(state.power_w) || 0) && status.config?.max_power_w ? ((Number(state.power_w) || 0) / Number(status.config.max_power_w)) * 100 : 0;
      const thermalVariant = thermalRatio >= 100 ? \"hot\" : thermalRatio >= 85 ? \"warn\" : \"\";
      const powerVariant = powerRatio >= 100 ? \"hot\" : powerRatio >= 90 ? \"warn\" : \"\";

      addHistoryPoint(state);
      renderHistoryChart();
      renderOverview(state, status);
      renderDomains(state);
      renderPresetStatus(config);
      renderProfileAdvisor(state, status);
      renderConfig(config);
      renderInfoRows(state, status, config);

      dom.health.className = health.className;
      dom.health.innerHTML = `<span class=\"pulse\"></span><span>${health.label}</span>`;
      dom.updatedAt.textContent = status.updated_at || \"Awaiting status\";
      dom.updatedChip.textContent = `Updated: ${status.updated_at || \"-\"}`;
      dom.modeChip.textContent = `Mode: ${status.config?.mode || \"-\"}`;
      dom.modeStripChip.textContent = `Mode: ${status.config?.mode || \"-\"}`;
      dom.dryRunChip.textContent = `Dry Run: ${prettyBool(status.config?.dry_run)}`;
      dom.fanChip.textContent = `Fan: ${prettyBool(config.BITAXE_AUTO_FAN)} / ${state.fan_percent ?? \"-\"}%`;
      dom.stabilityChip.textContent = `Stability: ${ratio ? ratio.toFixed(1) : \"-\"}% expected`;
      dom.domainGuardChip.className = domainGuard.className;
      dom.domainGuardChip.textContent = `Domain Guard: ${domainGuard.label}`;
      dom.heroText.textContent = `Miner ${config.BITAXE_URL || \"-\"} is running at ${state.frequency_mhz ?? \"-\"} MHz, ${state.voltage_mv ?? \"-\"} mV, ${state.temperature_c?.toFixed?.(1) ?? \"-\"}C, and ${state.hashrate_gh?.toFixed?.(1) ?? \"-\"} GH/s on the 1-minute window.`;
      dom.decisionReason.textContent = decision.reason || \"No decision available\";
      dom.decisionPatch.textContent = JSON.stringify(decision.patch || {}, null, 2);
      dom.decisionHint.textContent = explainTuning(state, status);
      dom.decision.textContent = JSON.stringify(decision, null, 2);
      dom.raw.textContent = JSON.stringify(status, null, 2);
      dom.thermalLabel.textContent = `${state.temperature_c?.toFixed?.(1) ?? \"-\"}C / ${status.config?.emergency_temp_c ?? \"-\"}C`;
      dom.powerLabel.textContent = `${state.power_w?.toFixed?.(2) ?? \"-\"}W / ${status.config?.max_power_w ?? \"-\"}W`;
      dom.thermalHint.textContent = `Target ${status.config?.target_temp_c ?? \"-\"}C. Hot ${status.config?.hot_temp_c ?? \"-\"}C. Emergency ${status.config?.emergency_temp_c ?? \"-\"}C.`;
      dom.powerHint.textContent = `Climb gate is 90% of cap: ${((Number(status.config?.max_power_w) || 0) * 0.9).toFixed(2)}W.`;
      dom.tuningLabel.textContent = decision.reason || \"Hold\";
      dom.nextStepHint.textContent = explainTuning(state, status);
      setBar(dom.thermalBar, thermalRatio, thermalVariant);
      setBar(dom.powerBar, powerRatio, powerVariant);

      const nextStepEpoch = status.next_change_at_epoch;
      if (nextStepEpoch) {
        const remaining = nextStepEpoch - (Date.now() / 1000);
        dom.nextStepCountdown.textContent = remaining > 0 ? formatSeconds(remaining) : \"Ready now\";
        dom.nextStepAt.textContent = `Next change allowed after ${new Date(nextStepEpoch * 1000).toLocaleTimeString()}`;
      } else {
        dom.nextStepCountdown.textContent = \"Ready now\";
        dom.nextStepAt.textContent = \"No recent frequency or voltage change is blocking the next step.\";
      }

      const bestDiff = Number(state.raw?.bestDiff) || 0;
      const bestSessionDiff = Number(state.raw?.bestSessionDiff) || 0;
      const networkDifficulty = Number(state.raw?.networkDifficulty) || 0;
      const uptimeSeconds = Number(state.raw?.uptimeSeconds) || 0;
      const healthInfo = status.health || {};
      const metricsInfo = status.metrics || {};
      const guardrailsInfo = status.guardrails || {};
      const allTimePercent = networkDifficulty > 0 ? (bestDiff / networkDifficulty) * 100 : 0;
      applyLiveText(dom.errorValue, `${state.error_percentage?.toFixed?.(2) ?? \"-\"}%`);
      applyLiveText(dom.expectedValue, `${expected ? expected.toFixed(1) : \"-\"} GH/s`);
      applyLiveText(dom.bestDiffValue, `bestDiff ${formatCompactNumber(bestDiff)}`);
      dom.bestDiffSubvalue.innerHTML = `bestSessionDiff ${formatCompactNumber(bestSessionDiff)} (${formatSeconds(uptimeSeconds)})<br>all-time progress ${formatPercent(allTimePercent)}`;
      applyLiveText(dom.responseValue, `${state.raw?.responseTime?.toFixed?.(1) ?? \"-\"} ms`);
      applyLiveText(dom.advancedHealthValue, healthInfo.status || (status.last_error ? \"degraded\" : \"healthy\"));
      dom.advancedHealthSubvalue.textContent = `actions ${healthInfo.successful_actions ?? \"-\"} / uptime ${formatSeconds(healthInfo.uptime_seconds || 0)}`;
      applyLiveText(dom.climbValue, guardrailsInfo.can_climb === undefined ? \"-\" : (guardrailsInfo.can_climb ? \"Allowed\" : \"Blocked\"));
      dom.climbSubvalue.textContent = `power ${guardrailsInfo.can_climb_by_power === undefined ? \"-\" : (guardrailsInfo.can_climb_by_power ? \"ok\" : \"blocked\")} / gate ${(status.climb_power_gate_w ?? guardrailsInfo.climb_power_gate_w ?? 0).toFixed?.(2) ?? \"-\"}W`;
      applyLiveText(dom.decisionCountValue, `${metricsInfo.total_decisions ?? \"-\"}`);
      dom.decisionCountSubvalue.textContent = `errors ${metricsInfo.error_count ?? 0} / avg latency ${(Number(metricsInfo.avg_api_latency) || 0).toFixed(2)}s`;
      applyLiveText(dom.guardrailValue, formatRatio(guardrailsInfo.power_ratio));
      dom.guardrailSubvalue.textContent = `domain ${formatRatio(guardrailsInfo.domain_spread_ratio)} / error ${formatRatio(guardrailsInfo.error_ratio)}`;
    }

    function setupObservers() {
      if (\"IntersectionObserver\" in window) {
        const observer = new IntersectionObserver((entries) => {
          entries.forEach((entry) => {
            if (entry.target.id === \"historyChart\" && entry.isIntersecting) {
              chartVisible = true;
              renderHistoryChart();
            }
            if (entry.isIntersecting) {
              document.querySelectorAll(\"[data-nav]\").forEach((link) => {
                link.classList.toggle(\"active\", link.dataset.nav === entry.target.id);
              });
            }
          });
        }, { threshold: 0.2 });
        document.querySelectorAll(\".section-card\").forEach((section) => observer.observe(section));
        observer.observe(dom.historyChart);
      } else {
        chartVisible = true;
      }
    }

    function setupSearch() {
      dom.search.addEventListener(\"input\", () => {
        const query = dom.search.value.trim().toLowerCase();
        document.querySelectorAll(\".section-card\").forEach((section) => {
          const text = section.textContent.toLowerCase();
          section.classList.toggle(\"hidden\", query && !text.includes(query));
        });
      });
    }

    document.getElementById(\"restartControllerBtn\").onclick = async () => {
      setActionMessage(\"Restarting controller...\");
      try {
        await postAction(\"restart-controller\");
        setActionMessage(\"Controller restart requested.\");
        pushActivity(\"Controller\", \"Controller restart requested from the dashboard.\");
      } catch (error) {
        setActionMessage(error.message, true);
      }
    };

    document.getElementById(\"restartMinerBtn\").onclick = async () => {
      setActionMessage(\"Restarting miner...\");
      try {
        await postAction(\"restart-miner\");
        setActionMessage(\"Miner restart requested. The Bitaxe may be unavailable briefly.\");
        pushActivity(\"Miner\", \"Miner reboot requested from the dashboard.\");
      } catch (error) {
        setActionMessage(error.message, true);
      }
    };

    document.querySelectorAll(\"[data-preset]\").forEach((button) => {
      button.onclick = () => applyPreset(button.dataset.preset);
    });

    dom.refreshSelect.onchange = (event) => {
      refreshIntervalMs = Number(event.target.value);
      scheduleRefresh();
      pushActivity(\"Refresh\", `Auto-refresh set to ${refreshIntervalMs / 1000}s.`);
    };

    dom.pauseRefreshBtn.onclick = () => {
      refreshPaused = !refreshPaused;
      dom.pauseRefreshBtn.textContent = refreshPaused ? \"Resume Refresh\" : \"Pause Refresh\";
      scheduleRefresh();
      pushActivity(\"Refresh\", refreshPaused ? \"Live refresh paused.\" : \"Live refresh resumed.\");
    };

    document.getElementById(\"copyStatusBtn\").onclick = async () => {
      try {
        await navigator.clipboard.writeText(dom.raw.textContent);
        setActionMessage(\"Status JSON copied to clipboard.\");
      } catch (error) {
        setActionMessage(\"Clipboard copy failed.\", true);
      }
    };

    setupObservers();
    setupSearch();
    refresh();
    scheduleRefresh();
  </script>
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
