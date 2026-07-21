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

# 圖示路徑
ico_path = resource_path("pt/ytd.ico")

def terminate_downloader_process(exe_name="Downloader.exe", timeout=10):
    """終止主程式進程"""
    try:
        creation_flags = 0
        if sys.platform == 'win32':
            creation_flags = subprocess.CREATE_NO_WINDOW
        subprocess.run(["taskkill", "/F", "/IM", exe_name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=creation_flags)
    except Exception:
        pass

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

        # 路徑設定
        self.app_dir = os.path.dirname(os.path.abspath(sys.executable)) if hasattr(sys, 'frozen') else os.path.abspath(".")
        self.temp_update_dir = os.path.join(os.environ.get('TEMP', '/tmp'), "downloader_update")
        os.makedirs(self.temp_update_dir, exist_ok=True)

        # 本地紀錄
        self.local_config_dir = "c:\\downloadsitt"
        os.makedirs(self.local_config_dir, exist_ok=True)
        self.json_path = os.path.join(self.local_config_dir, "renew.json")

    def _update_status(self, progress_bar, label, text, progress=None):
        """安全地在主線程更新 UI"""
        self.root.after(0, self._safe_ui_update, progress_bar, label, text, progress)

    def _safe_ui_update(self, progress_bar, label, text, progress):
        label.config(text=text)
        if progress is not None:
            progress_bar["value"] = progress

    def start_thread(self, progress_bar, label):
        """啟動背景執行緒"""
        t = threading.Thread(target=self.run_update, args=(progress_bar, label), daemon=True)
        t.start()

    def run_update(self, progress_bar, label):
        # 1. 檢查更新
        self._update_status(progress_bar, label, "正在檢查 GitHub 版本...")
        try:
            resp = requests.get(self.api_url, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            latest_version = data["tag_name"]
            
            # 優先找 zip
            asset = next((a for a in data.get("assets", []) if a["name"] == "update.zip"), None)
            if not asset:
                asset = next((a for a in data.get("assets", []) if a["name"] == "Downloader.exe"), None)
            
            if not asset:
                self.root.after(0, lambda: messagebox.showerror("錯誤", "找不到更新檔案"))
                self.root.after(0, self.root.destroy)
                return
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("網路錯誤", str(e)))
            self.root.after(0, self.root.destroy)
            return

        # 2. 關閉主程式
        self._update_status(progress_bar, label, "正在終止主程式...")
        terminate_downloader_process("Downloader.exe")

        # 3. 下載檔案
        save_path = os.path.join(self.temp_update_dir, asset["name"])
        try:
            r = requests.get(asset["browser_download_url"], stream=True, timeout=30)
            total = int(r.headers.get('content-length', 0))
            curr = 0
            with open(save_path, "wb") as f:
                # 提升至 128KB 緩衝區增加速度
                for chunk in r.iter_content(chunk_size=131072):
                    if chunk:
                        f.write(chunk)
                        curr += len(chunk)
                        p = (curr / total) * 100 if total > 0 else 0
                        self._update_status(progress_bar, label, f"下載中: {p:.1f}%", p)
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("下載失敗", str(e)))
            return

        # 4. 解壓縮處理
        install_source = self.temp_update_dir
        if save_path.endswith(".zip"):
            self._update_status(progress_bar, label, "正在解壓縮...")
            extract_path = os.path.join(self.temp_update_dir, "extracted")
            if os.path.exists(extract_path): shutil.rmtree(extract_path)
            os.makedirs(extract_path)
            with zipfile.ZipFile(save_path, 'r') as z:
                z.extractall(extract_path)
            install_source = extract_path

        # 5. 處理刪除清單 (方案一擴展)
        delete_cmds = ""
        del_list_file = os.path.join(install_source, "delete.txt")
        if os.path.exists(del_list_file):
            with open(del_list_file, "r", encoding="utf-8") as f:
                for line in f:
                    item = line.strip()
                    if item:
                        # 若有副檔名則用 del, 否則用 rd
                        if "." in item:
                            delete_cmds += f"del /f /q \"{os.path.join(self.app_dir, item)}\" > nul 2>&1\n"
                        else:
                            delete_cmds += f"rd /s /q \"{os.path.join(self.app_dir, item)}\" > nul 2>&1\n"

        # 6. 生成批次檔與 VBS
        self._update_status(progress_bar, label, "正在套用更新...")
        batch_path = os.path.join(self.temp_update_dir, "apply.bat")
        vbs_path = os.path.join(self.temp_update_dir, "run.vbs")

        with open(batch_path, "w", encoding="cp950") as f:
            f.write(f"@echo off\ntimeout /t 2 /nobreak > nul\n")
            f.write(delete_cmds) # 插入刪除指令
            f.write(f"xcopy \"{install_source}\\*\" \"{self.app_dir}\\\" /E /Y /I > nul\n")
            # 清理剛搬過去的 delete.txt
            f.write(f"del \"{os.path.join(self.app_dir, 'delete.txt')}\" > nul 2>&1\n")
            f.write(f"start \"\" \"{os.path.join(self.app_dir, 'Downloader.exe')}\"\n")
            f.write(f"del \"{vbs_path}\" & del \"%~f0\"\n")

        with open(vbs_path, "w", encoding="cp950") as f:
            f.write(f'CreateObject("WScript.Shell").Run "cmd /c ""{batch_path}""", 0, False\n')

        # 紀錄版本
        try:
            with open(self.json_path, "w", encoding="utf-8") as f:
                json.dump({"版本": latest_version, "時間": time.ctime()}, f, indent=4)
        except: pass

        # 啟動並退出
        subprocess.Popen(["wscript.exe", vbs_path], shell=False)
        self.root.after(500, self.root.destroy)

def renew_view():
    rview = tk.Tk()
    rview.title("軟體自動更新")
    rview.geometry("400x180")
    
    # 視窗置中
    sw, sh = rview.winfo_screenwidth(), rview.winfo_screenheight()
    rview.geometry(f"+{(sw-400)//2}+{(sh-180)//2}")

    try: rview.iconbitmap(ico_path)
    except: pass

    frame = tk.Frame(rview, padx=20, pady=20)
    frame.pack(expand=True, fill="both")

    lbl = tk.Label(frame, text="正在初始化...", font=("Microsoft JhengHei", 10))
    lbl.pack(pady=10)

    pb = Progressbar(frame, length=300, mode="determinate")
    pb.pack(pady=10)

    updater = Updater(rview)
    rview.after(500, lambda: updater.start_thread(pb, lbl))
    rview.mainloop()

if __name__ == "__main__":
    renew_view()