"""
授权文件生成工具。

开发者使用此工具为用户生成授权文件。
"""
import sys
import os
from pathlib import Path

try:
    from auth import generate_license, get_machine_id
except ImportError:
    print("错误: 无法导入 auth 模块")
    sys.exit(1)


def main():
    print("=" * 50)
    print("  RocoFlower 授权文件生成工具")
    print("=" * 50)
    print()
    
    if len(sys.argv) > 1:
        machine_id = sys.argv[1].strip().upper()
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
        abs_path = os.path.abspath(output_path)
        print(f"[成功] 授权文件已生成!")
        print(f"[路径] {abs_path}")
        print()
        print("请将 license.key 文件发送给用户，放置在程序同目录下即可使用。")
    else:
        print("[失败] 授权文件生成失败，请检查权限或路径。")
        sys.exit(1)


if __name__ == "__main__":
    main()
