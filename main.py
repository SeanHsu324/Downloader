'''主程式視窗(啟動點)'''


import colorsys
import json
import os
import sys
import threading
import tkinter as tk
import webbrowser
from re import search
from tkinter import colorchooser, filedialog, messagebox

import customtkinter as ctk
from PIL import Image
 
from modules.log import logger  # type: ignore
from modules.download import on_download_button_click, set_main_view, download_set_logger # type: ignore

from modules.word import browse_file, browse_folder, start_conversion, word_set_logger # type: ignore
from modules.mp4_to_mp3 import mp3, convert_mp4_to_mp3, mp34_set_logger # type: ignore
from modules.renew import check_for_updates, renew_set_logger, check_tool_updates  # type: ignore




download_set_logger(logger)
word_set_logger(logger)
mp34_set_logger(logger)
renew_set_logger(logger)


APP_TITLE = "Downloader"
WINDOW_SIZE = "640x350"
SPLASH_SIZE = (432, 102)
SPLASH_DURATION_MS = 5000
JSON_ENCODING = "utf-8"
DEFAULT_DOWNLOAD_FOLDER = os.path.join(
    os.path.expanduser("~"), "Desktop", "youtube下載"
)
FONT_TITLE = ("Arial", 50, "bold")
FONT_LARGE = ("Arial", 20, "bold")
FONT_NORMAL = ("Arial", 16)
BUTTON_RADIUS = 40
PRIMARY_BUTTON_SIZE = (150, 150)
SECONDARY_BUTTON_SIZE = (100, 100)
CONTROL_SIZE = (200, 40)
ICON_SIZE = (50, 45)


def resource_path(relative_path: str) -> str:

    """取得資源的正確路徑（適用於開發和打包後的環境）"""
    base_path = getattr(sys, "_MEIPASS", os.path.abspath("."))
    return os.path.join(base_path, relative_path)

# --- 資源路徑 ---
try:
    picture_path = resource_path("picture/stary.png")
    ico_path = resource_path("picture/yt.ico")
    setting_white_path = resource_path("picture/setting_white.png")
    setting_black_path = resource_path("picture/setting_black.png")
    return_white_path = resource_path("picture/return_white.png")
    return_black_path = resource_path("picture/return_black.png")
    notify_white_path = resource_path("picture/notify_white.png")
    notify_black_path = resource_path("picture/notify_black.png")
except Exception as e:
    logger.write_log(f"資源路徑載入失敗:{e}")

# --- 核心修改：啟動畫面函式 ---
def splash_screen(main_root):
    """載入畫面，依附於主視窗。"""
    splash = ctk.CTkToplevel(main_root)
    splash.overrideredirect(True)
    splash.attributes("-topmost", True)

    # 載入圖片並保持參考，防止被垃圾回收。
    try:
        img = Image.open(picture_path)
        img = img.resize(SPLASH_SIZE)
        splash.splash_img_ref = ctk.CTkImage(img, size=SPLASH_SIZE)
    except Exception as e:
        error_msg = f"無法載入啟動畫面圖片: {e}"
        print(error_msg)
        logger.write_log(error_msg)
        splash.splash_img_ref = None

    # 設定視窗大小與位置。
    win_width, win_height = SPLASH_SIZE
    screen_width = splash.winfo_screenwidth()
    screen_height = splash.winfo_screenheight()
    x = (screen_width - win_width) // 2
    y = (screen_height - win_height) // 2
    splash.geometry(f"{win_width}x{win_height}+{x}+{y}")

    if splash.splash_img_ref:
        label = ctk.CTkLabel(splash, image=splash.splash_img_ref, text="")
        label.pack()

    def show_main_window():
        """銷毀啟動畫面並顯示主視窗。"""
        if splash.winfo_exists():
            splash.destroy()
        main_root.deiconify()

    splash.after(SPLASH_DURATION_MS, show_main_window)
    return splash

# --- 核心修改：應用程式初始化流程 ---
# 1. 建立整個應用程式唯一的根視窗
root = ctk.CTk()
# 2. 立即隱藏主視窗，直到啟動畫面結束
root.withdraw()

# --- 主視窗設定 ---
root.geometry(WINDOW_SIZE)

root.resizable(False, False)
root.title(APP_TITLE)

root.iconbitmap(ico_path)

# 3. 啟動載入畫面，傳入唯一的 root
splash = splash_screen(root)

# --- 開始載入主程式其餘部分 ---
threads = []
first_open = 0


download_folder = DEFAULT_DOWNLOAD_FOLDER


settings = {}

def log_message(message: str) -> None:
    """同時輸出到終端與應用程式日誌。"""
    print(message)
    logger.write_log(message)


def write_json_file(file_path: str, data: dict, label: str) -> bool:
    """以 UTF-8、格式化且接近原子性的方式寫入 JSON 設定。"""
    temporary_path = f"{file_path}.tmp"
    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(temporary_path, "w", encoding=JSON_ENCODING) as file:
            json.dump(data, file, ensure_ascii=False, indent=4)
            file.write("\n")
        os.replace(temporary_path, file_path)
        return True
    except (OSError, TypeError, ValueError) as error:
        log_message(f"寫入 {label} 失敗: {error}")
        try:
            if os.path.exists(temporary_path):
                os.remove(temporary_path)
        except OSError:
            pass
        return False


def load_json_with_defaults(file_path: str, defaults: dict, label: str) -> tuple[dict, bool]:
    """讀取設定 JSON，補齊缺欄位並回傳是否需要回寫。"""
    data = {}
    needs_save = not os.path.exists(file_path)

    if not needs_save:
        try:
            with open(file_path, "r", encoding=JSON_ENCODING) as file:
                loaded_data = json.load(file)
            if isinstance(loaded_data, dict):
                data = loaded_data
            else:
                raise ValueError("JSON 根節點必須是物件")
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as error:
            log_message(f"讀取 {label} 失敗，將重建預設檔: {error}")
            needs_save = True

    merged_data = defaults.copy()
    merged_data.update(data)
    if merged_data != data:
        needs_save = True
    return merged_data, needs_save


def normalize_settings(data: dict, defaults: dict) -> bool:
    """修復已存在但型別或值不合法的設定；未知欄位保持不變。"""
    changed = False

    def ensure_string(key: str) -> None:
        nonlocal changed
        value = data.get(key)
        if not isinstance(value, str) or not value.strip():
            data[key] = defaults[key]
            changed = True

    # 檢查背景主題
    if data.get("background_color") not in {"Dark", "Light", "System"}:
        data["background_color"] = defaults["background_color"]
        changed = True

    QUALITY_FORMAT_MIGRATIONS = {
    "bestvideo[ext=mp4]+bestaudio/mp4": "bv*+ba/b",
    "bestvideo[height<=1080]+bestaudio/mp4": "bv*[height<=1080]+ba/b",
    "bestvideo[height<=720]+bestaudio/mp4": "bv*[height<=720]+ba/b",
    "bestvideo[height<=480]+bestaudio/mp4": "bv*[height<=480]+ba/b",
    "bestvideo[height<=240]+bestaudio/mp4": "bv*[height<=240]+ba/b",
    "bestvideo[height<=144]+bestaudio/mp4": "bv*[height<=144]+ba/b",
}

    old_mp4 = data.get("mp4")
    new_mp4 = QUALITY_FORMAT_MIGRATIONS.get(old_mp4)
    if new_mp4 is not None and new_mp4 != old_mp4:
        data["mp4"] = new_mp4
        changed = True


    if data.get("mp3") != "ba/best":
        data["mp3"] = "ba/best"
        changed = True    
            
    if data.get("oauth_check_button") == "True" :###未完成
        data["oauth_check_button"] = "False"
        changed = True 
    for key in (
        "subject_color",
        "text_color",
        "hover_color",
        "download_folder",
    ):
        ensure_string(key)

    # 檢查布林值字串欄位
    for key in ("check_button", "renew_check_button"):
        if data.get(key) not in {"True", "False"}:
            data[key] = defaults[key]
            changed = True

    return changed


def on_closing():
    """關閉主視窗並結束程式。"""
    root.destroy()
    sys.exit()


root.protocol("WM_DELETE_WINDOW", on_closing)
set_main_view(root)


####################   json   ####################
work_path = r"c:\downloadsitt"
json_work_path = os.path.join(work_path, "renew.json")

if os.path.exists(json_work_path):
    with open(json_work_path, "r", encoding="utf-8") as f:
        local_data = json.load(f)
else:
    local_data = {}

down_path = local_data.get("下載位置") or os.getcwd()

if down_path == None:
    try:
        existing_data = {}
        if os.path.exists(json_work_path):
            with open(json_work_path, "r", encoding="utf-8") as f:
                existing_data = json.load(f)
        existing_data["下載位置"] = os.getcwd()

        with open(json_work_path, "w", encoding="utf-8") as f:
            json.dump(existing_data, f, indent=4, ensure_ascii=False)
    except: pass


ffmpeg_path = os.path.join(down_path, "bin/ffmpeg", "ffmpeg.exe")
msg = f"FFmpeg 路徑: {ffmpeg_path}"
print(msg)
logger.write_log(msg)

sett_path = down_path or os.getcwd()
log_message(f"sett_path: {sett_path}")
os.makedirs(sett_path, exist_ok=True)


json_file_path = os.path.join(sett_path, "settings.json")
default_settings = {
    "background_color": "Dark",
    "subject_color": "#478058",
    "text_color": "black",
    "hover_color": "#223E2A",
    "mp4": "bv*+ba/b",
    "mp3": "ba/best",
    "download_folder": download_folder,
    "check_button": "True",
    "renew_check_button": "True",
    "oauth_check_button": "False",
}
settings, settings_needs_save = load_json_with_defaults(
    json_file_path, default_settings, "settings.json"
)
settings_needs_save = normalize_settings(settings, default_settings) or settings_needs_save
if settings_needs_save:
    write_json_file(json_file_path, settings, "settings.json")

# 安全設定主題顏色。
ctk.set_appearance_mode(settings.get("background_color", "Dark"))


# --- 函式定義 ---

def save_settings() -> bool:
    """儲存目前設定；所有 UI 設定事件都應透過此函式寫入。"""
    return write_json_file(json_file_path, settings, "settings.json")


VIDEO_QUALITY_FORMATS = {
    "最高畫質": "bv*+ba/b",
    "1080p": "bv*[height<=1080]+ba/b",
    "720p": "bv*[height<=720]+ba/b",
    "480p": "bv*[height<=480]+ba/b",
    "240p": "bv*[height<=240]+ba/b",
    "144p": "bv*[height<=144]+ba/b",
}

BACKGROUND_MODES = {"深色": "Dark", "淺色": "Light", "系統": "System"}
MENU_PALETTES = {
    "Dark": {
        "bg": "#2a2a2a",
        "fg": "white",
        "active_bg": "#3e3e3e",
        "active_fg": "white",
    },
    "Light": {
        "bg": "#f0f0f0",
        "fg": "black",
        "active_bg": "#d9d9d9",
        "active_fg": "black",
    },
}


def open_link_in_thread(url: str) -> None:

    """
    在一個獨立的執行緒中安全地開啟連結。
    這可以避免 webbrowser 模組在主 Tkinter 執行緒中呼叫底層 OS API 
    時可能發生的 GIL 衝突。
    """
    threading.Thread(target=lambda: webbrowser.open(url), daemon=True).start()


def set_background_color(choice: str) -> None:
    mode = BACKGROUND_MODES.get(choice)
    if mode is None:
        return
    settings["background_color"] = mode
    ctk.set_appearance_mode(mode)
    save_settings()
    if "menu" in globals():
        apply_menu_style()


def set_Image_quality(choice: str) -> None:
    settings["mp4"] = VIDEO_QUALITY_FORMATS.get(
        choice, VIDEO_QUALITY_FORMATS["最高畫質"]
    )
    save_settings()


def on_format_change(choice: str) -> None:
    is_disabled = choice in ("選擇格式", "mp3")
    Image_quality_menu.configure(state="disabled" if is_disabled else "normal")
    yt_button.configure(
        state="disabled" if choice == "選擇格式" else "normal"
    )


def match_search(format_str: str) -> str:
    match = search(r"height(?:<=|=)(\d+)", format_str)
    return match.group(1) + "p" if match else "最高畫質"

def open_link(url: str) -> None:
    open_link_in_thread(url)


def is_light_color(hex_color: str) -> bool:
    hex_color = hex_color.lstrip("#")
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    return (r * 299 + g * 587 + b * 114) / 1000 > 127

def darken_color(color: str, percent: float):
    color = color.lstrip("#")
    r, g, b = int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)
    h, l, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
    l = max(0, l - (percent / 100))
    r, g, b = colorsys.hls_to_rgb(h, l, s)
    return f"#{int(r * 255):02X}{int(g * 255):02X}{int(b * 255):02X}"

def choose_color() -> None:
    color_code = colorchooser.askcolor()[1]
    if not color_code:
        return
    settings["subject_color"] = color_code
    settings["text_color"] = "black" if is_light_color(color_code) else "white"
    settings["hover_color"] = darken_color(color_code, 20)
    save_settings()
    load()


def load() -> None:
    """把設定套用到主題、下拉選單及所有主要控制項。"""
    background_mode = settings.get("background_color", "System")
    backgroundcolor_menu.set(
        {value: key for key, value in BACKGROUND_MODES.items()}.get(
            background_mode, "系統"
        )
    )
    ctk.set_appearance_mode(background_mode)
    Image_quality_menu.set(match_search(settings.get("mp4", "")))

    items = [
        dropdown_menu,
        Image_quality_menu,
        backgroundcolor_menu,
        wordlabel,
        mp3label,
    ]
    buttons = [
        loadbutton,
        backbutton,
        home_button,
        previous_button,
        wordbutton,
        wordstart_button,
        changebutton,
        change_download_folder,
        log_button,
        wordbrowse_folder_button,
        wordbrowse_file_button,
        mp3start_button,
        mp3browse_button,
        mp4_to_mp3button,
        yt_button,
    ]

    fg_color = settings.get("subject_color", default_settings["subject_color"])
    text_color = settings.get("text_color", default_settings["text_color"])
    hover_color = settings.get("hover_color", default_settings["hover_color"])

    for component in items:
        component.configure(fg_color=fg_color, text_color=text_color)
    for button in buttons:
        button.configure(
            fg_color=fg_color,
            text_color=text_color,
            hover_color=hover_color,
        )

    root.bind("<Button-3>", show_fuontion_menu)

def paste_text():
    try: url_box.insert(tk.END, root.clipboard_get())
    except tk.TclError: pass

def cut_text():
    try:
        root.clipboard_clear()
        root.clipboard_append(url_box.selection_get())
        url_box.delete("sel.first", "sel.last")
    except tk.TclError: pass

def select_all():
    url_box.select_range(0, tk.END)
    url_box.icursor(tk.END)

def show_context_menu(event): menu.post(event.x_root, event.y_root)


def teaching() -> None:
    open_link_in_thread(
        "https://sites.google.com/view/yt-to-dowload/%E6%95%99%E5%AD%B8/%E6%95%99%E5%AD%B8"
    )


oauth_info_window = None


def show_oauth_info_window() -> None:
    global oauth_info_window
    if oauth_info_window is not None and oauth_info_window.winfo_exists():
        oauth_info_window.deiconify()
        oauth_info_window.lift()
        oauth_info_window.focus_force()
        return

    oauth_info_window = ctk.CTkToplevel(root)
    info_window = oauth_info_window
    info_window.title("OAuth2 裝置驗證說明")
    info_window.geometry("520x300")
    info_window.resizable(False, False)
    info_window.transient(root)
    info_window.lift()
    info_window.focus_force()
    ctk.CTkLabel(
        info_window,
        text="OAuth2 裝置驗證說明",
        font=("Arial", 22, "bold"),
    ).pack(pady=(20, 10))
    ctk.CTkLabel(
        info_window,
        text=(
            "OAuth2 只會授權目前下載所需的 YouTube 存取權，\n"
            "本程式不會要求或接觸您的帳號密碼。\n\n"
            "此模式適合需要登入驗證的限制影片；請避免大量或連續下載，\n"
            "以降低觸發 YouTube 風控或帳號限制的風險。建議使用非主要帳號。"
        ),
        justify="left",
        wraplength=450,
    ).pack(padx=24, pady=10)
    ctk.CTkButton(
        info_window, text="關閉", width=110, command=info_window.destroy
    ).pack(pady=12)


def teaching_2() -> None:
    show_oauth_info_window()


def teaching_3() -> None:
    open_link_in_thread("https://sites.google.com/view/yt-to-dowload/教學/取得網址")


def show_fuontion_menu(event) -> None:
    fuontionmenu.post(event.x_root, event.y_root)


def select_download_folder() -> None:
    folder = filedialog.askdirectory(
        title="變更下載位置",
        initialdir=settings.get("download_folder", download_folder),
    )
    if folder:
        settings["download_folder"] = folder
        save_settings()


def choose_Check_value() -> None:
    settings["check_button"] = status_var.get()
    save_settings()


def renew_choose_Check_value() -> None:
    current_value = settings.get("renew_check_button", "True")
    new_value = renew_status_var.get()

    if current_value == "True" and new_value == "False":
        confirmed = messagebox.askyesno(
            title="操作確認",
            message="確定關閉「檢查更新」嗎？\n這可能會導致您錯過重要的軟體更新。",
        )
        if not confirmed:
            renew_status_var.set(current_value)
            return

    settings["renew_check_button"] = new_value
    save_settings()


def oauth_choose_Check_value() -> None:
    new_value = oauth_status_var.get()
    settings["oauth_check_button"] = new_value
    save_settings()


class ToolTip:
    """建立一個通用的提示框，可傳入字串或回呼函式"""
    def __init__(self, widget, text_provider):
        self.widget = widget
        self.text_provider = text_provider  # 可以是字串，也可以是一個 lambda 函式
        self.tipwindow = None
        self.id = None
        
        # 綁定滑鼠事件
        self.widget.bind("<Enter>", self.enter)
        self.widget.bind("<Leave>", self.leave)

    def enter(self, event=None):
        self.schedule()

    def leave(self, event=None):
        self.unschedule()
        self.hidetip()

    def schedule(self):
        self.unschedule()
        self.id = self.widget.after(50, self.showtip)

    def unschedule(self):
        _id = self.id
        self.id = None
        if _id:
            self.widget.after_cancel(_id)

    def showtip(self, event=None):
        # 判斷 text_provider 是字串還是函式，動態獲取內容
        if callable(self.text_provider):
            text = self.text_provider()
        else:
            text = self.text_provider

        if self.tipwindow or not text:
            return
        
        self.tipwindow = ctk.CTkToplevel(self.widget)
        self.tipwindow.wm_overrideredirect(True) 
        
        # 計算位置
        x = self.widget.winfo_rootx()
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 10
        self.tipwindow.wm_geometry(f"+{x}+{y}")

        label = ctk.CTkLabel(self.tipwindow, text=text, justify="left", 
                             fg_color=("#3a3a3a", "#3a3a3a"), 
                             text_color="white", 
                             corner_radius=5,
                             padx=10, pady=5)
        label.pack(ipadx=1)

    def hidetip(self):
        tw = self.tipwindow
        self.tipwindow = None
        if tw:
            tw.destroy()

# --- 頁面切換函式 ---
PAGE_WIDGETS = []
SETTING_PAGE_WIDGETS = []


def _hide_widget(widget) -> None:
    """按照元件目前使用的 geometry manager 隱藏元件。"""
    manager = widget.winfo_manager()
    if manager == "pack":
        widget.pack_forget()
    elif manager == "place":
        widget.place_forget()
    elif manager == "grid":
        widget.grid_forget()


def _hide_widgets(widgets) -> None:
    """按照子元件到外層容器的順序隱藏一組元件。"""
    for widget in reversed(widgets):
        _hide_widget(widget)


def _hide_all_pages() -> None:
    """每次切換頁面前，統一隱藏已註冊的頁面元件。"""
    _hide_widgets(PAGE_WIDGETS)


def _hide_navigation(*widgets):
    """隱藏指定的頂部導覽按鈕。"""
    for widget in widgets:
        _hide_widget(widget)


def ytdownload():
    """下載頁：只負責設定下載頁的綁定與元件位置。"""
    _hide_all_pages()
    _hide_navigation(sett_button, previous_button)

    root.bind("<Button-3>", show_fuontion_menu)
    url_box.bind("<Button-3>", show_context_menu)
    url_box.focus_set()

    home_button.place(relx=0.05, rely=0.05)
    url_box.pack(pady=(50, 10))
    menu_frame.pack(pady=(20, 20))
    dropdown_menu.pack(side="left", padx=10)
    Image_quality_menu.pack(side="left", padx=10)
    yt_button.pack(pady=(20, 10))


def backhomepag():
    """主頁：顯示主要功能按鈕。"""
    _hide_all_pages()
    # 設定頁含有巢狀 pack 容器，額外明確收起一次以避免切回主頁時殘留。
    _hide_widgets(SETTING_PAGE_WIDGETS)
    _hide_navigation(home_button, previous_button)

    root.bind("<Button-3>", show_fuontion_menu)
    url_box.unbind("<Button-3>")
    root.focus()

    text_label.pack(pady=(20, 10))
    button_frame.pack(expand=True)
    loadbutton.pack(side="left", padx=20)
    backbutton.pack(side="left", padx=20)
    sett_button.place(relx=0.9, rely=0.05)


def setepag():
    """設定頁：顯示原有設定元件，位置與參數維持不變。"""
    _hide_all_pages()
    _hide_navigation(sett_button, previous_button)

    root.unbind("<Button-3>")
    url_box.unbind("<Button-3>")
    root.focus()

    home_button.place(relx=0.05, rely=0.05)
    sett_menu_frame.pack(expand=True, fill="both", padx=20, pady=(50, 20))
    sett_menu_frame_left.pack(side="left", expand=True, fill="both")
    sett_menu_frame_right.pack(side="right", expand=True, fill="both")
    backgroundcolor_menu.pack(side="top", anchor="w", padx=40, pady=(20, 20))
    changebutton.pack(side="top", anchor="w", padx=40, pady=(10, 20))
    log_button.pack(side="top", anchor="w", padx=40, pady=(10, 10))
    change_download_folder.pack(side="top", anchor="w", pady=(20, 20))
    check_button.pack(side="top", anchor="w", pady=(10, 20))
    renew_check_button.pack(side="top", anchor="w", pady=(10, 20))
    oauth_check_button.pack(side="top", anchor="w", pady=(10, 10))
   


def function():
    """其他功能頁：顯示 Word/PDF 與 MP4/MP3 功能按鈕。"""
    _hide_all_pages()
    _hide_navigation(sett_button, previous_button)

    root.unbind("<Button-3>")
    url_box.unbind("<Button-3>")
    function_frame.pack(expand=True)
    wordbutton.pack(side="left", padx=20)
    mp4_to_mp3button.pack(side="left", padx=20)
    home_button.place(relx=0.05, rely=0.05)


def word():
    """Word/PDF 轉換頁：由其他功能頁的 wordbutton 呼叫。"""
    _hide_all_pages()
    _hide_navigation(home_button, sett_button)

    root.bind("<Button-3>", show_fuontion_menu)
    url_box.unbind("<Button-3>")
    previous_button.place(relx=0.05, rely=0.05)
    wordlabel.pack(pady=(50, 10))
    wordbrowse_folder_button.pack(pady=20)
    wordbrowse_file_button.pack(pady=20)
    wordstart_button.pack(pady=20)


def mp3_page():
    """MP4 轉 MP3 頁：由其他功能頁的 mp4_to_mp3button 呼叫。"""
    _hide_all_pages()
    _hide_navigation(home_button, sett_button)

    root.bind("<Button-3>", show_fuontion_menu)
    url_box.unbind("<Button-3>")
    previous_button.place(relx=0.05, rely=0.05)
    mp3label.pack(pady=(50, 20))
    mp3browse_button.pack(pady=10)
    mp3start_button.pack(pady=20)


# 每個頁面都由自己的 def 負責顯示；按鈕 command 維持原本的函式名稱。
# backhomepag()、ytdownload()、function()、setepag()、word()、mp3_page()
# 皆可直接被其他元件或程式流程呼叫。

# --- UI 元件建立 ---

# 主頁
text_label = ctk.CTkLabel(
    root, text="選擇功能", font=FONT_TITLE, fg_color="transparent"
)

text_label.pack(pady=(20, 10))
button_frame = ctk.CTkFrame(root, fg_color="transparent")
button_frame.pack(expand=True)
loadbutton = ctk.CTkButton(
    button_frame,
    text="下載\nYouTube",
    command=ytdownload,
    width=PRIMARY_BUTTON_SIZE[0],
    height=PRIMARY_BUTTON_SIZE[1],
    corner_radius=BUTTON_RADIUS,
    font=FONT_LARGE,
)
loadbutton.pack(side="left", padx=20)
backbutton = ctk.CTkButton(
    button_frame,
    text="其他功能",
    command=function,
    width=PRIMARY_BUTTON_SIZE[0],
    height=PRIMARY_BUTTON_SIZE[1],
    corner_radius=BUTTON_RADIUS,
    font=FONT_LARGE,
)

backbutton.pack(side="left", padx=20)

# 下載頁
url_box = ctk.CTkEntry(
    root,
    placeholder_text="輸入網址",
    width=300,
    height=50,
    fg_color="transparent",
    font=FONT_LARGE,
)
menu_frame = ctk.CTkFrame(root, fg_color="transparent")
dropdown_menu = ctk.CTkOptionMenu(
    menu_frame,
    values=["選擇格式", "mp4", "mp3"],
    command=on_format_change,
    width=CONTROL_SIZE[0],
    height=CONTROL_SIZE[1],
    font=FONT_LARGE,
)

dropdown_menu.set("選擇格式")
Image_quality_menu = ctk.CTkOptionMenu(
    menu_frame,
    values=list(VIDEO_QUALITY_FORMATS),
    command=set_Image_quality,
    width=CONTROL_SIZE[0],
    height=CONTROL_SIZE[1],
    font=FONT_LARGE,
)

Image_quality_menu.configure(state="disabled")
yt_button = ctk.CTkButton(
    root,
    text="開始下載",
    width=100,
    height=40,
    corner_radius=BUTTON_RADIUS,
    command=lambda: on_download_button_click(
        root,
        url_box,
        dropdown_menu,
        ffmpeg_path,
        first_open,
        settings["mp3"],
        settings["mp4"],
        settings["download_folder"],
        settings["check_button"],
        settings["oauth_check_button"],
    ),
    font=FONT_LARGE,
)

yt_button.configure(state="disabled")
home_button = ctk.CTkButton(
    root,
    text="首頁",
    corner_radius=10,
    width=55,
    height=40,
    command=backhomepag,
    font=FONT_LARGE,
)

# 設定頁
try:
    root.setting_pil_image_black = Image.open(setting_black_path)
    root.setting_pil_image_white = Image.open(setting_white_path)

    msg = "圖片載入成功!"
    print(msg)
    logger.write_log(msg)

    setting_button_icon = ctk.CTkImage(
        dark_image=root.setting_pil_image_white,
        light_image=root.setting_pil_image_black,
        size=ICON_SIZE,
    )

except Exception as e:
    error_msg = f"載入設定圖示時發生錯誤: {e}"
    print(error_msg)
    logger.write_log(error_msg)

    setting_button_icon = None

if setting_button_icon:
    sett_button = ctk.CTkButton(
        root,
        text="",
        image=setting_button_icon,
        fg_color="transparent",
        hover_color="#99A19B",
        corner_radius=10,
        width=40,
        height=40,
        command=setepag,
    )
else:
    sett_button = ctk.CTkButton(
        root,
        text="設定",
        corner_radius=10,
        width=60,
        height=40,
        command=setepag,
        font=FONT_NORMAL,
    )

ToolTip(sett_button, "設定")
sett_button.place(relx=0.9, rely=0.05)
sett_menu_frame = ctk.CTkFrame(root, fg_color="transparent")

sett_menu_frame_left = ctk.CTkFrame(sett_menu_frame, fg_color="transparent")
sett_menu_frame_right = ctk.CTkFrame(sett_menu_frame, fg_color="transparent")
backgroundcolor_menu = ctk.CTkOptionMenu(
    sett_menu_frame_left,
    values=list(BACKGROUND_MODES),
    width=CONTROL_SIZE[0],
    height=CONTROL_SIZE[1],
    command=set_background_color,
    font=FONT_LARGE,
)
changebutton = ctk.CTkButton(
    sett_menu_frame_left,
    text="選擇顏色",
    command=choose_color,
    width=CONTROL_SIZE[0],
    height=CONTROL_SIZE[1],
    font=FONT_LARGE,
)
change_download_folder = ctk.CTkButton(
    sett_menu_frame_right,
    text="變更下載位置",
    command=select_download_folder,
    width=CONTROL_SIZE[0],
    height=CONTROL_SIZE[1],
    font=FONT_LARGE,
)

ToolTip(change_download_folder, lambda: f"目前下載位置:\n{settings['download_folder']}")

log_button = ctk.CTkButton(
    sett_menu_frame_left,
    text="查看日誌",
    command=lambda: logger.show_log_window(root, ico_path),
    width=CONTROL_SIZE[0],
    height=CONTROL_SIZE[1],
    font=FONT_LARGE,
)

status_var = ctk.StringVar(value=settings["check_button"])

check_button = ctk.CTkCheckBox(
    sett_menu_frame_right,
    text="顯示操作確認提示",
    variable=status_var,
    onvalue="True",  # 勾選時的值
    offvalue="False", # 未勾選時的值
    command=choose_Check_value,
    font=FONT_NORMAL
)
ToolTip(check_button, "啟用後將於下載全頻道影片時顯示確認提示")

renew_status_var = ctk.StringVar(value=settings["renew_check_button"])
renew_check_button = ctk.CTkCheckBox(
    sett_menu_frame_right,
    text="檢查更新",
    variable=renew_status_var,
    onvalue="True",  # 勾選時的值
    offvalue="False", # 未勾選時的值
    command=renew_choose_Check_value,
    font=FONT_NORMAL
)
ToolTip(renew_check_button, "啟用後將於啟動時自動檢查新版本")
#oauth_choose_Check_value
oauth_status_var = ctk.StringVar(value=settings.get("oauth_check_button", "False"))
oauth_check_button = ctk.CTkCheckBox(
    sett_menu_frame_right,
    text="啟用 OAuth2 裝置驗證",
    variable=oauth_status_var,
    onvalue="True",  # 勾選時的值
    offvalue="False", # 未勾選時的值
    command="",
    font=FONT_NORMAL
)
ToolTip(oauth_check_button, "正在研究，非常抱歉")

# 功能頁
previous_button = ctk.CTkButton(root, text="←", corner_radius=10, width=40, height=40, command=function, font=FONT_LARGE)
function_frame = ctk.CTkFrame(root, fg_color="transparent")
wordbutton = ctk.CTkButton(function_frame, text="word pdf\n轉換", command=word, width=SECONDARY_BUTTON_SIZE[0], height=SECONDARY_BUTTON_SIZE[1], corner_radius=BUTTON_RADIUS, font=FONT_LARGE)
wordbutton.pack(side="left",padx=20)
mp4_to_mp3button = ctk.CTkButton(function_frame, text="MP4 \n轉\n MP3", command=mp3_page, width=SECONDARY_BUTTON_SIZE[0], height=SECONDARY_BUTTON_SIZE[1], corner_radius=BUTTON_RADIUS, font=FONT_LARGE)
mp4_to_mp3button.pack(side="left",padx=20)

# Word 頁
wordlabel = ctk.CTkLabel(root, text="尚未選擇檔案或資料夾", font=FONT_LARGE, wraplength=480, anchor="w")
wordstart_button = ctk.CTkButton(root, text="開始轉換", width=100, height=40, corner_radius=BUTTON_RADIUS, command=lambda:start_conversion(wordlabel, wordstart_button, first_open), font=FONT_LARGE, state=ctk.DISABLED)
wordbrowse_file_button = ctk.CTkButton(root, text="瀏覽檔案", command=lambda:browse_file(wordlabel, wordstart_button, first_open), font=FONT_LARGE)
wordbrowse_folder_button = ctk.CTkButton(root, text="瀏覽資料夾", command=lambda:browse_folder(wordlabel, wordstart_button, first_open), font=FONT_LARGE)

# MP3 頁
mp3label = ctk.CTkLabel(root, text="請選擇 MP4 檔案", width=400, height=30, font=FONT_LARGE)
mp3start_button = ctk.CTkButton(root, text="開始轉換", state=ctk.DISABLED, command=lambda:convert_mp4_to_mp3(ffmpeg_path, first_open), font=FONT_LARGE)
mp3browse_button = ctk.CTkButton(
    root,
    text="瀏覽",
    command=lambda: mp3(mp3label, mp3start_button, first_open),
    font=FONT_LARGE,
)

SETTING_PAGE_WIDGETS.extend(
    [
        sett_menu_frame,
        sett_menu_frame_left,
        sett_menu_frame_right,
        backgroundcolor_menu,
        changebutton,
        change_download_folder,
        log_button,
        check_button,
        renew_check_button,
        oauth_check_button,
    ]
)

PAGE_WIDGETS.extend(
    [
        text_label,
        button_frame,
        loadbutton,
        backbutton,
        url_box,
        menu_frame,
        dropdown_menu,
        Image_quality_menu,
        yt_button,
        sett_menu_frame,
        sett_menu_frame_left,
        sett_menu_frame_right,
        backgroundcolor_menu,
        changebutton,
        change_download_folder,
        log_button,
        check_button,
        renew_check_button,
        oauth_check_button,
        function_frame,
        wordbutton,
        mp4_to_mp3button,
        wordlabel,
        wordbrowse_folder_button,
        wordbrowse_file_button,
        wordstart_button,
        mp3label,
        mp3browse_button,
        mp3start_button,
    ]
)

MENU_FONT = ("Arial", 12)


def apply_menu_style() -> None:
    """依目前主題更新兩個右鍵選單的顏色。"""
    mode = settings.get("background_color", "Dark")
    palette = MENU_PALETTES.get(mode, MENU_PALETTES["Light"])
    options = {
        "bg": palette["bg"],
        "fg": palette["fg"],
        "activebackground": palette["active_bg"],
        "activeforeground": palette["active_fg"],
        "font": MENU_FONT,
    }
    for context_menu in (menu, fuontionmenu):
        context_menu.configure(**options)


menu = tk.Menu(root, tearoff=0)
menu.add_command(label="貼上", command=paste_text)
menu.add_command(label="剪下", command=cut_text)
menu.add_command(label="全選", command=select_all)
menu.add_command(label="如何取得網址", command=teaching_3)

fuontionmenu = tk.Menu(root, tearoff=0)
fuontionmenu.add_command(label="官網教學", command=teaching)
#fuontionmenu.add_command(label="設置 Cookies 教學", command=teaching_2)
apply_menu_style()


# --- 程式啟動後載入設定 ---
if os.path.exists(json_file_path):
    load()
else:
    ctk.set_appearance_mode("Dark")

first_open = 1
check_tool_updates(down_path, root)
if settings["renew_check_button"] == "True":
   check_for_updates(root, manual=False)



root.mainloop()