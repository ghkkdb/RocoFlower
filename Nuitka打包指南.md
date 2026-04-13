# Nuitka 打包指南

本文档记录 YMJH 项目使用 Nuitka 打包的完整流程与经验总结。

---

## 一、环境要求

| 项目 | 要求 |
|------|------|
| Python | 3.10 (Anaconda) |
| 虚拟环境 | conda ymjh_venv |
| 操作系统 | Windows 10/11 |
| 打包工具 | Nuitka 4.0.1 |

---

## 二、依赖安装

### 2.1 安装 Nuitka

```powershell
conda activate ymjh_venv
pip install nuitka -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 2.2 项目依赖

```
PyQt5>=5.15.0
opencv-python>=4.5.0
Pillow>=8.0.0
numpy>=1.20.0
pywin32>=300
```

---

## 三、打包命令

### 3.1 标准打包命令

```powershell
conda activate ymjh_venv
$env:NUITKA_CACHE_DIR='D:\Python\YMJH\nuitka_cache'
python -m nuitka --standalone --onefile --windows-console-mode=disable --mingw64 --include-package=src --include-data-dir=assets=assets --enable-plugin=pyqt5 --output-filename=YMJH.exe --assume-yes-for-downloads main.py
```

### 3.2 参数说明

| 参数 | 说明 |
|------|------|
| `--standalone` | 独立运行，包含所有依赖库 |
| `--onefile` | 打包成单个 EXE 文件 |
| `--windows-console-mode=disable` | 隐藏控制台窗口（GUI 程序必用） |
| `--mingw64` | 使用 MinGW64 作为 C 编译器 |
| `--include-package=src` | 包含 src 模块代码 |
| `--include-data-dir=assets=assets` | 包含 assets 资源目录（格式：源目录=目标目录） |
| `--enable-plugin=pyqt5` | 启用 PyQt5 插件支持 |
| `--output-filename=YMJH.exe` | 指定输出文件名 |
| `--assume-yes-for-downloads` | 自动下载依赖工具（MinGW、Dependency Walker 等） |
| `main.py` | 程序入口文件 |

---

## 四、常见问题与解决方案

### 4.1 缓存目录权限问题

**问题描述**：
```
FATAL: Error, failed to create cache directory 'C:\Users\Administrator\AppData\Local\Nuitka\Nuitka\Cache'
```

**解决方案**：
设置本地缓存目录环境变量：
```powershell
$env:NUITKA_CACHE_DIR='D:\Python\YMJH\nuitka_cache'
```

### 4.2 MinGW 编译器下载慢/失败

**问题描述**：
Nuitka 首次运行需要下载 MinGW 编译器（约 300MB），国内网络可能下载失败。

**解决方案**：

1. 手动下载 MinGW：
   - 下载地址：https://github.com/brechtsanders/winlibs_mingw/releases
   - 推荐版本：`winlibs-x86_64-posix-seh-gcc-14.2.0-llvm-19.1.1-mingw-w64msvcrt-12.0.0-r2.zip`

2. 放置到缓存目录：
   ```
   nuitka_cache/downloads/gcc/x86_64/14.2.0posix-19.1.1-12.0.0-msvcrt-r2/mingw64/
   ```

3. 确保 `gcc.exe` 路径正确：
   ```
   nuitka_cache/downloads/gcc/x86_64/14.2.0posix-19.1.1-12.0.0-msvcrt-r2/mingw64/bin/gcc.exe
   ```

### 4.3 Dependency Walker 下载

**问题描述**：
Nuitka 需要 Dependency Walker 工具分析 DLL 依赖。

**解决方案**：
使用 `--assume-yes-for-downloads` 参数自动下载，或手动下载后放入：
```
nuitka_cache/downloads/depends/x86_64/depends.exe
```

### 4.4 PyQt5 警告

**问题描述**：
```
Nuitka-Plugins:WARNING: pyqt5: For the obsolete PyQt5 the Nuitka support is incomplete.
```

**说明**：
这是警告信息，不影响打包结果。如需完整支持，可考虑迁移到 PyQt6 或 PySide6。

---

## 五、打包输出

### 5.1 输出文件

| 文件 | 说明 |
|------|------|
| `YMJH.exe` | 最终可执行文件（单文件模式） |
| `main.build/` | 编译中间文件（可删除） |
| `main.dist/` | 分发目录文件（可删除） |
| `main.onefile-build/` | 单文件构建目录（可删除） |
| `nuitka_cache/` | Nuitka 缓存目录（建议保留，加速下次编译） |

### 5.2 清理临时文件

```powershell
Remove-Item -Path "main.build" -Recurse -Force
Remove-Item -Path "main.dist" -Recurse -Force
Remove-Item -Path "main.onefile-build" -Recurse -Force
```

---

## 六、优化建议

### 6.1 减小体积

1. **排除不需要的模块**：
   ```powershell
   --nofollow-import-to=tkinter
   --nofollow-import-to=unittest
   --nofollow-import-to=test
   ```

2. **使用 UPX 压缩**（需安装 UPX）：
   ```powershell
   --onefile-tempdir-spec={CACHE_DIR}/onefile_{PID}
   --windows-icon-from-ico=icon.ico
   ```

### 6.2 加速编译

1. **保留缓存目录**：`nuitka_cache/` 包含已下载的工具和编译缓存
2. **使用 ccache**：MinGW 自带 ccache，可加速 C 代码编译

### 6.3 添加图标

```powershell
--windows-icon-from-ico=assets/icon.ico
```

---

## 七、完整打包脚本

创建 `build.ps1` 文件：

```powershell
# YMJH 项目打包脚本

# 激活虚拟环境
conda activate ymjh_venv

# 设置缓存目录
$env:NUITKA_CACHE_DIR = "D:\Python\YMJH\nuitka_cache"

# 执行打包
python -m nuitka `
    --standalone `
    --onefile `
    --windows-console-mode=disable `
    --mingw64 `
    --include-package=src `
    --include-data-dir=assets=assets `
    --enable-plugin=pyqt5 `
    --output-filename=YMJH.exe `
    --assume-yes-for-downloads `
    main.py

# 清理临时文件
Remove-Item -Path "main.build" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -Path "main.dist" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -Path "main.onefile-build" -Recurse -Force -ErrorAction SilentlyContinue

Write-Host "打包完成！输出文件：YMJH.exe" -ForegroundColor Green
```

---

## 八、打包结果

| 项目 | 值 |
|------|------|
| 输出文件 | `YMJH.exe` |
| 文件大小 | 约 62 MB |
| 运行方式 | 双击直接运行，无需安装 |
| 首次启动 | 需解压资源，约 3-5 秒 |

---

**文档版本**：v1.0  
**创建日期**：2026-02-27  
**最后更新**：2026-02-27
