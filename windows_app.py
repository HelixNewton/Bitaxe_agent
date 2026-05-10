#!/usr/bin/env python3
import argparse
import ctypes
import ctypes.wintypes
import os
import sys
import threading
import time
import webbrowser
from pathlib import Path

WM_DESTROY = 0x0002
WM_COMMAND = 0x0111
WM_APP = 0x8000
WM_RBUTTONUP = 0x0205
WM_LBUTTONDBLCLK = 0x0203
NIM_ADD = 0x00000000
NIM_DELETE = 0x00000002
NIF_MESSAGE = 0x00000001
NIF_ICON = 0x00000002
NIF_TIP = 0x00000004
IDI_APPLICATION = 32512
IDC_ARROW = 32512
IMAGE_ICON = 1
LR_DEFAULTSIZE = 0x00000040
LR_SHARED = 0x00008000
TPM_LEFTALIGN = 0x0000
TPM_BOTTOMALIGN = 0x0020
TPM_RIGHTBUTTON = 0x0002
CS_HREDRAW = 0x0002
CS_VREDRAW = 0x0001
CW_USEDEFAULT = 0x80000000
WS_OVERLAPPED = 0x00000000
MF_STRING = 0x00000000
MF_SEPARATOR = 0x00000800
IDI_TRAY_OPEN = 1001
IDI_TRAY_EXIT = 1002
TRAY_CALLBACK = WM_APP + 1


def app_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def resource_base_dir() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return app_base_dir()


def startup_log(message: str) -> None:
    try:
        path = app_base_dir() / "startup.log"
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        with path.open("a", encoding="utf-8") as handle:
            handle.write(f"{timestamp} {message}\n")
    except OSError:
        pass


def dashboard_url() -> str:
    host = os.getenv("BITAXE_UI_HOST") or os.getenv("MINER_UI_HOST", "127.0.0.1")
    port = os.getenv("BITAXE_UI_PORT") or os.getenv("MINER_UI_PORT", "8787")
    if host == "0.0.0.0":
        host = "127.0.0.1"
    return f"http://{host}:{port}/"


def load_env_file() -> None:
    env_path = app_base_dir() / ".env"
    startup_log(f"base_dir={app_base_dir()} resource_dir={resource_base_dir()} env={env_path}")
    if not env_path.exists():
        sample = resource_base_dir() / "windows.env.example"
        startup_log(f"env_missing sample={sample} sample_exists={sample.exists()}")
        if sample.exists():
            env_path.write_text(sample.read_text(encoding="utf-8"), encoding="utf-8")
            startup_log("created_env_from_sample")
    if not env_path.exists():
        startup_log("env_not_found_after_bootstrap")
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if not line or line.lstrip().startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ[key.strip()] = value.strip()
    startup_log("env_loaded")


def run_controller() -> None:
    from controller import Config, Controller

    try:
        controller = Controller(Config.from_env())
        controller.run()
    except Exception as exc:
        startup_log(f"controller thread crashed: {type(exc).__name__}: {exc}")
        raise


def run_ui() -> None:
    from ui_server import create_server

    try:
        server = create_server()
        server.serve_forever()
    except Exception as exc:
        startup_log(f"ui thread crashed: {type(exc).__name__}: {exc}")
        raise


class WindowsTrayApp:
    def __init__(self, open_browser: bool = True):
        self.user32 = ctypes.windll.user32
        self.shell32 = ctypes.windll.shell32
        self.kernel32 = ctypes.windll.kernel32
        self.instance = self.kernel32.GetModuleHandleW(None)
        self.class_name = "BitaxeAgentTrayWindow"
        self.hwnd = None
        self.open_browser = open_browser

    def open_dashboard(self) -> None:
        webbrowser.open(dashboard_url())

    def exit_app(self) -> None:
        if self.hwnd:
            self._delete_tray_icon()
        os._exit(0)

    def _wndproc(self, hwnd, msg, wparam, lparam):
        if msg == WM_COMMAND:
            command = wparam & 0xFFFF
            if command == IDI_TRAY_OPEN:
                self.open_dashboard()
                return 0
            if command == IDI_TRAY_EXIT:
                self.exit_app()
                return 0
        elif msg == TRAY_CALLBACK:
            if lparam == WM_LBUTTONDBLCLK:
                self.open_dashboard()
                return 0
            if lparam == WM_RBUTTONUP:
                self._show_menu()
                return 0
        elif msg == WM_DESTROY:
            self._delete_tray_icon()
            self.user32.PostQuitMessage(0)
            return 0
        return self.user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _show_menu(self) -> None:
        menu = self.user32.CreatePopupMenu()
        self.user32.AppendMenuW(menu, MF_STRING, IDI_TRAY_OPEN, "Open Dashboard")
        self.user32.AppendMenuW(menu, MF_SEPARATOR, 0, None)
        self.user32.AppendMenuW(menu, MF_STRING, IDI_TRAY_EXIT, "Exit")
        point = ctypes.wintypes.POINT()
        self.user32.GetCursorPos(ctypes.byref(point))
        self.user32.SetForegroundWindow(self.hwnd)
        self.user32.TrackPopupMenu(
            menu,
            TPM_LEFTALIGN | TPM_BOTTOMALIGN | TPM_RIGHTBUTTON,
            point.x,
            point.y,
            0,
            self.hwnd,
            None,
        )
        self.user32.DestroyMenu(menu)

    def _register_window(self):
        WNDPROCTYPE = ctypes.WINFUNCTYPE(
            ctypes.c_long,
            ctypes.c_void_p,
            ctypes.c_uint,
            ctypes.c_size_t,
            ctypes.c_ssize_t,
        )
        self._wndproc_ref = WNDPROCTYPE(self._wndproc)

        class WNDCLASS(ctypes.Structure):
            _fields_ = [
                ("style", ctypes.c_uint),
                ("lpfnWndProc", WNDPROCTYPE),
                ("cbClsExtra", ctypes.c_int),
                ("cbWndExtra", ctypes.c_int),
                ("hInstance", ctypes.c_void_p),
                ("hIcon", ctypes.c_void_p),
                ("hCursor", ctypes.c_void_p),
                ("hbrBackground", ctypes.c_void_p),
                ("lpszMenuName", ctypes.c_wchar_p),
                ("lpszClassName", ctypes.c_wchar_p),
            ]

        icon = self.user32.LoadIconW(None, ctypes.c_wchar_p(IDI_APPLICATION))
        cursor = self.user32.LoadCursorW(None, ctypes.c_wchar_p(IDC_ARROW))
        wndclass = WNDCLASS()
        wndclass.style = CS_HREDRAW | CS_VREDRAW
        wndclass.lpfnWndProc = self._wndproc_ref
        wndclass.cbClsExtra = 0
        wndclass.cbWndExtra = 0
        wndclass.hInstance = self.instance
        wndclass.hIcon = icon
        wndclass.hCursor = cursor
        wndclass.hbrBackground = None
        wndclass.lpszMenuName = None
        wndclass.lpszClassName = self.class_name
        self.user32.RegisterClassW(ctypes.byref(wndclass))

    def _create_window(self):
        self.hwnd = self.user32.CreateWindowExW(
            0,
            self.class_name,
            "Bitaxe Agent",
            WS_OVERLAPPED,
            CW_USEDEFAULT,
            CW_USEDEFAULT,
            CW_USEDEFAULT,
            CW_USEDEFAULT,
            None,
            None,
            self.instance,
            None,
        )

    def _add_tray_icon(self):
        class NOTIFYICONDATA(ctypes.Structure):
            _fields_ = [
                ("cbSize", ctypes.c_uint),
                ("hWnd", ctypes.c_void_p),
                ("uID", ctypes.c_uint),
                ("uFlags", ctypes.c_uint),
                ("uCallbackMessage", ctypes.c_uint),
                ("hIcon", ctypes.c_void_p),
                ("szTip", ctypes.c_wchar * 128),
            ]

        icon = self.user32.LoadImageW(
            None,
            ctypes.c_wchar_p(IDI_APPLICATION),
            IMAGE_ICON,
            0,
            0,
            LR_DEFAULTSIZE | LR_SHARED,
        )
        data = NOTIFYICONDATA()
        data.cbSize = ctypes.sizeof(NOTIFYICONDATA)
        data.hWnd = self.hwnd
        data.uID = 1
        data.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
        data.uCallbackMessage = TRAY_CALLBACK
        data.hIcon = icon
        data.szTip = "Bitaxe Agent"
        self._tray_data = data
        self.shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(self._tray_data))

    def _delete_tray_icon(self):
        if hasattr(self, "_tray_data"):
            self.shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(self._tray_data))

    def run(self) -> int:
        self._register_window()
        self._create_window()
        self._add_tray_icon()
        if self.open_browser:
            self.open_dashboard()
        msg = ctypes.wintypes.MSG()
        while self.user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
            self.user32.TranslateMessage(ctypes.byref(msg))
            self.user32.DispatchMessageW(ctypes.byref(msg))
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Bitaxe Agent Windows application")
    parser.add_argument("--no-browser", action="store_true", help="do not open the dashboard automatically")
    args = parser.parse_args()
    load_env_file()

    controller_thread = threading.Thread(target=run_controller, name="bitaxe-controller", daemon=True)
    ui_thread = threading.Thread(target=run_ui, name="bitaxe-ui", daemon=True)
    controller_thread.start()
    ui_thread.start()

    time.sleep(2)
    if os.name == "nt":
        tray = WindowsTrayApp(open_browser=not args.no_browser)
        return tray.run()

    if not args.no_browser:
        webbrowser.open(dashboard_url())

    try:
        while True:
            if not controller_thread.is_alive():
                raise SystemExit("controller thread stopped")
            if not ui_thread.is_alive():
                raise SystemExit("ui thread stopped")
            time.sleep(1)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
