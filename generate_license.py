"""
授权文件生成工具。

开发者使用此工具为用户生成授权文件。
使用 Ed25519 非对称加密签名。
"""
import sys
import json
import base64
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519


def generate_keypair() -> tuple[bytes, bytes]:
    """
    生成 Ed25519 密钥对。

    生成私钥保存为 private.pem 文件（PEM 格式），
    公钥输出为可硬编码的原始字节格式。

    Returns:
        tuple[bytes, bytes]: (private_key_pem, public_key_bytes)
    """
    private_key = ed25519.Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    private_key_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )

    public_key_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    )

    private_path = Path("private.pem")
    private_path.write_bytes(private_key_pem)

    print("=" * 60)
    print("  Ed25519 密钥对已生成")
    print("=" * 60)
    print()
    print(f"私钥文件: {private_path.absolute()}")
    print("公钥 (十六进制，请复制到 auth.py):")
    print("-" * 60)
    print(public_key_bytes.hex())
    print("-" * 60)
    print()
    print("请将上述公钥十六进制字符串复制到 auth.py 的 PUBLIC_KEY_HEX 常量中。")
    print()

    return private_key_pem, public_key_bytes


def _load_private_key(key_path: str = "private.pem") -> ed25519.Ed25519PrivateKey:
    """
    从 PEM 文件加载 Ed25519 私钥。

    Args:
        key_path: 私钥文件路径，默认为 private.pem

    Returns:
        Ed25519PrivateKey: 加载的私钥对象

    Raises:
        FileNotFoundError: 私钥文件不存在
    """
    key_file = Path(key_path)
    if not key_file.exists():
        raise FileNotFoundError(f"私钥文件不存在: {key_file.absolute()}")

    private_key_pem = key_file.read_bytes()
    private_key = serialization.load_pem_private_key(
        private_key_pem,
        password=None
    )

    return private_key


def _sign_payload(payload: dict, private_key: ed25519.Ed25519PrivateKey) -> tuple[str, str]:
    """
    对 JSON payload 进行 Ed25519 签名。

    Args:
        payload: 要签名的数据字典
        private_key: Ed25519 私钥对象

    Returns:
        tuple[str, str]: (base64_payload, base64_signature)
    """
    payload_json = json.dumps(payload, ensure_ascii=False, separators=(',', ':'))
    payload_bytes = payload_json.encode('utf-8')

    signature = private_key.sign(payload_bytes)

    base64_payload = base64.b64encode(payload_bytes).decode('ascii')
    base64_signature = base64.b64encode(signature).decode('ascii')

    return base64_payload, base64_signature


def generate_license(machine_id: str, output_path: str = "license.key", key_path: str = "private.pem") -> bool:
    """
    生成授权文件。

    加载私钥，构建包含机器码的 payload，签名后写入授权文件。
    文件格式: Base64(JSON) + "." + Base64(Signature)

    Args:
        machine_id: 用户的机器码
        output_path: 授权文件输出路径，默认为 license.key
        key_path: 私钥文件路径，默认为 private.pem

    Returns:
        bool: 是否生成成功
    """
    try:
        private_key = _load_private_key(key_path)

        payload = {"machine_id": machine_id}

        base64_payload, base64_signature = _sign_payload(payload, private_key)

        license_content = f"{base64_payload}.{base64_signature}"

        output_file = Path(output_path)
        output_file.write_text(license_content, encoding='utf-8')

        return True

    except FileNotFoundError as e:
        print(f"[错误] {e}")
        return False
    except Exception as e:
        print(f"[错误] 生成授权文件失败: {e}")
        return False


def main():
    """
    命令行交互入口。

    支持以下用法:
        python generate_license.py --generate-keypair
        python generate_license.py <机器码>
        python generate_license.py <机器码> <输出路径>
    """
    print("=" * 60)
    print("  RocoFlower 授权文件生成工具")
    print("=" * 60)
    print()

    if len(sys.argv) > 1:
        arg = sys.argv[1]

        if arg == "--generate-keypair":
            generate_keypair()
            return

        machine_id = arg.strip().upper()
        output_path = sys.argv[2] if len(sys.argv) > 2 else "license.key"
    else:
        print("请输入用户的机器码 (格式: XXXX-XXXX-XXXX-XXXX):")
        machine_id = input("> ").strip().upper()

        print("\n请输入授权文件保存路径 (直接回车使用默认路径):")
        output_path = input("> ").strip()
        if not output_path:
            output_path = "license.key"

    print()
    print(f"机器码: {machine_id}")
    print(f"输出路径: {output_path}")
    print()

    if generate_license(machine_id, output_path):
        abs_path = Path(output_path).absolute()
        print("[成功] 授权文件已生成!")
        print(f"[路径] {abs_path}")
        print()
        print("请将 license.key 文件发送给用户，放置在程序同目录下即可使用。")
    else:
        print("[失败] 授权文件生成失败，请检查私钥文件是否存在。")
        sys.exit(1)


if __name__ == "__main__":
    main()
