import random
import threading
from typing import Callable, Optional

from tools import (
    background_key_down,
    background_key_up,
    create_input_controller,
    INPUT_BACKEND_PYWIN32,
)


Logger = Optional[Callable[[str, Optional[str]], None]]


def _emit_log(log_callback: Logger, message: str, color: Optional[str] = None) -> None:
    if log_callback:
        log_callback(message, color)
    else:
        print(message)


def _wait_or_stop(stop_event: threading.Event, seconds: float) -> bool:
    return stop_event.wait(max(0.0, float(seconds)))


def 刷鬼火(
    hwnd: int,
    mode: str = "hold_w",
    ad_interval_min: float = 0.15,
    ad_interval_max: float = 0.2,
    press_duration_min: float = 0.3,
    press_duration_max: float = 0.5,
    jump_interval_min: float = 6.0,
    jump_interval_max: float = 8.0,
    stop_event: threading.Event = None,
    log: Logger = None,
    input_controller=None,
):
    if stop_event is None:
        stop_event = threading.Event()
    controller = input_controller or create_input_controller(INPUT_BACKEND_PYWIN32)

    mode = str(mode or "hold_w").lower()
    ad_interval_min = max(0.05, float(ad_interval_min))
    ad_interval_max = max(0.05, float(ad_interval_max))
    press_duration_min = max(0.01, float(press_duration_min))
    press_duration_max = max(0.01, float(press_duration_max))
    jump_interval_min = max(0.1, float(jump_interval_min))
    jump_interval_max = max(0.1, float(jump_interval_max))
    if ad_interval_min > ad_interval_max:
        ad_interval_min, ad_interval_max = ad_interval_max, ad_interval_min
    if press_duration_min > press_duration_max:
        press_duration_min, press_duration_max = press_duration_max, press_duration_min
    if jump_interval_min > jump_interval_max:
        jump_interval_min, jump_interval_max = jump_interval_max, jump_interval_min

    def sample_range(min_value: float, max_value: float) -> float:
        return random.uniform(min_value, max_value)

    def press_key(key: str, **kwargs) -> bool:
        if getattr(controller, "is_hid", False):
            return controller.key_press(key, **kwargs)
        return controller.key_press(hwnd, key, **kwargs)

    def press_long(key: str, duration: float, **kwargs) -> bool:
        if getattr(controller, "is_hid", False):
            return controller.long_press(key, duration, **kwargs)
        return controller.long_press(hwnd, key, duration, **kwargs)

    if mode == "hold_w":
        if getattr(controller, "is_hid", False):
            _emit_log(log, "HID 输入方式不支持刷鬼火长按 W，请改用循环短按 A/D 或跳跃模式", "red")
            return
        _emit_log(log, "开始执行刷鬼火，模式: 长按 [W]", "green")
        pressed = False
        try:
            pressed = background_key_down(hwnd, "W")
            if not pressed:
                _emit_log(log, "刷鬼火执行失败，长按 [W] 未成功按下", "red")
                return
            while not stop_event.is_set():
                if _wait_or_stop(stop_event, 0.1):
                    break
        finally:
            if pressed:
                background_key_up(hwnd, "W")
        _emit_log(log, "刷鬼火已停止，已释放 [W]", "green")
        return

    if mode == "ad_loop":
        _emit_log(
            log,
            f"开始执行刷鬼火，模式: 循环短按 [A/D]，按住 {press_duration_min:.2f}-{press_duration_max:.2f} 秒，间隔 {ad_interval_min:.2f}-{ad_interval_max:.2f} 秒",
            "green",
        )
        while not stop_event.is_set():
            pair_press_duration = sample_range(press_duration_min, press_duration_max)
            first_wait_duration = sample_range(ad_interval_min, ad_interval_max)
            second_wait_duration = sample_range(ad_interval_min, ad_interval_max)

            def ad_pair_action() -> bool:
                if not press_long("A", pair_press_duration, enable_hesitation=False, stop_event=stop_event):
                    return False
                if _wait_or_stop(stop_event, first_wait_duration):
                    return False
                return press_long("D", pair_press_duration, enable_hesitation=False, stop_event=stop_event)

            if getattr(controller, "is_hid", False):
                pair_ok = controller.run_for_window(hwnd, ad_pair_action, stop_event=stop_event, log=log)
            else:
                pair_ok = ad_pair_action()

            if not pair_ok:
                if not stop_event.is_set():
                    _emit_log(log, "刷鬼火执行失败，A/D 成对短按未完成", "red")
                break
            if _wait_or_stop(stop_event, second_wait_duration):
                break

        _emit_log(log, "刷鬼火已停止，A/D 循环已结束", "green")
        return

    if mode == "jump":
        _emit_log(
            log,
            f"开始执行刷鬼火，模式: 跳跃 [Space]，间隔 {jump_interval_min:.2f}-{jump_interval_max:.2f} 秒",
            "green",
        )
        while not stop_event.is_set():
            def jump_action() -> bool:
                return press_key(
                    "Space",
                    enable_hesitation=False,
                    enable_rhythm=False,
                    stop_event=stop_event,
                )

            if getattr(controller, "is_hid", False):
                jump_ok = controller.run_for_window(hwnd, jump_action, stop_event=stop_event, log=log)
            else:
                jump_ok = jump_action()

            if not jump_ok:
                if not stop_event.is_set():
                    _emit_log(log, "刷鬼火执行失败，跳跃 [Space] 未成功完成", "red")
                break
            wait_duration = sample_range(jump_interval_min, jump_interval_max)
            if _wait_or_stop(stop_event, wait_duration):
                break

        _emit_log(log, "刷鬼火已停止，跳跃循环已结束", "green")
        return

    _emit_log(log, f"刷鬼火执行失败，未知模式: {mode}", "red")
