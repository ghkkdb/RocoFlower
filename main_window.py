"""
项目主窗口GUI模块。

提供图形用户界面，包含窗口选择、任务控制、配置选项和日志显示功能。
"""
import sys
import os
import json
import threading
import time
import ctypes
from datetime import datetime, timedelta
from pathlib import Path
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QRadioButton, QButtonGroup,
    QGroupBox, QTextEdit, QComboBox, QSpinBox, QApplication,
    QCheckBox, QMessageBox, QDialog, QLineEdit, QDoubleSpinBox
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QMetaObject, Q_ARG, pyqtSlot
from PyQt5.QtGui import QTextCursor

import win32gui
import win32con

from drag_window_picker import DragWindowPicker
from task import task_1
from auth import check_license, get_machine_id


def get_app_dir() -> Path:
    """
    获取应用程序目录路径，兼容打包后的exe。
    Returns:
        Path: 应用程序所在目录
    """
    if getattr(sys, 'frozen', False) or hasattr(sys, 'frozen'):
        try:
            buf = ctypes.create_unicode_buffer(260)
            ctypes.windll.kernel32.GetModuleFileNameW(None, buf, 260)
            return Path(buf.value).parent
        except Exception:
            pass
    try:
        buf = ctypes.create_unicode_buffer(260)
        ctypes.windll.kernel32.GetModuleFileNameW(None, buf, 260)
        exe_path = Path(buf.value)
        if exe_path.suffix.lower() == '.exe':
            return exe_path.parent
    except Exception:
        pass
    return Path(__file__).parent


def get_config_file_path() -> Path:
    """
    获取配置文件路径。
    Returns:
        Path: 配置文件完整路径
    """
    return get_app_dir() / "config.json"


class LicenseDialog(QDialog):
    """
    授权验证对话框。
    
    显示机器码并提示用户获取授权。
    """
    
    def __init__(self, result: str, parent=None):
        """
        初始化授权对话框。
        Args:
            result: 授权验证结果，可能包含错误类型前缀
            parent: 父窗口
        """
        super().__init__(parent)
        self.setWindowTitle("授权验证")
        self.setFixedSize(400, 220)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        error_type = None
        machine_id = result
        
        if result.startswith("ERROR:"):
            error_type = "ERROR"
            error_msg = result[6:]
            info_label = QLabel(f"系统环境异常，无法验证授权：\n\n{error_msg}")
            info_label.setWordWrap(True)
            info_label.setStyleSheet("color: #D32F2F;")
            layout.addWidget(info_label)
            
            self.machine_id_edit = None
            btn_layout = QHBoxLayout()
            btn_layout.addStretch()
            close_btn = QPushButton("关闭")
            close_btn.setFixedWidth(80)
            close_btn.clicked.connect(self.reject)
            btn_layout.addWidget(close_btn)
            layout.addLayout(btn_layout)
            return
            
        elif result.startswith("FORMAT:"):
            error_type = "FORMAT"
            machine_id = result[7:]
            info_text = "授权文件格式错误，请重新获取授权文件："
            
        elif result.startswith("SIGNATURE:"):
            error_type = "SIGNATURE"
            machine_id = result[10:]
            info_text = "授权文件签名无效（可能被篡改），请重新获取授权文件："
            
        else:
            info_text = "程序未授权，请将以下机器码发送给开发者获取授权文件："
        
        info_label = QLabel(info_text)
        info_label.setWordWrap(True)
        if error_type:
            info_label.setStyleSheet("color: #D32F2F;")
        else:
            info_label.setStyleSheet("color: #333;")
        layout.addWidget(info_label)
        
        self.machine_id_edit = QLineEdit(machine_id)
        self.machine_id_edit.setAlignment(Qt.AlignCenter)
        self.machine_id_edit.setReadOnly(True)
        self.machine_id_edit.setStyleSheet("""
            QLineEdit {
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 18px;
                font-weight: bold;
                padding: 8px;
                background-color: #f5f5f5;
                border: 2px solid #ddd;
                border-radius: 4px;
            }
        """)
        layout.addWidget(self.machine_id_edit)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        copy_btn = QPushButton("复制机器码")
        copy_btn.setFixedWidth(100)
        copy_btn.clicked.connect(self._copy_machine_id)
        btn_layout.addWidget(copy_btn)
        
        close_btn = QPushButton("关闭")
        close_btn.setFixedWidth(80)
        close_btn.clicked.connect(self.reject)
        btn_layout.addWidget(close_btn)
        
        layout.addLayout(btn_layout)
    
    def _copy_machine_id(self):
        """复制机器码到剪贴板。"""
        if self.machine_id_edit:
            clipboard = QApplication.clipboard()
            clipboard.setText(self.machine_id_edit.text())
            QMessageBox.information(self, "提示", "机器码已复制到剪贴板")


class ShutdownConfirmDialog(QDialog):
    """
    关机确认对话框。
    
    显示倒计时，用户可选择立即关机或取消。
    2分钟无操作则自动关机。
    """
    
    def __init__(self, parent=None):
        """
        初始化关机确认对话框。
        Args:
            parent: 父窗口
        """
        super().__init__(parent)
        self.setWindowTitle("关机确认")
        self.setFixedSize(400, 200)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        
        self._countdown_seconds = 120
        self._shutdown_triggered = False
        
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        self.info_label = QLabel("任务已完成，是否确认关机？")
        self.info_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        self.info_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.info_label)
        
        self.countdown_label = QLabel(f"倒计时: {self._countdown_seconds} 秒")
        self.countdown_label.setStyleSheet("font-size: 14px; color: #d32f2f;")
        self.countdown_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.countdown_label)
        
        self.hint_label = QLabel("2分钟内无操作将自动关机")
        self.hint_label.setStyleSheet("color: gray;")
        self.hint_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.hint_label)
        
        btn_layout = QHBoxLayout()
        
        self.shutdown_btn = QPushButton("立即关机")
        self.shutdown_btn.setFixedWidth(120)
        self.shutdown_btn.clicked.connect(self._on_shutdown_now)
        btn_layout.addWidget(self.shutdown_btn)
        
        btn_layout.addStretch()
        
        self.cancel_btn = QPushButton("取消关机")
        self.cancel_btn.setFixedWidth(100)
        self.cancel_btn.clicked.connect(self._on_cancel)
        btn_layout.addWidget(self.cancel_btn)
        
        layout.addLayout(btn_layout)
        
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_countdown)
        self._timer.start(1000)
    
    def _update_countdown(self):
        """更新倒计时。"""
        self._countdown_seconds -= 1
        self.countdown_label.setText(f"倒计时: {self._countdown_seconds} 秒")
        
        if self._countdown_seconds <= 0:
            self._timer.stop()
            self._execute_shutdown()
    
    def _on_shutdown_now(self):
        """立即关机。"""
        self._timer.stop()
        self._execute_shutdown()
    
    def _on_cancel(self):
        """取消关机。"""
        self._timer.stop()
        self.reject()
    
    def _execute_shutdown(self):
        """执行关机。"""
        if self._shutdown_triggered:
            return
        self._shutdown_triggered = True
        
        try:
            os.system("shutdown /s /t 60")
        except Exception:
            pass
        
        self.accept()


class MainWindow(QMainWindow):
    """
    项目主窗口类。
    
    信号：
        start_clicked: 开始按钮点击时触发
        stop_clicked: 停止按钮点击时触发
    """
    
    start_clicked = pyqtSignal()
    stop_clicked = pyqtSignal()
    
    def __init__(self, target_class_name: str = "UnrealWindow"):
        """
        初始化主窗口。
        Args:
            target_class_name: 目标窗口类名
        """
        super().__init__()
        
        self._target_class_name = target_class_name
        self._bound_hwnd: int = 0
        self._is_running: bool = False
        
        self._task_thread: threading.Thread = None
        self._stop_event: threading.Event = threading.Event()
        
        self._start_time: datetime = None
        self._remaining_seconds: int = 0
        
        self._init_ui()
        self._connect_signals()
        
        self._countdown_timer = QTimer(self)
        self._countdown_timer.timeout.connect(self._update_countdown)
        
        self.load_config()
    
    def _init_ui(self):
        """初始化用户界面。"""
        self.setWindowTitle("RocoFlower V2.4.5")
        self.setMinimumSize(700, 600)
        self.resize(800, 700)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        top_layout = QHBoxLayout()
        top_layout.addWidget(self._create_window_picker_group())
        top_layout.addWidget(self._create_control_group())
        main_layout.addLayout(top_layout)
        
        main_layout.addWidget(self._create_config_group())
        
        main_layout.addWidget(self._create_window_control_group())
        
        main_layout.addWidget(self._create_log_group(), 1)
    
    def _create_window_picker_group(self) -> QGroupBox:
        """
        创建窗口选择区域。
        Returns:
            QGroupBox: 窗口选择分组框
        """
        group = QGroupBox("窗口选择")
        layout = QHBoxLayout(group)
        
        self.window_picker = DragWindowPicker(
            target_class_name=self._target_class_name
        )
        layout.addWidget(self.window_picker.get_button())
        
        self.unbind_btn = QPushButton("解绑")
        self.unbind_btn.setMinimumWidth(60)
        self.unbind_btn.setEnabled(False)
        layout.addWidget(self.unbind_btn)
        
        self.window_status_label = QLabel("未绑定窗口")
        self.window_status_label.setStyleSheet("color: gray;")
        layout.addWidget(self.window_status_label)
        
        layout.addStretch()
        
        return group
    
    def _create_control_group(self) -> QGroupBox:
        """
        创建控制按钮区域。
        Returns:
            QGroupBox: 控制按钮分组框
        """
        group = QGroupBox("控制")
        layout = QHBoxLayout(group)
        
        self.start_btn = QPushButton("开始")
        self.start_btn.setMinimumWidth(80)
        self.start_btn.setEnabled(False)
        layout.addWidget(self.start_btn)
        
        self.stop_btn = QPushButton("停止")
        self.stop_btn.setMinimumWidth(80)
        self.stop_btn.setEnabled(False)
        layout.addWidget(self.stop_btn)
        
        layout.addSpacing(20)
        
        layout.addWidget(QLabel("剩余时间:"))
        self.remaining_time_label = QLabel("--:--")
        self.remaining_time_label.setStyleSheet("font-weight: bold; color: blue;")
        layout.addWidget(self.remaining_time_label)
        
        layout.addStretch()
        
        self.help_btn = QPushButton("点击查看使用手册")
        self.help_btn.setMinimumWidth(80)
        layout.addWidget(self.help_btn)
        
        return group
    
    def _create_config_group(self) -> QGroupBox:
        """
        创建任务配置区域。
        Returns:
            QGroupBox: 任务配置分组框
        """
        group = QGroupBox("任务配置")
        layout = QVBoxLayout(group)
        
        row1_layout = QHBoxLayout()
        
        row1_layout.addWidget(QLabel("任务类型:"))
        
        self.task_type_group = QButtonGroup(self)
        
        self.radio_small_account = QRadioButton("小号做动作(动作+跳)")
        self.radio_host_action = QRadioButton("房主同乘做动作")
        
        self.task_type_group.addButton(self.radio_small_account, 0)
        self.task_type_group.addButton(self.radio_host_action, 1)
        
        self.radio_small_account.setChecked(True)
        
        row1_layout.addWidget(self.radio_small_account)
        row1_layout.addWidget(self.radio_host_action)
        
        row1_layout.addSpacing(30)
        
        row1_layout.addWidget(QLabel("动作按键:"))
        self.action_key_combo = QComboBox()
        self.action_key_combo.addItems([str(i) for i in range(1, 6)])
        self.action_key_combo.setCurrentIndex(1)
        self.action_key_combo.setMinimumWidth(60)
        row1_layout.addWidget(self.action_key_combo)
        
        row1_layout.addSpacing(20)
        
        row1_layout.addWidget(QLabel("动作间隔(秒):"))
        row1_layout.addWidget(QLabel("最小"))
        self.interval_min_spin = QSpinBox()
        self.interval_min_spin.setRange(8, 30)
        self.interval_min_spin.setValue(8)
        self.interval_min_spin.setMinimumWidth(60)
        row1_layout.addWidget(self.interval_min_spin)
        
        row1_layout.addWidget(QLabel("最大"))
        self.interval_max_spin = QSpinBox()
        self.interval_max_spin.setRange(9, 30)
        self.interval_max_spin.setValue(20)
        self.interval_max_spin.setMinimumWidth(60)
        row1_layout.addWidget(self.interval_max_spin)
        
        row1_layout.addStretch()
        
        layout.addLayout(row1_layout)
        
        row2_layout = QHBoxLayout()
        
        row2_layout.addWidget(QLabel("运行时长(分钟):"))
        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(1, 60000)
        self.duration_spin.setValue(60)
        self.duration_spin.setMinimumWidth(60)
        row2_layout.addWidget(self.duration_spin)
        
        row2_layout.addSpacing(30)
        
        self.auto_shutdown_checkbox = QCheckBox("任务完成后自动关机")
        self.auto_shutdown_checkbox.setChecked(False)
        
        row2_layout.addWidget(self.auto_shutdown_checkbox)
        
        row2_layout.addStretch()
        
        layout.addLayout(row2_layout)
        
        row3_layout = QHBoxLayout()
        
        self.random_cruise_checkbox = QCheckBox("随机巡航")
        self.random_cruise_checkbox.setChecked(False)
        self.random_cruise_checkbox.stateChanged.connect(self._on_random_cruise_changed)
        row3_layout.addWidget(self.random_cruise_checkbox)
        
        row3_layout.addSpacing(20)
        
        row3_layout.addWidget(QLabel("巡航触发概率:"))
        self.cruise_probability_spin = QSpinBox()
        self.cruise_probability_spin.setRange(1, 100)
        self.cruise_probability_spin.setValue(22)
        self.cruise_probability_spin.setSuffix("%")
        self.cruise_probability_spin.setMinimumWidth(70)
        row3_layout.addWidget(self.cruise_probability_spin)
        
        row3_layout.addSpacing(20)
        
        row3_layout.addWidget(QLabel("移动时长:"))
        self.cruise_hold_min_spin = QDoubleSpinBox()
        self.cruise_hold_min_spin.setRange(0, 0.5)
        self.cruise_hold_min_spin.setValue(0.2)
        self.cruise_hold_min_spin.setSingleStep(0.1)
        self.cruise_hold_min_spin.setMinimumWidth(60)
        row3_layout.addWidget(self.cruise_hold_min_spin)
        
        row3_layout.addWidget(QLabel("-"))
        
        self.cruise_hold_max_spin = QDoubleSpinBox()
        self.cruise_hold_max_spin.setRange(0, 0.5)
        self.cruise_hold_max_spin.setValue(0.4)
        self.cruise_hold_max_spin.setSingleStep(0.1)
        self.cruise_hold_max_spin.setMinimumWidth(60)
        row3_layout.addWidget(self.cruise_hold_max_spin)
        
        row3_layout.addWidget(QLabel("秒"))
        
        row3_layout.addSpacing(20)
        
        row3_layout.addWidget(QLabel("空格次数:"))
        self.cruise_space_min_spin = QSpinBox()
        self.cruise_space_min_spin.setRange(0,2)
        self.cruise_space_min_spin.setValue(0)
        self.cruise_space_min_spin.setMinimumWidth(50)
        row3_layout.addWidget(self.cruise_space_min_spin)
        
        row3_layout.addWidget(QLabel("-"))
        
        self.cruise_space_max_spin = QSpinBox()
        self.cruise_space_max_spin.setRange(0,2)
        self.cruise_space_max_spin.setValue(1)
        self.cruise_space_max_spin.setMinimumWidth(50)
        row3_layout.addWidget(self.cruise_space_max_spin)
        
        row3_layout.addWidget(QLabel("次"))
        
        row3_layout.addStretch()
        
        layout.addLayout(row3_layout)
        
        return group
    
    def _on_random_cruise_changed(self, state):
        """
        随机巡航复选框状态改变处理。
        Args:
            state: 复选框状态
        """
        enabled = state == Qt.Checked
        self.cruise_probability_spin.setEnabled(enabled)
        self.cruise_hold_min_spin.setEnabled(enabled)
        self.cruise_hold_max_spin.setEnabled(enabled)
        self.cruise_space_min_spin.setEnabled(enabled)
        self.cruise_space_max_spin.setEnabled(enabled)
    
    def _create_window_control_group(self) -> QGroupBox:
        """
        创建窗口控制区域。
        Returns:
            QGroupBox: 窗口控制分组框
        """
        group = QGroupBox("窗口控制")
        layout = QHBoxLayout(group)
        
        layout.addWidget(QLabel("宽度:"))
        self.window_width_spin = QSpinBox()
        self.window_width_spin.setRange(400, 3840)
        self.window_width_spin.setValue(1280)
        self.window_width_spin.setMinimumWidth(80)
        layout.addWidget(self.window_width_spin)
        
        layout.addSpacing(10)
        
        layout.addWidget(QLabel("高度:"))
        self.window_height_spin = QSpinBox()
        self.window_height_spin.setRange(300, 2160)
        self.window_height_spin.setValue(720)
        self.window_height_spin.setMinimumWidth(80)
        layout.addWidget(self.window_height_spin)
        
        layout.addSpacing(20)
        
        layout.addWidget(QLabel("X:"))
        self.window_x_spin = QSpinBox()
        self.window_x_spin.setRange(0, 3840)
        self.window_x_spin.setValue(0)
        self.window_x_spin.setMinimumWidth(80)
        layout.addWidget(self.window_x_spin)
        
        layout.addSpacing(10)
        
        layout.addWidget(QLabel("Y:"))
        self.window_y_spin = QSpinBox()
        self.window_y_spin.setRange(0, 2160)
        self.window_y_spin.setValue(0)
        self.window_y_spin.setMinimumWidth(80)
        layout.addWidget(self.window_y_spin)
        
        layout.addSpacing(20)
        
        self.apply_window_btn = QPushButton("应用")
        self.apply_window_btn.setMinimumWidth(60)
        self.apply_window_btn.setEnabled(False)
        layout.addWidget(self.apply_window_btn)
        
        layout.addSpacing(20)
        
        self.force_topmost_checkbox = QCheckBox("强制置顶")
        self.force_topmost_checkbox.setEnabled(False)
        layout.addWidget(self.force_topmost_checkbox)
        
        layout.addStretch()
        
        return group
    
    def _create_log_group(self) -> QGroupBox:
        """
        创建日志显示区域。
        Returns:
            QGroupBox: 日志显示分组框
        """
        group = QGroupBox("日志信息")
        layout = QVBoxLayout(group)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet("background-color: #1e1e1e; color: #d4d4d4; font-family: Consolas;")
        layout.addWidget(self.log_text)
        
        return group
    
    def _connect_signals(self):
        """连接信号槽。"""
        self.window_picker.window_picked.connect(self._on_window_picked)
        self.window_picker.pick_failed.connect(self._on_pick_failed)
        self.window_picker.pick_status.connect(self._on_pick_status)
        
        self.start_btn.clicked.connect(self._on_start_clicked)
        self.stop_btn.clicked.connect(self._on_stop_clicked)
        self.apply_window_btn.clicked.connect(self._on_apply_window)
        self.unbind_btn.clicked.connect(self._on_unbind_clicked)
        self.help_btn.clicked.connect(self._on_help_clicked)
        self.force_topmost_checkbox.stateChanged.connect(self._on_topmost_changed)
    
    def _on_window_picked(self, hwnd: int):
        """
        窗口选择成功处理。
        Args:
            hwnd: 窗口句柄
        """
        self._bound_hwnd = hwnd
        
        try:
            window_title = win32gui.GetWindowText(hwnd)
            class_name = win32gui.GetClassName(hwnd)
            rect = win32gui.GetWindowRect(hwnd)
            width = rect[2] - rect[0]
            height = rect[3] - rect[1]
        except Exception:
            window_title = "未知"
            class_name = "未知"
            width = 0
            height = 0
        
        self.window_status_label.setText(f"已绑定: {hwnd}")
        self.window_status_label.setStyleSheet("color: green;")
        self.window_picker.get_button().setEnabled(False)
        self.unbind_btn.setEnabled(True)
        self.start_btn.setEnabled(True)
        self.apply_window_btn.setEnabled(True)
        self.force_topmost_checkbox.setEnabled(True)
        
        try:
            win32gui.SetWindowPos(
                self._bound_hwnd,
                win32con.HWND_NOTOPMOST,
                0, 0, 0, 0,
                win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_SHOWWINDOW
            )
        except Exception:
            pass
        
        self.append_log(f"成功绑定窗口")
        self.append_log(f"  句柄: {hwnd}")
        self.append_log(f"  标题: {window_title}")
        self.append_log(f"  类名: {class_name}")
        self.append_log(f"  尺寸: {width}x{height}")
    
    def _on_pick_failed(self):
        """窗口选择失败处理。"""
        self._bound_hwnd = 0
        
        self.window_status_label.setText("窗口选择失败，请重试")
        self.window_status_label.setStyleSheet("color: red;")
        self.window_picker.get_button().setEnabled(True)
        self.unbind_btn.setEnabled(False)
        self.start_btn.setEnabled(False)
        self.apply_window_btn.setEnabled(False)
        self.force_topmost_checkbox.setEnabled(False)
        
        self.append_log("窗口选择失败，请重新绑定窗口")
    
    def _on_pick_status(self, message: str):
        """
        窗口选择状态更新处理。
        Args:
            message: 状态消息
        """
        self.append_log(message)
    
    def _on_unbind_clicked(self):
        """解绑按钮点击处理。"""
        if self._is_running:
            self._stop_task()
            self.append_log("任务已停止")
        
        self._bound_hwnd = 0
        
        self.window_status_label.setText("未绑定窗口")
        self.window_status_label.setStyleSheet("color: gray;")
        self.window_picker.get_button().setEnabled(True)
        self.unbind_btn.setEnabled(False)
        self.start_btn.setEnabled(False)
        self.apply_window_btn.setEnabled(False)
        self.force_topmost_checkbox.setEnabled(False)
        
        self.append_log("已解绑窗口")
    
    def _on_help_clicked(self):
        """使用说明按钮点击处理。"""
        import webbrowser
        url = "https://wcn33wxdu7tm.feishu.cn/wiki/YGWiwIhsyio98NkiV95cpIcsnAc"
        try:
            webbrowser.open(url)
        except Exception as e:
            self.append_log(f"打开链接失败: {str(e)}")
    
    def _on_start_clicked(self):
        """开始按钮点击处理。"""
        if self._is_running:
            return
        
        if self._bound_hwnd == 0:
            self.append_log("错误: 未绑定窗口")
            return
        
        if self.interval_min_spin.value() > self.interval_max_spin.value():
            self.append_log(f"警告: 动作间隔最小值({self.interval_min_spin.value()})大于最大值({self.interval_max_spin.value()})，已自动交换", color="red")
            min_val = self.interval_min_spin.value()
            max_val = self.interval_max_spin.value()
            self.interval_min_spin.setValue(max_val)
            self.interval_max_spin.setValue(min_val)
        
        if self.random_cruise_checkbox.isChecked():
            if self.cruise_hold_min_spin.value() > self.cruise_hold_max_spin.value():
                self.append_log(f"警告: 长按时长最小值({self.cruise_hold_min_spin.value()})大于最大值({self.cruise_hold_max_spin.value()})，已自动交换", color="red")
                min_val = self.cruise_hold_min_spin.value()
                max_val = self.cruise_hold_max_spin.value()
                self.cruise_hold_min_spin.setValue(max_val)
                self.cruise_hold_max_spin.setValue(min_val)
            
            if self.cruise_space_min_spin.value() > self.cruise_space_max_spin.value():
                self.append_log(f"警告: 空格次数最小值({self.cruise_space_min_spin.value()})大于最大值({self.cruise_space_max_spin.value()})，已自动交换", color="red")
                min_val = self.cruise_space_min_spin.value()
                max_val = self.cruise_space_max_spin.value()
                self.cruise_space_min_spin.setValue(max_val)
                self.cruise_space_max_spin.setValue(min_val)
        
        self._is_running = True
        self._stop_event.clear()
        
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.unbind_btn.setEnabled(False)
        self.apply_window_btn.setEnabled(False)
        self._set_config_enabled(False)
        
        self._start_time = datetime.now()
        self._remaining_seconds = self.duration_spin.value() * 60
        self._countdown_timer.start(1000)
        
        config_info = self._get_config_info()
        self.append_log(f"任务开始运行 | {config_info}")
        
        self._start_task_thread()
        
        self.start_clicked.emit()
    
    def _on_stop_clicked(self):
        """停止按钮点击处理。"""
        if not self._is_running:
            return
        
        self._stop_task(auto_shutdown=False)
        
        self.append_log("任务已停止")
        self.stop_clicked.emit()
    
    def _stop_task(self, auto_shutdown: bool = True):
        """
        停止任务。
        
        Args:
            auto_shutdown: 是否触发自动关机流程（倒计时结束时为True，手动停止为False）
        """
        self._is_running = False
        self._stop_event.set()
        self._countdown_timer.stop()
        
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.unbind_btn.setEnabled(True)
        self.apply_window_btn.setEnabled(True)
        self._set_config_enabled(True)
        
        self.remaining_time_label.setText("--:--")
        
        if auto_shutdown and self.auto_shutdown_checkbox.isChecked():
            self._show_shutdown_confirm()
    
    def _show_shutdown_confirm(self):
        """显示关机确认对话框。"""
        dialog = ShutdownConfirmDialog(self)
        dialog.exec_()
    
    def _execute_shutdown(self):
        """执行系统关机。"""
        try:
            os.system("shutdown /s /t 60")
            self.append_log("系统将在60秒后关机，如需取消请运行: shutdown /a")
        except Exception as e:
            self.append_log(f"关机命令执行失败: {str(e)}")
    
    def _start_task_thread(self):
        """启动任务线程。"""
        config = self.get_config()
        
        def log_callback(message, color=None):
            if color:
                message = f"[COLOR:{color}]{message}"
            QMetaObject.invokeMethod(
                self,
                "_thread_safe_append_log",
                Qt.QueuedConnection,
                Q_ARG(str, message)
            )
        
        def task_wrapper():
            try:
                task_1(
                    hwnd=self._bound_hwnd,
                    动作=config["action_key"],
                    间隔_min=config["interval_min"],
                    间隔_max=config["interval_max"],
                    任务类型=config["task_type"],
                    随机巡航=config.get("random_cruise", False),
                    巡航概率=config.get("cruise_probability", 50),
                    长按最小=config.get("cruise_hold_min", 0.5),
                    长按最大=config.get("cruise_hold_max", 1.0),
                    空格最小=config.get("cruise_space_min", 1),
                    空格最大=config.get("cruise_space_max", 2),
                    stop_event=self._stop_event,
                    log_callback=log_callback
                )
            except Exception as e:
                log_callback(f"任务执行异常: {e}")
        
        self._task_thread = threading.Thread(target=task_wrapper, daemon=True)
        self._task_thread.start()
    
    @pyqtSlot(str)
    def _thread_safe_append_log(self, message: str):
        """
        线程安全的日志追加方法。
        Args:
            message: 日志消息（可能包含颜色标记）
        """
        if message.startswith("[COLOR:"):
            end_idx = message.index("]")
            color = message[7:end_idx]
            actual_message = message[end_idx + 1:]
            self.append_log(actual_message, color=color)
        else:
            self.append_log(message)
    
    def _update_countdown(self):
        """更新倒计时显示。"""
        if self._remaining_seconds > 0:
            self._remaining_seconds -= 1
            minutes = self._remaining_seconds // 60
            seconds = self._remaining_seconds % 60
            self.remaining_time_label.setText(f"{minutes:02d}:{seconds:02d}")
        else:
            self._countdown_timer.stop()
            if self._is_running:
                self.append_log("运行时长已到，自动停止任务")
                self._stop_task()
    
    def _on_apply_window(self):
        """应用窗口设置。"""
        if self._bound_hwnd == 0:
            self.append_log("错误: 未绑定窗口")
            return
        
        try:
            width = self.window_width_spin.value()
            height = self.window_height_spin.value()
            x = self.window_x_spin.value()
            y = self.window_y_spin.value()
            
            if self.force_topmost_checkbox.isChecked():
                hwnd_insert_after = win32con.HWND_TOPMOST
            else:
                hwnd_insert_after = win32con.HWND_NOTOPMOST
            
            win32gui.SetWindowPos(
                self._bound_hwnd,
                hwnd_insert_after,
                x, y,
                width, height,
                win32con.SWP_SHOWWINDOW
            )
            
            self.append_log(f"窗口已调整: {width}x{height} @ ({x}, {y})")
        except Exception as e:
            self.append_log(f"窗口调整失败: {str(e)}")
    
    def _on_topmost_changed(self, state):
        """
        置顶状态切换处理。
        Args:
            state: 复选框状态
        """
        if self._bound_hwnd == 0:
            return
        
        try:
            if state == Qt.Checked:
                win32gui.SetWindowPos(
                    self._bound_hwnd,
                    win32con.HWND_TOPMOST,
                    0, 0, 0, 0,
                    win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_SHOWWINDOW
                )
                self.append_log("窗口已置顶")
            else:
                win32gui.SetWindowPos(
                    self._bound_hwnd,
                    win32con.HWND_NOTOPMOST,
                    0, 0, 0, 0,
                    win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_SHOWWINDOW
                )
                self.append_log("窗口已取消置顶")
        except Exception as e:
            self.append_log(f"置顶切换失败: {str(e)}")
    
    def _set_config_enabled(self, enabled: bool):
        """
        设置配置区域启用状态。
        Args:
            enabled: 是否启用
        """
        self.radio_small_account.setEnabled(enabled)
        self.radio_host_action.setEnabled(enabled)
        self.action_key_combo.setEnabled(enabled)
        self.interval_min_spin.setEnabled(enabled)
        self.interval_max_spin.setEnabled(enabled)
        self.duration_spin.setEnabled(enabled)
        self.auto_shutdown_checkbox.setEnabled(enabled)
        self.window_width_spin.setEnabled(enabled)
        self.window_height_spin.setEnabled(enabled)
        self.window_x_spin.setEnabled(enabled)
        self.window_y_spin.setEnabled(enabled)
        self.random_cruise_checkbox.setEnabled(enabled)
        if enabled:
            self._on_random_cruise_changed(self.random_cruise_checkbox.checkState())
        else:
            self.cruise_probability_spin.setEnabled(False)
            self.cruise_hold_min_spin.setEnabled(False)
            self.cruise_hold_max_spin.setEnabled(False)
            self.cruise_space_min_spin.setEnabled(False)
            self.cruise_space_max_spin.setEnabled(False)
    
    def _get_config_info(self) -> str:
        """
        获取当前配置信息。
        Returns:
            str: 配置信息字符串
        """
        task_type = "小号做动作" if self.radio_small_account.isChecked() else "房主同乘做动作"
        action_key = self.action_key_combo.currentText()
        interval_min = self.interval_min_spin.value()
        interval_max = self.interval_max_spin.value()
        duration = self.duration_spin.value()
        auto_shutdown = "是" if self.auto_shutdown_checkbox.isChecked() else "否"
        random_cruise = "是" if self.random_cruise_checkbox.isChecked() else "否"
        return f"类型: {task_type} | 按键: {action_key} | 间隔: {interval_min}-{interval_max}秒 | 时长: {duration}分钟 | 自动关机: {auto_shutdown} | 随机巡航: {random_cruise}"
    
    def append_log(self, message: str, color: str = None):
        """
        追加日志信息。
        Args:
            message: 日志消息
            color: 文字颜色（可选，如 'red', 'green' 等）
        """
        from PyQt5.QtGui import QTextCharFormat, QColor
        
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        
        cursor = self.log_text.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.log_text.setTextCursor(cursor)
        
        char_format = QTextCharFormat()
        if color:
            char_format.setForeground(QColor(color))
        else:
            char_format.setForeground(QColor("#d4d4d4"))
        
        cursor.insertText(log_entry + "\n", char_format)
        
        cursor.movePosition(QTextCursor.End)
        self.log_text.setTextCursor(cursor)
    
    def get_bound_hwnd(self) -> int:
        """
        获取已绑定的窗口句柄。
        Returns:
            int: 窗口句柄，未绑定时返回0
        """
        return self._bound_hwnd
    
    def is_running(self) -> bool:
        """
        获取任务运行状态。
        Returns:
            bool: 是否正在运行
        """
        return self._is_running
    
    def get_config(self) -> dict:
        """
        获取当前配置状态。
        Returns:
            dict: 配置字典
        """
        task_type = "小号做动作" if self.radio_small_account.isChecked() else "房主同乘做动作"
        action_key = self.action_key_combo.currentText()
        interval_min = self.interval_min_spin.value()
        interval_max = self.interval_max_spin.value()
        duration = self.duration_spin.value()
        auto_shutdown = self.auto_shutdown_checkbox.isChecked()
        window_width = self.window_width_spin.value()
        window_height = self.window_height_spin.value()
        window_x = self.window_x_spin.value()
        window_y = self.window_y_spin.value()
        force_topmost = self.force_topmost_checkbox.isChecked()
        random_cruise = self.random_cruise_checkbox.isChecked()
        cruise_probability = self.cruise_probability_spin.value()
        cruise_hold_min = self.cruise_hold_min_spin.value()
        cruise_hold_max = self.cruise_hold_max_spin.value()
        cruise_space_min = self.cruise_space_min_spin.value()
        cruise_space_max = self.cruise_space_max_spin.value()
        
        return {
            "task_type": task_type,
            "action_key": action_key,
            "interval_min": interval_min,
            "interval_max": interval_max,
            "duration": duration,
            "auto_shutdown": auto_shutdown,
            "window_width": window_width,
            "window_height": window_height,
            "window_x": window_x,
            "window_y": window_y,
            "force_topmost": force_topmost,
            "random_cruise": random_cruise,
            "cruise_probability": cruise_probability,
            "cruise_hold_min": cruise_hold_min,
            "cruise_hold_max": cruise_hold_max,
            "cruise_space_min": cruise_space_min,
            "cruise_space_max": cruise_space_max
        }
    
    def save_config(self):
        """保存配置到文件。"""
        config = self.get_config()
        config_path = get_config_file_path()
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存配置失败: {e}")
    
    def load_config(self):
        """从文件读取配置。"""
        config_path = get_config_file_path()
        if not config_path.exists():
            return
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            if "task_type" in config:
                if config["task_type"] == "小号做动作":
                    self.radio_small_account.setChecked(True)
                else:
                    self.radio_host_action.setChecked(True)
            
            if "action_key" in config:
                index = self.action_key_combo.findText(config["action_key"])
                if index >= 0:
                    self.action_key_combo.setCurrentIndex(index)
            
            if "interval_min" in config:
                self.interval_min_spin.setValue(config["interval_min"])
            
            if "interval_max" in config:
                self.interval_max_spin.setValue(config["interval_max"])
            
            if "duration" in config:
                self.duration_spin.setValue(config["duration"])
            
            if "auto_shutdown" in config:
                self.auto_shutdown_checkbox.setChecked(config["auto_shutdown"])
            
            if "window_width" in config:
                self.window_width_spin.setValue(config["window_width"])
            
            if "window_height" in config:
                self.window_height_spin.setValue(config["window_height"])
            
            if "window_x" in config:
                self.window_x_spin.setValue(config["window_x"])
            
            if "window_y" in config:
                self.window_y_spin.setValue(config["window_y"])
            
            if "force_topmost" in config:
                self.force_topmost_checkbox.setChecked(config["force_topmost"])
            
            if "auto_shutdown" in config:
                self.auto_shutdown_checkbox.setChecked(config["auto_shutdown"])
            
            if "random_cruise" in config:
                self.random_cruise_checkbox.setChecked(config["random_cruise"])
            
            if "cruise_probability" in config:
                self.cruise_probability_spin.setValue(config["cruise_probability"])
            
            if "cruise_hold_min" in config:
                self.cruise_hold_min_spin.setValue(config["cruise_hold_min"])
            
            if "cruise_hold_max" in config:
                self.cruise_hold_max_spin.setValue(config["cruise_hold_max"])
            
            if "cruise_space_min" in config:
                self.cruise_space_min_spin.setValue(config["cruise_space_min"])
            
            if "cruise_space_max" in config:
                self.cruise_space_max_spin.setValue(config["cruise_space_max"])
                
        except Exception as e:
            print(f"读取配置失败: {e}")
    
    def set_target_class_name(self, class_name: str):
        """
        设置目标窗口类名。
        Args:
            class_name: 窗口类名
        """
        self._target_class_name = class_name
        self.window_picker.set_target_class_name(class_name)
    
    def closeEvent(self, event):
        """窗口关闭事件处理。"""
        self.save_config()
        if self._is_running:
            self._stop_event.set()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    is_authorized, result = check_license()
    
    if not is_authorized:
        dialog = LicenseDialog(result)
        if dialog.exec_() == QDialog.Rejected:
            sys.exit(0)
        sys.exit(0)
    
    try:
        import ctypes
        is_admin = ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        is_admin = False
    
    if not is_admin:
        QMessageBox.warning(
            None,
            "提示",
            "请右键程序图标，选择「以管理员身份运行」\n\n否则部分功能可能无法正常使用。",
            QMessageBox.Ok
        )
    
    window = MainWindow(target_class_name="UnrealWindow")
    window.start_clicked.connect(lambda: print("开始信号发射"))
    window.stop_clicked.connect(lambda: print("停止信号发射"))
    window.show()
    
    sys.exit(app.exec_())
