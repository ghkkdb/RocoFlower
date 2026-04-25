import copy
import ctypes
import ctypes.wintypes
import json
import os
import sys
import threading
import time
import webbrowser
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple
import random

import win32con
import win32gui
from PyQt5.QtCore import Q_ARG, QMetaObject, QTimer, Qt, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QColor, QKeySequence, QTextCharFormat, QTextCursor
from PyQt5.QtWidgets import (
    QApplication, QButtonGroup, QCheckBox, QComboBox, QDialog, QDoubleSpinBox,
    QGroupBox, QHBoxLayout, QKeySequenceEdit, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMainWindow, QMessageBox, QPushButton, QRadioButton, QSizePolicy, QSpinBox,
    QTextEdit, QVBoxLayout, QWidget,
)

from auth import check_license
from drag_window_picker import DragWindowPicker
from task import task_1, 月卡关闭, 时间调整

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
HOTKEY_ID_START = 0x5001
HOTKEY_ID_STOP = 0x5002
TASK_TYPE_SMALL = "小号做动作"
TASK_TYPE_HOST = "房主同乘做动作"
TASK_TYPE_TIME_ADJUST = "游戏时间调整"


def get_app_dir() -> Path:
    if getattr(sys, "frozen", False) or hasattr(sys, "frozen"):
        try:
            buf = ctypes.create_unicode_buffer(260)
            ctypes.windll.kernel32.GetModuleFileNameW(None, buf, 260)
            return Path(buf.value).parent
        except Exception:
            pass
    return Path(__file__).parent


def get_config_file_path() -> Path:
    return get_app_dir() / "config.json"


def _minutes_to_minute_second_parts(total_minutes: float) -> Tuple[int, int]:
    total_seconds = max(0, int(round(float(total_minutes) * 60)))
    return total_seconds // 60, total_seconds % 60


def _minute_second_parts_to_minutes(minutes: int, seconds: int) -> float:
    total_seconds = max(0, int(minutes) * 60 + int(seconds))
    return total_seconds / 60.0


@dataclass
class WindowProfile:
    task_type: str = TASK_TYPE_SMALL
    action_key: str = "2"
    interval_min: int = 8
    interval_max: int = 9
    duration: int = 60000
    time_adjust_interval_min: float = 15.0
    time_adjust_interval_max: float = 21.0
    time_adjust_release_pet: bool = False
    time_adjust_use_release_pet_recognition: bool = False
    time_adjust_anti_jelly: bool = False
    time_adjust_topmost_recognition: bool = False
    time_adjust_keep_open: bool = False
    auto_shutdown: bool = False
    window_width: int = 1000
    window_height: int = 600
    window_x: int = 0
    window_y: int = 0
    force_topmost: bool = False
    anti_jelly: bool = True
    random_cruise: bool = False
    cruise_probability: int = 22
    cruise_hold_min: float = 0.2
    cruise_hold_max: float = 0.4
    cruise_space_min: int = 0
    cruise_space_max: int = 1
    action_jump: bool = True
    monthly_card_close_enabled: bool = False
    monthly_card_minute: int = 1
    window_title: str = ""
    window_class: str = ""

    @classmethod
    def from_dict(cls, d: dict) -> "WindowProfile":
        p = cls()
        for k in p.__dataclass_fields__:
            if k in d:
                setattr(p, k, d[k])
        if "time_adjust_interval_minutes" in d:
            p.time_adjust_interval_min = d["time_adjust_interval_minutes"]
            p.time_adjust_interval_max = d["time_adjust_interval_minutes"]
        if d.get("time_adjust_enabled"):
            p.task_type = TASK_TYPE_TIME_ADJUST
        p.normalize()
        return p

    def to_dict(self) -> dict:
        self.normalize()
        return {k: getattr(self, k) for k in self.__dataclass_fields__}

    def normalize(self):
        if self.task_type not in (TASK_TYPE_SMALL, TASK_TYPE_HOST, TASK_TYPE_TIME_ADJUST):
            self.task_type = TASK_TYPE_SMALL
        self.action_key = str(self.action_key)
        if self.action_key not in {"1", "2", "3", "4", "5"}:
            self.action_key = "2"
        self.interval_min = max(1, int(self.interval_min))
        self.interval_max = max(1, int(self.interval_max))
        if self.interval_min > self.interval_max:
            self.interval_min, self.interval_max = self.interval_max, self.interval_min
        self.duration = max(1, int(self.duration))
        self.time_adjust_interval_min = max(0.1, min(25.0, float(self.time_adjust_interval_min)))
        self.time_adjust_interval_max = max(0.1, min(25.0, float(self.time_adjust_interval_max)))
        if self.time_adjust_interval_min > self.time_adjust_interval_max:
            self.time_adjust_interval_min, self.time_adjust_interval_max = self.time_adjust_interval_max, self.time_adjust_interval_min
        self.window_width = max(400, int(self.window_width))
        self.window_height = max(300, int(self.window_height))
        self.window_x = max(0, int(self.window_x))
        self.window_y = max(0, int(self.window_y))
        self.cruise_probability = min(100, max(1, int(self.cruise_probability)))
        self.cruise_hold_min = float(self.cruise_hold_min)
        self.cruise_hold_max = float(self.cruise_hold_max)
        if self.cruise_hold_min > self.cruise_hold_max:
            self.cruise_hold_min, self.cruise_hold_max = self.cruise_hold_max, self.cruise_hold_min
        self.cruise_space_min = max(0, int(self.cruise_space_min))
        self.cruise_space_max = max(0, int(self.cruise_space_max))
        if self.cruise_space_min > self.cruise_space_max:
            self.cruise_space_min, self.cruise_space_max = self.cruise_space_max, self.cruise_space_min
        self.monthly_card_minute = min(5, max(1, int(self.monthly_card_minute)))


@dataclass
class WindowSession:
    stop_event: threading.Event
    task_thread: threading.Thread
    monthly_thread: Optional[threading.Thread]
    end_monotonic: float
    running: bool = True


class LicenseDialog(QDialog):
    def __init__(self, result: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("授权验证")
        self.setFixedSize(400, 220)
        layout = QVBoxLayout(self)
        machine_id = result
        if result.startswith("ERROR:"):
            info = f"系统环境异常，无法验证授权：\n\n{result[6:]}"
            machine_id = ""
        elif result.startswith("FORMAT:"):
            info = "授权文件格式错误，请重新获取授权文件："
            machine_id = result[7:]
        elif result.startswith("SIGNATURE:"):
            info = "授权文件签名无效，请重新获取授权文件："
            machine_id = result[10:]
        else:
            info = "程序未授权，点击下方“获取收取文件”按钮获取授权文件！！！"
        layout.addWidget(QLabel(info))
        self.machine_id_edit = None
        if machine_id:
            self.machine_id_edit = QLineEdit(machine_id)
            self.machine_id_edit.setReadOnly(True)
            self.machine_id_edit.setAlignment(Qt.AlignCenter)
            layout.addWidget(self.machine_id_edit)
        row = QHBoxLayout(); row.addStretch()
        if self.machine_id_edit:
            b = QPushButton("复制机器码")
            b.clicked.connect(self._copy)
            row.addWidget(b)
        g = QPushButton("获取授权文件")
        g.clicked.connect(self._open_license_page)
        row.addWidget(g)
        c = QPushButton("关闭")
        c.clicked.connect(self.reject)
        row.addWidget(c)
        layout.addLayout(row)

    def _copy(self):
        QApplication.clipboard().setText(self.machine_id_edit.text())
        QMessageBox.information(self, "提示", "机器码已复制")

    def _open_license_page(self):
        webbrowser.open("https://m.tb.cn/h.imqLQmn")


class ShutdownConfirmDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("关机确认")
        self._sec = 120
        self._done = False
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("任务已完成，是否确认关机？"))
        self.label = QLabel("倒计时: 120 秒")
        layout.addWidget(self.label)
        row = QHBoxLayout()
        a = QPushButton("立即关机"); a.clicked.connect(self._shutdown); row.addWidget(a)
        row.addStretch()
        b = QPushButton("取消"); b.clicked.connect(self.reject); row.addWidget(b)
        layout.addLayout(row)
        self.t = QTimer(self)
        self.t.timeout.connect(self._tick)
        self.t.start(1000)

    def _tick(self):
        self._sec -= 1
        self.label.setText(f"倒计时: {self._sec} 秒")
        if self._sec <= 0:
            self._shutdown()

    def _shutdown(self):
        if self._done:
            return
        self._done = True
        self.t.stop()
        os.system("shutdown /s /t 60")
        self.accept()


class MainWindow(QMainWindow):
    start_clicked = pyqtSignal()
    stop_clicked = pyqtSignal()

    def __init__(self, target_class_name: str = "UnrealWindow"):
        super().__init__()
        self._target_class_name = target_class_name
        self._profiles: Dict[int, WindowProfile] = {}
        self._sessions: Dict[int, WindowSession] = {}
        self._selected_hwnd: Optional[int] = None
        self._loading_profile = False
        self._legacy_default = WindowProfile()
        self._start_hotkey_seq = QKeySequence("Ctrl+Alt+S")
        self._stop_hotkey_seq = QKeySequence("Ctrl+Alt+X")

        self._init_ui()
        self._connect_signals()
        self._ui_timer = QTimer(self)
        self._ui_timer.timeout.connect(self._on_ui_tick)
        self._ui_timer.start(100)
        self.load_config()
        self._register_hotkeys()
        self._refresh_control_state()

    def _init_ui(self):
        self.setWindowTitle("RocoFlower V2.5.3")
        self.resize(800, 760)
        root = QWidget(); self.setCentralWidget(root)
        main = QVBoxLayout(root)

        top = QHBoxLayout()
        top.addWidget(self._create_window_picker_group(), 2)
        right = QVBoxLayout()
        right.addWidget(self._create_group_info_group())
        right.addWidget(self._create_control_group())
        top.addLayout(right, 3)
        main.addLayout(top)
        main.addWidget(self._create_config_group())
        main.addWidget(self._create_window_control_group())
        main.addWidget(self._create_log_group(), 1)
    def _create_window_picker_group(self) -> QGroupBox:
        g = QGroupBox("窗口绑定")
        g.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        g.setMaximumHeight(210)
        v = QVBoxLayout(g)
        h = QHBoxLayout()
        self.window_picker = DragWindowPicker(target_class_name=self._target_class_name)
        h.addWidget(self.window_picker.get_button())
        self.unbind_btn = QPushButton("解绑选中")
        self.unbind_btn.setEnabled(False)
        h.addWidget(self.unbind_btn)
        self.bound_count_label = QLabel("已绑定: 0")
        h.addWidget(self.bound_count_label)
        h.addStretch()
        v.addLayout(h)
        self.bound_windows_list = QListWidget()
        self.bound_windows_list.setMinimumHeight(110)
        self.bound_windows_list.setMaximumHeight(125)
        v.addWidget(self.bound_windows_list)
        self.window_status_label = QLabel("未选择世界")
        self.window_status_label.setStyleSheet("color: gray;")
        v.addWidget(self.window_status_label)
        return g

    def _create_control_group(self) -> QGroupBox:
        g = QGroupBox("控制")
        g.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        g.setMaximumHeight(140)
        v = QVBoxLayout(g)
        r1 = QHBoxLayout()
        self.start_btn = QPushButton("开始(全部窗口)")
        self.stop_btn = QPushButton("停止(全部窗口)")
        r1.addWidget(self.start_btn); r1.addWidget(self.stop_btn)
        r1.addSpacing(16); r1.addWidget(QLabel("剩余时间:"))
        self.remaining_time_label = QLabel("--:--")
        r1.addWidget(self.remaining_time_label)
        r1.addSpacing(12); r1.addWidget(QLabel("运行中:"))
        self.running_count_label = QLabel("0")
        r1.addWidget(self.running_count_label)
        r1.addStretch()
        self.help_btn = QPushButton("使用手册")
        r1.addWidget(self.help_btn)
        v.addLayout(r1)

        r2 = QHBoxLayout()
        r2.addWidget(QLabel("开始热键:"))
        self.start_hotkey_edit = QKeySequenceEdit(self._start_hotkey_seq)
        r2.addWidget(self.start_hotkey_edit)
        r2.addSpacing(12)
        r2.addWidget(QLabel("停止热键:"))
        self.stop_hotkey_edit = QKeySequenceEdit(self._stop_hotkey_seq)
        r2.addWidget(self.stop_hotkey_edit)
        self.apply_hotkey_btn = QPushButton("应用热键")
        r2.addWidget(self.apply_hotkey_btn)
        r2.addStretch()
        v.addLayout(r2)
        return g

    def _create_config_group(self) -> QGroupBox:
        g = QGroupBox("任务配置（当前选中窗口）")
        v = QVBoxLayout(g)

        task_type_row = QHBoxLayout()
        task_type_row.addWidget(QLabel("任务类型:"))
        self.task_type_group = QButtonGroup(self)
        self.radio_small_account = QRadioButton(TASK_TYPE_SMALL)
        self.radio_host_action = QRadioButton(TASK_TYPE_HOST)
        self.radio_time_adjust = QRadioButton(TASK_TYPE_TIME_ADJUST)
        self.task_type_group.addButton(self.radio_small_account, 0)
        self.task_type_group.addButton(self.radio_host_action, 1)
        self.task_type_group.addButton(self.radio_time_adjust, 2)
        task_type_row.addWidget(self.radio_small_account)
        task_type_row.addWidget(self.radio_host_action)
        task_type_row.addWidget(self.radio_time_adjust)
        task_type_row.addStretch()
        v.addLayout(task_type_row)

        self.global_config_group = QGroupBox("全局配置")
        global_layout = QHBoxLayout(self.global_config_group)
        global_layout.addWidget(QLabel("运行时长(分钟):"))
        self.duration_spin = QSpinBox(); self.duration_spin.setRange(1, 60000)
        global_layout.addWidget(self.duration_spin)
        self.auto_shutdown_checkbox = QCheckBox("任务完成后自动关机")
        global_layout.addSpacing(20)
        global_layout.addWidget(self.auto_shutdown_checkbox)
        global_layout.addSpacing(20)
        self.monthly_card_close_checkbox = QCheckBox("启用月卡关闭")
        self.monthly_card_minute_spin = QSpinBox(); self.monthly_card_minute_spin.setRange(1, 5); self.monthly_card_minute_spin.setPrefix("0")
        global_layout.addWidget(self.monthly_card_close_checkbox)
        global_layout.addWidget(QLabel("执行时间: 04:"))
        global_layout.addWidget(self.monthly_card_minute_spin)
        global_layout.addWidget(QLabel("(仅支持 04:01-04:05)"))
        global_layout.addStretch()
        v.addWidget(self.global_config_group)

        self.action_task_group = QGroupBox("动作任务配置")
        action_layout = QVBoxLayout(self.action_task_group)

        action_row_1 = QHBoxLayout()
        action_row_1.addWidget(QLabel("动作按键:"))
        self.action_key_combo = QComboBox(); self.action_key_combo.addItems([str(i) for i in range(1, 6)])
        action_row_1.addWidget(self.action_key_combo)
        action_row_1.addSpacing(20)
        action_row_1.addWidget(QLabel("动作间隔(秒):"))
        self.interval_min_spin = QSpinBox(); self.interval_min_spin.setRange(1, 600)
        self.interval_max_spin = QSpinBox(); self.interval_max_spin.setRange(1, 600)
        action_row_1.addWidget(self.interval_min_spin)
        action_row_1.addWidget(QLabel("-"))
        action_row_1.addWidget(self.interval_max_spin)
        self.anti_jelly_checkbox = QCheckBox("防变果冻")
        action_row_1.addSpacing(20)
        action_row_1.addWidget(self.anti_jelly_checkbox)
        self.action_jump_checkbox = QCheckBox("开启动作跳")
        action_row_1.addSpacing(20)
        action_row_1.addWidget(self.action_jump_checkbox)
        action_row_1.addStretch()
        action_layout.addLayout(action_row_1)

        action_row_2 = QHBoxLayout()
        self.random_cruise_checkbox = QCheckBox("随机巡航")
        self.cruise_probability_spin = QSpinBox(); self.cruise_probability_spin.setRange(1, 100); self.cruise_probability_spin.setSuffix("%")
        self.cruise_hold_min_spin = QDoubleSpinBox(); self.cruise_hold_min_spin.setRange(0, 5); self.cruise_hold_min_spin.setSingleStep(0.1)
        self.cruise_hold_max_spin = QDoubleSpinBox(); self.cruise_hold_max_spin.setRange(0, 5); self.cruise_hold_max_spin.setSingleStep(0.1)
        self.cruise_space_min_spin = QSpinBox(); self.cruise_space_min_spin.setRange(0, 20)
        self.cruise_space_max_spin = QSpinBox(); self.cruise_space_max_spin.setRange(0, 20)
        action_row_2.addWidget(self.random_cruise_checkbox)
        action_row_2.addWidget(QLabel("概率:")); action_row_2.addWidget(self.cruise_probability_spin)
        action_row_2.addWidget(QLabel("移动:")); action_row_2.addWidget(self.cruise_hold_min_spin); action_row_2.addWidget(QLabel("-")); action_row_2.addWidget(self.cruise_hold_max_spin)
        action_row_2.addWidget(QLabel("空格:")); action_row_2.addWidget(self.cruise_space_min_spin); action_row_2.addWidget(QLabel("-")); action_row_2.addWidget(self.cruise_space_max_spin)
        action_row_2.addStretch()
        action_layout.addLayout(action_row_2)
        v.addWidget(self.action_task_group)

        self.time_adjust_group = QGroupBox("游戏时间调整配置")
        time_adjust_layout = QVBoxLayout(self.time_adjust_group)

        time_adjust_row = QHBoxLayout()
        time_adjust_row.addWidget(QLabel("调整间隔:"))
        time_adjust_row.addWidget(QLabel("最小"))
        self.time_adjust_interval_min_minute_spin = QSpinBox(); self.time_adjust_interval_min_minute_spin.setRange(0, 25)
        self.time_adjust_interval_min_second_spin = QSpinBox(); self.time_adjust_interval_min_second_spin.setRange(0, 59)
        time_adjust_row.addWidget(self.time_adjust_interval_min_minute_spin)
        time_adjust_row.addWidget(QLabel("分"))
        time_adjust_row.addWidget(self.time_adjust_interval_min_second_spin)
        time_adjust_row.addWidget(QLabel("秒"))
        time_adjust_row.addWidget(QLabel("-"))
        time_adjust_row.addWidget(QLabel("最大"))
        self.time_adjust_interval_max_minute_spin = QSpinBox(); self.time_adjust_interval_max_minute_spin.setRange(0, 25)
        self.time_adjust_interval_max_second_spin = QSpinBox(); self.time_adjust_interval_max_second_spin.setRange(0, 59)
        time_adjust_row.addWidget(self.time_adjust_interval_max_minute_spin)
        time_adjust_row.addWidget(QLabel("分"))
        time_adjust_row.addWidget(self.time_adjust_interval_max_second_spin)
        time_adjust_row.addWidget(QLabel("秒"))
        time_adjust_row.addStretch()
        time_adjust_layout.addLayout(time_adjust_row)

        time_adjust_options_row = QHBoxLayout()
        self.time_adjust_release_pet_checkbox = QCheckBox("非识别释放精灵")
        time_adjust_options_row.addWidget(self.time_adjust_release_pet_checkbox)
        self.time_adjust_use_release_pet_recognition_checkbox = QCheckBox("识别释放精灵")
        self.time_adjust_use_release_pet_recognition_checkbox.setToolTip("勾选后使用识别释放逻辑")
        time_adjust_options_row.addWidget(self.time_adjust_use_release_pet_recognition_checkbox)
        self.time_adjust_anti_jelly_checkbox = QCheckBox("防果冻")
        time_adjust_options_row.addWidget(self.time_adjust_anti_jelly_checkbox)
        self.time_adjust_topmost_recognition_checkbox = QCheckBox("置顶识别调整")
        time_adjust_options_row.addWidget(self.time_adjust_topmost_recognition_checkbox)
        self.time_adjust_exit_interface_checkbox = QCheckBox("退出改时间界面")
        time_adjust_options_row.addWidget(self.time_adjust_exit_interface_checkbox)
        time_adjust_options_row.addStretch()
        time_adjust_layout.addLayout(time_adjust_options_row)

        self.time_adjust_mouse_warning_label = QLabel("提示：勾选“释放精灵”或“置顶识别调整”任意一项都会抢鼠标。取消勾选“退出改时间界面”后无法使用释放精灵。")
        self.time_adjust_mouse_warning_label.setWordWrap(True)
        self.time_adjust_mouse_warning_label.setStyleSheet("color: #d9534f;")
        time_adjust_layout.addSpacing(6)
        time_adjust_layout.addWidget(self.time_adjust_mouse_warning_label)
        v.addWidget(self.time_adjust_group)

        self.radio_small_account.setChecked(True)
        self.action_key_combo.setCurrentText("2")
        self.interval_min_spin.setValue(8); self.interval_max_spin.setValue(9); self.duration_spin.setValue(60000)
        self.cruise_probability_spin.setValue(22)
        self.cruise_hold_min_spin.setValue(0.2); self.cruise_hold_max_spin.setValue(0.4)
        self.cruise_space_min_spin.setValue(0); self.cruise_space_max_spin.setValue(1)
        self.anti_jelly_checkbox.setChecked(True)
        self.action_jump_checkbox.setChecked(True)
        self.time_adjust_interval_min_minute_spin.setValue(15)
        self.time_adjust_interval_min_second_spin.setValue(0)
        self.time_adjust_interval_max_minute_spin.setValue(21)
        self.time_adjust_interval_max_second_spin.setValue(0)
        self.time_adjust_release_pet_checkbox.setChecked(False)
        self.time_adjust_use_release_pet_recognition_checkbox.setChecked(False)
        self.time_adjust_anti_jelly_checkbox.setChecked(False)
        self.time_adjust_topmost_recognition_checkbox.setChecked(False)
        self.time_adjust_exit_interface_checkbox.setChecked(True)
        self.monthly_card_minute_spin.setValue(1)
        self.monthly_card_minute_spin.setEnabled(False)
        self._update_task_type_ui()
        return g

    def _create_window_control_group(self) -> QGroupBox:
        g = QGroupBox("窗口控制（当前选中窗口）")
        h = QHBoxLayout(g)
        h.addWidget(QLabel("宽:")); self.window_width_spin = QSpinBox(); self.window_width_spin.setRange(400, 3840); h.addWidget(self.window_width_spin)
        h.addWidget(QLabel("高:")); self.window_height_spin = QSpinBox(); self.window_height_spin.setRange(300, 2160); h.addWidget(self.window_height_spin)
        h.addWidget(QLabel("X:")); self.window_x_spin = QSpinBox(); self.window_x_spin.setRange(0, 3840); h.addWidget(self.window_x_spin)
        h.addWidget(QLabel("Y:")); self.window_y_spin = QSpinBox(); self.window_y_spin.setRange(0, 2160); h.addWidget(self.window_y_spin)
        self.apply_window_btn = QPushButton("应用"); h.addWidget(self.apply_window_btn)
        self.force_topmost_checkbox = QCheckBox("强制置顶"); h.addWidget(self.force_topmost_checkbox)
        self.window_width_spin.setValue(1000)
        self.window_height_spin.setValue(600)
        h.addStretch()
        return g

    def _create_log_group(self) -> QGroupBox:
        g = QGroupBox("日志")
        v = QVBoxLayout(g)
        self.log_text = QTextEdit(); self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet("background:#1e1e1e;color:#d4d4d4;font-family:Consolas;")
        v.addWidget(self.log_text)
        return g

    def _create_group_info_group(self) -> QGroupBox:
        g = QGroupBox("交流群")
        g.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        g.setMaximumHeight(72)
        h = QHBoxLayout(g)
        h.addWidget(QLabel("秋秋群聊：625148675"))
        h.addStretch()
        self.qq_group_btn = QPushButton("加入群聊")
        h.addWidget(self.qq_group_btn)
        return g

    def _connect_signals(self):
        self.window_picker.window_picked.connect(self._on_window_picked)
        self.window_picker.pick_failed.connect(self._on_pick_failed)
        self.window_picker.pick_status.connect(lambda m: self.append_log(m))
        self.bound_windows_list.currentItemChanged.connect(self._on_selected_window_changed)
        self.unbind_btn.clicked.connect(self._on_unbind_clicked)
        self.start_btn.clicked.connect(self._on_start_clicked)
        self.stop_btn.clicked.connect(self._on_stop_clicked)
        self.apply_window_btn.clicked.connect(self._on_apply_window)
        self.force_topmost_checkbox.stateChanged.connect(self._on_topmost_changed)
        self.help_btn.clicked.connect(lambda: webbrowser.open("https://wcn33wxdu7tm.feishu.cn/wiki/YGWiwIhsyio98NkiV95cpIcsnAc"))
        self.qq_group_btn.clicked.connect(lambda: webbrowser.open("http://qm.qq.com/cgi-bin/qm/qr?_wv=1027&k=mlO8aqGphhWo2__HuVGrmxmxNmCwvzd-&authKey=atGfagiipTnEzXwbQYQbsz%2BmL9SZJLgRI47hGzmWOs%2BTcZ5Xv%2FKaT5bg4ZjvvUL7&noverify=0&group_code=625148675"))
        self.random_cruise_checkbox.stateChanged.connect(self._on_random_cruise_changed)
        self.time_adjust_release_pet_checkbox.stateChanged.connect(self._on_time_adjust_release_pet_changed)
        self.time_adjust_use_release_pet_recognition_checkbox.stateChanged.connect(self._on_time_adjust_release_pet_recognition_changed)
        self.time_adjust_exit_interface_checkbox.stateChanged.connect(self._on_time_adjust_exit_interface_changed)
        self.monthly_card_close_checkbox.stateChanged.connect(lambda s: self.monthly_card_minute_spin.setEnabled(s == Qt.Checked))
        self.radio_small_account.toggled.connect(self._on_task_type_changed)
        self.radio_host_action.toggled.connect(self._on_task_type_changed)
        self.radio_time_adjust.toggled.connect(self._on_task_type_changed)
        self.apply_hotkey_btn.clicked.connect(self._on_apply_hotkeys)
        self._connect_profile_signals()

    def _connect_profile_signals(self):
        ctrls = [
            self.radio_small_account, self.radio_host_action, self.radio_time_adjust, self.action_key_combo,
            self.interval_min_spin, self.interval_max_spin, self.duration_spin,
            self.time_adjust_interval_min_minute_spin, self.time_adjust_interval_min_second_spin,
            self.time_adjust_interval_max_minute_spin, self.time_adjust_interval_max_second_spin,
            self.auto_shutdown_checkbox, self.window_width_spin, self.window_height_spin,
            self.window_x_spin, self.window_y_spin, self.force_topmost_checkbox,
            self.anti_jelly_checkbox,
            self.random_cruise_checkbox, self.cruise_probability_spin, self.cruise_hold_min_spin,
            self.cruise_hold_max_spin, self.cruise_space_min_spin, self.cruise_space_max_spin,
            self.action_jump_checkbox, self.time_adjust_release_pet_checkbox,
            self.time_adjust_use_release_pet_recognition_checkbox, self.time_adjust_anti_jelly_checkbox,
            self.time_adjust_topmost_recognition_checkbox, self.time_adjust_exit_interface_checkbox, self.monthly_card_close_checkbox,
            self.monthly_card_minute_spin,
        ]
        for c in ctrls:
            if isinstance(c, (QSpinBox, QDoubleSpinBox)):
                c.valueChanged.connect(self._on_profile_changed)
            elif isinstance(c, QComboBox):
                c.currentTextChanged.connect(self._on_profile_changed)
            elif isinstance(c, QCheckBox):
                c.stateChanged.connect(self._on_profile_changed)
            else:
                c.toggled.connect(self._on_profile_changed)

    def _on_profile_changed(self, *_):
        if self._loading_profile:
            return
        self._save_ui_to_profile()

    def _on_random_cruise_changed(self, state):
        e = state == Qt.Checked
        self.cruise_probability_spin.setEnabled(e)
        self.cruise_hold_min_spin.setEnabled(e)
        self.cruise_hold_max_spin.setEnabled(e)
        self.cruise_space_min_spin.setEnabled(e)
        self.cruise_space_max_spin.setEnabled(e)
        self._on_profile_changed()

    def _on_time_adjust_release_pet_changed(self, state):
        if state == Qt.Checked and not self.time_adjust_exit_interface_checkbox.isChecked():
            self.time_adjust_exit_interface_checkbox.setChecked(True)
        if state == Qt.Checked and self.time_adjust_use_release_pet_recognition_checkbox.isChecked():
            self.time_adjust_use_release_pet_recognition_checkbox.setChecked(False)
        self.time_adjust_use_release_pet_recognition_checkbox.setEnabled(
            self._is_time_adjust_selected() and not self._is_time_adjust_keep_open_selected()
        )
        self._on_profile_changed()

    def _on_time_adjust_release_pet_recognition_changed(self, state):
        if state == Qt.Checked:
            if self.time_adjust_release_pet_checkbox.isChecked():
                self.time_adjust_release_pet_checkbox.setChecked(False)
            if not self.time_adjust_topmost_recognition_checkbox.isChecked():
                self.time_adjust_topmost_recognition_checkbox.setChecked(True)
            if not self.time_adjust_exit_interface_checkbox.isChecked():
                self.time_adjust_exit_interface_checkbox.setChecked(True)
        self._on_profile_changed()

    def _on_time_adjust_exit_interface_changed(self, state):
        keep_open = state != Qt.Checked
        if keep_open and self.time_adjust_release_pet_checkbox.isChecked():
            self.time_adjust_release_pet_checkbox.setChecked(False)
        if keep_open and self.time_adjust_use_release_pet_recognition_checkbox.isChecked():
            self.time_adjust_use_release_pet_recognition_checkbox.setChecked(False)
        if keep_open and self.time_adjust_anti_jelly_checkbox.isChecked():
            self.time_adjust_anti_jelly_checkbox.setChecked(False)
        self.time_adjust_release_pet_checkbox.setEnabled(self._is_time_adjust_selected() and not keep_open)
        self.time_adjust_use_release_pet_recognition_checkbox.setEnabled(
            self._is_time_adjust_selected() and not keep_open
        )
        self.time_adjust_anti_jelly_checkbox.setEnabled(self._is_time_adjust_selected() and not keep_open)
        self._on_profile_changed()

    def _set_time_adjust_interval_ui(self, min_minutes: float, max_minutes: float):
        min_m, min_s = _minutes_to_minute_second_parts(min_minutes)
        max_m, max_s = _minutes_to_minute_second_parts(max_minutes)
        self.time_adjust_interval_min_minute_spin.setValue(min_m)
        self.time_adjust_interval_min_second_spin.setValue(min_s)
        self.time_adjust_interval_max_minute_spin.setValue(max_m)
        self.time_adjust_interval_max_second_spin.setValue(max_s)

    def _get_time_adjust_interval_values(self) -> Tuple[float, float]:
        min_minutes = _minute_second_parts_to_minutes(
            self.time_adjust_interval_min_minute_spin.value(),
            self.time_adjust_interval_min_second_spin.value(),
        )
        max_minutes = _minute_second_parts_to_minutes(
            self.time_adjust_interval_max_minute_spin.value(),
            self.time_adjust_interval_max_second_spin.value(),
        )
        min_minutes = max(0.1, min(25.0, min_minutes))
        max_minutes = max(0.1, min(25.0, max_minutes))
        if min_minutes > max_minutes:
            min_minutes, max_minutes = max_minutes, min_minutes
        return min_minutes, max_minutes

    def _is_time_adjust_selected(self) -> bool:
        return self.radio_time_adjust.isChecked()

    def _is_time_adjust_keep_open_selected(self) -> bool:
        return not self.time_adjust_exit_interface_checkbox.isChecked()

    def _update_task_type_ui(self):
        is_time_adjust = self._is_time_adjust_selected()
        self.action_task_group.setEnabled(not is_time_adjust)
        self.time_adjust_group.setEnabled(is_time_adjust)
        self.random_cruise_checkbox.setEnabled(not is_time_adjust)
        cruise_enabled = not is_time_adjust and self.random_cruise_checkbox.isChecked()
        self.cruise_probability_spin.setEnabled(cruise_enabled)
        self.cruise_hold_min_spin.setEnabled(cruise_enabled)
        self.cruise_hold_max_spin.setEnabled(cruise_enabled)
        self.cruise_space_min_spin.setEnabled(cruise_enabled)
        self.cruise_space_max_spin.setEnabled(cruise_enabled)
        self.time_adjust_release_pet_checkbox.setEnabled(is_time_adjust and not self._is_time_adjust_keep_open_selected())
        self.time_adjust_use_release_pet_recognition_checkbox.setEnabled(
            is_time_adjust and not self._is_time_adjust_keep_open_selected()
        )
        self.time_adjust_anti_jelly_checkbox.setEnabled(is_time_adjust and not self._is_time_adjust_keep_open_selected())
        self.time_adjust_topmost_recognition_checkbox.setEnabled(is_time_adjust)
        self.time_adjust_exit_interface_checkbox.setEnabled(is_time_adjust)

    def _on_task_type_changed(self, *_):
        self._update_task_type_ui()
        self._on_profile_changed()

    def _on_pick_failed(self):
        self.window_picker.get_button().setEnabled(True)
        self.window_status_label.setText("世界选择失败，请重试")
        self.window_status_label.setStyleSheet("color: #d9534f;")
        self.append_log("窗口选择失败", "red")
    def _on_window_picked(self, hwnd: int):
        self.window_picker.get_button().setEnabled(True)
        try:
            title = win32gui.GetWindowText(hwnd) or "未命名窗口"
            cls = win32gui.GetClassName(hwnd)
        except Exception:
            title, cls = "未命名窗口", ""
        if hwnd not in self._profiles:
            p = copy.deepcopy(self._legacy_default)
            p.window_title = title; p.window_class = cls
            self._profiles[hwnd] = p
            item = QListWidgetItem(self._item_text(hwnd)); item.setData(Qt.UserRole, hwnd)
            self.bound_windows_list.addItem(item)
            self.append_log(f"新增绑定: {self._window_tag(hwnd)}", "green")
        else:
            self._profiles[hwnd].window_title = title
            self._profiles[hwnd].window_class = cls
            self._refresh_item(hwnd)
        self._select_hwnd(hwnd)
        self.window_status_label.setStyleSheet("color: #5cb85c;")
        self.window_status_label.setText(f"已绑定: {self._window_tag(hwnd)}")
        self.save_config()
        self._refresh_control_state()

    def _item_text(self, hwnd: int) -> str:
        running = self._sessions.get(hwnd).running if hwnd in self._sessions else False
        return f"{'●' if running else '○'} {self._window_alias(hwnd)}"

    def _window_alias(self, hwnd: int) -> str:
        for i in range(self.bound_windows_list.count()):
            it = self.bound_windows_list.item(i)
            if int(it.data(Qt.UserRole)) == hwnd:
                return f"第{i + 1}个世界"
        return f"第{self.bound_windows_list.count() + 1}个世界"

    def _window_tag(self, hwnd: int) -> str:
        return f"{self._window_alias(hwnd)}({hwnd})"

    def _refresh_item(self, hwnd: int):
        for i in range(self.bound_windows_list.count()):
            it = self.bound_windows_list.item(i)
            if int(it.data(Qt.UserRole)) == hwnd:
                it.setText(self._item_text(hwnd))
                return

    def _select_hwnd(self, hwnd: int):
        for i in range(self.bound_windows_list.count()):
            it = self.bound_windows_list.item(i)
            if int(it.data(Qt.UserRole)) == hwnd:
                self.bound_windows_list.setCurrentItem(it)
                return

    def _on_selected_window_changed(self, cur, _prev):
        if cur is None:
            self._selected_hwnd = None
            self.window_status_label.setText("未选择世界")
            self._refresh_control_state()
            return
        self._selected_hwnd = int(cur.data(Qt.UserRole))
        self.window_status_label.setText(f"当前选择: {self._window_tag(self._selected_hwnd)}")
        self._load_profile_to_ui()
        self._refresh_control_state()

    def _on_unbind_clicked(self):
        hwnd = self._selected_hwnd
        if hwnd is None:
            return
        self._stop_session(hwnd, manual=True)
        self._profiles.pop(hwnd, None)
        self._sessions.pop(hwnd, None)
        for i in range(self.bound_windows_list.count()):
            it = self.bound_windows_list.item(i)
            if int(it.data(Qt.UserRole)) == hwnd:
                self.bound_windows_list.takeItem(i)
                break
        self.append_log(f"已解绑: {self._window_tag(hwnd)}")
        for other_hwnd in self._profiles:
            self._refresh_item(other_hwnd)
        self.save_config()
        self._refresh_control_state()

    def _on_start_clicked(self):
        if self._selected_hwnd is not None:
            self._save_ui_to_profile()
        if not self._profiles:
            self.append_log("错误: 请先绑定至少一个窗口", "red"); return
        started = 0
        skipped = 0
        for hwnd in list(self._profiles.keys()):
            s = self._sessions.get(hwnd)
            if s and s.running:
                skipped += 1
                self.append_log(f"[{self._window_tag(hwnd)}] 已在运行，跳过")
                continue
            self._start_session(hwnd)
            started += 1
        if started:
            self.append_log(f"批量开始完成：启动 {started} 个窗口，跳过 {skipped} 个窗口", "green")
        else:
            self.append_log("批量开始未启动新窗口，所有绑定窗口都已在运行")

    def _on_stop_clicked(self):
        running_hwnds = [hwnd for hwnd, s in self._sessions.items() if s.running]
        if not running_hwnds:
            self.append_log("当前没有正在运行的窗口任务")
            return
        for hwnd in running_hwnds:
            self._stop_session(hwnd, manual=True)
        self.append_log(f"批量停止完成：共停止 {len(running_hwnds)} 个窗口")

    def _start_session(self, hwnd: int):
        p = self._profiles.get(hwnd)
        if not p:
            return
        p.normalize()
        stop_event = threading.Event()

        def log_cb(msg, color=None):
            s = f"[{self._window_tag(hwnd)}] {msg}"
            if color:
                s = f"[COLOR:{color}]" + s
            QMetaObject.invokeMethod(self, "_thread_safe_append_log", Qt.QueuedConnection, Q_ARG(str, s))

        def apply_time_adjust_resolution():
            try:
                win32gui.SetWindowPos(
                    hwnd,
                    win32con.HWND_TOPMOST if p.time_adjust_topmost_recognition else win32con.HWND_NOTOPMOST,
                    p.window_x,
                    p.window_y,
                    1000,
                    600,
                    win32con.SWP_SHOWWINDOW,
                )
                if p.time_adjust_topmost_recognition:
                    log_cb("游戏时间调整前已切换分辨率为 1000x600，并启用窗口置顶识别")
                else:
                    log_cb("游戏时间调整前已切换分辨率为 1000x600，当前按非置顶直操作流程执行")
            except Exception as exc:
                log_cb(f"切换分辨率到 1000x600 失败: {exc}", "red")
                raise

        def clear_time_adjust_topmost():
            try:
                win32gui.SetWindowPos(
                    hwnd,
                    win32con.HWND_NOTOPMOST,
                    0, 0, 0, 0,
                    win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_SHOWWINDOW,
                )
                log_cb("游戏时间调整完成，已取消窗口置顶")
            except Exception as exc:
                log_cb(f"取消窗口置顶失败: {exc}", "red")

        def task_worker():
            try:
                if p.task_type == TASK_TYPE_TIME_ADJUST:
                    while not stop_event.is_set():
                        apply_time_adjust_resolution()
                        log_cb("开始执行游戏时间调整")
                        时间调整(
                            hwnd,
                            0,
                            False,
                            p.time_adjust_release_pet or p.time_adjust_use_release_pet_recognition,
                            p.time_adjust_use_release_pet_recognition,
                            p.time_adjust_anti_jelly,
                            p.time_adjust_topmost_recognition,
                            p.time_adjust_keep_open,
                            log=log_cb,
                            stop_event=stop_event,
                        )
                        clear_time_adjust_topmost()
                        next_interval_minutes = random.uniform(p.time_adjust_interval_min, p.time_adjust_interval_max)
                        next_interval_seconds = max(1, int(round(next_interval_minutes * 60)))
                        log_cb(f"下一次游戏时间调整将在 {next_interval_seconds // 60}分{next_interval_seconds % 60:02d}秒后执行")
                        if stop_event.wait(next_interval_seconds):
                            return
                else:
                    task_1(
                        hwnd, p.action_key, p.interval_min, p.interval_max, p.task_type,
                        1, p.anti_jelly, p.random_cruise, p.cruise_probability, p.cruise_hold_min,
                        p.cruise_hold_max, p.cruise_space_min, p.cruise_space_max,
                        p.action_jump, stop_event=stop_event, log_callback=log_cb,
                    )
            except Exception as e:
                log_cb(f"任务执行异常: {e}", "red")
            finally:
                QMetaObject.invokeMethod(self, "_on_session_thread_finished", Qt.QueuedConnection, Q_ARG(int, hwnd))

        def monthly_worker():
            try:
                月卡关闭(hwnd, target_minute=p.monthly_card_minute, stop_event=stop_event, log=log_cb)
            except Exception as e:
                log_cb(f"月卡线程异常: {e}", "red")

        t = threading.Thread(target=task_worker, daemon=True)
        mt = threading.Thread(target=monthly_worker, daemon=True) if p.monthly_card_close_enabled else None
        self._sessions[hwnd] = WindowSession(stop_event, t, mt, time.monotonic() + p.duration * 60, True)
        t.start()
        if mt:
            mt.start()
        self.append_log(f"[{self._window_tag(hwnd)}] 窗口任务开始 | 类型={p.task_type}", "green")
        self._refresh_item(hwnd)
        self._refresh_control_state()
        self.start_clicked.emit()

    def _stop_session(self, hwnd: int, manual=False, auto_timeout=False):
        s = self._sessions.get(hwnd)
        if not s or not s.running:
            return
        s.running = False
        s.stop_event.set()
        if manual:
            self.append_log(f"[{self._window_tag(hwnd)}] 窗口任务已停止")
            self.stop_clicked.emit()
        elif auto_timeout:
            self.append_log(f"[{self._window_tag(hwnd)}] 窗口运行时长已到，自动停止")
            p = self._profiles.get(hwnd)
            if p and p.auto_shutdown:
                ShutdownConfirmDialog(self).exec_()
        self._refresh_item(hwnd)
        self._refresh_control_state()

    @pyqtSlot(int)
    def _on_session_thread_finished(self, hwnd: int):
        s = self._sessions.get(hwnd)
        if not s or not s.running:
            return
        s.running = False
        s.stop_event.set()
        self.append_log(f"[{self._window_tag(hwnd)}] 任务线程已结束", "green")
        self._refresh_item(hwnd)
        self._refresh_control_state()

    def _on_ui_tick(self):
        now = time.monotonic()
        for hwnd, s in list(self._sessions.items()):
            if s.running and now >= s.end_monotonic:
                self._stop_session(hwnd, auto_timeout=True)
        self._update_remaining()

    def _update_remaining(self):
        hwnd = self._selected_hwnd
        if hwnd is None:
            self.remaining_time_label.setText("--:--"); return
        s = self._sessions.get(hwnd)
        if not s or not s.running:
            self.remaining_time_label.setText("--:--"); return
        r = max(0, int(s.end_monotonic - time.monotonic()))
        self.remaining_time_label.setText(f"{r // 60:02d}:{r % 60:02d}")

    def _on_apply_window(self):
        hwnd = self._selected_hwnd
        if hwnd is None:
            self.append_log("错误: 未选择窗口", "red"); return
        self._save_ui_to_profile()
        p = self._profiles[hwnd]
        if not win32gui.IsWindow(hwnd):
            self.append_log(f"窗口句柄失效: {hwnd}", "red"); return
        try:
            top = win32con.HWND_TOPMOST if p.force_topmost else win32con.HWND_NOTOPMOST
            win32gui.SetWindowPos(hwnd, top, p.window_x, p.window_y, p.window_width, p.window_height, win32con.SWP_SHOWWINDOW)
            self.append_log(f"已应用窗口参数: {p.window_width}x{p.window_height} @ ({p.window_x},{p.window_y})")
        except Exception as e:
            self.append_log(f"窗口调整失败: {e}", "red")

    def _on_topmost_changed(self, state):
        if self._loading_profile:
            return
        hwnd = self._selected_hwnd
        if hwnd is None or not win32gui.IsWindow(hwnd):
            return
        try:
            win32gui.SetWindowPos(
                hwnd,
                win32con.HWND_TOPMOST if state == Qt.Checked else win32con.HWND_NOTOPMOST,
                0, 0, 0, 0,
                win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_SHOWWINDOW,
            )
        except Exception as e:
            self.append_log(f"置顶切换失败: {e}", "red")
        self._on_profile_changed()

    def _load_profile_to_ui(self):
        hwnd = self._selected_hwnd
        if hwnd is None or hwnd not in self._profiles:
            return
        p = self._profiles[hwnd]; p.normalize()
        self._loading_profile = True
        self.radio_small_account.setChecked(p.task_type == TASK_TYPE_SMALL)
        self.radio_host_action.setChecked(p.task_type == TASK_TYPE_HOST)
        self.radio_time_adjust.setChecked(p.task_type == TASK_TYPE_TIME_ADJUST)
        self.action_key_combo.setCurrentText(p.action_key)
        self.interval_min_spin.setValue(p.interval_min); self.interval_max_spin.setValue(p.interval_max)
        self.duration_spin.setValue(p.duration)
        self._set_time_adjust_interval_ui(p.time_adjust_interval_min, p.time_adjust_interval_max)
        self.time_adjust_release_pet_checkbox.setChecked(p.time_adjust_release_pet)
        self.time_adjust_use_release_pet_recognition_checkbox.setChecked(p.time_adjust_use_release_pet_recognition)
        self.time_adjust_anti_jelly_checkbox.setChecked(p.time_adjust_anti_jelly)
        self.time_adjust_topmost_recognition_checkbox.setChecked(p.time_adjust_topmost_recognition)
        self.time_adjust_exit_interface_checkbox.setChecked(not p.time_adjust_keep_open)
        if (
            self.time_adjust_use_release_pet_recognition_checkbox.isChecked()
            and not self.time_adjust_topmost_recognition_checkbox.isChecked()
        ):
            self.time_adjust_topmost_recognition_checkbox.setChecked(True)
        self.auto_shutdown_checkbox.setChecked(p.auto_shutdown)
        self.window_width_spin.setValue(p.window_width); self.window_height_spin.setValue(p.window_height)
        self.window_x_spin.setValue(p.window_x); self.window_y_spin.setValue(p.window_y)
        self.force_topmost_checkbox.setChecked(p.force_topmost)
        self.anti_jelly_checkbox.setChecked(p.anti_jelly)
        self.random_cruise_checkbox.setChecked(p.random_cruise)
        self.cruise_probability_spin.setValue(p.cruise_probability)
        self.cruise_hold_min_spin.setValue(p.cruise_hold_min); self.cruise_hold_max_spin.setValue(p.cruise_hold_max)
        self.cruise_space_min_spin.setValue(p.cruise_space_min); self.cruise_space_max_spin.setValue(p.cruise_space_max)
        self.action_jump_checkbox.setChecked(p.action_jump)
        self.monthly_card_close_checkbox.setChecked(p.monthly_card_close_enabled)
        self.monthly_card_minute_spin.setValue(p.monthly_card_minute)
        self._on_random_cruise_changed(self.random_cruise_checkbox.checkState())
        self.monthly_card_minute_spin.setEnabled(self.monthly_card_close_checkbox.isChecked())
        self._update_task_type_ui()
        self._loading_profile = False

    def _save_ui_to_profile(self):
        hwnd = self._selected_hwnd
        if hwnd is None or hwnd not in self._profiles:
            return
        p = self._profiles[hwnd]
        if self.radio_small_account.isChecked():
            p.task_type = TASK_TYPE_SMALL
        elif self.radio_host_action.isChecked():
            p.task_type = TASK_TYPE_HOST
        else:
            p.task_type = TASK_TYPE_TIME_ADJUST
        p.action_key = self.action_key_combo.currentText()
        p.interval_min = self.interval_min_spin.value(); p.interval_max = self.interval_max_spin.value()
        p.duration = self.duration_spin.value()
        p.time_adjust_interval_min, p.time_adjust_interval_max = self._get_time_adjust_interval_values()
        p.time_adjust_keep_open = self._is_time_adjust_keep_open_selected()
        p.time_adjust_release_pet = self.time_adjust_release_pet_checkbox.isChecked() and not p.time_adjust_keep_open
        p.time_adjust_use_release_pet_recognition = (
            self.time_adjust_use_release_pet_recognition_checkbox.isChecked() and not p.time_adjust_keep_open
        )
        p.time_adjust_anti_jelly = self.time_adjust_anti_jelly_checkbox.isChecked() and not p.time_adjust_keep_open
        p.time_adjust_topmost_recognition = (
            self.time_adjust_topmost_recognition_checkbox.isChecked()
            or p.time_adjust_use_release_pet_recognition
        )
        p.auto_shutdown = self.auto_shutdown_checkbox.isChecked()
        p.window_width = self.window_width_spin.value(); p.window_height = self.window_height_spin.value()
        p.window_x = self.window_x_spin.value(); p.window_y = self.window_y_spin.value()
        p.force_topmost = self.force_topmost_checkbox.isChecked()
        p.anti_jelly = self.anti_jelly_checkbox.isChecked()
        p.random_cruise = self.random_cruise_checkbox.isChecked()
        p.cruise_probability = self.cruise_probability_spin.value()
        p.cruise_hold_min = self.cruise_hold_min_spin.value(); p.cruise_hold_max = self.cruise_hold_max_spin.value()
        p.cruise_space_min = self.cruise_space_min_spin.value(); p.cruise_space_max = self.cruise_space_max_spin.value()
        p.action_jump = self.action_jump_checkbox.isChecked()
        p.monthly_card_close_enabled = self.monthly_card_close_checkbox.isChecked()
        p.monthly_card_minute = self.monthly_card_minute_spin.value()
        p.normalize(); self.save_config()

    def _refresh_control_state(self):
        sel = self._selected_hwnd is not None
        self.unbind_btn.setEnabled(sel)
        self.apply_window_btn.setEnabled(sel)
        self.force_topmost_checkbox.setEnabled(sel)
        self.start_btn.setEnabled(bool(self._profiles))
        self.stop_btn.setEnabled(any(s.running for s in self._sessions.values()))
        self.bound_count_label.setText(f"已绑定: {self.bound_windows_list.count()}")
        self.running_count_label.setText(str(sum(1 for s in self._sessions.values() if s.running)))

    @pyqtSlot(str)
    def _thread_safe_append_log(self, msg: str):
        if msg.startswith("[COLOR:"):
            i = msg.index("]")
            self.append_log(msg[i + 1 :], msg[7:i])
        else:
            self.append_log(msg)

    def append_log(self, msg: str, color: str = None):
        ts = datetime.now().strftime("%H:%M:%S")
        cursor = self.log_text.textCursor(); cursor.movePosition(QTextCursor.End)
        fmt = QTextCharFormat(); fmt.setForeground(QColor(color) if color else QColor("#d4d4d4"))
        cursor.insertText(f"[{ts}] {msg}\n", fmt)
        self.log_text.setTextCursor(cursor)
        self.log_text.ensureCursorVisible()
    def _qt_key_to_vk(self, key: int) -> Optional[int]:
        if 0x30 <= key <= 0x39 or 0x41 <= key <= 0x5A:
            return key
        if Qt.Key_F1 <= key <= Qt.Key_F24:
            return win32con.VK_F1 + (key - Qt.Key_F1)
        m = {
            Qt.Key_Space: win32con.VK_SPACE,
            Qt.Key_Tab: win32con.VK_TAB,
            Qt.Key_Escape: win32con.VK_ESCAPE,
            Qt.Key_Return: win32con.VK_RETURN,
            Qt.Key_Enter: win32con.VK_RETURN,
            Qt.Key_Delete: win32con.VK_DELETE,
            Qt.Key_Insert: win32con.VK_INSERT,
            Qt.Key_Home: win32con.VK_HOME,
            Qt.Key_End: win32con.VK_END,
            Qt.Key_PageUp: win32con.VK_PRIOR,
            Qt.Key_PageDown: win32con.VK_NEXT,
            Qt.Key_Left: win32con.VK_LEFT,
            Qt.Key_Right: win32con.VK_RIGHT,
            Qt.Key_Up: win32con.VK_UP,
            Qt.Key_Down: win32con.VK_DOWN,
        }
        return m.get(key)

    def _parse_hotkey(self, seq: QKeySequence) -> Optional[Tuple[int, int]]:
        if seq.isEmpty():
            return None
        k = int(seq[0]); mods = 0
        if k & Qt.CTRL: mods |= MOD_CONTROL
        if k & Qt.ALT: mods |= MOD_ALT
        if k & Qt.SHIFT: mods |= MOD_SHIFT
        if k & Qt.META: mods |= MOD_WIN
        base = k & ~(Qt.CTRL | Qt.ALT | Qt.SHIFT | Qt.META)
        vk = self._qt_key_to_vk(base)
        return None if mods == 0 or vk is None else (mods, vk)

    def _register_hotkeys(self):
        self._unregister_hotkeys()
        start = self._parse_hotkey(self._start_hotkey_seq)
        stop = self._parse_hotkey(self._stop_hotkey_seq)
        if not start or not stop:
            self.append_log("热键格式无效，需要修饰键(Ctrl/Alt/Shift/Win)", "red")
            return
        u = ctypes.windll.user32
        hwnd = int(self.winId())
        ok1 = bool(u.RegisterHotKey(hwnd, HOTKEY_ID_START, start[0], start[1]))
        ok2 = bool(u.RegisterHotKey(hwnd, HOTKEY_ID_STOP, stop[0], stop[1]))
        if not ok1 or not ok2:
            err = ctypes.get_last_error()
            if ok1: u.UnregisterHotKey(hwnd, HOTKEY_ID_START)
            if ok2: u.UnregisterHotKey(hwnd, HOTKEY_ID_STOP)
            self.append_log(f"全局热键注册失败，可能冲突 (err={err})", "red")
            return
        self.append_log(
            "热键已生效: 开始=" + self._start_hotkey_seq.toString(QKeySequence.NativeText)
            + " | 停止=" + self._stop_hotkey_seq.toString(QKeySequence.NativeText),
            "green",
        )

    def _unregister_hotkeys(self):
        u = ctypes.windll.user32
        hwnd = int(self.winId())
        u.UnregisterHotKey(hwnd, HOTKEY_ID_START)
        u.UnregisterHotKey(hwnd, HOTKEY_ID_STOP)

    def _on_apply_hotkeys(self):
        self._start_hotkey_seq = self.start_hotkey_edit.keySequence()
        self._stop_hotkey_seq = self.stop_hotkey_edit.keySequence()
        self._register_hotkeys()
        self.save_config()

    def _hotkey_start_selected(self):
        self._on_start_clicked()

    def _hotkey_stop_selected(self):
        self._on_stop_clicked()

    def nativeEvent(self, eventType, message):
        if eventType in ("windows_generic_MSG", "windows_dispatcher_MSG"):
            msg = ctypes.wintypes.MSG.from_address(int(message))
            if msg.message == win32con.WM_HOTKEY:
                wid = int(msg.wParam)
                if wid == HOTKEY_ID_START: QTimer.singleShot(0, self._hotkey_start_selected)
                elif wid == HOTKEY_ID_STOP: QTimer.singleShot(0, self._hotkey_stop_selected)
                return True, 0
        return super().nativeEvent(eventType, message)

    def save_config(self):
        p = get_config_file_path()
        data = {
            "hotkeys": {
                "start": self._start_hotkey_seq.toString(QKeySequence.PortableText),
                "stop": self._stop_hotkey_seq.toString(QKeySequence.PortableText),
            },
            "window_profiles": {str(hwnd): prof.to_dict() for hwnd, prof in self._profiles.items()},
        }
        with open(p, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load_config(self):
        p = get_config_file_path()
        if not p.exists():
            return
        try:
            with open(p, "r", encoding="utf-8") as f:
                d = json.load(f)
        except Exception as e:
            self.append_log(f"读取配置失败: {e}", "red")
            return
        if isinstance(d, dict) and "window_profiles" in d:
            hk = d.get("hotkeys", {})
            s = hk.get("start", "")
            t = hk.get("stop", "")
            if s:
                self._start_hotkey_seq = QKeySequence(s, QKeySequence.PortableText)
                self.start_hotkey_edit.setKeySequence(self._start_hotkey_seq)
            if t:
                self._stop_hotkey_seq = QKeySequence(t, QKeySequence.PortableText)
                self.stop_hotkey_edit.setKeySequence(self._stop_hotkey_seq)
            for k, v in d.get("window_profiles", {}).items():
                try:
                    hwnd = int(k)
                except Exception:
                    continue
                self._profiles[hwnd] = WindowProfile.from_dict(v or {})
                it = QListWidgetItem(self._item_text(hwnd)); it.setData(Qt.UserRole, hwnd)
                self.bound_windows_list.addItem(it)
        else:
            self._legacy_default = WindowProfile.from_dict(d if isinstance(d, dict) else {})
        if self.bound_windows_list.count() > 0:
            self.bound_windows_list.setCurrentRow(0)

    def closeEvent(self, event):
        for hwnd in list(self._sessions.keys()):
            self._stop_session(hwnd, manual=False)
        self._unregister_hotkeys()
        self.save_config()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    authorized, result = check_license()
    if not authorized:
        dlg = LicenseDialog(result)
        if dlg.exec_() == QDialog.Rejected:
            sys.exit(0)
        sys.exit(0)

    try:
        is_admin = ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        is_admin = False
    if not is_admin:
        QMessageBox.warning(None, "提示", "请右键程序图标，选择「以管理员身份运行」。")

    w = MainWindow(target_class_name="UnrealWindow")
    w.show()
    sys.exit(app.exec_())
