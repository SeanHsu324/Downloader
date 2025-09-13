import os
import json
import requests
import subprocess
import tkinter as tk
from tkinter import messagebox
from tkinter.ttk import Progressbar
import sys
import time

def resource_path(relative_path):
    if hasattr(sys, 'frozen'):
        base_path = sys._MEIPASS  # type: ignore
    else:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

ico_path = resource_path("pt/ytd.ico")

# 自動關閉 Downloader.exe
def terminate_downloader_process(exe_name="Downloader.exe", timeout=10):
    """嘗試終止指定的 .exe 進程，並在超時前確認其已關閉。"""
    try:
        # 在 Windows 上，設定 creationflags 來隱藏命令視窗
        creation_flags = 0
        if sys.platform == 'win32':
            creation_flags = subprocess.CREATE_NO_WINDOW

        # /T 參數可以一併關閉子進程
        subprocess.run(["taskkill", "/F", "/IM", exe_name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=creation_flags)
    except Exception as e:
        print(f"關閉 {exe_name} 發生錯誤：{e}")

    start_time = time.time()
    while time.time() - start_time < timeout:
        result = subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {exe_name}"], capture_output=True, text=True, creationflags=creation_flags)
        if exe_name not in result.stdout:
            print(f"{exe_name} 已成功關閉。")
            return True  # 成功關閉
        time.sleep(1)
    print(f"關閉 {exe_name} 超時。")
    return False # 未能關閉

class Updater:
    def __init__(self, root):
        self.root = root
        self.repo_owner = "SeanHsu324"
        self.repo_name = "Downloader"
        self.api_url = f"https://api.github.com/repos/{self.repo_owner}/{self.repo_name}/releases/latest"
        self.local_folder = "c:\\downloadsitt"
        os.makedirs(self.local_folder, exist_ok=True)
        self.json_path = os.path.join(self.local_folder, "renew.json")

    def _load_local_data(self):
        if os.path.exists(self.json_path):
            with open(self.json_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def _save_local_data(self, data):
        with open(self.json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

    def _update_status(self, progress_bar, label, text, progress=None):
        label.config(text=text)
        if progress is not None:
            progress_bar["value"] = progress
        self.root.update_idletasks()

    def run_update(self, progress_bar, label):
        # 1. 關閉主程式
        self._update_status(progress_bar, label, "正在關閉主程式...")
        if not terminate_downloader_process("Downloader.exe"):
            messagebox.showwarning("警告", "無法自動關閉主程式，請手動關閉後再試。")
            self.root.destroy()
            return

        # 2. 取得遠端版本資訊
        self._update_status(progress_bar, label, "正在檢查更新...")
        try:
            response = requests.get(self.api_url)
            response.raise_for_status()
            data = response.json()
            latest_version = data["tag_name"]
            downloader_asset = next((asset for asset in data.get("assets", []) if asset["name"] == "Downloader.exe"), None)
        except requests.RequestException as e:
            messagebox.showerror("網路錯誤", f"無法取得版本資訊: {e}")
            self.root.destroy()
            return

        if not downloader_asset:
            messagebox.showerror("更新失敗", "在最新版本中找不到 Downloader.exe。")
            self.root.destroy()
            return

        # 3. 刪除舊檔案
        local_data = self._load_local_data()
        lo_path = local_data.get("下載位置") or "C:\\Downloader" # 提供預設路徑
        os.makedirs(lo_path, exist_ok=True)
        
        local_filename = local_data.get("檔案名稱")
        if local_filename:
            local_file_path = os.path.join(lo_path, local_filename)
            if os.path.exists(local_file_path):
                self._update_status(progress_bar, label, f"正在刪除舊版本: {local_filename}")
                os.remove(local_file_path)

        # 4. 下載新檔案
        download_url = downloader_asset["browser_download_url"]
        save_path = os.path.join(lo_path, downloader_asset["name"])
        
        try:
            response = requests.get(download_url, stream=True)
            response.raise_for_status()
            total_size = int(response.headers.get('Content-Length', 0))
            downloaded = 0
            with open(save_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
                    downloaded += len(chunk)
                    progress = (downloaded / total_size) * 100 if total_size > 0 else 0
                    self._update_status(progress_bar, label, f"正在更新... {progress:.2f}%", progress)
        except requests.RequestException as e:
            messagebox.showerror("下載失敗", f"下載檔案時發生錯誤: {e}")
            self.root.destroy()
            return

        # 5. 更新本地紀錄並啟動
        self._update_status(progress_bar, label, "更新完成，正在啟動新版本...", 100)
        local_data.update({"檔案名稱": downloader_asset["name"], "版本": latest_version})
        self._save_local_data(local_data)
        subprocess.Popen([save_path])
        time.sleep(1) # 給予一點時間讓新程序啟動
        self.root.destroy()

def renew_view():
    rview = tk.Tk()
    rview.title("安裝")
    rview.geometry("500x350")
    rview.resizable(False, False)
    rview.iconbitmap(ico_path)

    rview_frame = tk.Frame(rview)
    rview_frame.pack(pady=20, padx=20, fill="both", expand=True)

    rviewprogress_label = tk.Label(rview_frame, text="準備更新...")
    rviewprogress_label.pack(pady=10)
    label = tk.Label(rview_frame, text="更新完後會自動開啟")
    label.pack(pady=10)
    rviewprogress_bar = Progressbar(rview_frame, length=300, mode="determinate")
    rviewprogress_bar.pack(pady=10)
    
    updater = Updater(rview)
    rview.after(100, lambda: updater.run_update(rviewprogress_bar, rviewprogress_label))

    rview.mainloop()

renew_view()
