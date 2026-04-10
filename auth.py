"""
授权验证模块。

提供机器码生成和授权验证功能，防止未授权使用。
"""
import hashlib
import hmac
import subprocess
import sys
import ctypes
import platform
import uuid
import base64
import time
from pathlib import Path


_SECRET_KEY = b"RocoFlower_2024_License_Key_Secret_Do_Not_Share"
_APP_ID = "RocoFlower"


def _xor_encrypt(data: bytes, key: bytes) -> bytes:
    """
    XOR 加密/解密。
    
    Args:
        data: 原始数据
        key: 密钥
        
    Returns:
        bytes: 加密/解密后的数据
    """
    result = bytearray(len(data))
    key_len = len(key)
    for i, byte in enumerate(data):
        result[i] = byte ^ key[i % key_len]
    return bytes(result)


def _encode_license(machine_id: str) -> str:
    """
    编码授权内容。
    
    Args:
        machine_id: 机器码
        
    Returns:
        str: 编码后的授权字符串
    """
    timestamp = int(time.time())
    data = f"{machine_id}|{timestamp}|{_APP_ID}"
    
    data_bytes = data.encode('utf-8')
    encrypted = _xor_encrypt(data_bytes, _SECRET_KEY)
    
    signature = hmac.new(_SECRET_KEY, encrypted, hashlib.sha256).hexdigest()[:16]
    
    payload = encrypted + signature.encode('utf-8')
    encoded = base64.b64encode(payload).decode('utf-8')
    
    lines = [encoded[i:i+64] for i in range(0, len(encoded), 64)]
    return '\n'.join(lines)


def _decode_license(content: str) -> tuple:
    """
    解码授权内容。
    
    Args:
        content: 授权文件内容
        
    Returns:
        tuple: (是否有效, 机器码或错误信息)
    """
    try:
        content = content.replace('\n', '').replace('\r', '').replace(' ', '')
        
        payload = base64.b64decode(content)
        
        if len(payload) < 16:
            return False, "授权文件格式错误"
        
        encrypted = payload[:-16]
        signature = payload[-16:].decode('utf-8')
        
        expected_signature = hmac.new(_SECRET_KEY, encrypted, hashlib.sha256).hexdigest()[:16]
        if not hmac.compare_digest(signature, expected_signature):
            return False, "授权文件已被篡改"
        
        decrypted = _xor_encrypt(encrypted, _SECRET_KEY)
        data = decrypted.decode('utf-8')
        
        parts = data.split('|')
        if len(parts) < 3:
            return False, "授权文件格式错误"
        
        machine_id = parts[0]
        app_id = parts[2]
        
        if app_id != _APP_ID:
            return False, "授权文件不匹配"
        
        return True, machine_id
        
    except Exception as e:
        return False, f"授权文件解析失败: {str(e)}"


def _run_wmic(command: str) -> str:
    """
    执行 wmic 命令并返回结果。
    
    Args:
        command: wmic 命令参数
        
    Returns:
        str: 命令输出结果
    """
    try:
        result = subprocess.run(
            ['wmic'] + command.split(),
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
            timeout=10
        )
        lines = result.stdout.strip().split('\n')
        results = []
        for line in lines:
            line = line.strip().replace('\r', '').replace('.', '')
            if line and line not in [command.split()[1], command.split()[-1]]:
                results.append(line)
        if results:
            results.sort()
            return results[0]
        return ""
    except Exception:
        return ""


def _get_mac_address() -> str:
    """
    获取第一个有效网卡的 MAC 地址。
    
    Returns:
        str: MAC 地址
    """
    try:
        mac = uuid.getnode()
        return format(mac, '012X')
    except Exception:
        return ""


def get_machine_id() -> str:
    """
    获取机器唯一标识码。
    
    使用最稳定的硬件标识符：CPU、主板、BIOS、MAC地址。
    这些标识符在正常使用情况下不会变化。
    
    Returns:
        str: 16位机器码，格式如 "A1B2-C3D4-E5F6-G7H8"
    """
    components = []
    
    cpu_id = _run_wmic("cpu get ProcessorId")
    if cpu_id:
        components.append(f"CPU:{cpu_id}")
    
    board_sn = _run_wmic("baseboard get SerialNumber")
    if board_sn and board_sn.upper() not in ["DEFAULT", "N/A", "NONE", ""]:
        components.append(f"BOARD:{board_sn}")
    
    bios_sn = _run_wmic("bios get SerialNumber")
    if bios_sn and bios_sn.upper() not in ["DEFAULT", "N/A", "NONE", ""]:
        components.append(f"BIOS:{bios_sn}")
    
    mac_addr = _get_mac_address()
    if mac_addr:
        components.append(f"MAC:{mac_addr}")
    
    if not components:
        components.append(f"FALLBACK:{uuid.getnode()}-{platform.processor()}")
    
    raw = "|".join(sorted(components))
    hash_val = hashlib.sha256(raw.encode()).hexdigest().upper()[:16]
    
    formatted = f"{hash_val[:4]}-{hash_val[4:8]}-{hash_val[8:12]}-{hash_val[12:16]}"
    
    return formatted


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
    except Exception:
        pass
    return Path.cwd()


def check_license(license_file: str = "license.key") -> tuple:
    """
    检查授权文件是否有效。
    
    Args:
        license_file: 授权文件名
        
    Returns:
        tuple: (是否授权通过, 消息)
    """
    machine_id = get_machine_id()
    license_path = get_app_dir() / license_file
    
    if not license_path.exists():
        return False, machine_id
    
    try:
        with open(license_path, 'r', encoding='utf-8') as f:
            content = f.read().strip()
        
        valid, result = _decode_license(content)
        
        if not valid:
            return False, result
        
        if result == machine_id:
            return True, "授权验证通过"
        else:
            return False, machine_id
            
    except Exception as e:
        return False, f"授权文件读取失败: {str(e)}"


def generate_license(machine_id: str, output_path: str = None) -> bool:
    """
    生成授权文件。
    
    Args:
        machine_id: 机器码
        output_path: 输出路径，默认为当前目录
        
    Returns:
        bool: 是否生成成功
    """
    if output_path is None:
        output_path = "license.key"
    
    try:
        encoded = _encode_license(machine_id)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(encoded)
        return True
    except Exception as e:
        print(f"生成授权文件失败: {e}")
        return False


if __name__ == "__main__":
    print("=" * 40)
    print("  机器码授权工具")
    print("=" * 40)
    print()
    
    machine_id = get_machine_id()
    print(f"当前机器码: {machine_id}")
    print()
    
    import os
    if len(sys.argv) > 1:
        target_id = sys.argv[1]
        output_path = sys.argv[2] if len(sys.argv) > 2 else "license.key"
        
        print(f"目标机器码: {target_id}")
        print(f"输出路径: {output_path}")
        
        if generate_license(target_id, output_path):
            print(f"\n授权文件已生成: {os.path.abspath(output_path)}")
        else:
            print("\n授权文件生成失败")
    else:
        print("用法: python auth.py <机器码> [输出路径]")
        print("示例: python auth.py A1B2-C3D4-E5F6-G7H8")
