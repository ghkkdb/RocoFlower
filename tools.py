"""
窗口操作工具模块
提供窗口位置修改、分辨率调整等功能
"""

import win32gui
import win32con
import win32api
import ctypes
import random
import time
from typing import Optional, Tuple


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
    def _maybe_add_hesitation():
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
            time.sleep(hesitation_time)
    
    @staticmethod
    def _simulate_micro_movement():
        """
        模拟微小的手部抖动/移动延迟。
        """
        micro_delay = random.uniform(0.01, 0.05)
        time.sleep(micro_delay)


def humanized_key_press(
    hwnd: int,
    key: str,
    base_delay: float = 0.05,
    enable_hesitation: bool = True,
    enable_rhythm: bool = True
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
        
        if enable_hesitation:
            HumanizedInput._maybe_add_hesitation()
        
        scan_code = win32api.MapVirtualKey(vk_code, 0)
        lParam_down = (scan_code << 16) | 1
        lParam_up = (scan_code << 16) | 0xC0000001
        
        HumanizedInput._simulate_micro_movement()
        
        win32gui.PostMessage(hwnd, win32con.WM_KEYDOWN, vk_code, lParam_down)
        
        key_duration = HumanizedInput._get_key_duration()
        time.sleep(key_duration)
        
        win32gui.PostMessage(hwnd, win32con.WM_KEYUP, vk_code, lParam_up)
        
        if enable_rhythm:
            inter_delay = HumanizedInput._get_inter_key_delay()
            time.sleep(inter_delay)
        
        return True
    except Exception as e:
        print(f"拟人化按键失败: {e}")
        return False


def long_press_key(
    hwnd: int,
    key: str,
    duration: float,
    enable_hesitation: bool = True
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
        
        if enable_hesitation:
            HumanizedInput._maybe_add_hesitation()
        
        scan_code = win32api.MapVirtualKey(vk_code, 0)
        lParam_down = (scan_code << 16) | 1
        lParam_up = (scan_code << 16) | 0xC0000001
        
        HumanizedInput._simulate_micro_movement()
        
        win32gui.PostMessage(hwnd, win32con.WM_KEYDOWN, vk_code, lParam_down)
        
        actual_duration = duration * random.uniform(0.95, 1.05)
        time.sleep(actual_duration)
        
        win32gui.PostMessage(hwnd, win32con.WM_KEYUP, vk_code, lParam_up)
        
        return True
    except Exception as e:
        print(f"拟人化按键失败: {e}")
        return False


def humanized_key_sequence(
    hwnd: int,
    keys: list,
    inter_key_delay: float = 0.1,
    enable_hesitation: bool = True
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
            if not humanized_key_press(hwnd, key, enable_hesitation=enable_hesitation):
                return False
            delay = HumanizedInput._get_inter_key_delay()
            time.sleep(delay)
        return True
    except Exception as e:
        print(f"拟人化按键序列失败: {e}")
        return False


def humanized_sleep(base_time: float, variation: float = 0.2) -> None:
    """
    拟人化睡眠（添加随机变化）。
    
    Args:
        base_time (float): 基础时间（秒）
        variation (float): 变化范围比例（0-1）
    """
    actual_time = base_time * (1 + random.uniform(-variation, variation))
    actual_time = max(0.01, actual_time)
    # print(f"拟人化睡眠时间: {actual_time:.1f}秒")
    time.sleep(actual_time)


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
