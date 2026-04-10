# RocoFlower

PyQt5 自动化工具 - 窗口选择与任务自动化

## 项目简介

RocoFlower 是一个基于 PyQt5 开发的 Windows 自动化工具，提供图形化界面进行窗口选择、任务自动化和授权管理。支持多种自动化任务模式，适用于游戏辅助、自动化测试等场景。

## 功能特性

- **窗口选择**: 支持拖拽选择目标窗口，自动获取窗口句柄
- **任务自动化**: 
  - 小号做动作模式
  - 房主同乘做动作模式
  - 自定义动作按键和间隔时间
- **随机巡航**: 可配置的随机巡航功能，模拟人工操作
- **授权管理**: 完整的授权验证系统，防止未授权使用
- **配置管理**: JSON 配置文件，支持自定义参数
- **日志显示**: 实时显示任务执行日志

## 环境要求

- Windows 10 或更高版本
- Python 3.10+

## 安装说明

### 1. 克隆仓库

```bash
git clone https://github.com/你的用户名/RocoFlower.git
cd RocoFlower
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 运行程序

```bash
python main_window.py
```

## 使用方法

### 基本使用

1. 启动程序后，点击"选择窗口"按钮
2. 拖拽鼠标到目标窗口，松开鼠标完成选择
3. 配置任务参数（动作按键、间隔时间等）
4. 点击"开始"按钮执行任务

### 配置文件说明

配置文件 `config.json` 包含以下参数：

```json
{
  "task_type": "小号做动作",
  "action_key": "2",
  "interval_min": 8,
  "interval_max": 20,
  "duration": 60,
  "auto_shutdown": false,
  "window_width": 1280,
  "window_height": 720,
  "window_x": 0,
  "window_y": 0,
  "force_topmost": false,
  "random_cruise": false,
  "cruise_probability": 50,
  "cruise_hold_min": 0.5,
  "cruise_hold_max": 1.0,
  "cruise_space_min": 1,
  "cruise_space_max": 2
}
```

### 授权说明

本程序需要授权才能使用。首次运行时会显示机器码，请联系开发者获取授权文件 `license.key`，将其放置在程序同目录下即可。

#### 生成授权文件（开发者）

开发者可使用 `generate_license.py` 工具生成授权文件：

```bash
python generate_license.py <机器码> [输出路径]
```

## 构建指南

### 使用 Nuitka 打包

项目提供了 PowerShell 构建脚本 `build.ps1`：

```powershell
# 普通构建
.\build.ps1

# 清理后构建
.\build.ps1 -Clean

# 详细输出
.\build.ps1 -Verbose
```

构建完成后会生成 `RocoFlower.exe` 单文件可执行程序。

### 构建要求

- Python 3.10+
- Nuitka: `pip install nuitka`
- MinGW-w64 工具链（Windows）

## 项目结构

```
RocoFlower/
├── main_window.py          # 主窗口GUI模块
├── auth.py                 # 授权验证模块
├── task.py                 # 任务执行模块
├── tools.py                # 窗口操作工具模块
├── drag_window_picker.py   # 窗口拖拽选择器
├── generate_license.py     # 授权文件生成工具
├── config.json             # 应用配置文件
├── favicon.ico             # 应用图标
├── build.ps1               # Nuitka 构建脚本
├── requirements.txt        # Python依赖列表
└── README.md               # 项目说明文档
```

## 技术栈

- **GUI框架**: PyQt5
- **Windows API**: pywin32 (win32gui, win32con, win32api)
- **打包工具**: Nuitka
- **配置管理**: JSON

## 注意事项

1. 本工具仅供学习和研究使用，请勿用于违反游戏规则或其他非法用途
2. 授权文件 `license.key` 包含用户特定信息，请勿分享
3. 首次使用需要安装 Visual C++ Redistributable（打包版本）

## 许可证

本项目采用 MIT 许可证，详见 LICENSE 文件。

## 联系方式

如有问题或建议，请提交 Issue 或联系开发者。
