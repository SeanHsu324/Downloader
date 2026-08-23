import customtkinter as ctk
import subprocess
import os
from tkinter import messagebox
import re
from threading import Thread, Event
from tkinter import END
import sys
import webbrowser
import json
from urllib.parse import urlparse, urlsplit, urlunsplit, parse_qsl, urlencode
import io
import contextlib
import time
import builtins
import requests

if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

TOKEN_DIR = os.path.join(BASE_DIR, "config")
CUSTOM_TOKEN_PATH = os.path.join(TOKEN_DIR, "tokens.json")
os.makedirs(TOKEN_DIR, exist_ok=True)

try:
    from pytubefix import YouTube, Playlist, Channel
except ImportError:
    YouTube = None
    Playlist = None
    Channel = None

try:
    from .log import logger
except ImportError:
    logger = None


def download_set_logger(log_instance):
    global logger
    logger = log_instance

def log(message):
    message_text = f"[download] {message}"
    if logger:
        logger.write_log(message_text)
    else:
        print(message_text)


def resource_path(relative_path):
    """取得資源的正確路徑（適用於開發和打包後的環境）"""
    if hasattr(sys, 'frozen'):  # 如果是打包後的執行檔
        base_path = sys._MEIPASS  # type: ignore
    else:  # 如果是開發環境
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

ico_path = resource_path("picture/yt.ico")

# 先檢查系統 PATH 有沒有 node，沒有才把打包的 ./bin/nodejs加入PATH 
_node_exe_path = None

def _setup_nodejs():
    global _node_exe_path
    import shutil
    node = shutil.which("node")
    if node:
        _node_exe_path = node
        log(f"使用系統 Node.js: {node}")
        return
    
    # 系統沒有，改用打包的 bin/nodejs
    bundled = os.path.join(down_path, "bin", "nodejs") if down_path else resource_path("./bin/nodejs")
    bundled_exe = os.path.join(bundled, "node.exe")
    if os.path.exists(bundled_exe):
        # 將 bin/nodejs 的目錄加入 PATH 優先順序中
        os.environ["PATH"] = bundled + os.pathsep + os.environ.get("PATH", "")
        _node_exe_path = bundled_exe
        log(f"使用內建 Node.js: {bundled_exe}")
    else:
        log("警告: 找不到 Node.js，部分影片格式可能無法下載")


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

_setup_nodejs()



def _get_yt_dlp_exe():
    """取得 down_path/bin 下的外部 yt-dlp.exe。"""
    base_path = down_path or resource_path(".")
    return os.path.join(base_path, "bin", "yt_dlp", "yt-dlp.exe")


def _run_external_yt_dlp(options, urls, progress_window):
    """將既有 ydl_opts 轉為 yt-dlp.exe 參數；未對外改動原下載選項。"""
    executable = _get_yt_dlp_exe()
    if not os.path.isfile(executable):
        raise FileNotFoundError(f"找不到外部 yt-dlp.exe: {executable}")

    # 使用 yt-dlp 官方 progress template，避免從人類可讀文字猜測檔名與 ETA。
    command = [executable, "--newline", "--progress", "--progress-template", "download:%(progress)j"]
    log(f"啟動外部 yt-dlp：網址數={len(urls)}，格式={options.get('format', '未指定')}，執行檔={executable}")
    option_map = {
        "format": "--format",
        "outtmpl": "--output",
        "ffmpeg_location": "--ffmpeg-location",
        "merge_output_format": "--merge-output-format",
        "download_archive": "--download-archive",
        "user_agent": "--user-agent",
    }
    for key, argument in option_map.items():
        if options.get(key) is not None:
            command.extend([argument, str(options[key])])

    if options.get("ignoreerrors"):
        command.append("--ignore-errors")
    if options.get("restrictfilenames"):
        command.append("--restrict-filenames")
    if options.get("quiet"):
        command.append("--quiet")

    postprocessors = options.get("postprocessors") or []
    for postprocessor in postprocessors:
        if postprocessor.get("key") == "FFmpegExtractAudio":
            command.extend(["--extract-audio", "--audio-format", str(postprocessor.get("preferredcodec", "mp3"))])
            if postprocessor.get("preferredquality"):
                command.extend(["--audio-quality", str(postprocessor["preferredquality"])])

    js_runtimes = options.get("js_runtimes") or {}
    node_runtime = js_runtimes.get("node")
    if isinstance(node_runtime, dict) and node_runtime.get("path"):
        command.extend(["--js-runtimes", f"node:{node_runtime['path']}"])
    extractor_args = options.get("extractor_args") or {}
    youtube_args = (extractor_args.get("youtube") or {}).get("player_client")
    if youtube_args:
        command.extend(["--extractor-args", f"youtube:player_client={','.join(youtube_args)}"])
    for component in options.get("remote_components") or []:
        command.extend(["--remote-components", str(component)])

    hook = (options.get("progress_hooks") or [None])[0]
    last_logged_percent = -25
    process = subprocess.Popen(
        command + list(urls), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace",
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    percent_pattern = re.compile(r"(\d+(?:\.\d+)?)%")
    if process.stdout:
        for line in process.stdout:
            if not hook:
                continue
            payload = line.strip()
            if payload.startswith("download:"):
                payload = payload[len("download:"):].strip()
            try:
                progress = json.loads(payload)
                if isinstance(progress, dict):
                    percent = progress.get("percent")
                    if percent is None:
                        downloaded = progress.get("downloaded_bytes") or 0
                        total = progress.get("total_bytes") or progress.get("total_bytes_estimate")
                        percent = (downloaded * 100 / total) if total else 0
                    filename = progress.get("filename") or progress.get("info", {}).get("filename", "")
                    percent_value = float(percent)
                    if percent_value >= last_logged_percent + 25:
                        log(f"yt-dlp 進度：{percent_value:.1f}% ，檔案={os.path.basename(filename) if filename else '解析中'}，ETA={progress.get('eta', '未知')}秒")
                        last_logged_percent = percent_value
                    hook({
                        "status": progress.get("status", "downloading"),
                        "_percent_str": f"{percent_value:.1f}%",
                        "filename": filename,
                        "eta": progress.get("eta"),
                    })
                    continue
            except (ValueError, TypeError, json.JSONDecodeError):
                pass
            match = percent_pattern.search(line)
            if match:
                hook({"status": "downloading", "_percent_str": f"{match.group(1)}%", "filename": "", "eta": None})
    return_code = process.wait()
    if return_code != 0 and not options.get("ignoreerrors"):
        log(f"yt-dlp 執行失敗，返回碼={return_code}")
        raise subprocess.CalledProcessError(return_code, command)
    log(f"外部 yt-dlp 完成，返回碼={return_code}")
    return return_code


class _ExternalYTDLP:
    def __init__(self, options):
        self.options = options

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def download(self, urls):
        return _run_external_yt_dlp(self.options, urls, None)



class DownloadProgressWindow(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("下載進度")
        self.geometry("400x200")
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.transient(parent)
        self.after(200, lambda: self.iconbitmap(ico_path) if os.path.exists(ico_path) else None)
        self.lift()
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

def sanitize_filename(filename):
    """移除 Windows 不合法的檔名字元"""
    # Windows 不合法字元: \ / : * ? " < > |
    return re.sub(r'[\\/:*?"<>|]', '', filename)

def format_eta(eta_seconds):
    if eta_seconds is None:
        return "正在尋找..."
    try:
        eta_seconds = max(0, int(float(eta_seconds)))
    except (TypeError, ValueError):
        return "正在尋找..."
    hours, remainder = divmod(eta_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours > 0:
        return f"{int(hours)}小時{int(minutes)}分{int(seconds)}秒"
    elif minutes > 0:
        return f"{int(minutes)}分{int(seconds)}秒"
    else:
        return f"{int(seconds)}秒"

def show_error_message(e):
    err = str(e)
    if "Sign in to confirm your age" in err or "login required" in err.lower():
        messagebox.showwarning(
            "需要 OAuth2 驗證",
            "此影片需要 YouTube OAuth2 裝置驗證。\n\n"
            "請開啟 OAuth2 驗證後再試；本程式不會要求您的帳號密碼。"
        )
    elif "members only" in err.lower() or "member-only" in err.lower() or "joined" in err.lower():
        messagebox.showwarning(
            "會員限定影片",
            "此影片需要已具備會員權限的 YouTube 帳號，請確認 OAuth2 驗證使用的帳號具有觀看權限。"
        )
    else:
        messagebox.showerror("錯誤", f"下載失敗: {err}")
        log(f"下載失敗: {err}")

def show_success_message(url_box, format_choice):
    try:
        url = url_box.get() if url_box else ""
    except Exception:
        url = ""
    if is_youtube_channel_url(url):
        messagebox.showinfo("成功", "頻道下載完成！")
    elif 'playlist?' in url:
        messagebox.showinfo("成功", "清單下載完成！")
    else:
        if format_choice == "mp3":
            messagebox.showinfo("成功", "音檔下載完成！")
        else:
            messagebox.showinfo("成功", "影片下載完成！")


oauth_state_path = os.path.join(TOKEN_DIR, "oauth2_state.json")


def is_oauth_linked():
    """以固定 Token 檔判斷 OAuth2 是否已完成連結。"""
    if not os.path.isfile(CUSTOM_TOKEN_PATH) or os.path.getsize(CUSTOM_TOKEN_PATH) == 0:
        return False
    try:
        with open(CUSTOM_TOKEN_PATH, "r", encoding="utf-8") as state_file:
            token_data = json.load(state_file)
        return isinstance(token_data, dict) and bool(
            token_data.get("refresh_token") or token_data.get("access_token")
        )
    except (OSError, ValueError, TypeError):
        return False


def mark_oauth_linked():
    try:
        os.makedirs(os.path.dirname(oauth_state_path), exist_ok=True)
        with open(oauth_state_path, "w", encoding="utf-8") as state_file:
            json.dump({"linked": True}, state_file, ensure_ascii=False, indent=2)
        log("OAuth2 授權狀態已保存；後續啟動不再重複顯示驗證視窗")
    except OSError as error:
        log(f"OAuth2 授權狀態保存失敗：{error}")


def clear_oauth_linked():
    try:
        for path in (oauth_state_path, CUSTOM_TOKEN_PATH):
            if os.path.exists(path):
                os.remove(path)
        log("OAuth2 授權狀態與固定 Token 已清除")
    except OSError as error:
        log(f"OAuth2 授權狀態清除失敗：{error}")


def force_revoke_oauth():
    """撤銷 Google OAuth2 授權並刪除固定位置的本機 Token。"""
    if not os.path.isfile(CUSTOM_TOKEN_PATH):
        log("找不到 OAuth2 Token，目前處於未授權狀態")
        clear_oauth_linked()
        return False
    try:
        with open(CUSTOM_TOKEN_PATH, "r", encoding="utf-8") as token_file:
            token_data = json.load(token_file)
        if not isinstance(token_data, dict):
            raise ValueError("OAuth2 Token 格式無效")
        token = token_data.get("refresh_token") or token_data.get("access_token")
        if token:
            response = requests.post(
                "https://oauth2.googleapis.com/revoke",
                params={"token": token},
                headers={"content-type": "application/x-www-form-urlencoded"},
                timeout=15,
            )
            if response.status_code != 200:
                log(f"Google OAuth2 撤銷回應狀態碼：{response.status_code}")
                return False
            log("Google OAuth2 授權已撤銷")
        clear_oauth_linked()
        return True
    except (OSError, ValueError, TypeError, requests.RequestException) as error:
        log(f"OAuth2 撤銷失敗：{error}")
        return False


class OAuthDeviceWindow(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("YouTube OAuth2 裝置驗證")
        self.geometry("500x340")
        self.resizable(False, False)
        self.transient(parent)
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        frame = ctk.CTkFrame(self, corner_radius=12)
        frame.pack(fill="both", expand=True, padx=18, pady=18)
        ctk.CTkLabel(frame, text="OAuth2 裝置驗證", font=("Arial", 22, "bold")).pack(pady=(12, 4))
        ctk.CTkLabel(frame, text="請使用瀏覽器開啟下列網址，輸入驗證碼完成授權。", wraplength=430).pack(pady=4)
        self.url_label = ctk.CTkLabel(frame, text="驗證網址：等待取得…", text_color="#65b7ff", cursor="hand2", wraplength=430)
        self.url_label.pack(pady=(10, 3))
        self.device_url = None
        self.url_label.bind("<Button-1>", self.open_device_url)
        self.code_label = ctk.CTkLabel(frame, text="驗證碼：等待取得…", font=("Consolas", 20, "bold"))
        self.code_label.pack(pady=(4, 2))
        self.copy_code_button = ctk.CTkButton(
            frame,
            text="複製驗證碼",
            command=self.copy_verification_code,
            width=140,
            height=30,
        )
        self.copy_code_button.pack(pady=(0, 4))
        ctk.CTkLabel(
            frame,
            text="此為 OAuth2 裝置驗證，不會危害您的帳號。本程式不會要求帳號密碼。\n請避免大量下載，以免觸發 YouTube 限制；建議使用非主要帳號。",
            wraplength=430, justify="left"
        ).pack(pady=(12, 8))
        self.complete_button = ctk.CTkButton(
            frame,
            text="已完成授權",
            command=self.confirm_authorization,
            width=180,
            height=36,
        )
        self.complete_button.pack(pady=(0, 8))
        self.withdraw()

    def on_close(self):
        oauth_cancel_event.set()
        log("OAuthDeviceWindow 已關閉，已發出取消 OAuth2 流程訊號")
        self.withdraw()

    def copy_verification_code(self):
        code_text = self.code_label.cget("text").replace("驗證碼：", "").strip()
        if not code_text or code_text == "等待取得…":
            log("OAuth2 尚未取得驗證碼，略過複製")
            return
        try:
            self.clipboard_clear()
            self.clipboard_append(code_text)
            self.update()
            log("OAuth2 驗證碼已複製到剪貼簿（內容不寫入 log）")
            self.copy_code_button.configure(text="已複製")
            self.after(1200, lambda: self.copy_code_button.configure(text="複製驗證碼") if self.winfo_exists() else None)
        except Exception as error:
            log(f"OAuth2 驗證碼複製失敗：{error}")

    def confirm_authorization(self):
        if oauth_cancel_event.is_set():
            log("OAuth2 已取消，忽略已完成授權按鈕")
            return
        oauth_complete_event.set()
        self.complete_button.configure(state="disabled", text="正在確認授權…")
        log("使用者按下已完成授權，解除 pytubefix 等待")

    def open_device_url(self, _event=None):
        if not self.device_url:
            log("OAuth2 驗證網址尚未取得，略過瀏覽器開啟")
            return
        try:
            if webbrowser.open(self.device_url):
                log("使用者已點擊 OAuth2 驗證網址並開啟瀏覽器")
            else:
                log("OAuth2 驗證網址已送出，但瀏覽器未回報成功")
        except Exception as error:
            log(f"開啟 OAuth2 驗證網址失敗：{error}")

    def set_device_info(self, url=None, code=None):
        if url:
            self.device_url = url
            log("OAuthDeviceWindow 已更新正式 Google 裝置驗證網址")
            self.url_label.configure(text=f"驗證網址：{url}")
        if code:
            log("OAuthDeviceWindow 已更新有效驗證碼（內容不寫入 log）")
            self.code_label.configure(text=f"驗證碼：{code}")
        self.deiconify()
        self.lift()

    def close_when_done(self):
        if self.winfo_exists():
            self.after(800, self.withdraw)


oauth_window = None
oauth_cancel_event = Event()
oauth_complete_event = Event()


class OAuthUserCancelled(Exception):
    """使用者關閉 OAuth2 裝置驗證視窗。"""


def _oauth_verifier(verification_url, user_code):
    """pytubefix 官方 OAuth verifier：顯示資料並等待 GUI 按鈕，不使用終端機 Enter。"""
    oauth_complete_event.clear()
    log("OAuth2 verifier 已收到裝置網址與驗證碼，等待使用者完成授權")
    if oauth_window is not None and main_view is not None:
        main_view.after(0, lambda: oauth_window.set_device_info(verification_url, user_code))
    while not oauth_cancel_event.is_set() and not oauth_complete_event.is_set():
        time.sleep(0.2)
    if oauth_cancel_event.is_set():
        log("使用者關閉 OAuth2 裝置驗證視窗，取消授權流程")
        raise OAuthUserCancelled("使用者取消 OAuth2 裝置驗證")
    log("收到已完成授權訊號，讓 pytubefix 繼續向 Google 確認並寫入 Token")


def show_oauth_device_window(parent):
    global oauth_window
    if oauth_window is None or not oauth_window.winfo_exists():
        oauth_window = OAuthDeviceWindow(parent)
    else:
        oauth_window.deiconify()
    oauth_window.lift()
    oauth_window.focus_force()
    return oauth_window


class _OAuthOutput(io.StringIO):
    """擷取 pytubefix OAuth2 的裝置網址與代碼，避免誤把一般提示當成驗證資料。"""
    def __init__(self):
        super().__init__()
        self.pending = ""
        self.logged_prompt_ignored = False

    def write(self, value):
        result = super().write(value)
        if oauth_window is None or not value:
            return result

        self.pending = (self.pending + value)[-4096:]
        text = self.pending
        # pytubefix 的裝置驗證固定使用 Google device endpoint；不接受其他網址。
        url = "https://www.google.com/device" if re.search(
            r"https?://(?:www\.)?google\.com/device\b", text, re.I
        ) else None

        code = None
        # 只接受「input code <代碼>」或「verification code <代碼>」後的內容。
        # 不再掃描整段輸出，避免把 AND-INPUT-CODE、PLEASE-OPEN 等提示當成驗證碼。
        code_match = re.search(
            r"(?:input\s+code|verification\s+code|authorization\s+code)\s*[:：]?\s*"
            r"([A-Z0-9]{3,5}(?:[- ]+[A-Z0-9]{3,5}){2})(?![A-Za-z0-9])",
            text,
            re.I,
        )
        if code_match:
            candidate = re.sub(r"[- ]+", "-", code_match.group(1)).upper()
            if candidate.replace("-", "").lower() not in {"pressenter", "pleaseopen", "andinputcode"}:
                code = candidate
                log("OAuth2 已從 input code 後擷取三段式裝置驗證碼（內容不寫入 log）")
            else:
                log(f"OAuth2 忽略提示文字：{candidate}")

        if url or code:
            log(f"OAuth2 裝置資訊已擷取：網址={'已取得' if url else '等待'}，驗證碼={'已取得' if code else '等待'}")
            main_view.after(0, lambda: oauth_window.set_device_info(url, code))
        elif "press enter" in text.lower() and not self.logged_prompt_ignored:
            log("OAuth2 忽略非驗證提示文字：Press enter")
            self.logged_prompt_ignored = True
        elif value.strip():
            log("OAuth2 尚未取得有效裝置網址或驗證碼，等待後續輸出")
        return result


def _oauth_progress(stream, chunk, bytes_remaining):
    total = getattr(stream, "filesize", None) or getattr(stream, "filesize_approx", None)
    if not total:
        return
    now = time.monotonic()
    start_time = getattr(_oauth_progress, "start_time", now)
    downloaded = max(0, total - bytes_remaining)
    elapsed = max(now - start_time, 0.001)
    speed = downloaded / elapsed
    eta = int(max(0, (total - downloaded) / speed)) if speed > 0 else None
    filename = getattr(stream, "default_filename", None) or getattr(stream, "title", None) or "OAuth2 串流"
    progress_hook_target = getattr(_oauth_progress, "target", None)
    last_logged = getattr(_oauth_progress, "last_logged", -25)
    percent = downloaded * 100 / total
    if percent >= last_logged + 25:
        log(f"OAuth2 進度：{percent:.1f}% ，檔案={os.path.basename(filename)}，ETA={eta if eta is not None else '未知'}秒")
        _oauth_progress.last_logged = percent
    if progress_hook_target:
        progress_hook_target({
            "status": "downloading",
            "_percent_str": f"{downloaded * 100 / total:.1f}%",
            "filename": filename,
            "eta": eta,
        })


def _select_oauth_streams(yt):
    # OAuth2 模式固定選擇最高畫質，不套用一般模式的畫質參數。
    video_stream = yt.streams.filter(adaptive=True, only_video=True).order_by("resolution").desc().first()
    audio_stream = yt.streams.filter(adaptive=True, only_audio=True).order_by("abr").desc().first()
    if not video_stream or not audio_stream:
        progressive = yt.streams.filter(progressive=True).order_by("resolution").desc().first()
        if not progressive:
            raise RuntimeError("OAuth2 模式找不到可下載的影片串流")
        return progressive, None
    return video_stream, audio_stream


def _download_oauth_video(url, format_choice, progress_window, ffmpeg_path, download_folder):
    log(f"OAuth2 開始下載：格式={format_choice}，網址={url}")
    if YouTube is None:
        raise ImportError("OAuth2 模式需要先安裝 pytubefix：pip install pytubefix")
    os.makedirs(download_folder, exist_ok=True)
    output_capture = _OAuthOutput()
    _oauth_progress.last_logged = -25
    with contextlib.redirect_stdout(output_capture), contextlib.redirect_stderr(output_capture):
        yt = YouTube(
            url,
                            use_oauth=True,

            allow_oauth_cache=True,
            token_file=CUSTOM_TOKEN_PATH,
            oauth_verifier=_oauth_verifier,
            on_progress_callback=_oauth_progress,
        )
        video_stream, audio_stream = _select_oauth_streams(yt)
        if not is_oauth_linked():
            log("OAuth2 串流解析後仍未取得有效 Token，保留驗證視窗並停止下載")
            if oauth_window is not None and main_view is not None:
                main_view.after(0, lambda: oauth_window.complete_button.configure(
                    state="normal", text="已完成授權"
                ))
            raise RuntimeError("OAuth2 尚未完成授權，請完成瀏覽器驗證後再按一次已完成授權")
        log("OAuth2 Token 已確認，準備自動關閉驗證視窗")
        if oauth_window is not None and main_view is not None:
            main_view.after(0, oauth_window.withdraw)
        title = sanitize_filename(yt.title).strip()[:120] or "youtube_video"
        log(f"OAuth2 驗證完成：標題={title}，影片畫質={getattr(video_stream, 'resolution', '未知')}，音訊品質={getattr(audio_stream, 'abr', '無')}")
        if format_choice == "mp3":
            if audio_stream is None:
                raise RuntimeError("OAuth2 模式找不到最高音訊串流")
            audio_file = os.path.join(download_folder, f".{title}.oauth-audio.mp4")
            output_file = os.path.join(download_folder, f"{title}.mp3")
            _oauth_progress.target = progress_hook(progress_window)
            _oauth_progress.start_time = time.monotonic()
            log(f"OAuth2 下載音訊串流：{os.path.basename(audio_file)}")
            audio_stream.download(output_path=download_folder, filename=os.path.basename(audio_file), skip_existing=False)
            log(f"OAuth2 開始 FFmpeg 轉換：{os.path.basename(output_file)}")
            result = subprocess.run([ffmpeg_path, "-y", "-i", audio_file, "-vn", "-codec:a", "libmp3lame", "-b:a", "192k", output_file], capture_output=True, text=True)
            if result.returncode != 0:
                raise RuntimeError(result.stderr.strip() or "FFmpeg 轉換 OAuth2 音訊失敗")
            if os.path.exists(audio_file):
                os.remove(audio_file)
            log(f"OAuth2 MP3 完成：{output_file}")
        elif audio_stream is None:
            output_file = os.path.join(download_folder, f"{title}.mp4")
            _oauth_progress.target = progress_hook(progress_window)
            _oauth_progress.start_time = time.monotonic()
            log(f"OAuth2 下載最高畫質串流：{os.path.basename(output_file)}")
            video_stream.download(output_path=download_folder, filename=os.path.basename(output_file), skip_existing=False)
            log(f"OAuth2 MP4 完成：{output_file}")
        else:
            video_file = os.path.join(download_folder, f".{title}.oauth-video.mp4")
            audio_file = os.path.join(download_folder, f".{title}.oauth-audio.mp4")
            _oauth_progress.target = progress_hook(progress_window)
            _oauth_progress.start_time = time.monotonic()
            log(f"OAuth2 下載影片串流：{os.path.basename(video_file)}")
            video_stream.download(output_path=download_folder, filename=os.path.basename(video_file), skip_existing=False)
            _oauth_progress.start_time = time.monotonic()
            log(f"OAuth2 下載音訊串流：{os.path.basename(audio_file)}")
            audio_stream.download(output_path=download_folder, filename=os.path.basename(audio_file), skip_existing=False)
            output_file = os.path.join(download_folder, f"{title}.mp4")
            log(f"OAuth2 開始 FFmpeg 合併：{os.path.basename(output_file)}")
            result = subprocess.run([ffmpeg_path, "-y", "-i", video_file, "-i", audio_file, "-c", "copy", output_file], capture_output=True, text=True)
            if result.returncode != 0:
                raise RuntimeError(result.stderr.strip() or "FFmpeg 合併 OAuth2 影片失敗")
            for temporary_file in (video_file, audio_file):
                if os.path.exists(temporary_file):
                    os.remove(temporary_file)
            log(f"OAuth2 MP4 完成：{output_file}")
    mark_oauth_linked()
    if oauth_window is not None:
        main_view.after(0, oauth_window.close_when_done)


def _download_oauth_collection(url, format_choice, progress_window, ffmpeg_path, download_folder, collection_type):
    """以 test.py 相同的 OAuth2 參數逐一下載清單或頻道影片。"""
    log(f"OAuth2 開始處理{collection_type}：{url}")
    if collection_type == "playlist":
        if Playlist is None:
            raise ImportError("OAuth2 模式需要先安裝 pytubefix")
        collection = Playlist(url)
    else:
        if Channel is None:
            raise ImportError("OAuth2 模式需要先安裝 pytubefix")
        collection = Channel(url)

    videos = getattr(collection, "videos", None)
    if videos is None:
        raise RuntimeError("OAuth2 模式無法讀取清單或頻道影片")
    for item in videos:
        video_url = getattr(item, "watch_url", None) or getattr(item, "url", None)
        if not video_url:
            continue
        log(f"OAuth2 處理第 {getattr(_download_oauth_collection, 'index', 0) + 1} 個項目")
        _download_oauth_collection.index = getattr(_download_oauth_collection, 'index', 0) + 1
        _download_oauth_video(video_url, format_choice, progress_window, ffmpeg_path, download_folder)


def download_video(url, format_choice, progress_window, on_complete_callback, url_box, ffmpeg_path, mp3_format, mp4_format, download_folder, oauth_check_button_var):
    log(f"單一影片下載開始：模式={'OAuth2' if oauth_check_button_var == 'True' else '一般 yt-dlp'}，格式={format_choice}，網址={url}")
    try:
        if oauth_check_button_var == "True":
            _download_oauth_video(url, format_choice, progress_window, ffmpeg_path, download_folder)
            main_view.after(0, lambda: show_success_message(url_box, format_choice))
            return
        if format_choice == "mp3":
            ydl_opts = {
                'format': f"{mp3_format}",
                'outtmpl': os.path.join(download_folder, '%(title)s.%(ext)s'),
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
                'ffmpeg_location': ffmpeg_path,
                'progress_hooks': [progress_hook(progress_window)],
                'quiet': True
            }
        else:
            ydl_opts = {
                'format': f"{mp4_format}",
                'outtmpl': os.path.join(download_folder, '%(title)s.%(ext)s'),
                'merge_output_format': 'mp4',
                'ffmpeg_location': ffmpeg_path,
                'progress_hooks': [progress_hook(progress_window)],
                'quiet': True
            }

        with _ExternalYTDLP(ydl_opts) as ydl:
            ydl.download([url])

        main_view.after(0, lambda: show_success_message(url_box, format_choice))
    except Exception as e:
        error_msg = str(e)
        if oauth_check_button_var == "True" and any(
            phrase in error_msg.lower()
            for phrase in ("oauth", "login required", "sign in", "authentication", "age")
        ):
            clear_oauth_linked()
            log("OAuth2 驗證可能失效，已清除連結狀態；下次下載會重新顯示驗證視窗")
        log(e)
        main_view.after(0, lambda: show_error_message(error_msg))
    finally:
        main_view.after(0, lambda: url_box.delete(0, END))
        main_view.after(0, progress_window.destroy)
        on_complete_callback()



def download_playlist(playlist_url, format_choice, progress_window, on_complete_callback, url_box, ffmpeg_path, mp3_format, mp4_format, download_folder, oauth_check_button_var):
    log(f"播放清單下載開始：模式={'OAuth2' if oauth_check_button_var == 'True' else '一般 yt-dlp'}，格式={format_choice}，網址={playlist_url}")
    try:
        if oauth_check_button_var == "True":
            _download_oauth_collection(playlist_url, format_choice, progress_window, ffmpeg_path, download_folder, "playlist")
            main_view.after(0, lambda: show_success_message(url_box, format_choice))
            return
        if format_choice == "mp3":
            ydl_opts = {
                'format': f"{mp3_format}",
                'outtmpl': os.path.join(download_folder, '%(playlist)s', '%(title)s.%(ext)s'),
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
                'ffmpeg_location': ffmpeg_path,
                'progress_hooks': [progress_hook(progress_window)], 
                'quiet': True
            }
        else:
            ydl_opts = {
            'format': f"{mp4_format}",
            'outtmpl': os.path.join(download_folder, '%(playlist)s', '%(title)s.%(ext)s'),
            'merge_output_format': 'mp4',
            'ffmpeg_location': ffmpeg_path,
            'progress_hooks': [progress_hook(progress_window)],
            'quiet': True
            }

        with _ExternalYTDLP(ydl_opts) as ydl:
            ydl.download([playlist_url])

        main_view.after(0, lambda: show_success_message(url_box, format_choice))
    except Exception as e:
        error_msg = str(e)
        if oauth_check_button_var == "True" and any(
            phrase in error_msg.lower()
            for phrase in ("oauth", "login required", "sign in", "authentication", "age")
        ):
            clear_oauth_linked()
            log("OAuth2 驗證可能失效，已清除連結狀態；下次下載會重新顯示驗證視窗")
        log(e)
        main_view.after(0, lambda: show_error_message(error_msg))
    finally:
        main_view.after(0, lambda: url_box.delete(0, END))
        main_view.after(0, progress_window.destroy)
        on_complete_callback()




def download_channel_videos(channel_url, format_choice, progress_window, on_complete_callback, url_box, ffmpeg_path, mp3_format, mp4_format, download_folder, oauth_check_button_var):
    log(f"頻道下載開始：模式={'OAuth2' if oauth_check_button_var == 'True' else '一般 yt-dlp'}，格式={format_choice}，網址={channel_url}")
    try:
        if oauth_check_button_var == "True":
            _download_oauth_collection(channel_url, format_choice, progress_window, ffmpeg_path, download_folder, "channel")
            main_view.after(0, lambda: show_success_message(url_box, format_choice))
            return
        channel_outtmpl = os.path.join(download_folder, '%(uploader)s', '%(title)s.%(ext)s')
        
        archive_file_path = os.path.join(download_folder, 'downloaded_archive.txt')

        if format_choice == "mp3":
            ydl_opts = {
                'format': f"{mp3_format}",
                'outtmpl': channel_outtmpl,
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
                'ffmpeg_location': ffmpeg_path,
                'progress_hooks': [progress_hook(progress_window)],
                'quiet': False,
                'download_archive': archive_file_path 
            }
        else:
            ydl_opts = {
                'format': f"{mp4_format}",
                # 專門用於頻道的輸出模板
                'outtmpl': channel_outtmpl,
                'merge_output_format': 'mp4',
                'ffmpeg_location': ffmpeg_path,
                'progress_hooks': [progress_hook(progress_window)],
                'quiet': False,
                'download_archive': archive_file_path 
            }

        with _ExternalYTDLP(ydl_opts) as ydl:
            ydl.download([channel_url])

        main_view.after(0, lambda: show_success_message(url_box, format_choice))
    except Exception as e:
        error_msg = str(e)
        if oauth_check_button_var == "True" and any(
            phrase in error_msg.lower()
            for phrase in ("oauth", "login required", "sign in", "authentication", "age")
        ):
            clear_oauth_linked()
            log("OAuth2 驗證可能失效，已清除連結狀態；下次下載會重新顯示驗證視窗")
        log(e)
        main_view.after(0, lambda: show_error_message(error_msg))
    finally:
        main_view.after(0, lambda: url_box.delete(0, END))
        main_view.after(0, progress_window.destroy)
        on_complete_callback()




def progress_hook(progress_window):
    last_filename = {"value": "解析中..."}
    last_eta = {"value": "正在尋找..."}

    def hook(d):
        status = d.get('status')
        if status == 'downloading':
            progress_percent_str = clean_ansi_codes(str(d.get('_percent_str', '0%')))
            try:
                progress_percent = float(progress_percent_str.strip('%'))
            except (ValueError, TypeError):
                progress_percent = 0
            incoming_filename = d.get('filename')
            if incoming_filename:
                last_filename['value'] = os.path.basename(str(incoming_filename))
            eta_value = d.get('eta')
            if eta_value is not None:
                last_eta['value'] = format_eta(eta_value)
            log(f"進度 UI 更新：{progress_percent:.1f}% ，檔案={last_filename['value']}，ETA={last_eta['value']}")

            progress_window.after(0, lambda: progress_window.set_progress(progress_percent))
            progress_window.after(0, lambda: progress_window.set_filename(last_filename['value']))
            progress_window.after(0, lambda: progress_window.set_eta(last_eta['value']))
        elif status == 'finished':
            log(f"進度 UI 完成：檔案={last_filename['value']}，進入合併階段")
            progress_window.after(0, lambda: progress_window.set_progress(100))
            progress_window.after(0, lambda: progress_window.set_filename("下載完成"))
            progress_window.after(0, lambda: progress_window.set_eta("合併中..."))
    return hook


def is_single_video_url(url: str) -> bool:
    """依 yt-dlp 常見分流邏輯判斷是否為指定單支影片。"""
    try:
        parsed = urlsplit(url)
        query = dict(parse_qsl(parsed.query, keep_blank_values=True))
        path = parsed.path.lower()
        return bool(query.get("v")) or path.startswith("/shorts/") or path.startswith("/embed/")
    except (TypeError, ValueError):
        return False


def remove_playlist_parameters(url: str) -> str:
    """保留影片 ID，移除 list/index 等播放清單參數。"""
    try:
        parsed = urlsplit(url)
        query = [(key, value) for key, value in parse_qsl(parsed.query, keep_blank_values=True)
                 if key.lower() not in {"list", "index", "start_radio"}]
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query), parsed.fragment))
    except (TypeError, ValueError):
        return url.split("&list=", 1)[0]


def is_playlist_url(url: str) -> bool:
    try:
        parsed = urlsplit(url)
        query = dict(parse_qsl(parsed.query, keep_blank_values=True))
        return "playlist" in parsed.path.lower() or bool(query.get("list"))
    except (TypeError, ValueError):
        return "playlist?" in url or "list=" in url


def is_youtube_channel_url(url: str) -> bool:
    try:
        # 1. 解析網址
        parsed_url = urlparse(url)
        path_segments = [s for s in parsed_url.path.split('/') if s]

        # 2. 檢查網域是否為 youtube
        if 'youtube.com' not in parsed_url.netloc:
            return False

        # 3. 檢查路徑結構
        if not path_segments:
            return False
            
        # 檢查新版 Handle (例如: /@Gemini)
        if path_segments[0].startswith('@'):
            return True
        
        # 檢查舊版關鍵字 (例如: /user/..., /channel/..., /c/...)
        channel_keywords = ['user', 'channel', 'c']
        if path_segments[0].lower() in channel_keywords:
            return True
            
        return False
        
    except Exception:
        # 處理無效的網址格式
        return False

is_downloading = False

def on_download_button_click(cook, url_box, dropdown_menu, ffmpeg_path, first_open, mp3_format, mp4_format, download_folder,check_button_var, oauth_check_button_var):
    global is_downloading
    
    if first_open != 1:
        first_open = 1
        log(first_open)
        return
    else:

        if not os.path.exists(ffmpeg_path):
            messagebox.showerror("錯誤", f"找不到 FFmpeg 路徑: {ffmpeg_path}")
            log(f"找不到 FFmpeg 路徑: {ffmpeg_path}")
            return  # 停止執行

        if oauth_check_button_var == "True" and not is_oauth_linked():
            oauth_cancel_event.clear()
            oauth_complete_event.clear()
            log("OAuth2 尚未連結，顯示裝置驗證視窗")
            show_oauth_device_window(cook)
        elif oauth_check_button_var == "True":
            oauth_cancel_event.clear()
            oauth_complete_event.clear()
            log("OAuth2 已連結，略過裝置驗證視窗")

        if is_downloading:
            messagebox.showinfo("提示", "已有下載正在進行，請稍候完成後再試！")
            return
        
        url = url_box.get()
        format_choice = dropdown_menu.get()

        # 檢查是否選擇了格式
        if format_choice == "選擇格式":
            messagebox.showwarning("警告", "請選擇下載格式")
            return
        log(f"下載資料夾:{download_folder}")
        if download_folder is None:
                download_folder = os.path.join(os.path.expanduser("~"), "Desktop", "youtube下載")
        
        if download_folder is not os.path.exists(download_folder):
            
            try:
                os.makedirs(download_folder, exist_ok=True)
                log(f"成功創建下載資料夾: {download_folder}")

            except OSError as e:
                log(f"錯誤：無法創建下載資料夾 '{download_folder}'。請檢查路徑和權限。錯誤訊息: {e}")
                return

        if url:
            cook.update()
            progress_window = DownloadProgressWindow(cook)
            progress_window.update()
            is_downloading = True  # 標記下載中

            def on_complete_callback():  # 下載完成後重置狀態
                global is_downloading
                is_downloading = False

        
            if is_youtube_channel_url(url):
                if check_button_var == "True":
                    result = messagebox.askyesno(
                        title="操作確認", 
                        message="輸入的是頻道網址，是否要繼續執行下載操作？\n這可能會花費一段時間且下載時無法取消!\n如不想看到此訊息可在設定中關閉此提示。"
                    )
                    if result:
                        log("使用者點擊了「是」/Yes，繼續執行操作...")
                        Thread(target=download_channel_videos, args=(url, format_choice, progress_window, on_complete_callback, url_box, ffmpeg_path, mp3_format, mp4_format, download_folder, oauth_check_button_var)).start()
                    else:
                        log("使用者點擊了「否」/No，取消操作。")
                        progress_window.destroy()
                        is_downloading = False
                        return  
                else:
                    Thread(target=download_channel_videos, args=(url, format_choice, progress_window, on_complete_callback, url_box, ffmpeg_path, mp3_format, mp4_format, download_folder, oauth_check_button_var)).start()

            elif is_single_video_url(url):
                # 必須先判斷 v=；watch?v=...&list=... 仍然只下載指定影片。
                single_video_url = remove_playlist_parameters(url)
                log(f"URL 判定為單一影片，移除播放清單參數後：{single_video_url}")
                Thread(target=download_video, args=(single_video_url, format_choice, progress_window, on_complete_callback, url_box, ffmpeg_path, mp3_format, mp4_format, download_folder, oauth_check_button_var)).start()
            elif is_playlist_url(url):
                log(f"URL 判定為播放清單：{url}")
                Thread(target=download_playlist, args=(url, format_choice, progress_window, on_complete_callback, url_box, ffmpeg_path, mp3_format, mp4_format, download_folder, oauth_check_button_var)).start()
            else:
                log(f"URL 未匹配特殊類型，按單一影片處理：{url}")
                Thread(target=download_video, args=(url, format_choice, progress_window, on_complete_callback, url_box, ffmpeg_path, mp3_format, mp4_format, download_folder, oauth_check_button_var)).start()
        else:
            messagebox.showwarning("警告", "請輸入有效的網址")
            url_box.delete(0, END)  # 清空輸入框


