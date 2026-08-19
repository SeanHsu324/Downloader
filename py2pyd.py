"""
把.py轉成.pyd

需使用Visual Studio
下載工具：前往 Microsoft Visual C++ Build Tools 下載安裝檔。
'https://visualstudio.microsoft.com/zh-hant/visual-cpp-build-tools/'
勾選「使用 C++ 的桌面開發」 (Desktop development with C++)後按安裝 
完成後重開 Visual Studio code
"""

import os
import shutil
import sys
from setuptools import setup, Extension
from Cython.Build import cythonize

# 如果執行時沒有帶參數，預設補上 build_ext
if len(sys.argv) == 1:
    sys.argv.append("build_ext")

# 定義你想輸出的目標資料夾
output_dir = "modules"

# 定義你的模組檔案對照
extensions_info = [
    ("download", "module_py/download.py"),
    ("word", "module_py/word.py"),
    ("mp4_to_mp3", "module_py/mp4_to_mp3.py"),
    ("renew", "module_py/renew.py"),
]

# --- 清理舊的 .c 檔 ---
for _, py_path in extensions_info:
    c_path = os.path.splitext(py_path)[0] + ".c"
    if os.path.exists(c_path):
        os.remove(c_path)
        print(f"已清理舊的 C 檔: {c_path}")

# 如果資料夾不存在就建立它
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

# 建立 Extension 物件
extensions = [Extension(name, [path]) for name, path in extensions_info]

setup(
    ext_modules = cythonize(extensions, compiler_directives={'language_level': "3"}),
    options={
        'build_ext': {
            'build_lib': output_dir,  # 編譯後 .pyd 存放的位置
        }
    }
)

# --- 清理 setuptools 產生的 build 暫存資料夾 ---
if os.path.exists("build"):
    shutil.rmtree("build")