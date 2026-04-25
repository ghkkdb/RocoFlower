# RocoFlower

一个基于 PyQt5 的 Windows 桌面自动化工具，提供窗口选择、任务执行、授权校验、全局热键和 Nuitka 打包能力。

## 项目简介

RocoFlower 主要用于在 Windows 环境下对指定窗口执行自动化操作。项目提供图形界面，支持为不同窗口保存独立配置，并内置授权验证、日志输出和打包脚本，方便直接分发为可执行文件。

## 功能特性

- 拖拽选择目标窗口，自动记录窗口信息
- 支持多窗口配置与窗口档案保存
- 支持多种任务模式
  - 小号做动作
  - 房主同乘做动作
  - 游戏时间调整
- 支持任务执行日志实时显示
- 支持开始/停止全局热键
- 支持授权文件校验
- 提供标准版和 slim 版 Nuitka 打包脚本

## 运行环境

- Windows 10 / Windows 11
- Python 3.10+

## 依赖安装

```bash
pip install -r requirements.txt
```

当前核心依赖：

- `PyQt5>=5.15.0`
- `pywin32>=300`

## 启动方式

```bash
python main_window.py
```

## 配置说明

程序配置保存在 `config.json`，当前配置结构示例：

```json
{
  "hotkeys": {
    "start": "Ctrl+Alt+S",
    "stop": "Ctrl+Alt+X"
  },
  "window_profiles": {}
}
```

说明：

- `hotkeys.start`：启动任务的全局热键
- `hotkeys.stop`：停止任务的全局热键
- `window_profiles`：不同窗口对应的独立任务配置

窗口详细配置会在程序运行过程中由界面自动维护，不建议手动随意修改。

## 使用流程

1. 启动程序并完成授权验证
2. 点击界面中的窗口选择功能，拖拽到目标窗口
3. 为当前窗口设置任务模式、按键、时间区间等参数
4. 保存当前窗口配置
5. 通过界面按钮或全局热键启动任务
6. 在日志区域查看运行状态，必要时停止任务

## 授权说明

程序包含授权校验逻辑，首次运行时如果未授权，会提示机器码并引导获取授权文件。

- 授权文件名：`license.key`
- 授权文件需要与程序放在同一目录下

开发侧如需生成授权文件，可使用：

```bash
python generate_license.py <机器码> [输出路径]
```

仓库中还包含 `private.pem`，这是授权生成链路相关文件。若此仓库继续长期维护或多人协作，建议尽快将敏感文件移出仓库并轮换密钥。

## 打包

### 标准打包

使用 `build.ps1`：

```powershell
.\build.ps1
.\build.ps1 -Clean
.\build.ps1 -Verbose
.\build.ps1 -Onefile
```

说明：

- 默认使用 Nuitka 构建
- 自动包含 `img` 资源目录
- 输出文件名默认为 `RocoFlower.exe`

### Slim 打包

使用 `build_slim.ps1`：

```powershell
.\build_slim.ps1
.\build_slim.ps1 -Clean
.\build_slim.ps1 -Verbose
```

说明：

- 使用独立的 CPython 3.10 虚拟环境构建
- 目的是尽量避开 Anaconda/MKL 带来的体积膨胀
- 输出文件名默认为 `RocoFlower-slim.exe`

## 项目结构

```text
RocoFlower/
|-- main_window.py           主界面与配置管理
|-- auth.py                  授权校验
|-- task.py                  任务执行逻辑
|-- tools.py                 窗口与自动化辅助工具
|-- drag_window_picker.py    拖拽选窗
|-- generate_license.py      授权文件生成工具
|-- config.json              程序配置
|-- build.ps1                标准 Nuitka 打包脚本
|-- build_slim.ps1           slim 打包脚本
|-- img/                     图片资源
|-- README.md                项目说明
```

## 注意事项

- 本项目当前定位为 Windows 桌面自动化工具，不适用于跨平台环境
- 请不要提交本地虚拟环境、构建缓存和打包产物
- 如果需要公开协作，建议先清理敏感授权文件与私钥相关内容

## 仓库地址

- GitHub: [ghkkdb/RocoFlower](https://github.com/ghkkdb/RocoFlower)
