import random
import threading
from typing import Callable, Optional

from tools import background_key_down, background_key_up, humanized_key_press, long_press_key


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
):
    if stop_event is None:
        stop_event = threading.Event()

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

    if mode == "hold_w":
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

            if not long_press_key(
                hwnd,
                "A",
                pair_press_duration,
                enable_hesitation=False,
                stop_event=stop_event,
            ):
                if not stop_event.is_set():
                    _emit_log(log, "刷鬼火执行失败，短按 [A] 未成功完成", "red")
                break
            if _wait_or_stop(stop_event, first_wait_duration):
                break

            if not long_press_key(
                hwnd,
                "D",
                pair_press_duration,
                enable_hesitation=False,
                stop_event=stop_event,
            ):
                if not stop_event.is_set():
                    _emit_log(log, "刷鬼火执行失败，短按 [D] 未成功完成", "red")
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
            if not humanized_key_press(
                hwnd,
                "Space",
                enable_hesitation=False,
                enable_rhythm=False,
                stop_event=stop_event,
            ):
                if not stop_event.is_set():
                    _emit_log(log, "刷鬼火执行失败，跳跃 [Space] 未成功完成", "red")
                break
            wait_duration = sample_range(jump_interval_min, jump_interval_max)
            if _wait_or_stop(stop_event, wait_duration):
                break

        _emit_log(log, "刷鬼火已停止，跳跃循环已结束", "green")
        return

    _emit_log(log, f"刷鬼火执行失败，未知模式: {mode}", "red")
