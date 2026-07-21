import os
import json
import requests
import customtkinter as ctk
import subprocess
import sys
import urllib.request

# 設定 GitHub 儲存庫資訊
REPO_OWNER = "SeanHsu324"
REPO_NAME = "Downloader"
API_URL = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/releases/latest"

# 設定本地存放路徑
LOCAL_CONFIG_FOLDER = "c:\\downloadsitt"
JSON_PATH = os.path.join(LOCAL_CONFIG_FOLDER, "renew.json")

def get_app_path():
    """取得目前執行檔所在的目錄"""
    if hasattr(sys, 'frozen'):
        return os.path.dirname(sys.executable)
    return os.path.abspath(".")

def load_local_data():
    """讀取本地版本資訊"""
    if os.path.exists(JSON_PATH):
        try:
            with open(JSON_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"讀取 JSON 失敗: {e}")
    return {}

def check_remote_version():
    """從 GitHub 取得最新版本資訊"""
    try:
        response = requests.get(API_URL, timeout=5)
        if response.status_code == 200:
            data = response.json()
            return {
                "latest_version": data["tag_name"],
                "assets": data["assets"],
                "release_notes": data.get("body", "沒有提供更新內容")
            }
    except Exception as e:
        print(f"檢查更新失敗: {e}")
    return None

def download_and_run_updater(version_info, app_path):
    """從 GitHub 下載 Updater.exe 並執行"""
    try:
        download_url = None
        # 從 assets 中尋找名稱包含 'Updater.exe' 的資源
        for asset in version_info["assets"]:
            if "Updater.exe" in asset["name"]:
                download_url = asset["browser_download_url"]
                break
        
        if not download_url:
            print("錯誤：GitHub Release 中找不到 Updater.exe")
            return

        save_path = os.path.join(app_path, "Updater.exe")
        print(f"正在下載更新程式: {download_url}")
        
        # 下載檔案
        urllib.request.urlretrieve(download_url, save_path)
        
        # 下載完後啟動並關閉主程式
        subprocess.Popen([save_path], cwd=app_path)
        sys.exit(0)
    except Exception as e:
        print(f"下載或執行 Updater 失敗: {e}")

def start_updater(version_info):
    """根據版本啟動更新程式"""
    app_path = get_app_path()
    latest_version = version_info["latest_version"]
    
    # 判斷版本系列
    is_v2 = latest_version.startswith("v1.1")
    updater_exe = os.path.join(app_path, "Updater.exe")
    rerenew_exe = os.path.join(app_path, "rerenew.exe")

    if is_v2:
        # v2 系列優先尋找 Updater.exe，沒有則下載
        if os.path.exists(updater_exe):
            subprocess.Popen([updater_exe], cwd=app_path)
            sys.exit(0)
        else:
            download_and_run_updater(version_info, app_path)
    else:
        # v1 系列執行 rerenew.exe
        if os.path.exists(rerenew_exe):
            subprocess.Popen([rerenew_exe], cwd=app_path)
            sys.exit(0)
        else:
            print(f"找不到更新程式: {rerenew_exe}")

def show_update_dialog(root, version_info):
    """顯示更新提示視窗"""
    latest_version = version_info["latest_version"]
    release_notes = version_info["release_notes"]
    app_path = get_app_path()
    
    is_v2 = latest_version.startswith("v1.1")
    updater_missing = is_v2 and not os.path.exists(os.path.join(app_path, "Updater.exe"))

    dialog = ctk.CTkToplevel(root)
    dialog.geometry("450x380")
    dialog.title("發現新版本")
    dialog.attributes("-topmost", True)

    if updater_missing:
        msg = f"新版本 {latest_version} 需要下載新的更新程式。\n點擊「立即下載」以繼續。"
        btn_text = "立即下載並更新"
    else:
        msg = f"發現新版本: {latest_version}\n是否立即更新?"
        btn_text = "立即更新"

    text_label = ctk.CTkLabel(dialog, text=msg, font=("Arial", 16, "bold"), wraplength=400)
    text_label.pack(pady=(20, 10))

      
    textbox = ctk.CTkTextbox(dialog, font=("Arial", 12))
    textbox.insert("1.0", f"更新內容：\n\n{release_notes}")
    textbox.configure(state="disabled")
    textbox.pack(pady=10, padx=20, fill="both", expand=True) 

    btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
    btn_frame.pack(side="bottom", pady=(10, 20), fill="x")

    def on_update():
        dialog.destroy()
        start_updater(version_info)

    update_btn = ctk.CTkButton(
        btn_frame, 
        text=btn_text, 
        command=on_update,
        font=("Arial", 14, "bold"),
        fg_color="#2fa572",
        hover_color="#106a43"
    )
    update_btn.pack(side="right", padx=20)

    close_btn = ctk.CTkButton(
        btn_frame, 
        text="稍後再說", 
        command=dialog.destroy,
        font=("Arial", 14)
    )
    close_btn.pack(side="right", padx=5)

    dialog.grab_set()

def check_for_updates(root, manual=False):
    """主進入點：檢查更新"""
    local_data = load_local_data()
    local_version = local_data.get("版本", "0.0.0")
    
    version_info = check_remote_version()
    if not version_info:
        if manual:
            print("無法連線至更新伺服器")
        return "無法連線至更新伺服器"

    latest_version = version_info["latest_version"]
    
    if latest_version != local_version:
        # 有新版本時彈出對話框
       show_update_dialog(root, version_info)
   