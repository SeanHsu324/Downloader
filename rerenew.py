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
    """取得資源的正確路徑（適用於開發和打包後的環境）"""
    if hasattr(sys, 'frozen'):  # 如果是打包後的執行檔
        base_path = sys._MEIPASS  # type: ignore
    else:  # 如果是開發環境
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

ico_path = resource_path("pt/ytd.ico")

def renew_view():
    rview = tk.Tk()  # 修正為tk.Tk()來創建視窗
    rview.title("安裝")
    rview.geometry("500x350")
    rview.resizable(False, False)
    rview.iconbitmap(ico_path)

    rview_frame = tk.Frame(rview)
    rviewprogress_label = tk.Label(rview_frame, text="更新中，請稍候...")
    rviewprogress_label.pack(pady=10)

    rviewprogress_bar = Progressbar(rview_frame, length=300, mode="determinate")
    rviewprogress_bar.pack(pady=10)

    rview_frame.pack(pady=20)

    # 設定 GitHub 儲存庫資訊
    repo_owner = "SeanHsu324"
    repo_name = "Downloader"
    api_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/releases/latest"

    # 設定本地存放路徑
    local_folder = "."
    os.makedirs(local_folder, exist_ok=True)  # 確保資料夾存在
    json_path = os.path.join(local_folder, "renew.json")

    # 讀取本地版本資訊
    if os.path.exists(json_path):
        with open(json_path, "r", encoding="utf-8") as f:
            local_data = json.load(f)
    else:
        local_data = {}

    # 取得 GitHub 最新版本資訊
    response = requests.get(api_url)
    if response.status_code == 200:
        data = response.json()
        latest_version = data["tag_name"]  # 取得最新版本號
        assets = data["assets"]  # 取得附件清單

        if assets:
            # 查找 Downloader.exe
            downloader_asset = next((asset for asset in assets if asset["name"] == "Downloader.exe"), None)

            if downloader_asset:
                filename = downloader_asset["name"]
                _url = downloader_asset["browser_download_url"]
                save_path = os.path.join(local_folder, filename)

                local_filename = local_data.get("檔案名稱")
                local_file_path = os.path.join(local_folder, local_filename) if local_filename else None

                # 刪除舊檔案（如果存在）
                if local_file_path and os.path.exists(local_file_path):
                    os.remove(local_file_path)
                    rviewprogress_label.configure(text=f"已刪除舊版本: {local_filename}")

                # 下載新檔案
                response = requests.get(_url, stream=True)
                if response.status_code == 200:
                    total_size = int(response.headers.get('Content-Length', 0))
                    downloaded = 0

                    with open(save_path, "wb") as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                                downloaded += len(chunk)
                                
                                # 避免 total_size 為 0
                                if total_size > 0:
                                    progress = (downloaded / total_size) * 100
                                    rviewprogress_bar["value"] = progress
                                    rviewprogress_label["text"] = f"正在更新... {progress:.2f}%"
                                    rview.update()

                    rviewprogress_label.configure(text=f"{filename} 下載完成！")

                    # 更新 renew.json
                    local_data["檔案名稱"] = filename
                    local_data["版本"] = latest_version
                    with open(json_path, "w", encoding="utf-8") as f:
                        json.dump(local_data, f, indent=4, ensure_ascii=False)

                    rviewprogress_label.configure(text="renew.json 已更新！")

                    # 執行 .exe 檔案
                    rviewprogress_label.configure(text=f"正在執行 {filename}...")
                    subprocess.Popen([save_path])  # 移除 shell=True

                    time.sleep(2)
                    rview.destroy()  # 修正這裡
                    sys.exit()  # 強制關閉 Python 進程
                else:
                    messagebox.showerror("下載失敗！")
            else:
                messagebox.showerror("未找到 Downloader.exe")
        else:
            messagebox.showerror("Release 無附件可下載")
    else:
        messagebox.showerror(f"無法取得 Release 資訊，錯誤碼: {response.status_code}")

    rview.mainloop()

# 開始更新視窗
renew_view()
