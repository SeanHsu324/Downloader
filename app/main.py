import customtkinter as ctk
import os
import sys
from PIL import Image
import colorsys
import tkinter as tk
import webbrowser
from tkinter import colorchooser, filedialog, messagebox
import json
from re import search
from module.download import on_download_button_click, set_main_view
from module.word import browse_file, browse_folder, start_conversion
from module.mp4_to_mp3 import mp3, convert_mp4_to_mp3
from module.renew import renew, renew_root, set_main_root
import threading 

def resource_path(relative_path):
    """取得資源的正確路徑（適用於開發和打包後的環境）"""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# --- 資源路徑 ---
picture_path = resource_path("picture/stary.png")
ico_path = resource_path("picture/yt.ico")
ffmpeg_path = resource_path("ffmpeg/bin/ffmpeg.exe")
setting_white_path = resource_path("picture/setting_white.png")
setting_black_path = resource_path("picture/setting_black.png")
return_white_path = resource_path("picture/return_white.png")
return_black_path = resource_path("picture/return_black.png")
notify_white_path = resource_path("picture/notify_white.png")
notify_black_path = resource_path("picture/notify_black.png")

# --- 核心修改：啟動畫面函式 ---
def splash_screen(main_root):
    """載入畫面，依附於主視窗"""
    splash = ctk.CTkToplevel(main_root)
    splash.overrideredirect(True)

    # 載入圖片並保持參考，防止被垃圾回收
    try:
        img = Image.open(picture_path)
        img = img.resize((432, 102))
        splash.splash_img_ref = ctk.CTkImage(img, size=(432, 102))
    except Exception as e:
        print(f"無法載入啟動畫面圖片: {e}")
        splash.splash_img_ref = None

    # 設定視窗大小與位置
    win_width, win_height = 432, 102
    screen_width = splash.winfo_screenwidth()
    screen_height = splash.winfo_screenheight()
    x = (screen_width - win_width) // 2
    y = (screen_height - win_height) // 2
    splash.geometry(f"{win_width}x{win_height}+{x}+{y}")

    # 顯示圖片
    if splash.splash_img_ref:
        label = ctk.CTkLabel(splash, image=splash.splash_img_ref, text="")
        label.pack()

    def show_main_window():
        """銷毀啟動畫面並顯示主視窗"""
        splash.destroy()
        main_root.deiconify() # 顯示主視窗

    # 停留 5 秒後執行
    splash.after(5000, show_main_window)
    return splash

# --- 核心修改：應用程式初始化流程 ---
# 1. 建立整個應用程式唯一的根視窗
root = ctk.CTk()
# 2. 立即隱藏主視窗，直到啟動畫面結束
root.withdraw()

# --- 主視窗設定 ---
root.geometry("640x350")
root.resizable(False, False)
root.title("Downloader")
root.iconbitmap(ico_path)

# 3. 啟動載入畫面，傳入唯一的 root
splash = splash_screen(root)

# --- 開始載入主程式其餘部分 ---
threads = []
first_open = 0

print(f"FFmpeg 路徑: {ffmpeg_path}")

download_folder = os.path.join(os.path.expanduser("~"), "Desktop", "youtube下載")

settings = {}

def on_closing():
    root.destroy()
    sys.exit()

root.protocol("WM_DELETE_WINDOW", on_closing)

set_main_root(root)
set_main_view(root)
renew_root(first_open, root)
print("renew_root:1")

work_path = "c:\\downloadsitt"
json_work_path = os.path.join(work_path, "renew.json")

if os.path.exists(json_work_path):
    with open(json_work_path, "r", encoding="utf-8") as f:
        local_data = json.load(f)
else:
    local_data = {}

down_path = local_data.get("下載位置")

sett_path = down_path if down_path else os.path.join(os.path.expanduser("~"), "Desktop")
os.makedirs(sett_path, exist_ok=True)

json_file_path = os.path.join(sett_path, "settings.json")

if os.path.exists(json_file_path):
    with open(json_file_path, "r") as file:
        settings = json.load(file)
        ctk.set_appearance_mode(settings["background_color"])
        if "check_button" not in settings:
            settings["check_button"] = "True"
            with open(json_file_path, "w") as file:
                json.dump(settings, file)
        if "renew_check_button" not in settings:
            settings["renew_check_button"] = "True"
            with open(json_file_path, "w") as file:
                json.dump(settings, file)
else:
    settings = {"background_color": "Dark", "subject_color": "#478058", "text_color": "black", "hover_color":"#223E2A", "mp4": "bestvideo[ext=mp4]+bestaudio/mp4", "mp3": "bestaudio/m4a", "download_folder": download_folder,"check_button":"True","renew_check_button":"True"}
    with open(json_file_path, "w") as file:
        json.dump(settings, file)


# --- 函式定義 (修復 GIL 錯誤) ---

def open_link_in_thread(url):
    """
    在一個獨立的執行緒中安全地開啟連結。
    這可以避免 webbrowser 模組在主 Tkinter 執行緒中呼叫底層 OS API 
    時可能發生的 GIL 衝突。
    """
    threading.Thread(target=lambda: webbrowser.open(url), daemon=True).start()


def set_background_color(choice):
    if choice == "深色": ctk.set_appearance_mode("Dark"); settings["background_color"] = "Dark"
    elif choice == "淺色": ctk.set_appearance_mode("Light"); settings["background_color"] = "Light"
    elif choice == "系統": ctk.set_appearance_mode("System"); settings["background_color"] = "System"
    with open(json_file_path, "w") as file: json.dump(settings, file)

def set_Image_quality(choice):
    quality_map = {"最高畫質": "bestvideo[ext=mp4]+bestaudio/mp4", "1080p": "bestvideo[height=1080]+bestaudio/mp4", "720p": "bestvideo[height=720]+bestaudio/mp4", "480p": "bestvideo[height=480]+bestaudio/mp4", "240p": "bestvideo[height=240]+bestaudio/mp4", "144p": "bestvideo[height=144]+bestaudio/mp4"}
    settings["mp4"] = quality_map.get(choice, "bestvideo[ext=mp4]+bestaudio/mp4")
    with open(json_file_path, "w") as file: json.dump(settings, file)

def on_format_change(choice):
    is_disabled = choice in ["選擇格式", "mp3"]
    Image_quality_menu.configure(state="disabled" if is_disabled else "normal")
    yt_button.configure(state="disabled" if choice == "選擇格式" else "normal")

def match_search(format_str):
    match = search(r'height=(\d+)', format_str)
    return match.group(1) + "p" if match else "最高畫質"

def open_link(url): 
    open_link_in_thread(url) 

def is_light_color(hex_color):
    hex_color = hex_color.lstrip('#')
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    return (r * 299 + g * 587 + b * 114) / 1000 > 127

def darken_color(color: str, percent: float):
    color = color.lstrip("#")
    r, g, b = int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)
    h, l, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
    l = max(0, l - (percent / 100))
    r, g, b = colorsys.hls_to_rgb(h, l, s)
    return f"#{int(r * 255):02X}{int(g * 255):02X}{int(b * 255):02X}"

def choose_color():
    color_code = colorchooser.askcolor()[1]
    if not color_code: return
    settings["subject_color"] = color_code
    settings["text_color"] = "black" if is_light_color(color_code) else "white"
    settings["hover_color"] = darken_color(color_code, 20)
    with open(json_file_path, "w") as file: json.dump(settings, file)
    load() # 重新載入顏色

def load():
    background_map = {"Dark": "深色", "Light": "淺色", "System": "系統"}
    backgroundcolor_menu.set(background_map.get(settings["background_color"], "系統"))
    ctk.set_appearance_mode(settings["background_color"])
    Image_quality_menu.set(match_search(settings["mp4"]))
    
    items = [dropdown_menu, Image_quality_menu, backgroundcolor_menu, wordlabel, mp3label]
    buttons = [loadbutton, backbutton, home_button, previous_button, wordbutton, wordstart_button, changebutton, change_download_folder, wordbrowse_folder_button, wordbrowse_file_button, mp3start_button, mp3browse_button, mp4_to_mp3button, yt_button]
    
    fg_color = settings["subject_color"]
    text_color = settings["text_color"]
    hover_color = settings["hover_color"]

    for component in items: component.configure(fg_color=fg_color, text_color=text_color)
    for com in buttons: com.configure(fg_color=fg_color, text_color=text_color, hover_color=hover_color)
    
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


def teaching(): 
    open_link_in_thread("https://sites.google.com/view/yt-to-dowload/教學")

def teaching_2():
    open_link_in_thread("https://sites.google.com/view/yt-to-dowload/教學/設置cookies")
    if down_path: os.startfile(os.path.join(down_path, "cookie.txt"))

def teaching_3(): 
    open_link_in_thread("https://sites.google.com/view/yt-to-dowload/教學/取得網址")

def show_fuontion_menu(event): fuontionmenu.post(event.x_root, event.y_root)

def select_download_folder():
    global download_folder
    folder = filedialog.askdirectory(title="變更下載位置", initialdir=settings.get("download_folder", download_folder))
    if folder:
        settings["download_folder"] = folder
        with open(json_file_path, "w") as file: json.dump(settings, file)

def choose_Check_value():
    settings["check_button"] = status_var.get()
    with open(json_file_path, "w") as file:
        json.dump(settings, file)

def renew_choose_Check_value():
    if settings["renew_check_button"]=="True":
        result = messagebox.askyesno(
            title="操作確認", 
            message="確定關閉「檢查更新」嗎？\n這可能會導致您錯過重要的軟體更新。",
        )
        if result:
            print("使用者點擊了「是」/Yes，繼續執行操作...")
            settings["renew_check_button"] = renew_status_var.get()
            with open(json_file_path, "w") as file:
                json.dump(settings, file)

        else:
            print("使用者點擊了「否」/No，取消操作。")
            renew_status_var.set("False" if renew_status_var.get() == "True" else "True")
    else:
        settings["renew_check_button"] = renew_status_var.get()
        with open(json_file_path, "w") as file:
            json.dump(settings, file)


class ToolTip:
    """建立一個提示框，當滑鼠懸停在指定元件上時顯示提示內容"""
    def __init__(self, widget):
        self.widget = widget
        self.tipwindow = None
        self.id = None
        
        # 綁定滑鼠事件
        self.widget.bind("<Enter>", self.enter)
        self.widget.bind("<Leave>", self.leave)

    def enter(self, event=None):
        # 設置延遲
        self.schedule()

    def leave(self, event=None):
        self.unschedule()
        self.hidetip()

    def schedule(self):
        self.unschedule()
        
        self.id = self.widget.after(50, self.showtip)

    def unschedule(self):
        id = self.id
        self.id = None
        if id:
            self.widget.after_cancel(id)

    def showtip(self, event=None):
        "顯示提示框，並從全域變數獲取最新內容"
        global settings
        
        text = f"目前下載位置:\n{settings["download_folder"]}"

        if self.tipwindow or not text:
            return
        
        self.tipwindow = ctk.CTkToplevel(self.widget)
        self.tipwindow.wm_overrideredirect(True) 
        
        x, y, cx, cy = self.widget.bbox("insert")
        x = x + self.widget.winfo_rootx() 
        y = y + cy + self.widget.winfo_rooty() + 10
        self.tipwindow.wm_geometry("+%d+%d" % (x, y))

        label = ctk.CTkLabel(self.tipwindow, text=text, justify="left", 
                             fg_color=("#3a3a3a", "#3a3a3a"), 
                             text_color="white", 
                             corner_radius=5,
                             padx=10, pady=5)
        label.pack(ipadx=1)

    def hidetip(self):
        "隱藏提示框"
        tw = self.tipwindow
        self.tipwindow = None
        if tw:
            tw.destroy()

# --- 頁面切換函式 ---
def ytdownload():
    root.bind("<Button-3>", show_fuontion_menu)
    url_box.bind("<Button-3>", show_context_menu)
    url_box.focus_set()
    home_button.place(relx=0.05, rely=0.05)
    url_box.pack(pady=(50, 10))
    menu_frame.pack(pady=(20, 20))
    dropdown_menu.pack(side="left", padx=10)
    Image_quality_menu.pack(side="left", padx=10)
    yt_button.pack(pady=(20, 10))
    wordbutton.pack_forget()
    sett_button.place_forget()
    text_label.pack_forget()
    loadbutton.pack_forget()
    backbutton.pack_forget()
    button_frame.pack_forget()
    backgroundcolor_menu.pack_forget()
    changebutton.pack_forget()
    change_download_folder.pack_forget()

# 返回主頁
def backhomepag():
    root.bind("<Button-3>", show_fuontion_menu)
    url_box.unbind("<Button-3>")
    root.focus()
    text_label.pack(pady=(20, 10))
    button_frame.pack(expand=True)
    loadbutton.pack(side="left", padx=20)
    backbutton.pack(side="left", padx=20)
    sett_button.place(relx=0.9, rely=0.05)
    wordbutton.pack_forget()
    menu_frame.pack_forget()
    sett_menu_frame.pack_forget()
    dropdown_menu.pack_forget() 
    Image_quality_menu.pack_forget()
    home_button.place_forget()
    url_box.pack_forget()
    yt_button.pack_forget()
    backgroundcolor_menu.pack_forget()
    changebutton.pack_forget()
    change_download_folder.pack_forget()
    function_frame.pack_forget()
    check_button.pack_forget()
    renew_check_button.pack_forget()
    
#設定
def setepag():
    root.unbind("<Button-3>")
    url_box.unbind("<Button-3>")
    root.focus()
    text_label.pack_forget()
    button_frame.pack_forget()
    loadbutton.pack_forget()
    backbutton.pack_forget()
    dropdown_menu.pack_forget()
    Image_quality_menu.pack_forget()
    url_box.pack_forget()
    yt_button.pack_forget()
    sett_button.place_forget()
    wordbutton.pack_forget()
    home_button.place(relx=0.05, rely=0.05)
    sett_menu_frame.pack(expand=True, fill="x", pady=30)
    sett_menu_frame_left.pack(side="left", expand=True, fill="both")
    sett_menu_frame_right.pack(side="right", expand=True, fill="both")
    backgroundcolor_menu.pack(side="top", anchor="w",padx=40, pady=(20, 20))
    changebutton.pack(side="top", anchor="w", padx=40,pady=(10, 20))
    change_download_folder.pack(side="top", anchor="w",pady=(20, 20))
    check_button.pack(side="top", anchor="w",pady=(10, 20))
    renew_check_button.pack(side="top", anchor="w",pady=(10, 20))



#功能頁
def function():
    root.unbind("<Button-3>")
    url_box.unbind("<Button-3>")
    sett_button.place_forget()
    text_label.pack_forget()
    loadbutton.pack_forget()
    backbutton.pack_forget()
    button_frame.pack_forget()
    backgroundcolor_menu.pack_forget()
    changebutton.pack_forget()
    change_download_folder.pack_forget()
    function_frame.pack(expand=True)
    wordbutton.pack(side="left",padx=20)
    mp4_to_mp3button.pack(side="left",padx=20)
    home_button.place(relx=0.05, rely=0.05)
    previous_button.place_forget()
    wordlabel.pack_forget()
    wordbrowse_folder_button.pack_forget()
    wordbrowse_file_button.pack_forget()
    wordstart_button.pack_forget()
    mp3label.pack_forget()
    mp3browse_button.pack_forget()
    mp3start_button.pack_forget()


def word():
    root.bind("<Button-3>", show_fuontion_menu)
    url_box.unbind("<Button-3>")
    wordbutton.pack_forget()
    home_button.place_forget()
    function_frame.pack_forget()
    previous_button.place(relx=0.05, rely=0.05)
    wordlabel.pack(pady=(50,10))
    wordbrowse_folder_button.pack(pady=20)
    wordbrowse_file_button.pack(pady=20)
    wordstart_button.pack(pady=20)


def mp3_page():
    root.bind("<Button-3>", show_fuontion_menu)
    url_box.unbind("<Button-3>")
    wordbutton.pack_forget()
    home_button.place_forget()
    function_frame.pack_forget()
    previous_button.place(relx=0.05, rely=0.05)
    mp3label.pack(pady=(50,20))
    mp3browse_button.pack(pady=10)
    mp3start_button.pack(pady=20)

# --- UI 元件建立 ---

# 主頁
text_label = ctk.CTkLabel(root, text="選擇功能", font=("Arial", 50, "bold"), fg_color="transparent")
text_label.pack(pady=(20, 10))
button_frame = ctk.CTkFrame(root, fg_color="transparent")
button_frame.pack(expand=True)
loadbutton = ctk.CTkButton(button_frame, text="下載\nyoutube", command=ytdownload, width=150, height=150, corner_radius=40, font=("Arial", 20, "bold"))
loadbutton.pack(side="left", padx=20)
backbutton = ctk.CTkButton(button_frame, text="其他功能", command=function, width=150, height=150, corner_radius=40, font=("Arial", 20, "bold"))
backbutton.pack(side="left", padx=20)

# 下載頁
url_box = ctk.CTkEntry(root, placeholder_text="輸入網址", width=300, height=50, fg_color="transparent", font=("Arial", 20, "bold"))
menu_frame = ctk.CTkFrame(root, fg_color="transparent")
dropdown_menu = ctk.CTkOptionMenu(menu_frame, values=["選擇格式", "mp4", "mp3"], command=on_format_change, width=200, height=40, font=("Arial", 20, "bold"))
dropdown_menu.set("選擇格式")
Image_quality_menu = ctk.CTkOptionMenu(menu_frame, values=["最高畫質", "1080p", "720p", "480p", "240p", "144p"], command=set_Image_quality, width=200, height=40, font=("Arial", 20, "bold"))
Image_quality_menu.configure(state="disabled")
yt_button = ctk.CTkButton(root, text="開始下載", width=100, height=40, corner_radius=40, command=lambda:on_download_button_click(root, url_box, dropdown_menu, ffmpeg_path, first_open, settings["mp3"], settings["mp4"], settings["download_folder"], settings["check_button"]), font=("Arial", 20, "bold"))
yt_button.configure(state="disabled")
home_button = ctk.CTkButton(root, text="home", corner_radius=10, width=40, height=40, command=backhomepag, font=("Arial", 20, "bold"))

# 設定頁
try:
    root.setting_pil_image_black = Image.open(setting_black_path)
    root.setting_pil_image_white = Image.open(setting_white_path)
    print("圖片載入成功!")
    setting_button_icon = ctk.CTkImage(dark_image=root.setting_pil_image_white, light_image=root.setting_pil_image_black, size=(50, 45))
except Exception as e:
    print(f"載入設定圖示時發生錯誤: {e}")
    setting_button_icon = None

if setting_button_icon:
    sett_button = ctk.CTkButton(root, text="", image=setting_button_icon, fg_color="transparent", hover_color="#99A19B", corner_radius=10, width=40, height=40, command=setepag)
else:
    sett_button = ctk.CTkButton(root, text="=", corner_radius=10, width=40, height=40, command=setepag, font=("Arial", 20, "bold"))
sett_button.place(relx=0.9, rely=0.05)
sett_menu_frame = ctk.CTkFrame(root, fg_color="transparent")
sett_menu_frame_left = ctk.CTkFrame(sett_menu_frame, fg_color="transparent")
sett_menu_frame_right = ctk.CTkFrame(sett_menu_frame, fg_color="transparent")
backgroundcolor_menu = ctk.CTkOptionMenu(sett_menu_frame_left, values=["系統", "深色", "淺色"], width=200, height=40, command=set_background_color, font=("Arial", 20, "bold"))
changebutton = ctk.CTkButton(sett_menu_frame_left, text="選擇顏色", command=choose_color, width=200, height=40, font=("Arial", 20, "bold"))
change_download_folder = ctk.CTkButton(sett_menu_frame_right, text="變更下載位置", command=select_download_folder, width=200, height=40, font=("Arial", 20, "bold"))
ToolTip(change_download_folder) # 提示目前下載位置
status_var = ctk.StringVar(value=settings["check_button"])

check_button = ctk.CTkCheckBox(
    sett_menu_frame_right,
    text="顯示操作確認提示",
    variable=status_var,
    onvalue="True",  # 勾選時的值
    offvalue="False", # 未勾選時的值
    command=choose_Check_value,
    font=("Arial", 16)
)
renew_status_var = ctk.StringVar(value=settings["renew_check_button"])
renew_check_button = ctk.CTkCheckBox(
    sett_menu_frame_right,
    text="檢查更新",
    variable=renew_status_var,
    onvalue="True",  # 勾選時的值
    offvalue="False", # 未勾選時的值
    command=renew_choose_Check_value,
    font=("Arial", 16)
)

# 功能頁
previous_button = ctk.CTkButton(root, text="←", corner_radius=10, width=40, height=40, command=function, font=("Arial", 20, "bold"))
function_frame = ctk.CTkFrame(root, fg_color="transparent")
wordbutton = ctk.CTkButton(function_frame, text="word pdf\n轉換", command=word, width=100, height=100, corner_radius=40, font=("Arial", 20, "bold"))
wordbutton.pack(side="left",padx=20)
mp4_to_mp3button = ctk.CTkButton(function_frame, text="MP4 \n轉\n MP3", command=mp3_page, width=100, height=100, corner_radius=40, font=("Arial", 20, "bold"))
mp4_to_mp3button.pack(side="left",padx=20)

# Word 頁
wordlabel = ctk.CTkLabel(root, text="尚未選擇檔案或資料夾", font=("Arial", 20, "bold"), wraplength=480, anchor="w")
wordstart_button = ctk.CTkButton(root, text="開始轉換", width=100, height=40, corner_radius=40, command=lambda:start_conversion(wordlabel, wordstart_button, first_open), font=("Arial", 20, "bold"), state=ctk.DISABLED)
wordbrowse_file_button = ctk.CTkButton(root, text="瀏覽檔案", command=lambda:browse_file(wordlabel, wordstart_button, first_open), font=("Arial", 20, "bold"))
wordbrowse_folder_button = ctk.CTkButton(root, text="瀏覽資料夾", command=lambda:browse_folder(wordlabel, wordstart_button, first_open), font=("Arial", 20, "bold"))

# MP3 頁
mp3label = ctk.CTkLabel(root, text="請選擇 MP4 檔案", width=400, height=30, font=("Arial", 20, "bold"))
mp3start_button = ctk.CTkButton(root, text="開始轉換", state=ctk.DISABLED, command=lambda:convert_mp4_to_mp3(ffmpeg_path, first_open), font=("Arial", 20, "bold"))
mp3browse_button = ctk.CTkButton(root, text="瀏覽", command=lambda:mp3(mp3label, mp3start_button, first_open), font=("Arial", 20, "bold"))

if settings["background_color"] == "Dark" :
    MENU_BG = "#2a2a2a" # 背景色
    MENU_FG = "white" # 文字顏色
    MENU_ACTIVE_BG = "#3e3e3e" # 懸停時的背景色
    MENU_ACTIVE_FG = "white"
else:
    MENU_BG = "#f0f0f0" # 背景色
    MENU_FG = "black" # 文字顏色
    MENU_ACTIVE_BG = "#d9d9d9" # 懸停時的背景色
    MENU_ACTIVE_FG = "black"
# 右鍵選單
menu = tk.Menu(root, tearoff=0, 
    bg=MENU_BG, 
    fg=MENU_FG, 
    activebackground=MENU_ACTIVE_BG, 
    activeforeground=MENU_ACTIVE_FG,
    font=("Arial", 12)
)
menu.add_command(label="貼上", command=paste_text)
menu.add_command(label="剪下", command=cut_text)
menu.add_command(label="全選", command=select_all)
menu.add_command(label="如何取得網址", command=teaching_3)
fuontionmenu = tk.Menu(root, tearoff=0,
    bg=MENU_BG, 
    fg=MENU_FG, 
    activebackground=MENU_ACTIVE_BG, 
    activeforeground=MENU_ACTIVE_FG,
    font=("Arial", 12)
)
fuontionmenu.add_command(label="官網教學", command=teaching)
fuontionmenu.add_command(label="設置Cookies教學", command=teaching_2)

# --- 程式啟動後載入設定 ---
if os.path.exists(json_file_path):
    load()
    print("load")
else:
    ctk.set_appearance_mode("Dark")
    print("ctk.set")

first_open = 1
if settings["renew_check_button"] == "True":
    renew(first_open, root)



root.mainloop()