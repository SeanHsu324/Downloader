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
def terminate_downloader_process(exe_name="Downloader.exe"):
    try:
        subprocess.run(["taskkill", "/F", "/IM", exe_name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        print(f"關閉 {exe_name} 發生錯誤：{e}")
    while True:
        result = subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {exe_name}"], capture_output=True, text=True)
        if exe_name not in result.stdout:
            break
        time.sleep(1)

def renew_view():
    rview = tk.Tk()
    rview.title("安裝")
    rview.geometry("500x350")
    rview.resizable(False, False)
    rview.iconbitmap(ico_path)

    rview_frame = tk.Frame(rview)
    rviewprogress_label = tk.Label(rview_frame, text="關閉主程式中...")
    rviewprogress_label.pack(pady=10)
    label = tk.Label(rview_frame, text="更新完後會自動開啟")
    label.pack(pady=10)
    rviewprogress_bar = Progressbar(rview_frame, length=300, mode="determinate")
    rviewprogress_bar.pack(pady=10)
    rview_frame.pack(pady=20)
    rview.update()

    # 自動關閉 Downloader.exe
    terminate_downloader_process("Downloader.exe")
    rviewprogress_label.configure(text="開始更新中...")
    rview.update()

    repo_owner = "SeanHsu324"
    repo_name = "Downloader"
    api_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/releases/latest"

    local_folder = "c:\\downloadsitt"
    os.makedirs(local_folder, exist_ok=True)
    json_path = os.path.join(local_folder, "renew.json")

    if os.path.exists(json_path):
        with open(json_path, "r", encoding="utf-8") as f:
            local_data = json.load(f)
    else:
        local_data = {}

    response = requests.get(api_url)
    if response.status_code == 200:
        data = response.json()
        latest_version = data["tag_name"]
        assets = data["assets"]

        if assets:
            downloader_asset = next((asset for asset in assets if asset["name"] == "Downloader.exe"), None)

            if downloader_asset:
                filename = downloader_asset["name"]
                _url = downloader_asset["browser_download_url"]
                lo_path = local_data.get("下載位置") or "C:\\Downloader"
                save_path = os.path.join(lo_path, filename)

                local_filename = local_data.get("檔案名稱")
                local_file_path = os.path.join(lo_path, local_filename) if local_filename else None

                if local_file_path and os.path.exists(local_file_path):
                    os.remove(local_file_path)
                    rviewprogress_label.configure(text=f"已刪除舊版本: {local_filename}")
                    rview.update()

                response = requests.get(_url, stream=True)
                if response.status_code == 200:
                    total_size = int(response.headers.get('Content-Length', 0))
                    downloaded = 0

                    with open(save_path, "wb") as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                                downloaded += len(chunk)
                                if total_size > 0:
                                    progress = (downloaded / total_size) * 100
                                    rviewprogress_bar["value"] = progress
                                    rviewprogress_label["text"] = f"正在更新... {progress:.2f}%"
                                    rview.update()

                    rviewprogress_label.configure(text=f"{filename} 下載完成！")
                    local_data["檔案名稱"] = filename
                    local_data["版本"] = latest_version
                    with open(json_path, "w", encoding="utf-8") as f:
                        json.dump(local_data, f, indent=4, ensure_ascii=False)

                    rviewprogress_label.configure(text="renew.json 已更新！")

                    # 啟動新版 Downloader.exe
                    rviewprogress_label.configure(text="啟動新版 Downloader.exe 中...")
                    rview.update()
                    subprocess.Popen([save_path])
                    time.sleep(1)
                    rview.destroy()
                    sys.exit()
                else:
                    messagebox.showerror("下載失敗", "下載檔案時發生錯誤")
            else:
                messagebox.showerror("未找到 Downloader.exe", "在 Release 中找不到 Downloader.exe")
        else:
            messagebox.showerror("Release 無附件", "此版本沒有可下載的檔案")
    else:
        messagebox.showerror("取得 Release 資訊失敗", f"錯誤碼: {response.status_code}")

    rview.mainloop()

renew_view()
