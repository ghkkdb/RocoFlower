"""
窗口操作工具模块
提供窗口位置修改、分辨率调整等功能
"""

import win32gui
import win32con
import win32api
import win32process
import win32ui
import ctypes
import cv2
import numpy as np
import random
import sys
import time
from pathlib import Path
import threading
from typing import Callable, Dict, Optional, Tuple, Union


def get_app_dir() -> Path:
    try:
        buf = ctypes.create_unicode_buffer(260)
        ctypes.windll.kernel32.GetModuleFileNameW(None, buf, 260)
        exe_path = Path(buf.value)
        if exe_path.exists():
            return exe_path.parent
    except Exception:
        pass
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def _iter_resource_base_dirs() -> list[Path]:
    seen = set()
    base_dirs: list[Path] = []

    def add_dir(path_like) -> None:
        if not path_like:
            return
        try:
            path = Path(path_like).expanduser().resolve()
        except Exception:
            return
        key = str(path).lower()
        if key in seen:
            return
        seen.add(key)
        base_dirs.append(path)

    # Onefile resources live next to module __file__ after extraction.
    add_dir(Path(__file__).resolve().parent)

    main_module = sys.modules.get("__main__")
    if getattr(main_module, "__file__", None):
        add_dir(Path(main_module.__file__).resolve().parent)

    add_dir(Path.cwd())
    if sys.argv:
        add_dir(Path(sys.argv[0]).resolve().parent)
    if getattr(sys, "executable", None):
        add_dir(Path(sys.executable).resolve().parent)
    add_dir(get_app_dir())

    return base_dirs


def get_resource_search_paths(path_like: Union[str, Path]) -> list[Path]:
    path = Path(path_like).expanduser()
    if path.is_absolute():
        return [path]
    return [base_dir / path for base_dir in _iter_resource_base_dirs()]


def resolve_resource_path(path_like: Union[str, Path]) -> Path:
    path = Path(path_like).expanduser()
    if path.is_absolute():
        return path

    candidates = get_resource_search_paths(path)
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    return candidates[0].resolve()


def get_window_rect(hwnd: int) -> Optional[Tuple[int, int, int, int]]:
    """
    获取窗口的位置和大小信息。

    Args:
        hwnd (int): 窗口句柄

    Returns:
        Optional[Tuple[int, int, int, int]]: 返回 (left, top, right, bottom) 元组，
            失败返回 None
    """
    try:
        return win32gui.GetWindowRect(hwnd)
    except Exception as e:
        print(f"获取窗口矩形失败: {e}")
        return None


def set_window_position(hwnd: int, x: int, y: int) -> bool:
    """
    设置窗口位置（不改变大小）。

    Args:
        hwnd (int): 窗口句柄
        x (int): 目标 X 坐标
        y (int): 目标 Y 坐标

    Returns:
        bool: 成功返回 True，失败返回 False
    """
    try:
        rect = win32gui.GetWindowRect(hwnd)
        if rect is None:
            return False
        left, top, right, bottom = rect
        width = right - left
        height = bottom - top
        win32gui.SetWindowPos(
            hwnd,
            win32con.HWND_TOP,
            x, y,
            width, height,
            win32con.SWP_NOZORDER
        )
        return True
    except Exception as e:
        print(f"设置窗口位置失败: {e}")
        return False


def set_window_size(hwnd: int, width: int, height: int) -> bool:
    """
    设置窗口大小（分辨率），不改变位置。

    Args:
        hwnd (int): 窗口句柄
        width (int): 目标宽度（像素）
        height (int): 目标高度（像素）

    Returns:
        bool: 成功返回 True，失败返回 False
    """
    try:
        rect = win32gui.GetWindowRect(hwnd)
        if rect is None:
            return False
        left, top, _, _ = rect
        win32gui.SetWindowPos(
            hwnd,
            win32con.HWND_TOP,
            left, top,
            width, height,
            win32con.SWP_NOZORDER
        )
        return True
    except Exception as e:
        print(f"设置窗口大小失败: {e}")
        return False


def set_window_rect(hwnd: int, x: int, y: int, width: int, height: int) -> bool:
    """
    同时设置窗口位置和大小（分辨率）。

    Args:
        hwnd (int): 窗口句柄
        x (int): 目标 X 坐标
        y (int): 目标 Y 坐标
        width (int): 目标宽度（像素）
        height (int): 目标高度（像素）

    Returns:
        bool: 成功返回 True，失败返回 False
    """
    try:
        win32gui.SetWindowPos(
            hwnd,
            win32con.HWND_TOP,
            x, y,
            width, height,
            win32con.SWP_NOZORDER
        )
        return True
    except Exception as e:
        print(f"设置窗口位置和大小失败: {e}")
        return False


def move_window(hwnd: int, x: int, y: int, width: int, height: int, repaint: bool = True) -> bool:
    """
    移动窗口并设置大小（使用 MoveWindow API）。

    Args:
        hwnd (int): 窗口句柄
        x (int): 目标 X 坐标
        y (int): 目标 Y 坐标
        width (int): 目标宽度（像素）
        height (int): 目标高度（像素）
        repaint (bool): 是否重绘窗口，默认 True

    Returns:
        bool: 成功返回 True，失败返回 False
    """
    try:
        win32gui.MoveWindow(hwnd, x, y, width, height, repaint)
        return True
    except Exception as e:
        print(f"移动窗口失败: {e}")
        return False


def find_window_by_title(title: str) -> Optional[int]:
    """
    根据窗口标题查找窗口句柄。

    Args:
        title (str): 窗口标题（支持部分匹配）

    Returns:
        Optional[int]: 找到返回窗口句柄，未找到返回 None
    """
    try:
        hwnd = win32gui.FindWindow(None, title)
        if hwnd:
            return hwnd

        result = [None]

        def enum_callback(handle, _):
            if win32gui.IsWindowVisible(handle):
                window_title = win32gui.GetWindowText(handle)
                if title.lower() in window_title.lower():
                    result[0] = handle
                    return False
            return True

        win32gui.EnumWindows(enum_callback, None)
        return result[0]
    except Exception as e:
        print(f"查找窗口失败: {e}")
        return None


def get_window_title(hwnd: int) -> Optional[str]:
    """
    获取窗口标题。

    Args:
        hwnd (int): 窗口句柄

    Returns:
        Optional[str]: 窗口标题，失败返回 None
    """
    try:
        return win32gui.GetWindowText(hwnd)
    except Exception as e:
        print(f"获取窗口标题失败: {e}")
        return None


def center_window(hwnd: int, screen_width: Optional[int] = None, screen_height: Optional[int] = None) -> bool:
    """
    将窗口居中显示。

    Args:
        hwnd (int): 窗口句柄
        screen_width (Optional[int]): 屏幕宽度，不指定则使用主显示器分辨率
        screen_height (Optional[int]): 屏幕高度，不指定则使用主显示器分辨率

    Returns:
        bool: 成功返回 True，失败返回 False
    """
    try:
        import win32api

        rect = win32gui.GetWindowRect(hwnd)
        if rect is None:
            return False

        left, top, right, bottom = rect
        window_width = right - left
        window_height = bottom - top

        if screen_width is None or screen_height is None:
            screen_width = win32api.GetSystemMetrics(win32con.SM_CXSCREEN)
            screen_height = win32api.GetSystemMetrics(win32con.SM_CYSCREEN)

        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2

        return set_window_position(hwnd, x, y)
    except Exception as e:
        print(f"窗口居中失败: {e}")
        return False


def is_window_active(hwnd: int) -> bool:
    """
    判断窗口是否为当前前台激活窗口。

    Args:
        hwnd (int): 窗口句柄

    Returns:
        bool: 是前台窗口返回 True，否则返回 False
    """
    try:
        foreground_hwnd = win32gui.GetForegroundWindow()
        return foreground_hwnd == hwnd
    except Exception as e:
        print(f"判断窗口激活状态失败: {e}")
        return False


def is_window_topmost(hwnd: int) -> bool:
    """
    判断窗口是否置顶。

    Args:
        hwnd (int): 窗口句柄

    Returns:
        bool: 置顶返回 True，否则返回 False
    """
    try:
        ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        return bool(ex_style & win32con.WS_EX_TOPMOST)
    except Exception as e:
        print(f"判断窗口置顶状态失败: {e}")
        return False


def set_window_topmost(hwnd: int, topmost: bool = True) -> bool:
    """
    设置窗口是否置顶。

    Args:
        hwnd (int): 窗口句柄
        topmost (bool): True 为置顶，False 为取消置顶

    Returns:
        bool: 成功返回 True，失败返回 False
    """
    try:
        insert_after = win32con.HWND_TOPMOST if topmost else win32con.HWND_NOTOPMOST
        rect = win32gui.GetWindowRect(hwnd)
        if rect is None:
            return False
        left, top, right, bottom = rect
        width = right - left
        height = bottom - top
        win32gui.SetWindowPos(
            hwnd,
            insert_after,
            left, top,
            width, height,
            win32con.SWP_SHOWWINDOW
        )
        return True
    except Exception as e:
        print(f"设置窗口置顶失败: {e}")
        return False


def activate_window(hwnd: int) -> bool:
    """
    激活窗口（使其成为前台窗口）。

    Args:
        hwnd (int): 窗口句柄

    Returns:
        bool: 成功返回 True，失败返回 False
    """
    try:
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)

        win32gui.SetForegroundWindow(hwnd)
        return True
    except Exception as e:
        try:
            alt_hwnd = win32gui.GetForegroundWindow()
            thread1 = win32api.GetCurrentThreadId()
            thread2 = win32gui.GetWindowThreadProcessId(hwnd)[0]
            thread3 = win32gui.GetWindowThreadProcessId(alt_hwnd)[0]

            ctypes.windll.user32.AttachThreadInput(thread1, thread2, True)
            ctypes.windll.user32.AttachThreadInput(thread1, thread3, True)

            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(hwnd)

            ctypes.windll.user32.AttachThreadInput(thread1, thread2, False)
            ctypes.windll.user32.AttachThreadInput(thread1, thread3, False)
            return True
        except Exception as e2:
            print(f"激活窗口失败: {e2}")
            return False


def ensure_window_foreground(hwnd: int, set_topmost: bool = False) -> bool:
    """
    确保窗口在前台显示（激活并可选置顶）。

    Args:
        hwnd (int): 窗口句柄
        set_topmost (bool): 是否同时设置窗口置顶

    Returns:
        bool: 成功返回 True，失败返回 False
    """
    try:
        if not win32gui.IsWindow(hwnd):
            print("无效的窗口句柄")
            return False

        if not is_window_active(hwnd):
            if not activate_window(hwnd):
                return False

        if set_topmost and not is_window_topmost(hwnd):
            if not set_window_topmost(hwnd, True):
                return False

        return True
    except Exception as e:
        print(f"确保窗口前台失败: {e}")
        return False


def foreground_click(hwnd: int, x: int, y: int, button: str = "left", ensure_foreground: bool = True, set_topmost: bool = False) -> bool:
    """
    前台点击：在点击前确保窗口激活并可选置顶。

    Args:
        hwnd (int): 窗口句柄
        x (int): 窗口内的相对 X 坐标
        y (int): 窗口内的相对 Y 坐标
        button (str): 鼠标按钮，可选 "left"、"right"、"middle"
        ensure_foreground (bool): 是否确保窗口在前台
        set_topmost (bool): 是否将窗口置顶

    Returns:
        bool: 成功返回 True，失败返回 False
    """
    try:
        if not win32gui.IsWindow(hwnd):
            print("无效的窗口句柄")
            return False

        if ensure_foreground:
            if not ensure_window_foreground(hwnd, set_topmost):
                print("无法将窗口置于前台")
                return False

        rect = win32gui.GetWindowRect(hwnd)
        if rect is None:
            return False
        left, top, _, _ = rect

        screen_x = left + x
        screen_y = top + y

        win32api.SetCursorPos((screen_x, screen_y))

        button_map = {
            "left": (win32con.MOUSEEVENTF_LEFTDOWN, win32con.MOUSEEVENTF_LEFTUP),
            "right": (win32con.MOUSEEVENTF_RIGHTDOWN, win32con.MOUSEEVENTF_RIGHTUP),
            "middle": (win32con.MOUSEEVENTF_MIDDLEDOWN, win32con.MOUSEEVENTF_MIDDLEUP),
        }

        if button not in button_map:
            print(f"无效的鼠标按钮: {button}")
            return False

        down_flag, up_flag = button_map[button]
        win32api.mouse_event(down_flag, 0, 0, 0, 0)
        win32api.mouse_event(up_flag, 0, 0, 0, 0)

        return True
    except Exception as e:
        print(f"前台点击失败: {e}")
        return False


def foreground_double_click(hwnd: int, x: int, y: int, ensure_foreground: bool = True, set_topmost: bool = False) -> bool:
    """
    前台双击：在双击前确保窗口激活并可选置顶。

    Args:
        hwnd (int): 窗口句柄
        x (int): 窗口内的相对 X 坐标
        y (int): 窗口内的相对 Y 坐标
        ensure_foreground (bool): 是否确保窗口在前台
        set_topmost (bool): 是否将窗口置顶

    Returns:
        bool: 成功返回 True，失败返回 False
    """
    try:
        if not foreground_click(hwnd, x, y, "left", ensure_foreground, set_topmost):
            return False

        import time
        time.sleep(0.1)

        return foreground_click(hwnd, x, y, "left", False, False)
    except Exception as e:
        print(f"前台双击失败: {e}")
        return False


VK_CODE_MAP = {
    "a": 0x41, "b": 0x42, "c": 0x43, "d": 0x44, "e": 0x45,
    "f": 0x46, "g": 0x47, "h": 0x48, "i": 0x49, "j": 0x4A,
    "k": 0x4B, "l": 0x4C, "m": 0x4D, "n": 0x4E, "o": 0x4F,
    "p": 0x50, "q": 0x51, "r": 0x52, "s": 0x53, "t": 0x54,
    "u": 0x55, "v": 0x56, "w": 0x57, "x": 0x58, "y": 0x59,
    "z": 0x5A,
    "0": 0x30, "1": 0x31, "2": 0x32, "3": 0x33, "4": 0x34,
    "5": 0x35, "6": 0x36, "7": 0x37, "8": 0x38, "9": 0x39,
    "f1": 0x70, "f2": 0x71, "f3": 0x72, "f4": 0x73, "f5": 0x74,
    "f6": 0x75, "f7": 0x76, "f8": 0x77, "f9": 0x78, "f10": 0x79,
    "f11": 0x7A, "f12": 0x7B,
    "enter": 0x0D, "return": 0x0D,
    "tab": 0x09, "escape": 0x1B, "esc": 0x1B,
    "space": 0x20, "backspace": 0x08,
    "insert": 0x2D, "delete": 0x2E,
    "home": 0x24, "end": 0x23,
    "pageup": 0x21, "pagedown": 0x22,
    "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
    "ctrl": 0x11, "alt": 0x12, "shift": 0x10,
    "win": 0x5B, "lwin": 0x5B, "rwin": 0x5C,
    "lctrl": 0xA2, "rctrl": 0xA3,
    "lshift": 0xA0, "rshift": 0xA1,
    "lalt": 0xA4, "ralt": 0xA5,
    "capslock": 0x14, "numlock": 0x90, "scrolllock": 0x91,
    "printscreen": 0x2A, "pause": 0x13,
    "`": 0xC0, "-": 0xBD, "=": 0xBB,
    "[": 0xDB, "]": 0xDD, "\\": 0xDC,
    ";": 0xBA, "'": 0xDE, ",": 0xBC, ".": 0xBE, "/": 0xBF,
}

MODIFIER_KEYS = {"ctrl", "alt", "shift", "win", "lctrl", "rctrl", "lshift", "rshift", "lalt", "ralt"}


def get_vk_code(key: str) -> Optional[int]:
    """
    获取按键对应的虚拟键码。

    Args:
        key (str): 按键名称或字符

    Returns:
        Optional[int]: 虚拟键码，未找到返回 None
    """
    key_lower = key.lower()
    if key_lower in VK_CODE_MAP:
        return VK_CODE_MAP[key_lower]
    if len(key) == 1:
        return ord(key.upper())
    return None


def background_key_down(hwnd: int, key: str) -> bool:
    """
    后台发送按键按下消息。

    Args:
        hwnd (int): 窗口句柄
        key (str): 按键名称或字符

    Returns:
        bool: 成功返回 True，失败返回 False
    """
    try:
        vk_code = get_vk_code(key)
        if vk_code is None:
            print(f"未知的按键: {key}")
            return False

        scan_code = win32api.MapVirtualKey(vk_code, 0)
        lParam = (scan_code << 16) | 1

        win32gui.PostMessage(hwnd, win32con.WM_KEYDOWN, vk_code, lParam)
        return True
    except Exception as e:
        print(f"后台按键按下失败: {e}")
        return False


def background_key_up(hwnd: int, key: str) -> bool:
    """
    后台发送按键释放消息。

    Args:
        hwnd (int): 窗口句柄
        key (str): 按键名称或字符

    Returns:
        bool: 成功返回 True，失败返回 False
    """
    try:
        vk_code = get_vk_code(key)
        if vk_code is None:
            print(f"未知的按键: {key}")
            return False

        scan_code = win32api.MapVirtualKey(vk_code, 0)
        lParam = (scan_code << 16) | 0xC0000001

        win32gui.PostMessage(hwnd, win32con.WM_KEYUP, vk_code, lParam)
        return True
    except Exception as e:
        print(f"后台按键释放失败: {e}")
        return False


def background_key_press(hwnd: int, key: str, delay: float = 0.05) -> bool:
    """
    后台发送按键（按下并释放）。

    Args:
        hwnd (int): 窗口句柄
        key (str): 按键名称或字符
        delay (float): 按下与释放之间的延迟（秒）

    Returns:
        bool: 成功返回 True，失败返回 False
    """
    try:
        import time

        if not background_key_down(hwnd, key):
            return False

        time.sleep(delay)

        if not background_key_up(hwnd, key):
            return False

        return True
    except Exception as e:
        print(f"后台按键失败: {e}")
        return False


def background_send_keys(hwnd: int, text: str, delay: float = 0.05) -> bool:
    """
    后台发送字符串（逐字符发送）。

    Args:
        hwnd (int): 窗口句柄
        text (str): 要发送的字符串
        delay (float): 每个按键之间的延迟（秒）

    Returns:
        bool: 成功返回 True，失败返回 False
    """
    try:
        import time

        for char in text:
            if not background_key_press(hwnd, char, delay):
                return False
            time.sleep(delay)

        return True
    except Exception as e:
        print(f"后台发送字符串失败: {e}")
        return False


def background_send_text(hwnd: int, text: str) -> bool:
    """
    后台发送文本（使用 WM_CHAR 消息，更可靠）。

    Args:
        hwnd (int): 窗口句柄
        text (str): 要发送的文本

    Returns:
        bool: 成功返回 True，失败返回 False
    """
    try:
        for char in text:
            win32gui.PostMessage(hwnd, win32con.WM_CHAR, ord(char), 0)
        return True
    except Exception as e:
        print(f"后台发送文本失败: {e}")
        return False


def background_hotkey(hwnd: int, *keys: str, delay: float = 0.05) -> bool:
    """
    后台发送组合键（如 Ctrl+C）。

    Args:
        hwnd (int): 窗口句柄
        *keys: 按键序列，修饰键在前，如 ("ctrl", "c")
        delay (float): 按键之间的延迟（秒）

    Returns:
        bool: 成功返回 True，失败返回 False
    """
    try:
        import time

        if len(keys) < 1:
            print("至少需要一个按键")
            return False

        modifier_keys = []
        normal_keys = []

        for key in keys:
            if key.lower() in MODIFIER_KEYS:
                modifier_keys.append(key)
            else:
                normal_keys.append(key)

        for mod_key in modifier_keys:
            if not background_key_down(hwnd, mod_key):
                return False
            time.sleep(delay)

        for normal_key in normal_keys:
            if not background_key_press(hwnd, normal_key, delay):
                for mod_key in reversed(modifier_keys):
                    background_key_up(hwnd, mod_key)
                return False
            time.sleep(delay)

        for mod_key in reversed(modifier_keys):
            if not background_key_up(hwnd, mod_key):
                return False
            time.sleep(delay)

        return True
    except Exception as e:
        print(f"后台组合键失败: {e}")
        return False


def background_key_press_ex(hwnd: int, key: str, delay: float = 0.05, use_post: bool = True) -> bool:
    """
    后台发送按键（扩展版本，可选择消息类型）。

    Args:
        hwnd (int): 窗口句柄
        key (str): 按键名称或字符
        delay (float): 按下与释放之间的延迟（秒）
        use_post (bool): True 使用 PostMessage（异步），False 使用 SendMessage（同步）

    Returns:
        bool: 成功返回 True，失败返回 False
    """
    try:
        import time

        vk_code = get_vk_code(key)
        if vk_code is None:
            print(f"未知的按键: {key}")
            return False

        scan_code = win32api.MapVirtualKey(vk_code, 0)
        lParam_down = (scan_code << 16) | 1
        lParam_up = (scan_code << 16) | 0xC0000001

        send_func = win32gui.PostMessage if use_post else win32gui.SendMessage

        send_func(hwnd, win32con.WM_KEYDOWN, vk_code, lParam_down)
        time.sleep(delay)
        send_func(hwnd, win32con.WM_KEYUP, vk_code, lParam_up)

        return True
    except Exception as e:
        print(f"后台按键失败: {e}")
        return False


class HumanizedInput:
    """
    拟人化输入类，提供防检测的键盘输入功能。
    
    特征：
    - 随机延时：正态分布的延时，模拟人类反应时间
    - 按键持续时间随机化：按下与抬起之间的时间差
    - 行为节奏变化：偶尔的停顿和犹豫
    - 输入模式变化：随机微小的节奏波动
    """
    
    _hesitation_counter = 0
    _last_key_time = 0.0
    _rhythm_base = 1.0
    
    @staticmethod
    def _random_delay(mean: float, std: float, min_val: float, max_val: float) -> float:
        """
        生成正态分布的随机延时。
        
        Args:
            mean (float): 平均值（秒）
            std (float): 标准差（秒）
            min_val (float): 最小值（秒）
            max_val (float): 最大值（秒）
        
        Returns:
            float: 随机延时（秒）
        """
        delay = random.gauss(mean, std)
        return max(min_val, min(max_val, delay))
    
    @staticmethod
    def _should_hesitate() -> bool:
        """
        判断是否应该产生犹豫停顿。
        每隔 5-15 次操作会有一次较长的停顿。
        
        Returns:
            bool: 是否应该停顿
        """
        HumanizedInput._hesitation_counter += 1
        if HumanizedInput._hesitation_counter >= random.randint(5, 15):
            HumanizedInput._hesitation_counter = 0
            return True
        return False
    
    @staticmethod
    def _get_key_duration() -> float:
        """
        获取按键持续时间（按下到抬起的间隔）。
        人类按键持续时间通常在 50-150ms，呈正态分布。
        
        Returns:
            float: 按键持续时间（秒）
        """
        return HumanizedInput._random_delay(
            mean=0.08,
            std=0.03,
            min_val=0.04,
            max_val=0.20
        )
    
    @staticmethod
    def _get_inter_key_delay() -> float:
        """
        获取按键之间的间隔时间。
        模拟人类连续按键时的节奏。
        
        Returns:
            float: 按键间隔（秒）
        """
        base_delay = HumanizedInput._random_delay(
            mean=0.12,
            std=0.05,
            min_val=0.05,
            max_val=0.30
        )
        rhythm_variation = random.uniform(-0.02, 0.02)
        return max(0.03, base_delay + rhythm_variation)
    
    @staticmethod
    def _get_action_delay() -> float:
        """
        获取动作之间的延时（用于较大动作间隔）。
        
        Returns:
            float: 动作延时（秒）
        """
        return HumanizedInput._random_delay(
            mean=0.5,
            std=0.15,
            min_val=0.3,
            max_val=1.0
        )
    
    @staticmethod
    def _maybe_add_hesitation(stop_event: Optional[threading.Event] = None) -> bool:
        """
        可能添加犹豫停顿。
        """
        if HumanizedInput._should_hesitate():
            hesitation_time = HumanizedInput._random_delay(
                mean=0.8,
                std=0.3,
                min_val=0.3,
                max_val=1.5
            )
            return not _interruptible_wait(hesitation_time, stop_event)
        return True
    
    @staticmethod
    def _simulate_micro_movement(stop_event: Optional[threading.Event] = None) -> bool:
        """
        模拟微小的手部抖动/移动延迟。
        """
        micro_delay = random.uniform(0.01, 0.05)
        return not _interruptible_wait(micro_delay, stop_event)


def _interruptible_wait(
    duration: float,
    stop_event: Optional[threading.Event] = None
) -> bool:
    """
    可被停止事件打断的等待。

    Returns:
        bool: True 表示等待期间被停止；False 表示正常等待完成
    """
    duration = max(0.0, float(duration))
    if duration <= 0:
        return bool(stop_event and stop_event.is_set())
    if stop_event is None:
        time.sleep(duration)
        return False
    max_chunk = 3600.0
    remaining = duration
    while remaining > 0:
        if stop_event.is_set():
            return True
        current_chunk = min(remaining, max_chunk)
        if stop_event.wait(current_chunk):
            return True
        remaining -= current_chunk
    return bool(stop_event.is_set())


def humanized_key_press(
    hwnd: int,
    key: str,
    base_delay: float = 0.05,
    enable_hesitation: bool = True,
    enable_rhythm: bool = True,
    stop_event: Optional[threading.Event] = None
) -> bool:
    """
    拟人化后台按键（按下并释放）。
    
    特征：
    - 随机按键持续时间：50-150ms 正态分布
    - 随机按键间隔：模拟人类节奏
    - 偶尔犹豫停顿：每 5-15 次操作可能停顿 0.3-1.5 秒
    - 微小节奏变化：每次操作时间略有不同
    
    Args:
        hwnd (int): 窗口句柄
        key (str): 按键名称或字符
        base_delay (float): 基础延时（会被随机化调整）
        enable_hesitation (bool): 是否启用犹豫停顿
        enable_rhythm (bool): 是否启用节奏变化
    
    Returns:
        bool: 成功返回 True，失败返回 False
    """
    try:
        vk_code = get_vk_code(key)
        if vk_code is None:
            print(f"未知的按键: {key}")
            return False
        
        if stop_event and stop_event.is_set():
            return False

        if enable_hesitation and not HumanizedInput._maybe_add_hesitation(stop_event):
            return False
        
        scan_code = win32api.MapVirtualKey(vk_code, 0)
        lParam_down = (scan_code << 16) | 1
        lParam_up = (scan_code << 16) | 0xC0000001
        
        if not HumanizedInput._simulate_micro_movement(stop_event):
            return False
        
        win32gui.PostMessage(hwnd, win32con.WM_KEYDOWN, vk_code, lParam_down)
        
        key_duration = HumanizedInput._get_key_duration()
        interrupted = _interruptible_wait(key_duration, stop_event)
        
        win32gui.PostMessage(hwnd, win32con.WM_KEYUP, vk_code, lParam_up)
        if interrupted:
            return False
        
        if enable_rhythm:
            inter_delay = HumanizedInput._get_inter_key_delay()
            if _interruptible_wait(inter_delay, stop_event):
                return False
        
        return True
    except Exception as e:
        print(f"拟人化按键失败: {e}")
        return False


def long_press_key(
    hwnd: int,
    key: str,
    duration: float,
    enable_hesitation: bool = True,
    stop_event: Optional[threading.Event] = None
) -> bool:
    """
    拟人化长按按键（按下并保持一段时间后释放）。
    
    特征：
    - 按下前有微小延迟
    - 按下后保持指定时长
    - 释放时有微小延迟
    
    Args:
        hwnd (int): 窗口句柄
        key (str): 按键名称或字符
        duration (float): 长按时长（秒）
        enable_hesitation (bool): 是否启用犹豫停顿
        
    Returns:
        bool: 成功返回 True，失败返回 False
    """
    try:
        vk_code = get_vk_code(key)
        if vk_code is None:
            print(f"未知的按键: {key}")
            return False
        
        if stop_event and stop_event.is_set():
            return False

        if enable_hesitation and not HumanizedInput._maybe_add_hesitation(stop_event):
            return False
        
        scan_code = win32api.MapVirtualKey(vk_code, 0)
        lParam_down = (scan_code << 16) | 1
        lParam_up = (scan_code << 16) | 0xC0000001
        
        if not HumanizedInput._simulate_micro_movement(stop_event):
            return False
        
        win32gui.PostMessage(hwnd, win32con.WM_KEYDOWN, vk_code, lParam_down)
        
        actual_duration = duration * random.uniform(0.95, 1.05)
        interrupted = _interruptible_wait(actual_duration, stop_event)
        
        win32gui.PostMessage(hwnd, win32con.WM_KEYUP, vk_code, lParam_up)
        if interrupted:
            return False
        
        return True
    except Exception as e:
        print(f"拟人化按键失败: {e}")
        return False


def humanized_key_sequence(
    hwnd: int,
    keys: list,
    inter_key_delay: float = 0.1,
    enable_hesitation: bool = True,
    stop_event: Optional[threading.Event] = None
) -> bool:
    """
    拟人化按键序列（连续发送多个按键）。
    
    Args:
        hwnd (int): 窗口句柄
        keys (list): 按键列表
        inter_key_delay (float): 按键之间的基础间隔
        enable_hesitation (bool): 是否启用犹豫停顿
    
    Returns:
        bool: 成功返回 True，失败返回 False
    """
    try:
        for key in keys:
            if stop_event and stop_event.is_set():
                return False
            if not humanized_key_press(
                hwnd,
                key,
                enable_hesitation=enable_hesitation,
                stop_event=stop_event
            ):
                return False
            delay = HumanizedInput._get_inter_key_delay()
            if _interruptible_wait(delay, stop_event):
                return False
        return True
    except Exception as e:
        print(f"拟人化按键序列失败: {e}")
        return False


def humanized_sleep(
    base_time: float,
    variation: float = 0.2,
    stop_event: Optional[threading.Event] = None
) -> bool:
    """
    拟人化睡眠（添加随机变化）。
    
    Args:
        base_time (float): 基础时间（秒）
        variation (float): 变化范围比例（0-1）

    Returns:
        bool: True 表示被停止事件打断；False 表示正常等待完成
    """
    actual_time = base_time * (1 + random.uniform(-variation, variation))
    actual_time = max(0.01, actual_time)
    return _interruptible_wait(actual_time, stop_event)


def get_humanized_delay(
    base_delay: float,
    min_multiplier: float = 0.7,
    max_multiplier: float = 1.3
) -> float:
    """
    获取拟人化延时值。
    
    Args:
        base_delay (float): 基础延时（秒）
        min_multiplier (float): 最小乘数
        max_multiplier (float): 最大乘数
    
    Returns:
        float: 拟人化延时（秒）
    """
    multiplier = random.uniform(min_multiplier, max_multiplier)
    return base_delay * multiplier


def click_mouse(
    hwnd: int,
    x: int,
    y: int,
    button: str = 'left',
    hold_time: float = 0.05,
    stop_event: Optional[threading.Event] = None
) -> bool:
    """
    前台发送鼠标点击到窗口。

    Args:
        hwnd (int): 窗口句柄
        x (int): 窗口内 X 坐标
        y (int): 窗口内 Y 坐标
        button (str): 鼠标按钮 ('left', 'right', 'middle')
        hold_time (float): 按键按住到松开的时间（秒），默认0.05秒

    Returns:
        bool: 操作是否成功

    Raises:
        ValueError: 当句柄无效时抛出
    """
    if not win32gui.IsWindow(hwnd):
        raise ValueError(f"无效的窗口句柄：{hwnd}")
    if stop_event and stop_event.is_set():
        return False

    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    
    screen_x = left + x
    screen_y = top + y

    if button == 'left':
        down_event = win32con.MOUSEEVENTF_LEFTDOWN
        up_event = win32con.MOUSEEVENTF_LEFTUP
    elif button == 'right':
        down_event = win32con.MOUSEEVENTF_RIGHTDOWN
        up_event = win32con.MOUSEEVENTF_RIGHTUP
    elif button == 'middle':
        down_event = win32con.MOUSEEVENTF_MIDDLEDOWN
        up_event = win32con.MOUSEEVENTF_MIDDLEUP
    else:
        raise ValueError(f"不支持的鼠标按钮：{button}")

    win32api.SetCursorPos((screen_x, screen_y))
    if _interruptible_wait(0.02, stop_event):
        return False
    win32api.mouse_event(down_event, 0, 0, 0, 0)
    interrupted = _interruptible_wait(hold_time, stop_event)
    win32api.mouse_event(up_event, 0, 0, 0, 0)
    return not interrupted


INPUT_BACKEND_PYWIN32 = "pywin32"
INPUT_BACKEND_BUKE_HID = "buke_hid"
HID_SWITCH_CHECK_NONE = "none"
HID_SWITCH_CHECK_FOREGROUND = "foreground"
BUKE_HID_DRIVER_SERVICE_NAME = "ddhid63340"


class BukeKmHidError(RuntimeError):
    pass


def get_buke_hid_driver_dir() -> Path:
    return resolve_resource_path(Path("DD_master") / "2.hid" / "drv")


def is_buke_hid_driver_installed() -> bool:
    advapi32 = ctypes.windll.advapi32
    advapi32.OpenSCManagerW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32]
    advapi32.OpenSCManagerW.restype = ctypes.c_void_p
    advapi32.OpenServiceW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_uint32]
    advapi32.OpenServiceW.restype = ctypes.c_void_p
    advapi32.CloseServiceHandle.argtypes = [ctypes.c_void_p]
    advapi32.CloseServiceHandle.restype = ctypes.c_int
    scm = advapi32.OpenSCManagerW(None, None, 0x0001)
    if not scm:
        return False
    try:
        service = advapi32.OpenServiceW(scm, BUKE_HID_DRIVER_SERVICE_NAME, 0x0001)
        if not service:
            return False
        advapi32.CloseServiceHandle(service)
        return True
    finally:
        advapi32.CloseServiceHandle(scm)


def run_buke_hid_driver_installer(install: bool = True) -> bool:
    driver_dir = get_buke_hid_driver_dir()
    bat_name = "install.bat" if install else "uninstall.bat"
    bat_path = driver_dir / bat_name
    if not bat_path.exists():
        raise BukeKmHidError("未找到 HID 驱动脚本，请确认驱动目录完整")
    shell32 = ctypes.windll.shell32
    shell32.ShellExecuteW.argtypes = [
        ctypes.c_void_p,
        ctypes.c_wchar_p,
        ctypes.c_wchar_p,
        ctypes.c_wchar_p,
        ctypes.c_wchar_p,
        ctypes.c_int,
    ]
    shell32.ShellExecuteW.restype = ctypes.c_void_p
    result = shell32.ShellExecuteW(
        None,
        "runas",
        str(bat_path),
        None,
        str(driver_dir),
        1,
    )
    return int(result or 0) > 32


class BukeKmHidDevice:
    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        self._dll = None
        self._load()

    @classmethod
    def get(cls) -> "BukeKmHidDevice":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    @classmethod
    def reset(cls) -> None:
        with cls._lock:
            cls._instance = None

    def _load(self) -> None:
        dll_path = resolve_resource_path(Path("DD_master") / "2.hid" / "ddhid.63340.dll")
        if not dll_path.exists():
            raise BukeKmHidError("未找到 HID 输入组件，请确认程序目录完整")

        try:
            self._dll = ctypes.windll.LoadLibrary(str(dll_path))
        except Exception as exc:
            raise BukeKmHidError(f"加载 HID 输入组件失败: {exc}") from exc

        self._dll.DD_btn.argtypes = [ctypes.c_int]
        self._dll.DD_btn.restype = ctypes.c_int
        self._dll.DD_key.argtypes = [ctypes.c_int, ctypes.c_int]
        self._dll.DD_key.restype = ctypes.c_int
        self._dll.DD_mov.argtypes = [ctypes.c_int, ctypes.c_int]
        self._dll.DD_mov.restype = ctypes.c_int
        self._dll.DD_movR.argtypes = [ctypes.c_int, ctypes.c_int]
        self._dll.DD_movR.restype = ctypes.c_int
        self._dll.DD_todc.argtypes = [ctypes.c_int]
        self._dll.DD_todc.restype = ctypes.c_int

        if self._dll.DD_btn(0) != 1:
            raise BukeKmHidError("HID 输入组件初始化失败，请检查驱动、网络、权限和组件位数")

    def _dd_code(self, vk_code: int) -> int:
        dd_code = int(self._dll.DD_todc(int(vk_code)))
        if dd_code <= 0:
            raise BukeKmHidError(f"DD 键码转换失败: VK={vk_code}")
        return dd_code

    def key_down(self, vk_code: int) -> None:
        self._dll.DD_key(self._dd_code(vk_code), 1)

    def key_up(self, vk_code: int) -> None:
        self._dll.DD_key(self._dd_code(vk_code), 2)

    def mouse_move(self, x: int, y: int) -> None:
        self._dll.DD_mov(int(x), int(y))

    def mouse_move_relative(self, dx: int, dy: int) -> None:
        self._dll.DD_movR(int(dx), int(dy))

    def mouse_down(self, button: str) -> None:
        {
            "left": lambda: self._dll.DD_btn(1),
            "right": lambda: self._dll.DD_btn(4),
            "middle": lambda: self._dll.DD_btn(16),
        }[button]()

    def mouse_up(self, button: str) -> None:
        {
            "left": lambda: self._dll.DD_btn(2),
            "right": lambda: self._dll.DD_btn(8),
            "middle": lambda: self._dll.DD_btn(32),
        }[button]()


class HidForegroundScheduler:
    def __init__(self):
        self._lock = threading.RLock()
        self._window_order: list[int] = []
        self._current_index = 0
        self._check_mode = HID_SWITCH_CHECK_NONE

    def configure(self, window_order: list[int], check_mode: str = HID_SWITCH_CHECK_NONE) -> None:
        with self._lock:
            self._window_order = [int(hwnd) for hwnd in window_order]
            if self._current_index >= len(self._window_order):
                self._current_index = 0
            self._check_mode = check_mode if check_mode == HID_SWITCH_CHECK_FOREGROUND else HID_SWITCH_CHECK_NONE

    def run_for_window(
        self,
        hwnd: int,
        controller: "BukeHidInputController",
        action: Callable[[], bool],
        stop_event: Optional[threading.Event] = None,
        log: Optional[Callable[[str, Optional[str]], None]] = None,
    ) -> bool:
        with self._lock:
            if stop_event and stop_event.is_set():
                return False
            if not self._switch_to_window(hwnd, controller, stop_event, log):
                return False
            return action()

    def _switch_to_window(
        self,
        hwnd: int,
        controller: "BukeHidInputController",
        stop_event: Optional[threading.Event],
        log: Optional[Callable[[str, Optional[str]], None]],
    ) -> bool:
        if not self._window_order:
            self._window_order = [int(hwnd)]

        try:
            target_index = self._window_order.index(int(hwnd))
        except ValueError:
            self._window_order.append(int(hwnd))
            target_index = len(self._window_order) - 1

        steps = (target_index - self._current_index) % len(self._window_order)
        if steps:
            if log:
                log(f"HID 前台切换：Alt+Tab {steps} 次")
            controller.key_down("alt")
            if _interruptible_wait(0.08, stop_event):
                controller.key_up("alt")
                return False
            for _ in range(steps):
                controller.key_press("tab", base_delay=0.05, enable_hesitation=False, enable_rhythm=False, stop_event=stop_event)
                if _interruptible_wait(0.12, stop_event):
                    controller.key_up("alt")
                    return False
            controller.key_up("alt")
            self._current_index = target_index
            if _interruptible_wait(0.3, stop_event):
                return False

        if self._check_mode == HID_SWITCH_CHECK_FOREGROUND:
            for _ in range(max(1, len(self._window_order))):
                try:
                    if win32gui.GetForegroundWindow() == int(hwnd):
                        return True
                except Exception:
                    break
                controller.key_down("alt")
                if _interruptible_wait(0.05, stop_event):
                    controller.key_up("alt")
                    return False
                controller.key_press("tab", base_delay=0.05, enable_hesitation=False, enable_rhythm=False, stop_event=stop_event)
                controller.key_up("alt")
                self._current_index = (self._current_index + 1) % len(self._window_order)
                if _interruptible_wait(0.2, stop_event):
                    return False
            if log:
                log("HID 前台切换校验失败，请确认窗口顺序未被手动改变", "red")
            return False

        return True


_hid_foreground_scheduler = HidForegroundScheduler()


def configure_hid_foreground_scheduler(window_order: list[int], check_mode: str = HID_SWITCH_CHECK_NONE) -> None:
    _hid_foreground_scheduler.configure(window_order, check_mode)


def check_buke_hid_initialization() -> Tuple[bool, bool, str]:
    driver_installed = is_buke_hid_driver_installed()
    BukeKmHidDevice.reset()
    try:
        BukeKmHidDevice.get()
        if driver_installed:
            return True, True, "HID 驱动已安装，初始化成功"
        return (
            False,
            False,
            "未检测到 HID 驱动服务，但 HID 仍能初始化。"
            "这通常表示驱动刚卸载但仍在当前系统会话中残留，请重启电脑后再检测。",
        )
    except BukeKmHidError as exc:
        if driver_installed:
            return False, True, f"驱动已安装，但 HID 初始化失败：{exc}。建议重启电脑，或检查杀毒软件/安全软件拦截。"
        return False, False, f"未检测到 HID 驱动，请点击安装驱动后重启或重新检测。详细信息：{exc}"


class PyWin32InputController:
    mode = INPUT_BACKEND_PYWIN32
    is_hid = False

    def run_for_window(self, hwnd: int, action: Callable[[], bool], stop_event=None, log=None) -> bool:
        return action()

    def key_press(self, hwnd: int, key: str, **kwargs) -> bool:
        return humanized_key_press(hwnd, key, **kwargs)

    def long_press(self, hwnd: int, key: str, duration: float, **kwargs) -> bool:
        return long_press_key(hwnd, key, duration, **kwargs)

    def hold_down(self, hwnd: int, key: str) -> bool:
        return background_key_down(hwnd, key)

    def hold_up(self, hwnd: int, key: str) -> bool:
        return background_key_up(hwnd, key)

    def click(self, hwnd: int, x: int, y: int, button: str = "left", **kwargs) -> bool:
        return click_mouse(hwnd, x, y, button, **kwargs)


class BukeHidInputController:
    mode = INPUT_BACKEND_BUKE_HID
    is_hid = True

    def __init__(self, scheduler: HidForegroundScheduler = None):
        self.device = BukeKmHidDevice.get()
        self.scheduler = scheduler or _hid_foreground_scheduler

    def run_for_window(self, hwnd: int, action: Callable[[], bool], stop_event=None, log=None) -> bool:
        return self.scheduler.run_for_window(hwnd, self, action, stop_event=stop_event, log=log)

    def _vk(self, key: str) -> Optional[int]:
        vk_code = get_vk_code(key)
        if vk_code is None:
            print(f"未知的按键: {key}")
        return vk_code

    def key_down(self, key: str) -> bool:
        vk_code = self._vk(key)
        if vk_code is None:
            return False
        self.device.key_down(vk_code)
        return True

    def key_up(self, key: str) -> bool:
        vk_code = self._vk(key)
        if vk_code is None:
            return False
        self.device.key_up(vk_code)
        return True

    def key_press(
        self,
        key: str,
        base_delay: float = 0.05,
        enable_hesitation: bool = True,
        enable_rhythm: bool = True,
        stop_event: Optional[threading.Event] = None,
    ) -> bool:
        if stop_event and stop_event.is_set():
            return False
        if enable_hesitation and not HumanizedInput._maybe_add_hesitation(stop_event):
            return False
        if not HumanizedInput._simulate_micro_movement(stop_event):
            return False
        if not self.key_down(key):
            return False
        key_duration = max(base_delay, HumanizedInput._get_key_duration())
        interrupted = _interruptible_wait(key_duration, stop_event)
        self.key_up(key)
        if interrupted:
            return False
        if enable_rhythm and _interruptible_wait(HumanizedInput._get_inter_key_delay(), stop_event):
            return False
        return True

    def long_press(
        self,
        key: str,
        duration: float,
        enable_hesitation: bool = True,
        stop_event: Optional[threading.Event] = None,
    ) -> bool:
        if stop_event and stop_event.is_set():
            return False
        if enable_hesitation and not HumanizedInput._maybe_add_hesitation(stop_event):
            return False
        if not self.key_down(key):
            return False
        interrupted = _interruptible_wait(duration * random.uniform(0.95, 1.05), stop_event)
        self.key_up(key)
        return not interrupted

    def click(self, hwnd: int, x: int, y: int, button: str = "left", hold_time: float = 0.05, stop_event=None) -> bool:
        if button not in {"left", "right", "middle"}:
            raise ValueError(f"不支持的鼠标按钮：{button}")
        if not win32gui.IsWindow(hwnd):
            raise ValueError(f"无效的窗口句柄：{hwnd}")
        if stop_event and stop_event.is_set():
            return False
        self.device.mouse_down(button)
        interrupted = _interruptible_wait(hold_time, stop_event)
        self.device.mouse_up(button)
        return not interrupted


def create_input_controller(mode: str = INPUT_BACKEND_BUKE_HID):
    if mode == INPUT_BACKEND_PYWIN32:
        return PyWin32InputController()
    return BukeHidInputController()


def activate_window(hwnd: int, force: bool = True) -> bool:
    """
    激活窗口并将其带到前台。

    Args:
        hwnd (int): 窗口句柄
        force (bool): 是否强制激活（使用 AttachThreadInput 技术），默认 True

    Returns:
        bool: 操作是否成功
    """
    if not win32gui.IsWindow(hwnd):
        print(f"无效的窗口句柄：{hwnd}")
        return False

    try:
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)

        if force:
            foreground_hwnd = win32gui.GetForegroundWindow()
            if foreground_hwnd != hwnd:
                foreground_thread = win32process.GetWindowThreadProcessId(foreground_hwnd)[0]
                current_thread = win32api.GetCurrentThreadId()
                target_thread = win32process.GetWindowThreadProcessId(hwnd)[0]

                if current_thread != target_thread:
                    ctypes.windll.user32.AttachThreadInput(current_thread, target_thread, True)
                    if foreground_thread != current_thread:
                        ctypes.windll.user32.AttachThreadInput(current_thread, foreground_thread, True)

                win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
                win32gui.SetForegroundWindow(hwnd)
                win32gui.SetFocus(hwnd)

                if current_thread != target_thread:
                    ctypes.windll.user32.AttachThreadInput(current_thread, target_thread, False)
                    if foreground_thread != current_thread:
                        ctypes.windll.user32.AttachThreadInput(current_thread, foreground_thread, False)
        else:
            win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
            win32gui.SetForegroundWindow(hwnd)

        return True
    except Exception as e:
        print(f"激活窗口失败: {e}")
        return False

def deactivate_window(hwnd: int, force: bool = True, minimize_if_failed: bool = False) -> bool:
    """
    取消激活窗口，使其失去前台焦点。

    注意：
        Windows 没有直接“取消激活某窗口”的标准 API，
        本函数通过将焦点切换到桌面来实现“取消激活”的效果。
        如果失败，可选择最小化目标窗口。

    Args:
        hwnd (int): 目标窗口句柄
        force (bool): 是否强制切换焦点（使用 AttachThreadInput 技术），默认 True
        minimize_if_failed (bool): 若切换到桌面失败，是否最小化目标窗口，默认 False

    Returns:
        bool: 操作是否成功
    """
    if not win32gui.IsWindow(hwnd):
        print(f"无效的窗口句柄：{hwnd}")
        return False

    try:
        foreground_hwnd = win32gui.GetForegroundWindow()

        # 如果目标窗口本来就不是前台窗口，视为已取消激活
        if foreground_hwnd != hwnd:
            return True

        # 获取桌面/外壳窗口句柄
        desktop_hwnd = win32gui.GetDesktopWindow()
        shell_hwnd = ctypes.windll.user32.GetShellWindow()

        target_switch_hwnd = shell_hwnd if shell_hwnd else desktop_hwnd
        if not target_switch_hwnd or not win32gui.IsWindow(target_switch_hwnd):
            print("无法获取可切换的桌面窗口句柄")
            if minimize_if_failed:
                win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
                return True
            return False

        if force:
            current_thread = win32api.GetCurrentThreadId()
            foreground_thread = win32process.GetWindowThreadProcessId(foreground_hwnd)[0]
            switch_thread = win32process.GetWindowThreadProcessId(target_switch_hwnd)[0]

            attached_foreground = False
            attached_switch = False

            try:
                if current_thread != foreground_thread:
                    ctypes.windll.user32.AttachThreadInput(current_thread, foreground_thread, True)
                    attached_foreground = True

                if current_thread != switch_thread:
                    ctypes.windll.user32.AttachThreadInput(current_thread, switch_thread, True)
                    attached_switch = True

                win32gui.ShowWindow(target_switch_hwnd, win32con.SW_SHOW)
                win32gui.SetForegroundWindow(target_switch_hwnd)
                win32gui.SetFocus(target_switch_hwnd)

            finally:
                if attached_switch:
                    ctypes.windll.user32.AttachThreadInput(current_thread, switch_thread, False)
                if attached_foreground:
                    ctypes.windll.user32.AttachThreadInput(current_thread, foreground_thread, False)
        else:
            win32gui.ShowWindow(target_switch_hwnd, win32con.SW_SHOW)
            win32gui.SetForegroundWindow(target_switch_hwnd)

        # 检查目标窗口是否已失去前台
        new_foreground_hwnd = win32gui.GetForegroundWindow()
        if new_foreground_hwnd != hwnd:
            return True

        # 可选兜底：最小化目标窗口
        if minimize_if_failed:
            win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
            return True

        return False

    except Exception as e:
        print(f"取消激活窗口失败: {e}")
        return False


ImageSource = Union[str, Path, np.ndarray]
Region = Tuple[int, int, int, int]


def _get_capture_base_rect(hwnd: int, client_area: bool = False) -> Region:
    """
    获取截图基准区域。

    Args:
        hwnd (int): 窗口句柄
        client_area (bool): True 时返回客户区在屏幕中的矩形，False 时返回整个窗口矩形

    Returns:
        Region: (left, top, width, height)
    """
    if client_area:
        left_top = win32gui.ClientToScreen(hwnd, (0, 0))
        client_rect = win32gui.GetClientRect(hwnd)
        width = client_rect[2] - client_rect[0]
        height = client_rect[3] - client_rect[1]
        return left_top[0], left_top[1], width, height

    rect = win32gui.GetWindowRect(hwnd)
    return rect[0], rect[1], rect[2] - rect[0], rect[3] - rect[1]


def _normalize_capture_region(
    area_width: int,
    area_height: int,
    region: Optional[Region] = None
) -> Region:
    """
    规范化并校验相对截图区域。

    Args:
        area_width (int): 基准区域宽度
        area_height (int): 基准区域高度
        region (Optional[Region]): 相对区域 (x, y, width, height)

    Returns:
        Region: 规范化后的相对区域 (x, y, width, height)
    """
    if area_width <= 0 or area_height <= 0:
        raise ValueError("窗口截图区域宽高必须大于 0")

    if region is None:
        return 0, 0, area_width, area_height

    x, y, width, height = map(int, region)
    if width <= 0 or height <= 0:
        raise ValueError("截图区域的宽高必须大于 0")
    if x < 0 or y < 0:
        raise ValueError("截图区域的 x 和 y 不能小于 0")
    if x + width > area_width or y + height > area_height:
        raise ValueError(
            f"截图区域超出窗口范围: region={region}, window_size=({area_width}, {area_height})"
        )
    return x, y, width, height


def _capture_screen_region(left: int, top: int, width: int, height: int) -> np.ndarray:
    """
    从屏幕拷贝指定区域。

    Returns:
        np.ndarray: BGR 图像
    """
    hwnd_desktop = win32gui.GetDesktopWindow()
    desktop_dc = win32gui.GetWindowDC(hwnd_desktop)
    src_dc = win32ui.CreateDCFromHandle(desktop_dc)
    mem_dc = src_dc.CreateCompatibleDC()
    bitmap = win32ui.CreateBitmap()

    try:
        bitmap.CreateCompatibleBitmap(src_dc, width, height)
        mem_dc.SelectObject(bitmap)
        mem_dc.BitBlt((0, 0), (width, height), src_dc, (left, top), win32con.SRCCOPY)

        bitmap_bits = bitmap.GetBitmapBits(True)
        image = np.frombuffer(bitmap_bits, dtype=np.uint8)
        image.shape = (height, width, 4)
        return cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)
    finally:
        win32gui.DeleteObject(bitmap.GetHandle())
        mem_dc.DeleteDC()
        src_dc.DeleteDC()
        win32gui.ReleaseDC(hwnd_desktop, desktop_dc)


def capture_window_foreground(
    hwnd: int,
    region: Optional[Region] = None,
    client_area: bool = False,
    ensure_foreground: bool = True,
    set_topmost: bool = False
) -> np.ndarray:
    """
    通过窗口句柄进行前台截图，可选择窗口内指定位置。

    Args:
        hwnd (int): 窗口句柄
        region (Optional[Region]): 相对窗口区域 (x, y, width, height)，不传则截取整个区域
        client_area (bool): True 时以客户区为基准；False 时以整个窗口为基准
        ensure_foreground (bool): 是否先确保窗口在前台
        set_topmost (bool): 激活时是否顺便置顶

    Returns:
        np.ndarray: BGR 图像
    """
    if not win32gui.IsWindow(hwnd):
        raise ValueError(f"无效的窗口句柄：{hwnd}")

    if ensure_foreground and not ensure_window_foreground(hwnd, set_topmost=set_topmost):
        raise RuntimeError(f"无法将窗口置于前台：{hwnd}")

    base_left, base_top, area_width, area_height = _get_capture_base_rect(hwnd, client_area)
    offset_x, offset_y, capture_width, capture_height = _normalize_capture_region(
        area_width,
        area_height,
        region
    )

    return _capture_screen_region(
        base_left + offset_x,
        base_top + offset_y,
        capture_width,
        capture_height
    )


def save_window_foreground_screenshot(
    hwnd: int,
    save_path: Union[str, Path],
    region: Optional[Region] = None,
    client_area: bool = False,
    ensure_foreground: bool = True,
    set_topmost: bool = False
) -> str:
    """
    保存窗口前台截图到文件。

    Returns:
        str: 保存后的绝对路径
    """
    image = capture_window_foreground(
        hwnd=hwnd,
        region=region,
        client_area=client_area,
        ensure_foreground=ensure_foreground,
        set_topmost=set_topmost
    )

    save_path = Path(save_path).expanduser().resolve()
    save_path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(save_path), image):
        raise RuntimeError(f"截图保存失败：{save_path}")
    return str(save_path)


def _load_template_image(template: ImageSource) -> np.ndarray:
    """
    ??????
    """
    if isinstance(template, np.ndarray):
        template_image = template.copy()
    else:
        resource_candidates = get_resource_search_paths(template)
        template_path = resolve_resource_path(template)
        template_image = cv2.imread(str(template_path), cv2.IMREAD_UNCHANGED)
        if template_image is None:
            attempted_paths = " | ".join(str(candidate) for candidate in resource_candidates)
            raise FileNotFoundError(
                f"????????: {template_path} | ????: {template} | ????: {attempted_paths}"
            )

    if template_image.ndim == 2:
        return template_image
    if template_image.ndim == 3 and template_image.shape[2] == 4:
        return cv2.cvtColor(template_image, cv2.COLOR_BGRA2BGR)
    return template_image


def _prepare_match_image(image: np.ndarray, grayscale: bool) -> np.ndarray:
    """
    按匹配模式预处理图像。
    """
    if grayscale and image.ndim == 3:
        return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return image


def match_template_in_window_foreground(
    hwnd: int,
    template: ImageSource,
    region: Optional[Region] = None,
    client_area: bool = False,
    threshold: float = 0.8,
    ensure_foreground: bool = True,
    set_topmost: bool = False,
    grayscale: bool = False,
    method: int = cv2.TM_CCOEFF_NORMED
) -> Dict[str, Union[bool, float, Tuple[int, int], Region]]:
    """
    在窗口前台截图中进行模板匹配，可限制到窗口内指定位置。

    Args:
        hwnd (int): 窗口句柄
        template (ImageSource): 模板图片路径或 numpy 图像
        region (Optional[Region]): 只在该相对区域内匹配 (x, y, width, height)
        client_area (bool): True 时以客户区为基准；False 时以整个窗口为基准
        threshold (float): 匹配阈值。对 SQDIFF 系列方法表示最大允许误差，其他方法表示最小置信度
        ensure_foreground (bool): 是否先确保窗口在前台
        set_topmost (bool): 激活时是否顺便置顶
        grayscale (bool): 是否转为灰度图后匹配
        method (int): cv2.matchTemplate 的匹配方法

    Returns:
        Dict[str, Union[bool, float, Tuple[int, int], Region]]:
            matched: 是否匹配成功
            confidence: 匹配值
            top_left: 命中左上角，相对当前基准区域
            center: 命中中心点，相对当前基准区域
            screen_top_left: 命中左上角的屏幕坐标
            screen_center: 命中中心点的屏幕坐标
            search_region: 实际搜索区域，相对当前基准区域
    """
    screenshot = capture_window_foreground(
        hwnd=hwnd,
        region=region,
        client_area=client_area,
        ensure_foreground=ensure_foreground,
        set_topmost=set_topmost
    )
    template_image = _load_template_image(template)

    search_image = _prepare_match_image(screenshot, grayscale)
    template_image = _prepare_match_image(template_image, grayscale)

    search_height, search_width = search_image.shape[:2]
    template_height, template_width = template_image.shape[:2]
    if template_width > search_width or template_height > search_height:
        raise ValueError(
            "模板尺寸不能大于搜索区域尺寸: "
            f"template=({template_width}, {template_height}), "
            f"search=({search_width}, {search_height})"
        )

    result = cv2.matchTemplate(search_image, template_image, method)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

    sqdiff_methods = {cv2.TM_SQDIFF, cv2.TM_SQDIFF_NORMED}
    if method in sqdiff_methods:
        confidence = float(min_val)
        matched = confidence <= threshold
        match_left, match_top = min_loc
    else:
        confidence = float(max_val)
        matched = confidence >= threshold
        match_left, match_top = max_loc

    base_left, base_top, area_width, area_height = _get_capture_base_rect(hwnd, client_area)
    search_region = _normalize_capture_region(area_width, area_height, region)
    region_x, region_y, _, _ = search_region

    top_left = (region_x + match_left, region_y + match_top)
    center = (
        top_left[0] + template_width // 2,
        top_left[1] + template_height // 2
    )

    return {
        "matched": matched,
        "confidence": confidence,
        "top_left": top_left,
        "center": center,
        "screen_top_left": (base_left + top_left[0], base_top + top_left[1]),
        "screen_center": (base_left + center[0], base_top + center[1]),
        "search_region": search_region,
    }
