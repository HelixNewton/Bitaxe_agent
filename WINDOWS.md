# Windows App

This is the separate Windows launcher for Bitaxe Agent. It runs the controller loop and the dashboard in one local application process.

Files:

- `windows_app.py`: Windows launcher
- `windows.env.example`: Windows-local config template
- `bitaxe-agent.spec`: PyInstaller spec
- `build_windows.bat`: build script

## What Changed

The Windows app now matches the current Linux project behavior more closely:

- it loads `.env` automatically on startup
- if `.env` does not exist, it creates it from `windows.env.example`
- the packaged `.exe` now runs without a console window
- on Windows, the app now lives in the system tray
- the tray supports `Open Dashboard` and `Exit`
- it uses the current shared dashboard with:
  - domain instability alerting
  - domain guard status badge
  - preset status detection
  - controller restart and miner restart actions
  - current guardrail config editing

## Customize the Bitaxe IP

The Windows app reads `BITAXE_URL` from `.env`.

First run:

1. Copy `windows.env.example` to `.env`
2. Set `BITAXE_URL`, for example:

```env
BITAXE_URL=http://192.168.1.50
```

You can also change `BITAXE_URL` from the dashboard UI.

## Current Windows Guardrails

The Windows template includes the current stability rails:

```env
BITAXE_MAX_ERROR_PERCENTAGE=20
BITAXE_MAX_DOMAIN_SPREAD_PERCENTAGE=10
BITAXE_CRITICAL_DOMAIN_SPREAD_PERCENTAGE=18
BITAXE_DOMAIN_SPREAD_POLLS=2
```

That means the Windows app will use the same domain-spread rollback logic as the current Linux controller.

## Run Without Packaging

```bat
copy windows.env.example .env
python windows_app.py
```

Then open:

```text
http://127.0.0.1:8787/
```

## Build EXE On Windows

On a Windows machine with Python and PyInstaller installed:

```bat
build_windows.bat
```

That produces:

```text
dist\bitaxe-agent.exe
```

## Notes

- The `.exe` must be built on Windows for a real Windows executable.
- The app writes runtime state to `status.json` beside the executable.
- The dashboard and controller run inside the same Windows application process.
- The packaged build also includes `WINDOWS.md` and `WINDOWS_INSTRUCTIONS.txt`.
- Double-click the tray icon to open the dashboard.
- Right-click the tray icon for `Open Dashboard` and `Exit`.
