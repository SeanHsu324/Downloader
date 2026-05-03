from setuptools import setup, Extension
from Cython.Build import cythonize
import os

# 定義你想輸出的目標資料夾
output_dir = "modules"

# 如果資料夾不存在就建立它
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

extensions = [
    Extension("download", ["module_py/download.py"]),
    Extension("word", ["module_py/word.py"]),
    Extension("mp4_to_mp3", ["module_py/mp4_to_mp3.py"]),
    Extension("renew", ["module_py/renew.py"]),
]

setup(
    ext_modules = cythonize(extensions, compiler_directives={'language_level': "3"}),
    # 這裡可以進一步設定編譯暫存檔的位置
    options={
        'build_ext': {
            'build_lib': output_dir,  # 這是編譯後 .pyd 存放的位置
        }
    }
)