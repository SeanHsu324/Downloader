import os
import json
import requests
import customtkinter as ctk


"""檢查 GitHub 上的更新版本並提示更新"""
# 設定 GitHub 儲存庫資訊
repo_owner = "SeanHsu324"
repo_name = "Downloader"
api_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/releases/latest"

response = requests.get(api_url)
if response.status_code == 200:
    data = response.json()
    latest_version = data["tag_name"]  # 取得最新版本號
    assets = data["assets"]  # 取得附件清單
    release_notes = data.get("body", "沒有提供更新內容")
else:
    print(f"無法取得 Release 資訊，錯誤碼: {response.status_code}")

# 設定本地存放路徑
local_folder = "c:\\downloadsitt"
json_path = os.path.join(local_folder, "renew.json")

# 讀取本地版本資訊
if os.path.exists(json_path):
    with open(json_path, "r", encoding="utf-8") as f:
        local_data = json.load(f)
else:
    local_data = {}  # 如果沒有 renew.json，假設為空字典

local_version = local_data.get("版本")
local_path = local_data.get("下載位置")

main_root = None  # 用於儲存 main.py 的 root

def set_main_root(root):
    global main_root
    main_root = root
# 記錄計時器 ID
animation_id = None

def work(renew_root):
    global main_root
    """執行更新並關閉主視窗"""
    os.system(local_path + "\\rerenew.exe")
    print(local_path + "\\rerenew.exe")


def renew_root(first_open, root):
    if first_open != 1:
        first_open = 1
        print(f"renew_root:{first_open}")
        return
    else:

        """顯示更新提示視窗"""
        renew_root = ctk.CTkToplevel(root)
        renew_root.geometry("400x200")
        renew_root.resizable(False, False)
        renew_root.title("更新")
        renew_root.attributes("-topmost", True)
        

        text_label = ctk.CTkLabel(
            renew_root, 
            text=f"新版本:{latest_version}\n是否更新？",
            font=("Arial", 20, "bold")
        )
        text_label.pack(pady=10)

        textbox = ctk.CTkTextbox(renew_root, height=60, font=("Arial", 14))
        textbox.insert("1.0", f"更新內容\n{release_notes}")
        textbox.configure(state="disabled")  # 設為唯讀
        textbox.pack(pady=10, padx=20, fill="both", expand=False)

        btn_frame = ctk.CTkFrame(renew_root, fg_color="transparent")
        btn_frame.pack()

        renew_start = ctk.CTkButton(
            btn_frame, 
            text="更新", 
            command=lambda:work(renew_root),  # 按下後執行更新，並關閉 main.py 的 root
            font=("Arial", 20, "bold")
        )
        renew_start.pack(side="right", padx=5)

        renew_root_button = ctk.CTkButton(
            btn_frame, 
            text="關閉", 
            command=renew_root.destroy, 
            font=("Arial", 20, "bold")
        )
        renew_root_button.pack(side="left", padx=5)

        renew_root.grab_set()

settings_path = (local_path+"\\settings.json")

def renew(first_open, root):
    first_open = 1

    if assets:
        # 讀取本地檔案資訊
        local_version = local_data.get("版本")
        print(f"版本:{local_version}")

        # 如果版本相同，直接執行
        if local_version == latest_version:
            print(f"已是最新版本")
            print(f"{local_version}={latest_version}")
        else:
            print(f"{local_version}!={latest_version}")
            print(f"發現新版本 {latest_version}，正在更新...")
            renew_root(first_open, root)

    else:
        print("此 Release 沒有可下載的檔案！")

def download_data(json_path):
    repo_name = "Setup"
    api_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/releases/latest"
    response = requests.get(api_url)
    if response.status_code == 200:
        data = response.json()
        release_notes = data.get("body", "沒有提供更新內容")
    else:
        print(f"無法取得 Release 資訊，錯誤碼: {response.status_code}")

    sett_path = json_path
    os.makedirs(sett_path, exist_ok=True)
    
    # 設定 JSON 檔案路徑
    json_file_path = os.path.join(sett_path, "settings.json")

    # 讀取現有的 JSON 設定，若沒有則創建預設設定
    if os.path.exists(json_file_path):
        with open(json_file_path, "r") as file:
            settings = json.load(file)
            
            with open(json_file_path, "w") as file:
                json.dump(settings, file)

