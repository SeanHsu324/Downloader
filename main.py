import customtkinter as ctk
import os
import sys
from PIL import Image
import colorsys

def resource_path(relative_path):
    """取得資源的正確路徑（適用於開發和打包後的環境）"""
    if hasattr(sys, 'frozen'):  # 如果是打包後的執行檔
        base_path = sys._MEIPASS  # type: ignore
    else:  # 如果是開發環境
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

picture_path = resource_path("picture/stary.png")
ico_path = resource_path("picture/yt.ico")


def splash_screen(load_windows):
    """載入畫面"""
    splash = ctk.CTkToplevel(load_windows)  # 使用 Toplevel
    splash.overrideredirect(True)  # 移除標題欄

    # 載入圖片
    img = Image.open(picture_path)
    img = img.resize((432, 102))
    splash_img = ctk.CTkImage(img, size=(432, 102))  # 使用 CTkImage 而非 ImageTk.PhotoImage

    # 設定視窗大小與位置
    win_width, win_height = 432, 102
    screen_width = splash.winfo_screenwidth()
    screen_height = splash.winfo_screenheight()
    x = (screen_width - win_width) // 2
    y = (screen_height - win_height) // 2
    splash.geometry(f"{win_width}x{win_height}+{x}+{y}")

    # 顯示圖片
    label = ctk.CTkLabel(splash, image=splash_img, text="")
    label.image = splash_img
    label.pack()

    # 停留 5 秒後關閉
    splash.after(5000, splash.destroy)

    return splash


# 建立一個隱藏的根視窗
load_windows = ctk.CTk()
load_windows.withdraw()

# 啟動載入畫面
splash = splash_screen(load_windows)
splash.update()


"""開始載入主程式"""
import tkinter as tk
import webbrowser
from tkinter import  colorchooser
import json
from module.download import on_download_button_click, set_main_view
from module.word import browse_file, browse_folder, start_conversion
from module.mp4_to_mp3 import mp3, convert_mp4_to_mp3
from module.renew import renew, renew_root, set_main_root, download_data
# 追蹤所有執行中的執行緒
threads = []

first_open  = 0

# 設定 ffmpeg 路徑
ffmpeg_path = resource_path("ffmpeg/bin/ffmpeg.exe")
print(f"FFmpeg 路徑: {ffmpeg_path}")


# 設定外觀模式（"System" 依系統主題，"Dark" 深色模式，"Light" 淺色模式）
#ctk.set_appearance_mode("Dark")
#ctk.set_default_color_theme("blue")
settings = {}
root = ctk.CTk()
root.geometry("640x350")
root.resizable(False, False)
root.title("Downloader")
root.iconbitmap(ico_path)



def on_closing():
    root.destroy()  # 銷毀主視窗
    sys.exit()  # 強制關閉 Python 進程

root.protocol("WM_DELETE_WINDOW", on_closing)

set_main_root(root)
set_main_view(root)
renew_root(first_open, root)

work_path = "c:\\downloadsitt"
json_work_path = os.path.join(work_path, "renew.json")

if os.path.exists(json_work_path):
    with open(json_work_path, "r", encoding="utf-8") as f:
        local_data = json.load(f)
else:
    local_data = {}  # 如果沒有 renew.json，假設為空字典

down_path = local_data.get("下載位置")


#設定json
sett_path = down_path
os.makedirs(sett_path, exist_ok=True)

# 設定 JSON 檔案路徑
json_file_path = os.path.join(sett_path, "settings.json")

# 讀取現有的 JSON 設定，若沒有則創建預設設定
if os.path.exists(json_file_path):
    with open(json_file_path, "r") as file:
        settings = json.load(file)
        ctk.set_appearance_mode(settings["background_color"])
        settings.setdefault("hover_color", "#47DB00")
        with open(json_file_path, "w") as file:
            json.dump(settings, file)
else:
    settings = {"background_color": "Dark", "subject_color": "#80ff42", "text_color": "black", "hover_color":"#47DB00", "mp4": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4", "mp3": "bestaudio[ext=m4a]/m4a"}
    with open(json_file_path, "w") as file:
        json.dump(settings, file)

# 設置顯示的背景顏色
def set_background_color(choice):
    # 根據選擇更新背景顏色
    if choice == "深色":
        ctk.set_appearance_mode("Dark")
        settings["background_color"] = "Dark"

    elif choice == "淺色":
        ctk.set_appearance_mode("Light")
        settings["background_color"] = "Light"
        
    elif choice == "自動":
        ctk.set_appearance_mode("System")
        settings["background_color"] = "System"

    # 儲存選擇的顏色到 JSON 檔案
    with open(json_file_path, "w") as file:
        json.dump(settings, file)


def open_link(url):
    webbrowser.open(url)


def choose_color():
    color_code = colorchooser.askcolor()[1]  # 顯示顏色選擇器並獲取顏色代碼
    if color_code:
        settings["subject_color"] = color_code  # 儲存選擇的顏色
        text_color = "black" if is_light_color(color_code) else "white"
        settings["text_color"] = text_color
        hover_color = darken_color(settings["subject_color"], 20)
        settings["hover_color"] = hover_color
        item = [
            dropdown_menu, backgroundcolor_menu, wordlabel, mp3label
        ]
        botton = [
            loadbutton, backbutton, sett_button, home_button, previous_button,
            wordbutton, wordstart_button, changebutton, wordbrowse_folder_button, 
            wordbrowse_file_button, mp3start_button, mp3browse_button,
            mp4_to_mp3button, yt_button

        ]
        def update_color():
            for component in item:
                component.configure(fg_color=color_code, text_color=text_color)
            for com in botton:
                com.configure(fg_color=color_code, text_color=text_color, hover_color=hover_color)
            

        # 更新所有元件的顏色
        update_color()

        # 保存顏色設置到 JSON 文件
        with open(json_file_path, "w") as file:
            json.dump(settings, file)


def load():
    if settings["background_color"] == "Dark":
        backgroundcolor_menu.set("深色")
        ctk.set_appearance_mode("Dark")

    elif settings["background_color"] == "Light":
        backgroundcolor_menu.set("淺色")
        ctk.set_appearance_mode("Light")

    elif settings["background_color"] == "System":
        backgroundcolor_menu.set("自動")
        ctk.set_appearance_mode("System")


    items = [
             dropdown_menu, backgroundcolor_menu, wordlabel, mp3label
        ]
    bottons = [
        loadbutton, backbutton, sett_button, home_button, previous_button,
        wordbutton, wordstart_button, changebutton, wordbrowse_folder_button, 
        wordbrowse_file_button, mp3start_button, mp3browse_button,
        mp4_to_mp3button, yt_button
    ]
    # 定義更新樣式的函式
    def update_component_styles():
        for component in items:
            component.configure(fg_color=settings["subject_color"], text_color=settings["text_color"])
        for com in bottons:
            if settings.setdefault("hover_color", "#47DB00") == "#47DB00":
                hover_color = darken_color(settings["subject_color"], 20)
                settings["hover_color"] = hover_color
                with open(json_file_path, "w") as file:
                    json.dump(settings, file)

                com.configure(fg_color=settings["subject_color"], text_color=settings["text_color"], hover_color=hover_color)
            else:
                com.configure(fg_color=settings["subject_color"], text_color=settings["text_color"], hover_color=settings["hover_color"])

    # 綁定右鍵菜單顯示事件
    root.bind("<Button-3>", show_fuontion_menu)

    # 更新樣式
    update_component_styles()

def darken_color(color: str, percent: float):
    """
    將 HEX 色碼變暗一定比例（降低 HSL 亮度值）。
    
    :param color: 原始 HEX 色碼，例如 "#80FF42"
    :param percent: 降低的百分比，例如 20 表示降低 20%
    :return: 變暗後的 HEX 色碼
    """
    # 解析 HEX 顏色為 RGB（0-255）
    color = color.lstrip("#")
    r, g, b = int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)

    # 轉換 RGB 到 HLS (HSL)
    h, l, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)

    # 降低亮度 L
    l = max(0, l - (percent / 100))  # 確保不低於 0

    # 轉回 RGB
    r, g, b = colorsys.hls_to_rgb(h, l, s)
    r, g, b = int(r * 255), int(g * 255), int(b * 255)

    # 回傳 HEX 色碼
    return f"#{r:02X}{g:02X}{b:02X}"

def is_light_color(hex_color):
    """
    根據顏色的亮度判斷是否為淺色。
    hex_color: 顏色的 16 進位碼（#RRGGBB）
    返回: True 表示淺色，False 表示深色
    """
    hex_color = hex_color.lstrip('#')
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    brightness = (r * 299 + g * 587 + b * 114) / 1000  # 加權計算亮度
    return brightness > 127  # 亮度高於 127 為淺色

def paste_text():
    try:
        clipboard_content = root.clipboard_get()  # 獲取剪貼簿內容
        url_box.insert(tk.END, clipboard_content)  # 插入到文字框中
    except tk.TclError:
        pass  # 如果剪貼簿是空的，什麼都不做

def cut_text():
    try:
        selected_text = url_box.selection_get()  # 獲取選中的文字
        root.clipboard_clear()  # 清空剪貼簿
        root.clipboard_append(selected_text)  # 將文字添加到剪貼簿
        url_box.delete("sel.first", "sel.last")  # 刪除選中的文字
    except tk.TclError:
        pass  # 如果沒有選中內容，什麼都不做

def select_all():
    url_box.select_range(0, tk.END)  # 選中全部文字
    url_box.icursor(tk.END)  # 將光標放置在文字結尾

menu = tk.Menu(root, tearoff=0)
menu.add_command(label="貼上", command=paste_text)
menu.add_command(label="剪下", command=cut_text)
menu.add_command(label="全選", command=select_all)

def show_context_menu(event):
    menu.post(event.x_root, event.y_root)  # 在滑鼠點擊位置顯示菜單

def teaching():
    webbrowser.open("https://sites.google.com/view/yt-to-dowload/教學")

def witter():
    webbrowser.open("https://www.instagram.com/yt.download_")

fuontionmenu = tk.Menu(root, tearoff=0)
fuontionmenu.add_command(label="官網教學", command=teaching)
fuontionmenu.add_command(label="聯絡作者", command=witter)

def show_fuontion_menu(event):
    fuontionmenu.post(event.x_root, event.y_root)  # 在滑鼠點擊位置顯示菜單
    
# 切換到下載頁面
def ytdownload():
    root.unbind("<Button-3>")
    url_box.bind("<Button-3>", show_context_menu)
    url_box.focus_set()
    home_button.place(relx=0.05, rely=0.05)
    url_box.pack(pady=(50, 10))
    dropdown_menu.pack(pady=(10, 20))
    yt_button.pack(pady=(20, 10))
    wordbutton.pack_forget()
    sett_button.place_forget()
    text_label.pack_forget()
    loadbutton.pack_forget()
    backbutton.pack_forget()
    button_frame.pack_forget()
    backgroundcolor_menu.pack_forget()
    changebutton.pack_forget()

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
    dropdown_menu.pack_forget()  # 隱藏下拉選單
    home_button.place_forget()
    url_box.pack_forget()
    yt_button.pack_forget()
    backgroundcolor_menu.pack_forget()
    changebutton.pack_forget()
    function_frame.pack_forget()
    
#設定
def setepag():
    root.unbind("<Button-3>")
    url_box.unbind("<Button-3>")
    root.focus()
    text_label.pack_forget()
    button_frame.pack_forget()
    loadbutton.pack_forget()
    backbutton.pack_forget()
    dropdown_menu.pack_forget()  # 隱藏下拉選單
    url_box.pack_forget()
    yt_button.pack_forget()
    sett_button.place_forget()
    wordbutton.pack_forget()
    home_button.place(relx=0.05, rely=0.05)
    backgroundcolor_menu.pack(pady=(50, 20))
    changebutton.pack(pady=(10, 20))

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



'''主頁'''

text_label = ctk.CTkLabel(root, text="選擇功能", font=("Arial", 50, "bold"), fg_color="transparent")
text_label.pack(pady=(20, 10))

button_frame = ctk.CTkFrame(root, fg_color="transparent")
button_frame.pack(expand=True)

loadbutton = ctk.CTkButton(button_frame, text="下載\nyoutube", command=ytdownload, width=150, height=150, corner_radius=40, font=("Arial", 20, "bold"))
loadbutton.pack(side="left", padx=20)

backbutton = ctk.CTkButton(button_frame, text="其他功能", command=function, width=150, height=150, corner_radius=40, font=("Arial", 20, "bold"))
backbutton.pack(side="left", padx=20)

'''下載頁'''

url_box = ctk.CTkEntry(root, placeholder_text="輸入網址", width=300, height=50, fg_color="transparent", font=("Arial", 20, "bold"))
root.focus()

dropdown_menu = ctk.CTkOptionMenu(root, values=["選擇格式", "mp4", "mp3"], width=200, height=40, font=("Arial", 20, "bold"))
dropdown_menu.set("選擇格式")

yt_button = ctk.CTkButton(root, text="開始下載", width=100, height=40, corner_radius=40, command=lambda:on_download_button_click(root, url_box, dropdown_menu, ffmpeg_path, first_open, settings["mp3"], settings["mp4"]), font=("Arial", 20, "bold")) 

home_button = ctk.CTkButton(root, text="home",corner_radius=10,width=40,height=40,command=backhomepag, font=("Arial", 20, "bold"))

'''set 視窗'''

sett_button = ctk.CTkButton(root, text="=",corner_radius=10,width=40,height=40,command=setepag, font=("Arial", 20, "bold"))
sett_button.place(relx=0.9, rely=0.05)

backgroundcolor_menu = ctk.CTkOptionMenu(root, values=["自動", "深色", "淺色"], width=200, height=40, command=set_background_color, font=("Arial", 20, "bold"))

changebutton = ctk.CTkButton(root, text="選擇顏色", command=choose_color, width=200, height=40, font=("Arial", 20, "bold"))

'''功能頁'''

previous_button = ctk.CTkButton(root, text="←",corner_radius=10,width=40,height=40,command=function, font=("Arial", 20, "bold"))

function_frame = ctk.CTkScrollableFrame(root, width=620, height=200,fg_color="transparent")

wordbutton = ctk.CTkButton(function_frame, text="word pdf\n轉換", command=word, width=100, height=100, corner_radius=40, font=("Arial", 20, "bold"))

mp4_to_mp3button = ctk.CTkButton(function_frame, text="MP4 \n轉\n MP3", command=mp3_page, width=100, height=100, corner_radius=40, font=("Arial", 20, "bold"))

'''word頁'''

wordlabel = ctk.CTkLabel(root, text="尚未選擇檔案或資料夾", font=("Arial", 20, "bold"), wraplength=480, anchor="w")

wordstart_button = ctk.CTkButton(root, text="開始轉換", width=100, height=40, corner_radius=40, command=lambda:start_conversion(wordlabel, wordstart_button, first_open), font=("Arial", 20, "bold"), state=ctk.DISABLED)

wordbrowse_file_button = ctk.CTkButton(root, text="瀏覽檔案", command=lambda:browse_file(wordlabel, wordstart_button, first_open), font=("Arial", 20, "bold"))

wordbrowse_folder_button = ctk.CTkButton(root, text="瀏覽資料夾", command=lambda:browse_folder(wordlabel, wordstart_button, first_open), font=("Arial", 20, "bold"))

'''mp3'''

mp3label = ctk.CTkLabel(root, text="請選擇 MP4 檔案", width=400, height=30, font=("Arial", 20, "bold"))

# 開始轉換按鈕
mp3start_button = ctk.CTkButton(root, text="開始轉換", state=ctk.DISABLED, command=lambda:convert_mp4_to_mp3(ffmpeg_path, first_open), font=("Arial", 20, "bold"))

# 瀏覽按鈕
mp3browse_button = ctk.CTkButton(root, text="瀏覽", command=lambda:mp3(mp3label, mp3start_button,first_open), font=("Arial", 20, "bold"))


if os.path.exists(json_file_path) == True :
    load()
    print("load")
else :
    ctk.set_appearance_mode("Dark")
    print("ctk.set")


first_open = 1

download_data(first_open,down_path)
renew(first_open, root)
print("renew")
# 關閉載入畫面，顯示主視窗
splash.destroy()
root.mainloop()
load_windows.destroy() #程式結束時銷毀load_windows視窗