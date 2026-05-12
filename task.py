import random
import threading
import time
from datetime import datetime, timedelta
from typing import Callable, Optional

import win32con
import win32gui

from tools import (
    activate_window,
    background_key_down,
    background_key_up,
    click_mouse,
    create_input_controller,
    deactivate_window,
    humanized_key_press,
    humanized_sleep,
    INPUT_BACKEND_PYWIN32,
    match_template_in_window_foreground,
    long_press_key,
)


Logger = Optional[Callable[[str, Optional[str]], None]]
_time_adjust_keep_open_hwnds: set[int] = set()


def _emit_log(log_callback: Logger, message: str, color: Optional[str] = None) -> None:
    if log_callback:
        log_callback(message, color)
    else:
        print(message)


def _wait_or_stop(stop_event: threading.Event, seconds: float) -> bool:
    return stop_event.wait(max(0.0, float(seconds)))


def _key_press(controller, hwnd: int, key: str, **kwargs) -> bool:
    if getattr(controller, "is_hid", False):
        return controller.key_press(key, **kwargs)
    return controller.key_press(hwnd, key, **kwargs)


def _long_press(controller, hwnd: int, key: str, duration: float, **kwargs) -> bool:
    if getattr(controller, "is_hid", False):
        return controller.long_press(key, duration, **kwargs)
    return controller.long_press(hwnd, key, duration, **kwargs)


def _click(controller, hwnd: int, x: int, y: int, button: str = "left", **kwargs) -> bool:
    return controller.click(hwnd, x, y, button, **kwargs)


def _ensure_window_topmost(hwnd: int, log: Logger = None) -> bool:
    try:
        ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        if ex_style & win32con.WS_EX_TOPMOST:
            return True
        win32gui.SetWindowPos(
            hwnd,
            win32con.HWND_TOPMOST,
            0,
            0,
            0,
            0,
            win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_SHOWWINDOW,
        )
        _emit_log(log, "检测到窗口未置顶，已强制置顶")
        return True
    except Exception as exc:
        _emit_log(log, f"窗口置顶检测失败: {exc}", "red")
        return False


def _match_template_with_topmost(hwnd: int, template_path: str, log: Logger = None, **kwargs):
    _ensure_window_topmost(hwnd, log=log)
    return match_template_in_window_foreground(hwnd, template_path, **kwargs)


def _match_template_direct(hwnd: int, template_path: str, **kwargs):
    return match_template_in_window_foreground(hwnd, template_path, ensure_foreground=False, **kwargs)


def _long_press_key(hwnd: int, key: str, duration: float, stop_event: threading.Event) -> bool:
    import win32api
    import win32con

    key_map = {
        "W": 0x57,
        "S": 0x53,
        "A": 0x41,
        "D": 0x44,
        "SPACE": 0x20,
    }

    vk_code = key_map.get(key.upper())
    if vk_code is None:
        return False

    win32api.PostMessage(hwnd, win32con.WM_KEYDOWN, vk_code, 0)
    interrupted = _wait_or_stop(stop_event, duration)
    win32api.PostMessage(hwnd, win32con.WM_KEYUP, vk_code, 0)
    return not interrupted


def task_1(
    hwnd: int,
    动作,
    间隔_min: int,
    间隔_max: int,
    任务类型,
    同乘精灵: int = 1,
    防变果冻: bool = True,
    随机巡航: bool = False,
    巡航概率: int = 25,
    长按最小: float = 0.0,
    长按最大: float = 1.5,
    空格最小: int = 1,
    空格最大: int = 2,
    动作跳: bool = True,
    stop_event: threading.Event = None,
    log_callback: Logger = None,
    input_controller=None,
):
    """
    主任务循环。
    """
    if stop_event is None:
        stop_event = threading.Event()
    controller = input_controller or create_input_controller(INPUT_BACKEND_PYWIN32)

    def log(message: str, color: Optional[str] = None) -> None:
        _emit_log(log_callback, message, color)

    def press(key: str, enable_hesitation: bool = True, enable_rhythm: bool = True) -> bool:
        if stop_event.is_set():
            return False
        return _key_press(
            controller,
            hwnd,
            key,
            enable_hesitation=enable_hesitation,
            enable_rhythm=enable_rhythm,
            stop_event=stop_event,
        )

    def sleep_for(seconds: float, variation: float = 0.2) -> bool:
        return humanized_sleep(seconds, variation=variation, stop_event=stop_event)

    def get_random_interval() -> float:
        return random.uniform(间隔_min, 间隔_max)

    if 间隔_min > 间隔_max:
        log(f"警告: 动作间隔最小值({间隔_min})大于最大值({间隔_max})，已自动交换", color="red")
        间隔_min, 间隔_max = 间隔_max, 间隔_min

    if 长按最小 > 长按最大:
        log(f"警告: 长按时长最小值({长按最小})大于最大值({长按最大})，已自动交换", color="red")
        长按最小, 长按最大 = 长按最大, 长按最小

    if 空格最小 > 空格最大:
        log(f"警告: 空格次数最小值({空格最小})大于最大值({空格最大})，已自动交换", color="red")
        空格最小, 空格最大 = 空格最大, 空格最小

    def _execute_direction_cruise() -> bool:
        if random.randint(1, 100) > 巡航概率 or stop_event.is_set():
            return False

        direction = random.choice(["W", "S", "A", "D"])
        hold_time = random.uniform(长按最小, 长按最大)
        reverse_direction = {"W": "S", "S": "W", "A": "D", "D": "A"}[direction]

        log(f"  [随机巡航] 长按方向键 [{direction}] {hold_time:.2f}秒")
        if not _long_press(controller, hwnd, direction, hold_time, enable_hesitation=False, stop_event=stop_event):
            return False

        if sleep_for(0.2, variation=0.2):
            return False

        log(f"  [随机巡航] 长按方向键 [{direction}] 完成，反向走回...")
        if not _long_press(controller, hwnd, reverse_direction, hold_time, enable_hesitation=False, stop_event=stop_event):
            return False

        log(f"  [随机巡航] 长按方向键 [{reverse_direction}] 完成")
        return True

    def _execute_space_cruise() -> bool:
        if random.randint(1, 100) > 巡航概率 or stop_event.is_set():
            return False

        tap_count = random.randint(空格最小, 空格最大)
        log(f"  [随机巡航] 点按空格键 {tap_count}次")

        for _ in range(tap_count):
            if not press("Space"):
                return False
            if sleep_for(1, variation=0.3):
                return False
        return True

    def _maybe_execute_cruise() -> None:
        if not 随机巡航 or stop_event.is_set():
            return
        if sleep_for(0.2, variation=0.3):
            return
        if random.choice(["direction", "space"]) == "direction":
            _execute_direction_cruise()
        else:
            _execute_space_cruise()

    def _run_small_account_once(iteration: int, interval: float) -> bool:
        log(f"执行动作: 第{iteration}次按执行动作 [{动作}]，下次间隔: {interval:.1f}秒")

        if 防变果冻:
            # log("防变果冻")
            if not press("X"):
                return False
            if sleep_for(1, variation=0.15):
                return False

        if not press("Tab"):
            return False
        if sleep_for(0.5, variation=0.15):
            return False

        if not press(动作):
            return False
        if sleep_for(0.5, variation=0.15):
            return False

        if not press("Escape"):
            return False
        if sleep_for(0.5, variation=0.15):
            return False

        if 动作跳:
            if not press("space"):
                return False
            if sleep_for(0.5, variation=0.15):
                return False
        
        _maybe_execute_cruise()
        return not stop_event.is_set()

    def _run_host_once(iteration: int, interval: float) -> bool:
        log(f"【第{iteration}次】执行动作序列开始...")

        if 防变果冻:
            if not press("X"):
                return False
            if sleep_for(1, variation=0.15):
                return False

        for key, delay in [("X", 0.5), ("Tab", 0.5), (动作, 0.5), ("Escape", 0.5)]:
            key_text = 动作 if key == 动作 else key
            log(f"  按键 [{key_text}]")
            if not press(key):
                return False
            if sleep_for(delay, variation=0.15):
                return False

        if 动作跳:
            if not press("space"):
                return False
            if sleep_for(2, variation=0.15):
                return False
        
        _maybe_execute_cruise()

        log("  按键 [R]")
        if not press("R"):
            return False

        log(f"执行动作序列完成，下次间隔: {interval:.1f}秒")
        return not stop_event.is_set()

    iteration = 0
    runner = _run_small_account_once if 任务类型 == "小号做动作" else _run_host_once

    while not stop_event.is_set():
        current_interval = get_random_interval()
        log(f"下一次执行等待 {current_interval:.1f}秒")
        if _wait_or_stop(stop_event, current_interval):
            break
        iteration += 1
        if getattr(controller, "is_hid", False):
            ok = controller.run_for_window(
                hwnd,
                lambda: runner(iteration, current_interval),
                stop_event=stop_event,
                log=log,
            )
        else:
            ok = runner(iteration, current_interval)
        if not ok:
            break


def 时间调整(
    hwnd,
    同乘精灵=0,
    大号同乘=False,
    释放精灵=False,
    使用识别释放精灵=True,
    防果冻=False,
    置顶识别调整=False,
    不退出改时间界面=False,
    log: Logger = None,
    stop_event: threading.Event = None,
    input_controller=None,
):
    if stop_event is None:
        stop_event = threading.Event()
    controller = input_controller or create_input_controller(INPUT_BACKEND_PYWIN32)

    def emit(message: str, color: Optional[str] = None) -> None:
        _emit_log(log, message, color)

    def sleep_for(seconds: float, variation: float = 0.2) -> bool:
        return humanized_sleep(seconds, variation=variation, stop_event=stop_event)

    def press(key: str) -> bool:
        return _key_press(controller, hwnd, key, stop_event=stop_event)

    if getattr(controller, "is_hid", False):
        if 置顶识别调整 or 使用识别释放精灵:
            emit("HID 输入方式不开放图片识别流程，本次按固定步骤执行游戏时间调整", "green")
        使用识别释放精灵 = False
        置顶识别调整 = False

        def hid_time_adjust_action() -> bool:
            emit("HID 前台模式：开始执行固定步骤游戏时间调整")
            if 防果冻 and not press("X"):
                return False
            if sleep_for(0.5, variation=0.15):
                return False
            emit("触发传送石")
            if not press("F"):
                return False
            if sleep_for(10, variation=0.15):
                return False
            emit("选择调整时间")
            if not press("1"):
                return False
            if sleep_for(3, variation=0.15):
                return False
            emit("开启/关闭自动播放")
            if not press("Tab"):
                return False
            if sleep_for(5, variation=0.15):
                return False
            emit("选择早上")
            if not press("1"):
                return False
            if sleep_for(10, variation=0.15):
                return False
            if 不退出改时间界面:
                _time_adjust_keep_open_hwnds.add(hwnd)
                emit("按配置不退出改时间界面")
            else:
                if not press("2"):
                    return False
                emit("退出")
                _time_adjust_keep_open_hwnds.discard(hwnd)
                if sleep_for(5, variation=0.15):
                    return False
            if 释放精灵:
                emit("非识别释放精灵流程开始", color="green")
                for i in range(1, 7):
                    if i == 同乘精灵:
                        emit(f"跳过{i}号骑乘精灵")
                        if sleep_for(1, variation=0.15):
                            return False
                        continue
                    if 防果冻 and not press("X"):
                        return False
                    if sleep_for(2, variation=0.15):
                        return False
                    emit(f"执行非识别释放 {i}号精灵")
                    if not press(str(i)):
                        return False
                    if sleep_for(2, variation=0.15):
                        return False
                    if not _click(controller, hwnd, 0, 0, "left", stop_event=stop_event):
                        return False
                emit("非识别释放精灵流程完成", color="green")
            emit("游戏时间调整流程执行完成")
            return not stop_event.is_set()

        controller.run_for_window(hwnd, hid_time_adjust_action, stop_event=stop_event, log=emit)
        return

    if 不退出改时间界面 and 释放精灵:
        释放精灵 = False
        emit("已关闭退出改时间界面，本次将自动关闭释放精灵流程", color="green")

    if not 不退出改时间界面 and hwnd in _time_adjust_keep_open_hwnds:
        _time_adjust_keep_open_hwnds.discard(hwnd)

    for _ in range(3):
        if stop_event.is_set():
            return

        should_continue_after_adjust = False
        already_in_time_adjust_ui = 不退出改时间界面 and hwnd in _time_adjust_keep_open_hwnds

        emit(
            f"游戏时间调整开始，当前模式: {'置顶识别调整' if 置顶识别调整 else '非置顶直操作'}，释放精灵: {'开启' if 释放精灵 else '关闭'}，退出改时间界面: {'关闭' if 不退出改时间界面 else '开启'}"
        )

        if 置顶识别调整:
            _ensure_window_topmost(hwnd, log=log)
            activate_window(hwnd)
            if sleep_for(1, variation=0.15):
                return
            if 防果冻:
                press("X")
            if sleep_for(2, variation=0.15):
                return
            if already_in_time_adjust_ui:
                should_continue_after_adjust = True
                emit("检测到当前窗口已停留在改时间界面，跳过传送石触碰判断")
            elif _match_template_with_topmost(hwnd, "./img/ff.png", log=log, client_area=True, threshold=0.8)["matched"]:
                should_continue_after_adjust = True
                emit("已找到传送石交互按钮，进入置顶识别调整流程")

                press("F")
                emit("触碰传送石")
            else:
                emit("置顶识别调整未找到传送石交互按钮，准备尝试自动调整", color="green")

            if should_continue_after_adjust:
                while not stop_event.is_set():

                    if sleep_for(2, variation=0.15):
                        return
                    if _match_template_with_topmost(hwnd, "./img/xmsj.png", log=log, client_area=True, threshold=0.8)["matched"]:
                        press("1")
                        emit("选择调整时间")
                        if sleep_for(1, variation=0.15):
                            return

                    if _match_template_with_topmost(hwnd, "./img/zt.png", log=log, client_area=True, threshold=0.8)["matched"]:
                        press("Tab")
                        emit("开启/关闭自动播放")
                        if sleep_for(1, variation=0.15):
                            return

                    if _match_template_with_topmost(hwnd, "./img/zs.png", log=log, client_area=True, threshold=0.8)["matched"]:
                        press("1")
                        emit("选择早上")
                        if 不退出改时间界面:
                            _time_adjust_keep_open_hwnds.add(hwnd)
                            emit("按配置不退出改时间界面")
                        else:
                            while not stop_event.is_set():
                                if sleep_for(1, variation=0.15):
                                    return
                                if _match_template_with_topmost(hwnd, "./img/tc.png", log=log, client_area=True, threshold=0.8)["matched"]:
                                    press("2")
                                    emit("退出")
                                    _time_adjust_keep_open_hwnds.discard(hwnd)
                                    break
                            if sleep_for(2, variation=0.15):
                                return
                        break
        else:
            emit("未开启置顶识别调整，按固定步骤直接操作窗口")
            if not already_in_time_adjust_ui and not 不退出改时间界面:
                emit("触碰传送石")

            if not already_in_time_adjust_ui:
                press("F")
                if sleep_for(10, variation=0.15):
                    return
            else:
                emit("检测到当前窗口已停留在改时间界面，跳过传送石触碰步骤")

            press("1")
            emit("选择调整时间")
            if sleep_for(3, variation=0.15):
                return

            press("Tab")
            emit("开启/关闭自动播放")
            if sleep_for(5, variation=0.15):
                return 
            
            press("1")
            emit("选择早上")
            if sleep_for(10, variation=0.15):
                return

            if not 不退出改时间界面:
                press("2")
                emit("退出")
                _time_adjust_keep_open_hwnds.discard(hwnd)
                if sleep_for(5, variation=0.15):
                    return
            else:
                _time_adjust_keep_open_hwnds.add(hwnd)
                emit("按配置不退出改时间界面")

            should_continue_after_adjust = True

        if should_continue_after_adjust:
            matcher = _match_template_with_topmost if 置顶识别调整 else _match_template_direct

            if 释放精灵:
                release_mode = "识别释放" if 使用识别释放精灵 else "非识别释放"
                if 使用识别释放精灵:
                    emit(f"释放精灵流程开始，模式: {release_mode}，识别方式: {'置顶识别' if 置顶识别调整 else '非置顶识别'}")
                else:
                    emit(f"释放精灵流程开始，模式: {release_mode}", color="green")


            while 释放精灵 and not stop_event.is_set():
                if 置顶识别调整:
                    _ensure_window_topmost(hwnd, log=log)
                    activate_window(hwnd)
                if sleep_for(1, variation=0.15):
                    return
                if not 使用识别释放精灵:
                    activate_window(hwnd)
                    for i in range(1, 7):
                        if i == 同乘精灵:
                            emit(f"跳过{i}号骑乘精灵")
                            if sleep_for(1, variation=0.15):
                                return
                            continue
                        if sleep_for(1, variation=0.15):
                            return
                        if 防果冻:
                            press("X")
                        if sleep_for(2, variation=0.15):
                            return
                        emit(f"执行非识别释放: {i}号精灵")
                        press(str(i))
                        if sleep_for(2, variation=0.15):
                            return
                        click_mouse(hwnd, 0, 0, "left", stop_event=stop_event)

                    emit("非识别释放精灵流程完成", color="green")
                    break
                cw_regions = [(50, 57, 47, 35), (50, 100, 47, 35), (50, 140, 100, 30), (50, 179, 47, 35), (50, 219, 47, 35), (50, 262, 47, 35)]
                for i in range(1, 7):
                    activate_window(hwnd)
                    if i == 同乘精灵:
                        emit(f"跳过{i}号骑乘精灵")
                        if sleep_for(1, variation=0.15):
                            return
                        continue
                    c = 0                  
                    while not stop_event.is_set():
                        if c > 2:
                            emit(f"{i}号精灵识别释放未命中，已达到最大尝试次数", color="green")
                            break
                        matched = matcher(
                            hwnd,
                            "./img/shifang.png",
                            region=cw_regions[i - 1],
                            client_area=True,
                            threshold=0.8,
                        )["matched"]
                        if matched:
                            emit(f"成功释放{i}号精灵")
                            break
                        if 防果冻:
                            press("X")
                        if sleep_for(2, variation=0.15):
                            return
                        emit(f"尝试识别释放{i}号精灵，第{c + 1}次")
                        press(str(i))
                        if sleep_for(2, variation=0.15):
                            return
                        click_mouse(hwnd, 0, 0, "left", stop_event=stop_event)
                        if sleep_for(3, variation=0.15):
                            return
                        c += 1
                emit("识别释放精灵流程完成", color="green")
                break

            if 大号同乘:
                emit(f"大号同乘流程开始，识别方式: {'置顶识别' if 置顶识别调整 else '非置顶识别'}")

            while 大号同乘 and not stop_event.is_set():
                if sleep_for(2, variation=0.15):
                    return
                if matcher(hwnd, "./img/zjm.png", client_area=True, threshold=0.8)["matched"]:
                    press(str(同乘精灵))
                    emit(f"选择同乘精灵{同乘精灵}")
                    if sleep_for(2, variation=0.15):
                        return
                    press("R")
                    break
                if sleep_for(2, variation=0.15):
                    return

            emit("游戏时间调整流程执行完成")
            deactivate_window(hwnd)
            sleep_for(7, variation=0.15)
            return

        emit("未找到传送石触碰按钮，无法调整时间！！！自动调整中", color="green")
        _long_press_key(hwnd, "A", 0.1, stop_event)

    emit("未找到传送石触碰按钮，无法调整时间！！！请手动调整", color="red")

def 月卡关闭(
    hwnd,
    target_minute=1,
    stop_event: threading.Event = None,
    log: Logger = None,
    input_controller=None,
):
    """
    每天在 04:01-04:05 的指定时间执行一次月卡关闭点击。
    """
    if stop_event is None:
        stop_event = threading.Event()
    controller = input_controller or create_input_controller(INPUT_BACKEND_PYWIN32)

    if target_minute < 1 or target_minute > 5:
        raise ValueError("月卡关闭时间仅支持 04:01-04:05，请传入 1-5 的分钟值")

    def emit(message: str, color: Optional[str] = None) -> None:
        _emit_log(log, message, color)

    emit(f"月卡关闭已启用，将在每天 04:{target_minute:02d} 自动执行", color="green")
    last_trigger_date = None

    while not stop_event.is_set():
        now = datetime.now()
        today_target = now.replace(hour=4, minute=target_minute, second=0, microsecond=0)

        if now.hour == 4 and now.minute == target_minute and last_trigger_date != now.date():
            try:
                emit(f"到达月卡关闭时间 04:{target_minute:02d}，开始执行前台点击", color="green")
                def close_action() -> bool:
                    if not getattr(controller, "is_hid", False):
                        activate_window(hwnd)
                    if humanized_sleep(0.2, variation=0.1, stop_event=stop_event):
                        return False
                    _click(controller, hwnd, 0, 0, "left", stop_event=stop_event)
                    if not getattr(controller, "is_hid", False):
                        deactivate_window(hwnd)
                    return True

                controller.run_for_window(hwnd, close_action, stop_event=stop_event, log=emit)
                emit("月卡关闭点击完成", color="green")
            except Exception as exc:
                emit(f"月卡关闭执行失败: {exc}", color="red")
            last_trigger_date = now.date()
            continue

        if now < today_target:
            next_run = today_target
        else:
            next_run = today_target + timedelta(days=1)

        _wait_or_stop(stop_event, min((next_run - now).total_seconds(), 1.0))


def 刷鬼火(
    hwnd: int,
    mode: str = "hold_w",
    ad_interval_min: float = 0.15,
    ad_interval_max: float = 0.15,
    press_duration_min: float = 0.08,
    press_duration_max: float = 0.08,
    jump_interval_min: float = 2.0,
    jump_interval_max: float = 4.0,
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
        next_key = "A"
        while not stop_event.is_set():
            press_duration = sample_range(press_duration_min, press_duration_max)
            if not long_press_key(
                hwnd,
                next_key,
                press_duration,
                enable_hesitation=False,
                stop_event=stop_event,
            ):
                if not stop_event.is_set():
                    _emit_log(log, f"刷鬼火执行失败，短按 [{next_key}] 未成功完成", "red")
                break
            next_key = "D" if next_key == "A" else "A"
            wait_duration = sample_range(ad_interval_min, ad_interval_max)
            if _wait_or_stop(stop_event, wait_duration):
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
