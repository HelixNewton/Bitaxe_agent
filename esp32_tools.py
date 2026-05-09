from __future__ import annotations

import os
import re
import subprocess
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
