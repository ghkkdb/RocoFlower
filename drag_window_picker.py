import win32api
import win32gui
import win32con
from PyQt5.QtCore import QObject, pyqtSignal, QTimer, Qt, QPoint
from PyQt5.QtGui import QMouseEvent
from PyQt5.QtWidgets import QWidget, QPushButton, QToolTip


class CrosshairButton(QPushButton):
    """
    瞄准镜样式按钮控件，支持拖拽操作。
    
    信号：
        released_at: 拖动释放时触发，参数为屏幕坐标(x, y)
    """
    
    released_at = pyqtSignal(int, int)
    
    def __init__(self, text: str = "🎯", parent: QWidget = None):
        """
        初始化瞄准镜按钮。
        Args:
            text: 按钮显示文本
            parent: 父窗口部件
        """
        super().__init__(text, parent)
        self.is_dragging: bool = False
        self.drag_start_pos: QPoint = None
        self.drag_threshold: int = 10
        self._tooltip_dragging: str = "拖动到目标窗口后释放"
    
    def mousePressEvent(self, event: QMouseEvent):
        """
        鼠标按下事件处理。
        Args:
            event: 鼠标事件对象
        """
        if event.button() == Qt.LeftButton:
            self.drag_start_pos = event.pos()
            self.is_dragging = False
            self.setCursor(Qt.CrossCursor)
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event: QMouseEvent):
        """
        鼠标移动事件处理。
        Args:
            event: 鼠标事件对象
        """
        if self.drag_start_pos is not None:
            distance = (event.pos() - self.drag_start_pos).manhattanLength()
            if distance > self.drag_threshold:
                if not self.is_dragging:
                    self.is_dragging = True
            if self.is_dragging:
                global_pos = self.mapToGlobal(event.pos())
                QToolTip.showText(global_pos, self._tooltip_dragging)
        super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event: QMouseEvent):
        """
        鼠标释放事件处理。
        Args:
            event: 鼠标事件对象
        """
        if event.button() == Qt.LeftButton:
            QToolTip.hideText()
            if self.is_dragging:
                global_pos = self.mapToGlobal(event.pos())
                self.released_at.emit(global_pos.x(), global_pos.y())
            self.is_dragging = False
            self.drag_start_pos = None
            self.unsetCursor()
        super().mouseReleaseEvent(event)


class WindowPicker(QObject):
    """
    窗口选择器类，用于识别目标窗口。
    
    信号：
        window_picked: 窗口选择成功时触发，参数为窗口句柄(hwnd)
        pick_failed: 窗口选择失败时触发
        pick_status: 状态消息更新时触发
    """
    window_picked = pyqtSignal(int)
    pick_failed = pyqtSignal()
    pick_status = pyqtSignal(str)

    target_class_name: str = ""

    def pick_at_position(self, parent_widget=None):
        """
        在当前位置立即执行窗口识别。
        Args:
            parent_widget: 父窗口部件（用于显示对话框）
        """
        try:
            pos = win32api.GetCursorPos()
            hwnd = win32gui.WindowFromPoint(pos)
            hwnd = win32gui.GetAncestor(hwnd, win32con.GA_ROOT)

            if not win32gui.IsWindow(hwnd):
                self.pick_failed.emit()
                return

            class_name = win32gui.GetClassName(hwnd)

            if class_name == self.target_class_name:
                self.window_picked.emit(hwnd)
            else:
                self.pick_status.emit(f"窗口类名不匹配: {class_name}")
                self.pick_failed.emit()

        except (win32gui.error, OSError) as e:
            self.pick_status.emit(f"窗口识别异常: {str(e)}")
            self.pick_failed.emit()


class DragWindowPicker(QObject):
    """
    拖拽窗口选择器，整合瞄准镜按钮和窗口选择器组件。

    信号：
        window_picked: 窗口选择成功时触发，参数为窗口句柄(hwnd)
        pick_failed: 窗口选择失败时触发
        pick_status: 状态消息更新时触发
    """

    window_picked = pyqtSignal(int)
    pick_failed = pyqtSignal()
    pick_status = pyqtSignal(str)

    def __init__(self, parent: QObject = None, target_class_name: str = ""):
        """
        初始化拖拽窗口选择器。
        Args:
            parent: 父对象
            target_class_name: 目标窗口类名
        """
        super().__init__(parent)

        self._target_class_name: str = target_class_name

        self.button: CrosshairButton = CrosshairButton()
        self.picker: WindowPicker = WindowPicker()

        self._apply_config()
        self._setup_connections()

    def _apply_config(self):
        """应用配置到组件。"""
        self.picker.target_class_name = self._target_class_name

    def _setup_connections(self):
        """设置信号槽连接。"""
        self.button.released_at.connect(self._on_button_released)
        self.picker.window_picked.connect(self._on_window_picked)
        self.picker.pick_failed.connect(self._on_pick_failed)
        self.picker.pick_status.connect(self.pick_status.emit)

    def _on_button_released(self, x: int, y: int):
        """
        按钮释放事件处理。
        Args:
            x: 屏幕 X 坐标
            y: 屏幕 Y 坐标
        """
        self.button.setEnabled(False)
        QTimer.singleShot(50, lambda: self.picker.pick_at_position())

    def _on_window_picked(self, hwnd: int):
        """
        窗口选择成功处理。
        Args:
            hwnd: 窗口句柄
        """
        self.button.setEnabled(True)
        self.window_picked.emit(hwnd)

    def _on_pick_failed(self):
        self.button.setEnabled(True)
        self.pick_failed.emit()

    def set_target_class_name(self, class_name: str):
        """
        设置目标窗口类名。
        Args:
            class_name: 窗口类名
        """
        self._target_class_name = class_name
        self.picker.target_class_name = class_name

    def get_button(self) -> CrosshairButton:
        """
        获取瞄准镜按钮实例。
        Returns:
            CrosshairButton: 按钮实例
        """
        return self.button


if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication, QVBoxLayout, QWidget, QLabel

    app = QApplication(sys.argv)

    print("=== 测试 CrosshairButton ===")
    button = CrosshairButton("🎯 拖拽选择窗口")

    released_coords = []
    button.released_at.connect(lambda x, y: released_coords.append((x, y)))

    press_event = QMouseEvent(
        QMouseEvent.MouseButtonPress,
        QPoint(0, 0),
        Qt.LeftButton,
        Qt.LeftButton,
        Qt.NoModifier
    )
    button.mousePressEvent(press_event)
    assert button.drag_start_pos is not None
    print("✓ 鼠标按下事件正常")

    move_event = QMouseEvent(
        QMouseEvent.MouseMove,
        QPoint(5, 5),
        Qt.NoButton,
        Qt.LeftButton,
        Qt.NoModifier
    )
    button.mouseMoveEvent(move_event)
    assert not button.is_dragging
    print("✓ 短距离移动未触发拖拽")

    move_event = QMouseEvent(
        QMouseEvent.MouseMove,
        QPoint(20, 20),
        Qt.NoButton,
        Qt.LeftButton,
        Qt.NoModifier
    )
    button.mouseMoveEvent(move_event)
    assert button.is_dragging
    print("✓ 长距离移动触发拖拽")

    release_event = QMouseEvent(
        QMouseEvent.MouseButtonRelease,
        QPoint(20, 20),
        Qt.LeftButton,
        Qt.LeftButton,
        Qt.NoModifier
    )
    button.mouseReleaseEvent(release_event)
    assert len(released_coords) == 1
    print(f"✓ 释放信号发射，坐标: {released_coords[0]}")

    print("\n=== 测试 DragWindowPicker ===")
    picker = DragWindowPicker(target_class_name="Notepad")
    assert picker.button is not None
    assert picker.picker is not None
    assert picker.picker.target_class_name == "Notepad"
    print("✓ DragWindowPicker 初始化正常")

    picker.set_target_class_name("UnrealWindow")
    assert picker.picker.target_class_name == "UnrealWindow"
    print("✓ 配置更新正常")

    print("\n=== 所有测试通过 ===")

    window = QWidget()
    layout = QVBoxLayout(window)
    label = QLabel("点击下方按钮并拖拽到目标窗口")
    demo_picker = DragWindowPicker(target_class_name="UnrealWindow")
    demo_picker.window_picked.connect(lambda h: print(f"窗口选择成功，句柄: {h}"))
    demo_picker.pick_failed.connect(lambda: print("窗口选择失败"))

    layout.addWidget(label)
    layout.addWidget(demo_picker.get_button())
    window.setWindowTitle("拖拽窗口选择器演示")
    window.show()

    sys.exit(app.exec_())
