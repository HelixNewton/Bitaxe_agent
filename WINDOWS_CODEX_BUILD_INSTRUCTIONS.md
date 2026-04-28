# Windows Codex Build Instructions

Use this file as the handoff prompt/instructions for Codex running on a Windows machine. The goal is to build a working `bitaxe-agent.exe` from this project and verify it can run safely.

## Project Summary

This project controls a Bitaxe miner through AxeOS HTTP APIs and serves a local dashboard.

Core files:

- `controller.py`: standard live controller used by the current Linux service.
- `deepseek_python_controller.py`: advanced controller with health, metrics, Prometheus, circuit breakers, richer guardrails, and OpenAI structured-output handling.
- `ui_server.py`: local dashboard and config editor.
- `windows_app.py`: Windows tray launcher. It starts the controller and dashboard in one process.
- `windows.env.example`: Windows `.env` template.
- `bitaxe-agent.spec`: PyInstaller build spec.
- `build_windows.bat`: Windows build command.
- `assets/`: dashboard CSS/assets.

Important: do not run two controllers against the same Bitaxe at the same time.

## Current Packaging Behavior

As written, `windows_app.py` imports:

```python
from controller import Config, Controller
```

That means the Windows `.exe` currently packages and runs the standard controller, not `deepseek_python_controller.py`.

If the requested Windows build should use the advanced controller, update `windows_app.py` to import from `deepseek_python_controller.py` instead:

```python
from deepseek_python_controller import Config, Controller
```

Also update `bitaxe-agent.spec` hidden imports/data only if PyInstaller misses optional modules. Normally the Python imports should be discovered automatically.

## Recommended Build Choice

For a conservative first `.exe`, use the standard controller:

```python
from controller import Config, Controller
```

For the advanced `.exe`, use:

```python
from deepseek_python_controller import Config, Controller
```

The advanced controller expects these optional Python packages if advanced features are enabled:

```bat
python -m pip install prometheus-client tenacity
```

It still runs without them because the imports have fallbacks, but install them for the intended advanced build.

## Safety Requirements

Before building or testing:

1. Keep `BITAXE_DRY_RUN=true` for the first run.
2. Confirm `BITAXE_URL` points to the intended miner.
3. Confirm only one controller process is running.
4. Do not expose the dashboard to the public internet.
5. Do not hardcode API keys into source files.
6. If OpenAI is used, put the key in `.env`, not in code.

Recommended Windows `.env` first-run values:

```env
BITAXE_URL=http://192.168.1.50
BITAXE_MODE=openai
BITAXE_DRY_RUN=true
BITAXE_AUTO_FAN=true
BITAXE_LOOP_SECONDS=15

BITAXE_MIN_FREQUENCY=500
BITAXE_MAX_FREQUENCY=625
BITAXE_ABSOLUTE_MAX_FREQUENCY=625
BITAXE_FREQ_STEP=5

BITAXE_MIN_VOLTAGE=980
BITAXE_MAX_VOLTAGE=1125
BITAXE_ABSOLUTE_MAX_VOLTAGE=1150
BITAXE_VOLTAGE_STEP=5

BITAXE_TARGET_TEMP_C=65
BITAXE_HOT_TEMP_C=69
BITAXE_EMERGENCY_TEMP_C=70
BITAXE_ABSOLUTE_MAX_EMERGENCY_TEMP_C=70
BITAXE_COOL_TEMP_C=64
BITAXE_MAX_VR_TEMP_C=70
BITAXE_ABSOLUTE_MAX_VR_TEMP_C=75

BITAXE_MIN_INPUT_VOLTAGE_MV=4800
BITAXE_MAX_POWER_W=17.5
BITAXE_ABSOLUTE_MAX_POWER_W=18
BITAXE_CLIMB_POWER_RATIO=0.97

BITAXE_MIN_FAN_PERCENT=60
BITAXE_MAX_FAN_PERCENT=100
BITAXE_STEP_COOLDOWN_SECONDS=120

BITAXE_MAX_ERROR_PERCENTAGE=25
BITAXE_MAX_DOMAIN_SPREAD_PERCENTAGE=9
BITAXE_CRITICAL_DOMAIN_SPREAD_PERCENTAGE=16
BITAXE_DOMAIN_SPREAD_POLLS=2

BITAXE_LEARNING_ENABLED=true
BITAXE_LEARNING_MIN_SAMPLES=3
BITAXE_LEARNING_BAD_LIMIT=2
BITAXE_LEARNING_RESTORE_MARGIN=0.03
BITAXE_LEARNING_EFFICIENCY_WEIGHT=0.25

BITAXE_ADAPTIVE_COOLDOWN_ENABLED=true
BITAXE_ADAPTIVE_MIN_COOLDOWN_SECONDS=45
BITAXE_ADAPTIVE_MAX_COOLDOWN_SECONDS=300
BITAXE_ADAPTIVE_STABLE_SAMPLES=8

BITAXE_STATUS_FILE=status.json
BITAXE_LEARNING_FILE=learning.json
BITAXE_UI_HOST=127.0.0.1
BITAXE_UI_PORT=8787

AI_MODEL=gpt-4.1-mini
# Add your OpenAI API key only in your private .env file.
```

If not using OpenAI, set:

```env
BITAXE_MODE=rules
```

and omit `OPENAI_API_KEY`.

## Windows Build Steps

Run these commands in PowerShell or Command Prompt from the project folder.

1. Create and activate a virtual environment:

```bat
python -m venv .venv
.venv\Scripts\activate
```

2. Install build/runtime dependencies:

```bat
python -m pip install --upgrade pip
python -m pip install pyinstaller prometheus-client tenacity
```

3. Create `.env` if missing:

```bat
copy windows.env.example .env
```

4. Edit `.env`:

```bat
notepad .env
```

Set at minimum:

```env
BITAXE_URL=http://YOUR_BITAXE_IP
BITAXE_DRY_RUN=true
```

5. Run without packaging first:

```bat
python windows_app.py
```

Open:

```text
http://127.0.0.1:8787/
```

Verify:

- Dashboard loads.
- `status.json` is created.
- The miner telemetry appears.
- Dry-run is shown as enabled.
- No unexpected frequency/voltage write occurs.

6. Stop the app from the tray icon.

7. Build the `.exe`:

```bat
build_windows.bat
```

Expected output:

```text
dist\bitaxe-agent.exe
```

8. Run the built `.exe`:

```bat
dist\bitaxe-agent.exe
```

Verify again:

- Tray icon appears.
- Double-click opens dashboard.
- `status.json` updates beside the `.exe`.
- `.env` is read from beside the `.exe`.

## PyInstaller Notes

The current spec uses:

```python
Analysis(["windows_app.py"], ...)
```

It includes:

```python
datas=[
    ("windows.env.example", "."),
    ("WINDOWS.md", "."),
    ("WINDOWS_INSTRUCTIONS.txt", "."),
    ("assets", "assets"),
]
```

If building the advanced controller and PyInstaller misses optional modules, add hidden imports:

```python
hiddenimports=[
    "prometheus_client",
    "tenacity",
]
```

Only add this if the generated `.exe` fails at runtime due to missing modules.

## Advanced Controller Verification

If `windows_app.py` was switched to `deepseek_python_controller`, verify `status.json` contains these advanced fields:

```json
{
  "health": {},
  "metrics": {},
  "guardrails": {},
  "performance_metrics": {}
}
```

The dashboard has been updated to display these fields when present, while still working with standard `controller.py`.

## Release Checklist

Before sharing the `.exe`:

1. Remove any real `OPENAI_API_KEY` from packaged sample files.
2. Keep only placeholder keys in templates.
3. Confirm `.env` is not embedded with secrets.
4. Confirm `BITAXE_DRY_RUN=true` in `windows.env.example`.
5. Confirm the app starts from `dist\bitaxe-agent.exe`.
6. Confirm the dashboard opens at `http://127.0.0.1:8787/`.
7. Confirm `Exit` from tray closes both controller and dashboard threads.

## Troubleshooting

If the `.exe` starts but dashboard does not open:

- Check whether port `8787` is already in use.
- Set another port in `.env`:

```env
BITAXE_UI_PORT=8788
```

If telemetry does not load:

- Confirm `BITAXE_URL`.
- Open `http://YOUR_BITAXE_IP/api/system/info` in a browser.
- Keep `BITAXE_DRY_RUN=true` until telemetry works.

If OpenAI decisions fail:

- Confirm `OPENAI_API_KEY`.
- Confirm `AI_MODEL`.
- Switch temporarily to:

```env
BITAXE_MODE=rules
```

If PyInstaller fails:

- Rebuild in a clean virtual environment.
- Run:

```bat
python -m PyInstaller --clean --noconfirm bitaxe-agent.spec
```

If the advanced controller crashes due to missing modules:

```bat
python -m pip install prometheus-client tenacity
```

then rebuild.
