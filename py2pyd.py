"""
把 .py 轉成 .pyd (模組編譯工具)

需使用Visual Studio
下載工具：前往 Microsoft Visual C++ Build Tools 下載安裝檔。
'https://visualstudio.microsoft.com/zh-hant/visual-cpp-build-tools/'
勾選「使用 C++ 的桌面開發」 (Desktop development with C++)後按安裝 
完成後重開 Visual Studio code

用法：
    1. 編譯指定模組 (支援帶或不帶副檔名/路徑)：
       python py2pyd.py download
       python py2pyd.py modules/word.py

    2. 自動掃描 modules/ 目錄下的所有模組：
       python py2pyd.py
"""

import glob
import os
import shutil
import sys
from Cython.Build import cythonize
from setuptools import Extension, setup

# .py 的資料夾
py_dir = "module_py"

# 輸出的目標資料夾
output_dir = "modules"

# 確保輸出目錄存在
os.makedirs(output_dir, exist_ok=True)

# --- 解析命令列參數 ---
# 過濾掉 setuptools 相關參數 (如 build_ext)
raw_args = [arg for arg in sys.argv[1:] if arg != "build_ext"]

targets_to_process = []

if raw_args:
    # 使用者指定了特定檔案或模組名稱
    for arg in raw_args:
        # 去除副檔名與路徑，只取模組純檔名 (例: modules/download.py -> download)
        clean_name = os.path.splitext(os.path.basename(arg))[0]
        py_file_path = os.path.join(py_dir, f"{clean_name}.py")

        if os.path.exists(py_file_path):
            targets_to_process.append((clean_name, py_file_path))
        else:
            print(f"❌ 找不到原始碼檔案：{py_file_path}")
else:
    # 使用者沒帶參數，自動掃描 modules/ 下所有 .py
    all_py_files = [
        f
        for f in glob.glob(os.path.join(py_dir, "*.py"))
        if not os.path.basename(f).startswith("__")
    ]
    for py_path in all_py_files:
        mod_name = os.path.splitext(os.path.basename(py_path))[0]
        targets_to_process.append((mod_name, py_path))

# 重置 sys.argv 給 setuptools 讀取 (補上 build_ext)
sys.argv = [sys.argv[0], "build_ext"]

# --- 檢查編譯狀態與選擇性編譯 ---
target_extensions = []

print("🔍 檢查模組編譯狀態...\n" + "-" * 40)

for mod_name, py_path in targets_to_process:
    # 檢查 build/ 是否已有該模組的 .pyd / .so
    existing_builds = glob.glob(os.path.join(output_dir, f"{mod_name}*.pyd")) + glob.glob(
        os.path.join(output_dir, f"{mod_name}*.so")
    )

    if existing_builds:
        print(f"⚠️  模組 [{mod_name}] 已存在於 {output_dir}/ 中。")
        ans = input(f"   是否重新編譯 {mod_name}？(y/N): ").strip().lower()

        if ans != "y":
            print(f"   ⏩ 跳過編譯 [{mod_name}]")
            print(f"   💡 提醒：若無重新編譯，請確認現有 .pyd 是否已簽章。\n")
            continue

    # 清理舊的 C 檔
    c_path = os.path.splitext(py_path)[0] + ".c"
    if os.path.exists(c_path):
        os.remove(c_path)

    target_extensions.append(Extension(mod_name, [py_path]))

print("-" * 40)

# 如果沒有要編譯的模組就直接結束
if not target_extensions:
    print("✅ 沒有需要編譯的模組。")
    sys.exit(0)

# 執行 Cython 編譯
setup(
    ext_modules=cythonize(
        target_extensions, compiler_directives={"language_level": "3"}
    ),
    options={
        "build_ext": {
            "build_lib": output_dir,  # 編譯後 .pyd 存放位置
            "build_temp": os.path.join("build_temp"),  # 中間檔暫存區
        }
    },
)

# 清理 C++ 中間檔資料夾
if os.path.exists("build_temp"):
    shutil.rmtree("build_temp")

print("\n" + "=" * 50)
print("🎉 編譯完成！")
for ext in target_extensions:
    print(f"   python tools/sign_plugin.py sign build/{ext.name}.pyd")
print("=" * 50)