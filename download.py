import customtkinter as ctk
import yt_dlp
import os
from tkinter import messagebox
import re
from threading import Thread
from tkinter import END
import sys
import webbrowser
import json

main_view = None  # 用於儲存 main.py 的 root

def set_main_view(root):
    global main_view
    main_view = root

work_path = "c:\\downloadsitt"
json_work_path = os.path.join(work_path, "renew.json")

if os.path.exists(json_work_path):
    with open(json_work_path, "r", encoding="utf-8") as f:
        local_data = json.load(f)
else:
    local_data = {}  # 如果沒有 renew.json，假設為空字典

down_path = local_data.get("下載位置")

cookie_txt_path = f"{down_path}\\cookie.txt"

if os.path.exists(cookie_txt_path):
    print("cookie.txt 存在")
    cookies = cookie_txt_path

def resource_path(relative_path):
    """取得資源的正確路徑（適用於開發和打包後的環境）"""
    if hasattr(sys, 'frozen'):  # 如果是打包後的執行檔
        base_path = sys._MEIPASS  # type: ignore
    else:  # 如果是開發環境
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

ico_path = resource_path("picture/yt.ico")

class DownloadProgressWindow(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("下載進度")
        self.geometry("400x200")
        self.resizable(False, False)
        self.iconbitmap(ico_path)
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.attributes("-topmost", True)
        self.scrollable_frame = ctk.CTkScrollableFrame(self, width=380, height=180, fg_color="transparent")
        self.scrollable_frame.pack(pady=10, padx=10)

        self.progress_bar = ctk.CTkProgressBar(self.scrollable_frame, width=380, mode="determinate")
        self.progress_bar.pack(pady=10)

        self.filename_label = ctk.CTkLabel(self.scrollable_frame, text="", wraplength=380, justify="left", fg_color="transparent")
        self.filename_label.pack(pady=5)

        self.eta_label = ctk.CTkLabel(self.scrollable_frame, text="預估時間: 等待", fg_color="transparent")
        self.eta_label.pack(pady=5)

    def on_close(self):
        pass  # 不執行任何操作，阻止窗口關閉

    def set_progress(self, value):
        self.progress_bar.set(value / 100)  # customtkinter 使用比例設定進度條
        self.update_idletasks()

    def set_filename(self, filename):
        self.filename_label.configure(text=f"下載中: {filename}")
        self.update_idletasks()

    def set_eta(self, eta):
        self.eta_label.configure(text=f"預估時間: {eta}")
        self.update_idletasks()

    @staticmethod
    def wrap_text(text, line_length):
        lines = []
        for i in range(0, len(text), line_length):
            lines.append(text[i:i+line_length])
        return "\n".join(lines)

def clean_ansi_codes(text):
    return re.sub(r'\x1b\[[0-9;]*m', '', text)

def format_eta(eta_seconds):
    if eta_seconds is None:
        return "正在尋找..."
    hours, remainder = divmod(eta_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours > 0:
        return f"{int(hours)}小時{int(minutes)}分{int(seconds)}秒"
    elif minutes > 0:
        return f"{int(minutes)}分{int(seconds)}秒"
    else:
        return f"{int(seconds)}秒"

download_folder = os.path.join(os.path.expanduser("~"), "Desktop", "youtube下載")# 設置保存下載視頻的根目錄到桌面的「youtube下載」文件夾中
os.makedirs(download_folder, exist_ok=True)

def show_error_message(e):
    messagebox.showerror("錯誤", f"下載失敗: {str(e)}")

def show_success_message(url_box ,format_choice):
    url = url_box.get()
    if 'list=' in url:
        messagebox.showinfo("成功", "清單下載完成！")
    else:
        if format_choice == "mp3":
            messagebox.showinfo("成功", "音檔下載完成！")
        else:
            messagebox.showinfo("成功", "影片下載完成！")



def download_video(url, format_choice, progress_window, on_complete_callback, url_box, ffmpeg_path):
    try:
        global download_folder

        if format_choice == "mp3":
            ydl_opts = {
                'format': str(mp3_format),
                'outtmpl': os.path.join(download_folder, '%(title)s.%(ext)s'),
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
                'ffmpeg_location': ffmpeg_path,
                'progress_hooks': [progress_hook(progress_window)],
                "cookies": cookie_txt_path,
                'quiet': True
            }
        else:
            ydl_opts = {
                'format': str(mp4_format),
                'outtmpl': os.path.join(download_folder, '%(title)s.%(ext)s'),
                'merge_output_format': 'mp4',
                'ffmpeg_location': ffmpeg_path,
                'progress_hooks': [progress_hook(progress_window)],
                "cookies": cookie_txt_path,
                'quiet': True
            }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        main_view.after(0, lambda: show_success_message(url_box, format_choice))
    except Exception as e:
        main_view.after(0, lambda: show_error_message(e))
    finally:
        main_view.after(0, lambda: url_box.delete(0, END))
        main_view.after(0, progress_window.destroy)
        on_complete_callback()



def download_playlist(playlist_url, format_choice, progress_window, on_complete_callback, url_box, ffmpeg_path):
    try:
        global download_folder

        if format_choice == "mp3":
            ydl_opts = {
                'format': '140',
                'outtmpl': os.path.join(download_folder, '%(playlist)s', '%(title)s.%(ext)s'),
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
                'ffmpeg_location': ffmpeg_path,
                'progress_hooks': [progress_hook(progress_window)], 
                "cookies": cookie_txt_path,
                'quiet': True
            }
        else:
            ydl_opts = {
                'format': '137+140',
                'outtmpl': os.path.join(download_folder, '%(playlist)s', '%(title)s.%(ext)s'),
                'merge_output_format': 'mp4',
                'ffmpeg_location': ffmpeg_path,
                'progress_hooks': [progress_hook(progress_window)],
                "cookies": cookie_txt_path,
                'quiet': True
            }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([playlist_url])

        main_view.after(0, lambda: show_success_message(url_box, format_choice))
    except Exception as e:
        main_view.after(0, lambda: show_error_message(e))
    finally:
        main_view.after(0, lambda: url_box.delete(0, END))
        main_view.after(0, progress_window.destroy)
        on_complete_callback()


def progress_hook(progress_window):
    def hook(d):
        if d['status'] == 'downloading':
            progress_percent_str = clean_ansi_codes(d.get('_percent_str', '0%'))
            try:
                progress_percent = float(progress_percent_str.strip('%'))
            except ValueError:
                progress_percent = 0
            filename = d.get('filename', '未知文件')
            eta = format_eta(d.get('eta', None))

            # 安全地更新 GUI
            progress_window.after(0, lambda: progress_window.set_progress(progress_percent))
            progress_window.after(0, lambda: progress_window.set_filename(filename))
            progress_window.after(0, lambda: progress_window.set_eta(eta))
        elif d['status'] == 'finished':
            progress_window.after(0, lambda: progress_window.set_progress(100))
            progress_window.after(0, lambda: progress_window.set_filename("下載完成"))
            progress_window.after(0, lambda: progress_window.set_eta("合併中..."))
    return hook

is_downloading = False

def on_download_button_click(cook, url_box, dropdown_menu, ffmpeg_path, first_open):
    global is_downloading
    
    if first_open != 1:
        first_open = 1
        print(first_open)
        return
    else:
        if not os.path.exists(cookie_txt_path):
            cookies_path()
            return

        if not os.path.exists(ffmpeg_path):
            messagebox.showerror("錯誤", f"找不到 FFmpeg 路徑: {ffmpeg_path}")
            return  # 停止執行

        if is_downloading:
            messagebox.showinfo("提示", "已有下載正在進行，請稍候完成後再試！")
            return

        url = url_box.get()
        format_choice = dropdown_menu.get()

        # 檢查是否選擇了格式
        if format_choice == "選擇格式":
            messagebox.showwarning("警告", "請選擇下載格式")
            return

        if url:
            progress_window = DownloadProgressWindow(cook)
            is_downloading = True  # 標記下載中

            def on_complete_callback():  # 下載完成後重置狀態
                global is_downloading
                is_downloading = False

        
                # 判斷是否為播放清單
            if 'list=' in url:
                Thread(target=download_playlist, args=(url, format_choice, progress_window, on_complete_callback, url_box, ffmpeg_path)).start()
            else:
                Thread(target=download_video, args=(url, format_choice, progress_window, on_complete_callback, url_box, ffmpeg_path)).start()
        else:
            messagebox.showwarning("警告", "請輸入有效的網址")
            url_box.delete(0, END)  # 清空輸入框


def cook_open_url(event):
    webbrowser.open("https://sites.google.com/view/yt-to-dowload/%E6%95%99%E5%AD%B8/%E8%A8%AD%E7%BD%AEcookies")

def cookies_path():
    cook = ctk.CTk()
    cook.geometry("400x200")
    cook.resizable(False, False)
    cook.iconbitmap(ico_path)
    cook.title("cookies")
    cook.attributes("-topmost", True)
    
    txat_label= ctk.CTkLabel(
        cook, 
        text="沒有cookies前往下載和設定",  
        font=("Arial", 20, "bold"), 
        fg_color="transparent",
    )
    txat_label.pack(pady=20)

    cook_label = ctk.CTkLabel(
        cook, 
        text="前往官網",  # 顯示網址
        font=("Arial", 20, "bold"), 
        fg_color="transparent",
        text_color="blue",  # 設置為藍色，看起來像超連結
        cursor="hand2"  # 讓滑鼠變成手型
    )
    cook_label.pack(pady=20)

    # 綁定點擊事件
    cook_label.bind("<Button-1>", cook_open_url)

    cook_button = ctk.CTkButton(cook, text="關閉",corner_radius=10,width=40,height=40,command=cook.destroy, font=("Arial", 20, "bold"))
    cook_button.pack(pady=20)
    cook.mainloop()