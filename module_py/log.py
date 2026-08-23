import os
import threading

import customtkinter as ctk
from tkinter import messagebox


class LogManager:
    """集中管理所有模組的日誌檔案與日誌視窗。"""

    REFRESH_INTERVAL_MS = 500

    def __init__(self, log_folder=None, filename="download_log.txt"):
        if log_folder is None:
            log_folder = os.getcwd()

        os.makedirs(log_folder, exist_ok=True)
        self.log_file_path = os.path.join(log_folder, filename)
        self._file_lock = threading.RLock()
        self.log_window = None
        self.textbox = None
        self._refresh_job = None
        self._last_displayed_content = None
        self.init_log_file()

    def init_log_file(self):
        """建立本次執行使用的日誌檔案並寫入標頭。"""
        try:
            with self._file_lock:
                with open(self.log_file_path, "w", encoding="utf-8") as file:
                    file.write("=== 下載日誌記錄開始 ===\n")
        except OSError as error:
            print(f"無法建立 Log 檔案: {error}")

    def write_log(self, message):
        """將訊息追加到檔案；GUI 由主執行緒定時刷新，避免跨執行緒操作 Tk。"""
        message_text = f"{message}\n"
        try:
            with self._file_lock:
                with open(self.log_file_path, "a", encoding="utf-8") as file:
                    file.write(message_text)
        except OSError as error:
            print(f"無法寫入 Log 檔案: {error}")

    def _read_log_content(self):
        try:
            with self._file_lock:
                with open(self.log_file_path, "r", encoding="utf-8") as file:
                    return file.read()
        except (OSError, UnicodeError) as error:
            print(f"無法讀取 Log 檔案: {error}")
            return ""

    def _refresh_textbox(self):
        """在 Tk 主執行緒中把檔案最新內容載入日誌視窗。"""
        if self.log_window is None or not self.log_window.winfo_exists():
            return
        if self.textbox is None or not self.textbox.winfo_exists():
            return

        content = self._read_log_content()
        if content == self._last_displayed_content:
            return

        try:
            self.textbox.configure(state="normal")
            self.textbox.delete("1.0", "end")
            self.textbox.insert("1.0", content)
            self.textbox.see("end")
            self.textbox.configure(state="disabled")
            self._last_displayed_content = content
        except Exception as error:
            print(f"更新 Log 視窗失敗: {error}")

    def _schedule_refresh(self):
        if self.log_window is None or not self.log_window.winfo_exists():
            self._refresh_job = None
            return

        self._refresh_textbox()
        self._refresh_job = self.log_window.after(
            self.REFRESH_INTERVAL_MS,
            self._schedule_refresh,
        )

    def _close_log_window(self):
        if self._refresh_job and self.log_window is not None:
            try:
                self.log_window.after_cancel(self._refresh_job)
            except Exception:
                pass
        self._refresh_job = None
        self.textbox = None
        if self.log_window is not None and self.log_window.winfo_exists():
            self.log_window.destroy()
        self.log_window = None
        self._last_displayed_content = None

    def show_log_window(self, parent_window, ico_path=None):
        """開啟顯示所有模組共用 Log 檔案的獨立視窗。"""
        if self.log_window is not None and self.log_window.winfo_exists():
            self.log_window.focus()
            return

        self.log_window = ctk.CTkToplevel(parent_window)
        self.log_window.title("執行日誌 (Log)")
        self.log_window.geometry("600x400")
        self.log_window.attributes("-topmost", True)
        self.log_window.protocol("WM_DELETE_WINDOW", self._close_log_window)

        if ico_path and os.path.exists(ico_path):
            self.log_window.after(200, lambda: self.log_window.iconbitmap(ico_path))

        self.textbox = ctk.CTkTextbox(self.log_window, wrap="word")
        self.textbox.pack(padx=10, pady=10, fill="both", expand=True)
        self._last_displayed_content = None
        self._refresh_textbox()

        btn_frame = ctk.CTkFrame(self.log_window, fg_color="transparent")
        btn_frame.pack(padx=10, pady=(0, 10), fill="x")

        copy_btn = ctk.CTkButton(
            btn_frame,
            text="複製日誌內容",
            command=self.copy_log_content,
        )
        copy_btn.pack(side="left", padx=5, expand=True, fill="x")

        open_btn = ctk.CTkButton(
            btn_frame,
            text="開啟 .txt 檔案",
            command=self.open_log_file,
        )
        open_btn.pack(side="right", padx=5, expand=True, fill="x")

        self._schedule_refresh()

    def copy_log_content(self):
        """將 Log 檔案內容複製至剪貼簿。"""
        try:
            content = self._read_log_content()
            if self.log_window is not None and self.log_window.winfo_exists():
                self.log_window.clipboard_clear()
                self.log_window.clipboard_append(content)
                messagebox.showinfo("提示", "已將日誌內容複製到剪貼簿！", parent=self.log_window)
        except Exception as error:
            messagebox.showerror("錯誤", f"複製失敗: {error}", parent=self.log_window)

    def open_log_file(self):
        """用系統預設軟體開啟 Log 文字檔。"""
        try:
            if os.path.exists(self.log_file_path):
                os.startfile(self.log_file_path)
            else:
                messagebox.showwarning("警告", "日誌檔案不存在！", parent=self.log_window)
        except Exception as error:
            messagebox.showerror("錯誤", f"無法開啟檔案: {error}", parent=self.log_window)


# 所有模組與 main.py 都應使用這個共用實例。
logger = LogManager()
