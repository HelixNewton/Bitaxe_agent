from __future__ import annotations

import os
import re
import select
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
            "tools": {"platformio": tool_available("platformio") or tool_available("pio"), "esptool": tool_available("esptool")},
        }
    return {
        "available": True,
        "root": str(root),
        "message": "NerdMiner_v2 workspace detected.",
        "ports": serial_ports(),
        "envs": platformio_envs(root),
        "firmware_bundles": firmware_bundles(root),
        "tools": {"platformio": tool_available("platformio") or tool_available("pio"), "esptool": tool_available("esptool")},
    }
