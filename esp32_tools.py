from __future__ import annotations

import os
import re
import select
import shutil
import subprocess
import time
from pathlib import Path


def app_base_dir() -> Path:
    return Path(__file__).resolve().parent


def nerdminer_root() -> Path | None:
    configured = os.getenv("NERDMINER_ROOT")
    candidates = []
    if configured:
        candidates.append(Path(configured))
    base = app_base_dir()
    candidates.extend([
        base.parent / "NerdMiner_v2",
        base.parent.parent / "GitHub" / "NerdMiner_v2",
        Path.home() / "git" / "NerdMiner_v2",
        Path.home() / "NerdMiner_v2",
    ])
    for candidate in candidates:
        if (candidate / "platformio.ini").exists():
            return candidate
    return None


def platformio_envs(root: Path) -> list[str]:
    text = (root / "platformio.ini").read_text(encoding="utf-8", errors="ignore")
    return re.findall(r"^\[env:([^\]]+)\]", text, flags=re.MULTILINE)


def firmware_bundles(root: Path) -> list[dict]:
    bin_root = root / "bin"
    if not bin_root.exists():
        return []
    bundles = []
    for path in sorted(bin_root.rglob("*.bin")):
        if "flash_download_tool" in str(path).lower():
            continue
        rel = path.relative_to(root)
        bundles.append({
            "id": str(rel).replace("\\", "/"),
            "name": path.stem,
            "path": str(rel).replace("\\", "/"),
            "size": path.stat().st_size,
        })
    return bundles


def firmware_patch_source_dir() -> Path:
    return app_base_dir() / "firmware" / "nerdminer_config_api"


def insert_once(text: str, marker: str, insertion: str, label: str) -> tuple[str, bool]:
    if insertion in text:
        return text, False
    if marker not in text:
        raise ValueError(f"Unable to patch NerdMiner firmware: missing {label}")
    return text.replace(marker, marker + insertion, 1), True


def cpp_string_literal(value: object) -> str:
    text = "" if value is None else str(value)
    escaped = (
        text.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\r", "\\r")
        .replace("\n", "\\n")
        .replace("\t", "\\t")
    )
    return f'"{escaped}"'


def exclude_from_git(root: Path, relative_path: str) -> None:
    exclude_path = root / ".git" / "info" / "exclude"
    if not exclude_path.exists():
        return
    existing = exclude_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    if relative_path not in existing:
        exclude_path.write_text("\n".join([*existing, relative_path]) + "\n", encoding="utf-8")


def nerdminer_config_api_patch_status(root: Path | None = None) -> dict:
    project_root = root or nerdminer_root()
    if not project_root:
        return {"available": False, "installed": False, "message": "NerdMiner_v2 workspace not found."}
    main_path = project_root / "src" / "NerdMinerV2.ino.cpp"
    header_path = project_root / "src" / "config_api.h"
    source_path = project_root / "src" / "config_api.cpp"
    local_header_path = project_root / "src" / "config_api_local.h"
    main_text = main_path.read_text(encoding="utf-8", errors="ignore") if main_path.exists() else ""
    checks = {
        "header": header_path.exists(),
        "source": source_path.exists(),
        "local_defaults": local_header_path.exists(),
        "include": '#include "config_api.h"' in main_text,
        "defaults": "applyConfigApiDefaults();" in main_text,
        "setup": "setupConfigApi();" in main_text,
        "loop": "configApiLoop();" in main_text,
    }
    installed = all(value for key, value in checks.items() if key != "local_defaults")
    return {
        "available": True,
        "installed": installed,
        "root": str(project_root),
        "checks": checks,
        "defaults_header": str(local_header_path) if local_header_path.exists() else "",
        "message": "NerdMiner config API patch is installed." if installed else "NerdMiner config API patch is not installed.",
    }


def apply_nerdminer_config_api_patch(root: Path | None = None) -> dict:
    project_root = root or nerdminer_root()
    if not project_root:
        raise RuntimeError("NerdMiner_v2 workspace not found. Set NERDMINER_ROOT first.")
    source_dir = firmware_patch_source_dir()
    main_path = project_root / "src" / "NerdMinerV2.ino.cpp"
    if not main_path.exists():
        raise RuntimeError(f"{main_path} was not found")
    if not (source_dir / "config_api.cpp").exists():
        raise RuntimeError(f"Patch source missing at {source_dir}")

    changed: list[str] = []
    for name in ("config_api.h", "config_api.cpp"):
        source = source_dir / name
        target = project_root / "src" / name
        new_text = source.read_text(encoding="utf-8")
        old_text = target.read_text(encoding="utf-8") if target.exists() else None
        if old_text != new_text:
            shutil.copyfile(source, target)
            changed.append(str(target.relative_to(project_root)).replace("\\", "/"))

    main_text = main_path.read_text(encoding="utf-8", errors="ignore")
    main_text, did_change = insert_once(main_text, '#include "monitor.h"\n', '#include "config_api.h"\n', "monitor include")
    if did_change:
        changed.append("src/NerdMinerV2.ino.cpp#include")
    main_text, did_change = insert_once(main_text, "  /******** INIT WIFI ************/\n", "  applyConfigApiDefaults();\n", "Wi-Fi init block")
    if did_change:
        changed.append("src/NerdMinerV2.ino.cpp#defaults")
    main_text, did_change = insert_once(main_text, "  init_WifiManager();\n", "\n  setupConfigApi();\n", "init_WifiManager call")
    if did_change:
        changed.append("src/NerdMinerV2.ino.cpp#setup")
    main_text, did_change = insert_once(main_text, "  wifiManagerProcess(); // avoid delays() in loop when non-blocking and other long running code\n", "  configApiLoop();\n", "wifiManagerProcess call")
    if did_change:
        changed.append("src/NerdMinerV2.ino.cpp#loop")
    main_path.write_text(main_text, encoding="utf-8")

    status = nerdminer_config_api_patch_status(project_root)
    status.update({
        "ok": True,
        "changed": changed,
        "message": "NerdMiner config API patch installed. Rebuild and flash the firmware for it to run on the ESP32." if changed else "NerdMiner config API patch was already installed.",
    })
    return status


def write_nerdminer_firmware_defaults(values: dict, root: Path | None = None) -> dict:
    project_root = root or nerdminer_root()
    if not project_root:
        raise RuntimeError("NerdMiner_v2 workspace not found. Set NERDMINER_ROOT first.")
    src_dir = project_root / "src"
    if not src_dir.exists():
        raise RuntimeError(f"{src_dir} was not found")

    header_path = src_dir / "config_api_local.h"
    pool_port = int(values.get("PoolPort") or 21496)
    timezone = int(values.get("Timezone") or 2)
    save_stats = str(bool(values.get("SaveStats"))).lower()
    text = "\n".join([
        "#ifndef NERDMINER_CONFIG_API_LOCAL_H",
        "#define NERDMINER_CONFIG_API_LOCAL_H",
        "",
        "// Generated by Bitaxe Agent. Keep this file private; it may contain Wi-Fi and wallet settings.",
        f"#define CONFIG_API_WIFI_SSID {cpp_string_literal(values.get('SSID') or '')}",
        f"#define CONFIG_API_WIFI_PASSWORD {cpp_string_literal(values.get('WifiPW') or '')}",
        f"#define CONFIG_API_POOL_URL {cpp_string_literal(values.get('PoolUrl') or 'public-pool.io')}",
        f"#define CONFIG_API_POOL_PORT {pool_port}",
        f"#define CONFIG_API_POOL_PASSWORD {cpp_string_literal(values.get('PoolPassword') or 'x')}",
        f"#define CONFIG_API_WALLET {cpp_string_literal(values.get('BtcWallet') or '')}",
        f"#define CONFIG_API_TIMEZONE {timezone}",
        f"#define CONFIG_API_SAVE_STATS {save_stats}",
        "#define CONFIG_API_FORCE_DEFAULTS false",
        "",
        "#endif",
        "",
    ])
    changed = header_path.read_text(encoding="utf-8", errors="ignore") != text if header_path.exists() else True
    header_path.write_text(text, encoding="utf-8")
    exclude_from_git(project_root, "src/config_api_local.h")

    status = nerdminer_config_api_patch_status(project_root)
    status.update({
        "ok": True,
        "changed": ["src/config_api_local.h"] if changed else [],
        "defaults_header": str(header_path),
        "message": "Firmware defaults written. Rebuild and flash NerdMiner_v2 once so the ESP32 can join Wi-Fi and expose the dashboard API.",
    })
    return status


def serial_ports() -> list[dict]:
    if os.name == "nt":
        script = "[System.IO.Ports.SerialPort]::GetPortNames() | ConvertTo-Json"
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", script],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        ports = []
        for line in result.stdout.replace("[", "").replace("]", "").replace('"', "").split(","):
            port = line.strip()
            if port:
                ports.append({"device": port, "name": port})
        return ports
    dev = Path("/dev")
    prefixes = ("ttyUSB", "ttyACM", "cu.usbserial", "cu.SLAB", "cu.wchusbserial")
    if not dev.exists():
        return []
    return [
        {"device": f"/dev/{entry.name}", "name": entry.name}
        for entry in dev.iterdir()
        if entry.name.startswith(prefixes)
    ]


def default_serial_port() -> str:
    configured = os.getenv("NERDMINER_SERIAL_PORT", "").strip()
    if configured:
        return configured
    ports = serial_ports()
    return str(ports[0]["device"]) if ports else ""


def is_allowed_serial_device(device: str) -> bool:
    configured = os.getenv("NERDMINER_SERIAL_PORT", "").strip()
    if configured and device == configured:
        return True
    if os.name == "nt":
        return bool(re.fullmatch(r"COM\d+", device, flags=re.IGNORECASE))
    path = Path(device)
    return str(path).startswith("/dev/") and path.name.startswith(("ttyUSB", "ttyACM", "cu.usbserial", "cu.SLAB", "cu.wchusbserial"))


def read_serial_log(port: str | None = None, baud: int = 115200, seconds: float = 3.0, max_bytes: int = 32768) -> dict:
    device = (port or default_serial_port()).strip()
    if not device:
        return {
            "ok": False,
            "service": "nerdminer",
            "unit": "serial",
            "port": "",
            "lines": [],
            "message": "No ESP32 serial port detected. Connect the miner by USB or set NERDMINER_SERIAL_PORT.",
        }
    if not is_allowed_serial_device(device):
        return {
            "ok": False,
            "service": "nerdminer",
            "unit": "serial",
            "port": device,
            "lines": [],
            "message": f"{device} is not an allowed ESP32 serial device. Use a detected USB serial port or NERDMINER_SERIAL_PORT.",
        }
    if os.name == "nt":
        return {
            "ok": False,
            "service": "nerdminer",
            "unit": "serial",
            "port": device,
            "lines": [],
            "message": "Serial capture from the dashboard is currently supported on Linux services.",
        }

    try:
        import fcntl
        import termios
        import tty
    except ImportError:
        return {
            "ok": False,
            "service": "nerdminer",
            "unit": "serial",
            "port": device,
            "lines": [],
            "message": "Serial capture is unavailable on this platform.",
        }

    chunks: list[bytes] = []
    fd = None
    old_attrs = None
    try:
        fd = os.open(device, os.O_RDONLY | os.O_NOCTTY | os.O_NONBLOCK)
        old_attrs = termios.tcgetattr(fd)
        tty.setraw(fd)
        attrs = termios.tcgetattr(fd)
        speed = getattr(termios, f"B{int(baud)}", termios.B115200)
        attrs[2] = attrs[2] | termios.CLOCAL | termios.CREAD
        attrs[4] = speed
        attrs[5] = speed
        termios.tcsetattr(fd, termios.TCSANOW, attrs)
        flags = fcntl.fcntl(fd, fcntl.F_GETFL)
        fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

        deadline = time.monotonic() + max(0.5, min(float(seconds), 10.0))
        total = 0
        while time.monotonic() < deadline and total < max_bytes:
            readable, _, _ = select.select([fd], [], [], 0.2)
            if not readable:
                continue
            try:
                chunk = os.read(fd, min(4096, max_bytes - total))
            except BlockingIOError:
                continue
            if not chunk:
                continue
            chunks.append(chunk)
            total += len(chunk)
    except PermissionError:
        return {
            "ok": False,
            "service": "nerdminer",
            "unit": "serial",
            "port": device,
            "lines": [],
            "message": f"Permission denied for {device}. Add the service user to the dialout group, then restart the UI service.",
        }
    except OSError as exc:
        return {
            "ok": False,
            "service": "nerdminer",
            "unit": "serial",
            "port": device,
            "lines": [],
            "message": f"Unable to read {device}: {exc}",
        }
    finally:
        if fd is not None:
            try:
                if old_attrs is not None:
                    termios.tcsetattr(fd, termios.TCSANOW, old_attrs)
            finally:
                os.close(fd)

    text = b"".join(chunks).decode("utf-8", errors="replace").replace("\r\n", "\n").replace("\r", "\n")
    lines = [line for line in text.splitlines() if line.strip()]
    return {
        "ok": True,
        "service": "nerdminer",
        "unit": "serial",
        "port": device,
        "lines": lines,
        "message": f"Captured {len(lines)} serial log line(s) from {device}." if lines else f"No serial output captured from {device}. Try pressing reset on the ESP32, or close picocom if it is already using the port.",
    }


def tool_available(command: str) -> bool:
    executable = "where.exe" if os.name == "nt" else "which"
    result = subprocess.run([executable, command], capture_output=True, text=True, check=False, timeout=3)
    return result.returncode == 0


def esp32_status() -> dict:
    root = nerdminer_root()
    if not root:
        return {
            "available": False,
            "message": "NerdMiner_v2 workspace not found. Set NERDMINER_ROOT to enable ESP32 firmware tools.",
            "ports": serial_ports(),
            "envs": [],
            "firmware_bundles": [],
            "config_api_patch": {"available": False, "installed": False, "message": "NerdMiner_v2 workspace not found."},
            "tools": {"platformio": tool_available("platformio") or tool_available("pio"), "esptool": tool_available("esptool")},
        }
    return {
        "available": True,
        "root": str(root),
        "message": "NerdMiner_v2 workspace detected.",
        "ports": serial_ports(),
        "envs": platformio_envs(root),
        "firmware_bundles": firmware_bundles(root),
        "config_api_patch": nerdminer_config_api_patch_status(root),
        "tools": {"platformio": tool_available("platformio") or tool_available("pio"), "esptool": tool_available("esptool")},
    }
