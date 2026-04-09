import os
import json
import requests
import subprocess
import tkinter as tk
from tkinter import messagebox
from tkinter.ttk import Progressbar
import sys
import time
import zipfile
import shutil
import hashlib
import threading  

def resource_path(relative_path):
    if hasattr(sys, 'frozen'):
        base_path = sys._MEIPASS  # type: ignore
    else:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# 假設圖示路徑
ico_path = resource_path("pt/ytd.ico")

def get_file_hash(filepath):
    """計算檔案的 SHA256 雜湊值"""
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def terminate_downloader_process(exe_name="Downloader.exe", timeout=10):
    """嘗試終止指定的 .exe 進程"""
    try:
        creation_flags = 0
        if sys.platform == 'win32':
            creation_flags = subprocess.CREATE_NO_WINDOW
        subprocess.run(["taskkill", "/F", "/IM", exe_name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=creation_flags)
    except Exception as e:
        print(f"關閉 {exe_name} 發生錯誤：{e}")

    start_time = time.time()
    while time.time() - start_time < timeout:
        result = subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {exe_name}"], capture_output=True, text=True, creationflags=creation_flags)
        if exe_name not in result.stdout:
            return True
        time.sleep(1)
    return False

class Updater:
    def __init__(self, root):
        self.root = root
        self.repo_owner = "SeanHsu324"
        self.repo_name = "Downloader"
        self.api_url = f"https://api.github.com/repos/{self.repo_owner}/{self.repo_name}/releases/latest"

        # 設定更新暫存目錄
        self.app_dir = os.path.dirname(os.path.abspath(sys.executable)) if hasattr(sys, 'frozen') else os.path.abspath(".")
        self.temp_update_dir = os.path.join(os.environ.get('TEMP', '/tmp'), "downloader_update")
        os.makedirs(self.temp_update_dir, exist_ok=True)

        # 本地版本資訊紀錄
        self.local_config_dir = "c:\\downloadsitt"
        os.makedirs(self.local_config_dir, exist_ok=True)
        self.json_path = os.path.join(self.local_config_dir, "renew.json")

    def _load_local_data(self):
        if os.path.exists(self.json_path):
            try:
                with open(self.json_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except: pass
        return {}

    def _save_local_data(self, data):
        try:
            with open(self.json_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
        except: pass

    def _update_status(self, progress_bar, label, text, progress=None):
        """透過 root.after 將 UI 更新派發回主執行緒，避免多線程操作 UI 崩潰"""
        self.root.after(0, self._safe_ui_update, progress_bar, label, text, progress)

    def _safe_ui_update(self, progress_bar, label, text, progress):
        label.config(text=text)
        if progress is not None:
            progress_bar["value"] = progress

    def _show_error_and_exit(self, title, msg):
        """安全地在 UI 執行緒顯示錯誤並關閉"""
        self.root.after(0, lambda: messagebox.showerror(title, msg))
        self.root.after(0, self.root.destroy)

    def start_update_thread(self, progress_bar, label):
        """啟動背景更新線程"""
        t = threading.Thread(target=self.run_update, args=(progress_bar, label), daemon=True)
        t.start()

    def run_update(self, progress_bar, label):
        # 1. 檢查更新
        self._update_status(progress_bar, label, "正在檢查網路更新...")
        try:
            response = requests.get(self.api_url, timeout=15)
            response.raise_for_status()
            release_data = response.json()
            latest_version = release_data["tag_name"]

            # 先尋找 zip，後尋找 exe
            zip_asset = next((asset for asset in release_data.get("assets", []) if asset["name"] == "update.zip"), None)

            if not zip_asset:
                exe_asset = next((asset for asset in release_data.get("assets", []) if asset["name"] == "Downloader.exe"), None)
                if not exe_asset:
                    self._show_error_and_exit("更新失敗", "找不到更新檔 (update.zip 或 Downloader.exe)")
                    return
                assets_to_download = [exe_asset]
            else:
                assets_to_download = [zip_asset]

        except Exception as e:
            self._show_error_and_exit("錯誤", f"檢查更新失敗: {e}")
            return

        # 2. 關閉主程式
        self._update_status(progress_bar, label, "正在關閉主程式...")
        terminate_downloader_process("Downloader.exe")

        # 3. 下載檔案
        downloaded_files = []
        for asset in assets_to_download:
            save_path = os.path.join(self.temp_update_dir, asset["name"])
            try:
                resp = requests.get(asset["browser_download_url"], stream=True, timeout=30)
                total = int(resp.headers.get('content-length', 0))
                curr = 0
                with open(save_path, "wb") as f:
                    for chunk in resp.iter_content(131072):
                        if chunk:
                            f.write(chunk)
                            curr += len(chunk)
                            p = (curr / total) * 100 if total > 0 else 0
                            self._update_status(progress_bar, label, f"下載中: {asset['name']} ({p:.1f}%)", p)
                downloaded_files.append(save_path)
            except Exception as e:
                self._show_error_and_exit("下載失敗", str(e))
                return

        # 4. 處理更新 (解壓縮)
        self._update_status(progress_bar, label, "正在準備安裝更新...", 100)
        install_source = self.temp_update_dir
        if downloaded_files[0].endswith(".zip"):
            try:
                extract_path = os.path.join(self.temp_update_dir, "extracted")
                if os.path.exists(extract_path): shutil.rmtree(extract_path)
                os.makedirs(extract_path)
                with zipfile.ZipFile(downloaded_files[0], 'r') as zip_ref:
                    zip_ref.extractall(extract_path)
                install_source = extract_path
            except Exception as e:
                self._show_error_and_exit("解壓縮失敗", str(e))
                return

        # 5. 產生更新腳本與隱藏啟動器 (VBScript)
        self._update_status(progress_bar, label, "正在完成更新腳本...")
        target_dir = self.app_dir
        batch_script = os.path.join(self.temp_update_dir, "apply_update.bat")
        vbs_script = os.path.join(self.temp_update_dir, "silent_run.vbs")

        try:
            with open(batch_script, "w", encoding="cp950") as f:
                f.write(f"@echo off\n")
                f.write(f"timeout /t 2 /nobreak > nul\n") 
                f.write(f"xcopy \"{install_source}\\*\" \"{target_dir}\\\" /E /Y /I > nul\n")
                f.write(f"start \"\" \"{os.path.join(target_dir, 'Downloader.exe')}\"\n")
                f.write(f"del \"{vbs_script}\" & del \"%~f0\"\n")

            with open(vbs_script, "w", encoding="cp950") as f:
                f.write(f'Set WshShell = CreateObject("WScript.Shell")\n')
                f.write(f'WshShell.Run chr(34) & "{batch_script}" & chr(34), 0, False\n')
                f.write(f'Set WshShell = Nothing\n')
        except Exception as e:
            self._show_error_and_exit("寫入腳本失敗", str(e))
            return

        # 更新本地紀錄
        local_data = self._load_local_data()
        local_data.update({"版本": latest_version, "最後更新時間": time.ctime()})
        self._save_local_data(local_data)

        # 6. 執行 VBS 並關閉 Updater
        self._update_status(progress_bar, label, "更新完成！正在重新啟動...")
        time.sleep(1) # 給使用者看一眼 100% 的機會
        subprocess.Popen(["wscript.exe", vbs_script], shell=False)
        self.root.after(100, self.root.destroy)

def renew_view():
    rview = tk.Tk()
    rview.title("軟體更新程式")
    rview.geometry("400x180")
    rview.resizable(False, False)
    
    # 置中視窗
    screen_width = rview.winfo_screenwidth()
    screen_height = rview.winfo_screenheight()
    x = (screen_width // 2) - (400 // 2)
    y = (screen_height // 2) - (180 // 2)
    rview.geometry(f"400x180+{x}+{y}")

    try: rview.iconbitmap(ico_path)
    except: pass

    frame = tk.Frame(rview, padx=30, pady=20)
    frame.pack(fill="both", expand=True)

    label = tk.Label(frame, text="準備檢查更新...", font=("Microsoft JhengHei", 10))
    label.pack(pady=(10, 5))

    progress_bar = Progressbar(frame, length=300, mode="determinate")
    progress_bar.pack(pady=10)

    updater = Updater(rview)
    # 關鍵：使用 start_update_thread 而不是 run_update
    rview.after(1000, lambda: updater.start_update_thread(progress_bar, label))
    rview.mainloop()

if __name__ == "__main__":
    renew_view()
