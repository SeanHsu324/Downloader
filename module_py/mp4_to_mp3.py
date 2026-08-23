import subprocess
import customtkinter as ctk
from tkinter import filedialog, messagebox

try:
    from .log import logger
except ImportError:
    logger = None


def mp34_set_logger(log_instance):

    global logger
    logger = log_instance

def log(message):
    message_text = f"[mp4_to_mp3] {message}"
    if logger:
        logger.write_log(message_text)
    else:
        print(message_text)

file_path = None  # 用於儲存選擇的檔案路徑

def mp3(mp3label, mp3start_button, first_open):
    global file_path  # 使用全域變數
    if first_open != 1:
        first_open = 1
        log(first_open)
        return
    else:
        file_path = filedialog.askopenfilename(
            title="選擇檔案",
            filetypes=[("所有支持檔案", "*.mp4"), ("mp4 檔案", "*.mp4")]
        )
        
        if file_path:
            # 顯示選擇的檔案
            mp3label.configure(text=f"選擇的檔案：{file_path}")
            # 啟用開始按鈕
            mp3start_button.configure(state=ctk.NORMAL)

def convert_mp4_to_mp3(ffmpeg_path, first_open):
    global file_path  # 使用全域變數
    if first_open != 1:
        first_open = 1
        log(first_open)
        return
    else:
        if not file_path:
            log("未選擇 MP4 檔案，取消轉換")
            messagebox.showerror("錯誤", "請先選擇一個 MP4 檔案！")
            file_path = None
            return

        # 設定輸出檔案路徑
        mp3_file = file_path.rsplit('.', 1)[0] + '.mp3'  # 輸出 mp3 檔案與原檔案同名
        
        try:
            log(f"開始 MP4 轉 MP3: {file_path}")
            command = [ffmpeg_path, '-i', file_path, '-vn', '-acodec', 'libmp3lame', mp3_file]
            subprocess.run(command, check=True)
            log(f"MP4 轉 MP3 成功: {mp3_file}")
            messagebox.showinfo("轉換完成", f"檔案已轉換為：\n{mp3_file}")
            file_path = None
        except subprocess.CalledProcessError as e:
            log(f"MP4 轉 MP3 失敗: {e}")
            messagebox.showerror("錯誤", f"轉換失敗：\n{e}")
            file_path = None
        except Exception as e:
            log(f"MP4 轉 MP3 發生錯誤: {e}")
            messagebox.showerror("錯誤", f"發生錯誤：\n{e}")
            file_path = None


