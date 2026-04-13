import time
import threading
import random
from tools import background_key_press, humanized_key_press, humanized_sleep


def task_1(
    hwnd: int, 
    动作, 
    间隔_min: int, 
    间隔_max: int, 
    任务类型, 
    随机巡航: bool = False, 
    巡航概率: int = 50,
    长按最小: float = 0.0,
    长按最大: float = 1.5,
    空格最小: int = 1,
    空格最大: int = 2,
    stop_event: threading.Event = None, 
    log_callback=None
):
    """
    任务函数。
    
    Args:
        hwnd: 窗口句柄
        动作: 动作按键
        间隔_min: 最小动作间隔（秒）
        间隔_max: 最大动作间隔（秒）
        任务类型: 任务类型（"小号做动作" 或 "房主同乘做动作"）
        随机巡航: 是否开启随机巡航功能
        巡航概率: 随机巡航触发概率（1-100）
        长按最小: 长按方向键最小时长（秒）
        长按最大: 长按方向键最大时长（秒）
        空格最小: 点按空格最小次数
        空格最大: 点按空格最大次数
        stop_event: 停止事件，用于安全停止任务
        log_callback: 日志回调函数，用于输出日志到UI
    """
    if stop_event is None:
        stop_event = threading.Event()
    
    def log(message, color=None):
        if log_callback:
            log_callback(message, color)
        else:
            print(message)
    
    if 间隔_min > 间隔_max:
        log(f"警告: 动作间隔最小值({间隔_min})大于最大值({间隔_max})，已自动交换", color="red")
        间隔_min, 间隔_max = 间隔_max, 间隔_min
    
    if 长按最小 > 长按最大:
        log(f"警告: 长按时长最小值({长按最小})大于最大值({长按最大})，已自动交换", color="red")
        长按最小, 长按最大 = 长按最大, 长按最小
    
    if 空格最小 > 空格最大:
        log(f"警告: 空格次数最小值({空格最小})大于最大值({空格最大})，已自动交换", color="red")
        空格最小, 空格最大 = 空格最大, 空格最小
    
    def get_random_interval():
        """获取随机间隔时间。"""
        return random.uniform(间隔_min, 间隔_max)
    
    def _long_press_key(hwnd: int, key: str, duration: float):
        """
        长按按键。
        
        Args:
            hwnd: 窗口句柄
            key: 按键名称
            duration: 按键时长（秒）
        """
        import win32api
        import win32con
        
        key_map = {
            'W': 0x57,
            'S': 0x53,
            'A': 0x41,
            'D': 0x44,
            'Space': 0x20,
        }
        
        vk_code = key_map.get(key.upper())
        if not vk_code:
            return
        
        win32api.PostMessage(hwnd, win32con.WM_KEYDOWN, vk_code, 0)
        
        start_time = time.time()
        while time.time() - start_time < duration:
            if stop_event.is_set():
                win32api.PostMessage(hwnd, win32con.WM_KEYUP, vk_code, 0)
                return
            time.sleep(0.01)
        
        win32api.PostMessage(hwnd, win32con.WM_KEYUP, vk_code, 0)
    
    def _execute_direction_cruise():
        """
        执行方向键随机巡航。
        
        长按方向键 W/S/A/D（向前走后需反向走回原点）
        """
        if random.randint(1, 100) > 巡航概率:
            return False
        
        directions = ['W', 'S', 'A', 'D']
        direction = random.choice(directions)
        hold_time = random.uniform(长按最小, 长按最大)
        
        log(f"  [随机巡航] 长按方向键 [{direction}] {hold_time:.1f}秒")
        _long_press_key(hwnd, direction, hold_time)
        
        if stop_event.is_set():
            return True
        
        if direction == 'W':
            reverse_direction = 'S'
        elif direction == 'S':
            reverse_direction = 'W'
        elif direction == 'A':
            reverse_direction = 'D'
        else:
            reverse_direction = 'A'
        
        log(f"  [随机巡航] 长按方向键 [{direction}] 完成，反向走回...")
        humanized_sleep(0.2, variation=0.2)
        
        if stop_event.is_set():
            return True
        
        _long_press_key(hwnd, reverse_direction, hold_time)
        
        if stop_event.is_set():
            return True
        
        log(f"  [随机巡航] 长按方向键 [{reverse_direction}] 完成")
        return True
    
    def _execute_space_cruise():
        """
        执行空格随机巡航。
        
        点按空格键
        """
        if random.randint(1, 100) > 巡航概率:
            return False
        
        tap_count = random.randint(空格最小, 空格最大)
        log(f"  [随机巡航] 点按空格键 {tap_count}次")
        
        for _ in range(tap_count):
            if stop_event.is_set():
                return True
            humanized_key_press(hwnd, 'Space')
            humanized_sleep(1, variation=0.3)
        
        return True
    
    if 任务类型 == "小号做动作":
        last_time = time.time()
        current_interval = get_random_interval()
        i = 0
        log(f"第一次执行动作,需等待 {current_interval:.1f}秒")
        while not stop_event.is_set():
            if time.time() - last_time >= current_interval:
                i += 1
                log(f"执行动作: 第{i}次按执行动作 [{动作}]，下次间隔: {current_interval:.1f}秒")
                # log("  按键 [Tab]")

                humanized_key_press(hwnd, 'Tab')
                humanized_sleep(0.5, variation=0.15)

                # log(f"  按键 [{动作}]")
                humanized_key_press(hwnd, 动作)
                humanized_sleep(0.5, variation=0.15)
               
                if stop_event.is_set():
                    break
                # log("  按键 [Escape]")
                humanized_key_press(hwnd, 'Escape')
                humanized_sleep(0.5, variation=0.15)

                humanized_key_press(hwnd, 'space')
                humanized_sleep(0.5, variation=0.15)
                last_time = time.time()
                current_interval = get_random_interval()
                
                if 随机巡航:
                    print("随机巡航")
                    humanized_sleep(0.2, variation=0.3)
                    if random.choice(['direction', 'space']) == 'direction':
                        _execute_direction_cruise()
                    else:
                        _execute_space_cruise()
            humanized_sleep(0.1, variation=0.3)
    
    elif 任务类型 == "房主同乘做动作":
        last_time = time.time()
        current_interval = get_random_interval()
        i = 0
        log(f"第一次执行动作,需等待 {current_interval:.1f}秒")
        while not stop_event.is_set():
            if time.time() - last_time >= current_interval:
                i += 1
                log(f"【第{i}次】执行动作序列开始...")
                log("  按键 [X]")
                humanized_key_press(hwnd, 'X')
                if stop_event.is_set():
                    break
                humanized_sleep(0.5, variation=0.15)
                
                log("  按键 [Tab]")
                humanized_key_press(hwnd, 'Tab')
                if stop_event.is_set():
                    break
                humanized_sleep(0.5, variation=0.15)
                
                log(f"  按键 [{动作}]")
                humanized_key_press(hwnd, 动作)
                if stop_event.is_set():
                    break
                humanized_sleep(0.5, variation=0.15)
                
                log("  按键 [Escape]")
                humanized_key_press(hwnd, 'Escape')
                if stop_event.is_set():
                    break
                humanized_sleep(0.5, variation=0.15)

                humanized_key_press(hwnd, 'space')
                humanized_sleep(0.5, variation=0.15)
                if 随机巡航:
                    if random.choice(['direction', 'space']) == 'direction':
                        _execute_direction_cruise()
                    else:
                        _execute_space_cruise()

                log("  按键 [R]")
                humanized_key_press(hwnd, 'R')
                if stop_event.is_set():
                    break
                
                log(f"执行动作序列完成，下次间隔: {current_interval:.1f}秒")
                last_time = time.time()
                current_interval = get_random_interval()
                
