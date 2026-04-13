"""
授权验证模块。

提供机器码生成和授权验证功能，使用 Ed25519 签名验证授权文件。
"""
import base64
import ctypes
import hashlib
import json
import subprocess
from enum import Enum
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


PUBLIC_KEY = bytes.fromhex("c9d509a6fe88eaed2b14d536f0aaea05fe02436f076650a45b1b129f6bed959b")


class AuthErrorType(Enum):
    """授权错误类型枚举。"""
    HARDWARE_ERROR = "硬件特征获取失败"
    LICENSE_NOT_FOUND = "授权文件不存在"
    LICENSE_FORMAT_ERROR = "授权文件格式错误"
    SIGNATURE_INVALID = "授权文件签名无效"
    MACHINE_ID_MISMATCH = "机器码不匹配"


class AuthError(Exception):
    """授权验证异常。"""

    def __init__(self, error_type: AuthErrorType, message: str, machine_id: str = None):
        self.error_type = error_type
        self.message = message
        self.machine_id = machine_id
        super().__init__(message)


def _init_com_thread() -> bool:
    """
    初始化 COM 线程环境。

    在多线程或 GUI 环境中调用 COM 接口前必须初始化。

    Returns:
        bool: 是否初始化成功
    """
    try:
        import pythoncom
        pythoncom.CoInitialize()
        return True
    except Exception:
        return False


def _uninit_com_thread() -> None:
    """
    反初始化 COM 线程环境。

    在 COM 操作完成后调用，释放资源。
    """
    try:
        import gc
        gc.collect()
    except Exception:
        pass
    try:
        import pythoncom
        pythoncom.CoUninitialize()
    except Exception:
        pass


def _safe_del_com_objects(*objects) -> None:
    """
    安全删除 COM 对象，忽略 Win32 异常。

    Args:
        *objects: 要删除的 COM 对象
    """
    for obj in objects:
        try:
            del obj
        except Exception:
            pass


def _get_hardware_via_com() -> dict:
    """
    通过 COM 接口获取硬件信息（优先方案）。

    使用 WMI 获取主板 UUID 和 CPU ID。
    支持多线程/GUI 环境，自动进行 COM 初始化。

    Returns:
        dict: {"uuid": str, "cpu_id": str}

    Raises:
        RuntimeError: COM 接口获取失败时抛出
    """
    com_initialized = False
    locator = None
    service = None
    try:
        import win32com.client

        com_initialized = _init_com_thread()

        locator = win32com.client.Dispatch("WbemScripting.SWbemLocator")
        service = locator.ConnectServer(".", "root\\cimv2")

        uuid_result = service.ExecQuery("SELECT UUID FROM Win32_ComputerSystemProduct")
        uuid_value = None
        for item in uuid_result:
            uuid_value = item.UUID
            break

        cpu_result = service.ExecQuery("SELECT ProcessorId FROM Win32_Processor")
        cpu_id = None
        for item in cpu_result:
            cpu_id = item.ProcessorId
            break

        if not uuid_value or not cpu_id:
            raise RuntimeError("无法获取完整硬件信息（UUID 或 CPU ID 为空）")

        return {"uuid": str(uuid_value), "cpu_id": str(cpu_id)}

    except ImportError as e:
        raise RuntimeError(f"依赖缺失: pywin32 未安装，请执行 pip install pywin32 ({e})")
    except Exception as e:
        error_name = type(e).__name__
        if "com_error" in error_name.lower() or "COM" in error_name:
            raise RuntimeError(f"COM 接口错误: {e}（请检查 WMI 服务是否正常运行）")
        raise RuntimeError(f"COM 接口获取硬件信息失败 [{error_name}]: {e}")
    finally:
        _safe_del_com_objects(service, locator)
        if com_initialized:
            _uninit_com_thread()


def _get_hardware_via_powershell() -> dict:
    """
    通过 PowerShell 获取硬件信息（备选方案）。

    使用 PowerShell 命令获取主板 UUID 和 CPU ID。

    Returns:
        dict: {"uuid": str, "cpu_id": str}

    Raises:
        RuntimeError: PowerShell 获取失败时抛出
    """
    try:
        uuid_cmd = [
            "powershell",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "Get-CimInstance -ClassName Win32_ComputerSystemProduct | Select-Object -ExpandProperty UUID"
        ]
        uuid_result = subprocess.run(
            uuid_cmd,
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
            timeout=10
        )
        uuid_value = uuid_result.stdout.strip()

        if uuid_result.returncode != 0 and not uuid_value:
            stderr = uuid_result.stderr.strip()
            raise RuntimeError(f"PowerShell 执行失败 (返回码 {uuid_result.returncode}): {stderr}")

        cpu_cmd = [
            "powershell",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "Get-CimInstance -ClassName Win32_Processor | Select-Object -ExpandProperty ProcessorId"
        ]
        cpu_result = subprocess.run(
            cpu_cmd,
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
            timeout=10
        )
        cpu_id = cpu_result.stdout.strip()

        if cpu_result.returncode != 0 and not cpu_id:
            stderr = cpu_result.stderr.strip()
            raise RuntimeError(f"PowerShell 执行失败 (返回码 {cpu_result.returncode}): {stderr}")

        if not uuid_value or not cpu_id:
            raise RuntimeError(f"无法获取完整硬件信息（UUID={uuid_value}, CPU_ID={cpu_id}）")

        return {"uuid": uuid_value, "cpu_id": cpu_id}

    except subprocess.TimeoutExpired:
        raise RuntimeError("PowerShell 命令执行超时（>10秒），请检查系统性能或安全软件拦截")
    except FileNotFoundError:
        raise RuntimeError("PowerShell 未找到（可能被删除或禁用）")
    except PermissionError as e:
        raise RuntimeError(f"权限不足，无法执行 PowerShell: {e}")
    except Exception as e:
        error_name = type(e).__name__
        raise RuntimeError(f"PowerShell 获取硬件信息失败 [{error_name}]: {e}")


def _get_hardware_info() -> dict:
    """
    整合两种硬件信息获取方式。

    优先尝试 COM 接口，失败时回退到 PowerShell。

    Returns:
        dict: {"uuid": str, "cpu_id": str}

    Raises:
        RuntimeError: 所有方式均失败时抛出，包含详细错误信息
    """
    errors = []

    try:
        return _get_hardware_via_com()
    except RuntimeError as e:
        errors.append(f"[COM 接口] {e}")

    try:
        return _get_hardware_via_powershell()
    except RuntimeError as e:
        errors.append(f"[PowerShell] {e}")

    error_detail = "\n    ".join(errors)
    raise RuntimeError(
        f"系统环境异常，硬件信息无法读取\n"
        f"    {error_detail}\n"
        f"请确保:\n"
        f"    1. WMI 服务正常运行（services.msc -> Windows Management Instrumentation）\n"
        f"    2. PowerShell 未被安全软件禁用\n"
        f"    3. 已安装 pywin32 库（pip install pywin32）"
    )


def get_machine_id() -> str:
    """
    生成机器唯一标识码。

    获取硬件信息并计算 SHA256 哈希，格式化为标准格式。

    Returns:
        str: 16位机器码，格式如 "XXXX-XXXX-XXXX-XXXX"

    Raises:
        RuntimeError: 硬件信息获取失败时抛出
    """
    hardware = _get_hardware_info()
    uuid = hardware["uuid"]
    cpu_id = hardware["cpu_id"]

    raw = f"{uuid}|{cpu_id}"
    hash_val = hashlib.sha256(raw.encode("utf-8")).hexdigest().upper()[:16]

    formatted = f"{hash_val[:4]}-{hash_val[4:8]}-{hash_val[8:12]}-{hash_val[12:16]}"

    return formatted


def _verify_ed25519_signature(payload: bytes, signature: bytes, public_key: bytes) -> bool:
    """
    验证 Ed25519 签名。

    Args:
        payload: 原始数据
        signature: 签名数据
        public_key: Ed25519 公钥

    Returns:
        bool: 签名是否有效
    """
    try:
        key = Ed25519PublicKey.from_public_bytes(public_key)
        key.verify(signature, payload)
        return True
    except InvalidSignature:
        return False
    except Exception:
        return False


def get_app_dir() -> Path:
    """
    获取应用程序目录路径。

    Returns:
        Path: 应用程序所在目录
    """
    try:
        buf = ctypes.create_unicode_buffer(260)
        ctypes.windll.kernel32.GetModuleFileNameW(None, buf, 260)
        exe_path = Path(buf.value)
        if exe_path.suffix.lower() == '.exe' and 'python' not in exe_path.name.lower():
            return exe_path.parent
    except OSError:
        pass
    return Path.cwd()


def check_license(license_file: str = "license.key") -> tuple[bool, str]:
    """
    检查授权文件是否有效。

    验证流程：
    1. 获取当前机器码（失败则立即中断）
    2. 读取授权文件
    3. 验证 Ed25519 签名
    4. 对比机器码

    Args:
        license_file: 授权文件名

    Returns:
        tuple[bool, str]:
            - (True, "授权验证通过") - 验证成功
            - (False, machine_id) - 授权文件不存在/机器码不匹配，返回机器码
            - (False, "FORMAT:机器码") - 授权文件格式错误
            - (False, "SIGNATURE:机器码") - 授权文件签名无效
            - (False, "ERROR:错误信息") - 系统环境异常
    """
    try:
        machine_id = get_machine_id()
    except RuntimeError as e:
        return False, f"ERROR:{e}"

    license_path = get_app_dir() / license_file

    if not license_path.exists():
        return False, machine_id

    try:
        with open(license_path, 'r', encoding='utf-8') as f:
            content = f.read().strip()
    except IOError:
        return False, f"FORMAT:{machine_id}"

    parts = content.split('.')
    if len(parts) != 2:
        return False, f"FORMAT:{machine_id}"

    try:
        payload_b64 = parts[0]
        signature_b64 = parts[1]

        payload = base64.b64decode(payload_b64)
        signature = base64.b64decode(signature_b64)
    except base64.binascii.Error:
        return False, f"FORMAT:{machine_id}"

    if not PUBLIC_KEY:
        return False, f"ERROR:公钥未配置"

    if not _verify_ed25519_signature(payload, signature, PUBLIC_KEY):
        return False, f"SIGNATURE:{machine_id}"

    try:
        payload_str = payload.decode('utf-8')
        payload_data = json.loads(payload_str)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return False, f"FORMAT:{machine_id}"

    licensed_machine_id = payload_data.get("machine_id")
    if not licensed_machine_id:
        return False, f"FORMAT:{machine_id}"

    if licensed_machine_id == machine_id:
        return True, "授权验证通过"
    else:
        return False, machine_id


def check_license_detailed(license_file: str = "license.key") -> tuple[bool, str, str]:
    """
    检查授权文件是否有效（详细版本，返回错误类型）。

    Args:
        license_file: 授权文件名

    Returns:
        tuple[bool, str, str]:
            - (True, "授权验证通过", machine_id) - 验证成功
            - (False, error_message, machine_id) - 授权失败，包含错误信息和机器码
    """
    try:
        machine_id = get_machine_id()
    except RuntimeError as e:
        return False, f"ERROR:{e}", None

    license_path = get_app_dir() / license_file

    if not license_path.exists():
        return False, AuthErrorType.LICENSE_NOT_FOUND.value, machine_id

    try:
        with open(license_path, 'r', encoding='utf-8') as f:
            content = f.read().strip()
    except IOError:
        return False, AuthErrorType.LICENSE_FORMAT_ERROR.value, machine_id

    parts = content.split('.')
    if len(parts) != 2:
        return False, AuthErrorType.LICENSE_FORMAT_ERROR.value, machine_id

    try:
        payload_b64 = parts[0]
        signature_b64 = parts[1]

        payload = base64.b64decode(payload_b64)
        signature = base64.b64decode(signature_b64)
    except base64.binascii.Error:
        return False, AuthErrorType.LICENSE_FORMAT_ERROR.value, machine_id

    if not PUBLIC_KEY:
        return False, "公钥未配置", machine_id

    if not _verify_ed25519_signature(payload, signature, PUBLIC_KEY):
        return False, AuthErrorType.SIGNATURE_INVALID.value, machine_id

    try:
        payload_str = payload.decode('utf-8')
        payload_data = json.loads(payload_str)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return False, AuthErrorType.LICENSE_FORMAT_ERROR.value, machine_id

    licensed_machine_id = payload_data.get("machine_id")
    if not licensed_machine_id:
        return False, AuthErrorType.LICENSE_FORMAT_ERROR.value, machine_id

    if licensed_machine_id == machine_id:
        return True, "授权验证通过", machine_id
    else:
        return False, AuthErrorType.MACHINE_ID_MISMATCH.value, machine_id
