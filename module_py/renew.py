import os
import json
import requests
import customtkinter as ctk
import subprocess
import sys
import urllib.request
import shutil
import re


try:
    from .log import logger
except ImportError:
    logger = None


def renew_set_logger(log_instance):
    global logger
    logger = log_instance  

def log(message):
    message_text = f"[renew] {message}"
    if logger:
        logger.write_log(message_text)
    else:
        print(message_text)


# 設定 GitHub 儲存庫資訊
REPO_OWNER = "SeanHsu324"
REPO_NAME = "Downloader"
API_URL = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/releases/latest"

# 設定本地存放路徑
LOCAL_CONFIG_FOLDER = "c:\\downloadsitt"
JSON_PATH = os.path.join(LOCAL_CONFIG_FOLDER, "renew.json")
SPECIAL_UPDATER_VERSION = "v1.1.0-bate.3.2"


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
            log(f"讀取 JSON 失敗: {e}")
    return {}

def save_local_data(local_data):
    """儲存本地版本資訊。"""
    try:
        os.makedirs(LOCAL_CONFIG_FOLDER, exist_ok=True)
        with open(JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(local_data, f, ensure_ascii=False, indent=4)
        return True
    except Exception as e:
        log(f"寫入 JSON 失敗: {e}")
        return False


def download_updater_only(version_info, app_path, local_data):
    """下載 Updater.exe，但絕不執行；成功後記錄特殊版本欄位。"""
    try:
        download_url = None
        for asset in version_info["assets"]:
            if "Updater.exe" in asset["name"]:
                download_url = asset["browser_download_url"]
                break

        if not download_url:
            log("錯誤：GitHub Release 中找不到 Updater.exe")
            return False

        save_path = os.path.join(app_path, "Updater.exe")
        log(f"正在下載更新程式（只下載，不執行）: {download_url}")
        urllib.request.urlretrieve(download_url, save_path)

        local_data["Updater.exe版本"] = SPECIAL_UPDATER_VERSION
        if not save_local_data(local_data):
            return False

        log(f"Updater.exe 已下載至 {save_path}，不會執行 Updater.exe")
        return True
    except Exception as e:
        log(f"只下載 Updater.exe 失敗: {e}")
        return False


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
        log(f"檢查更新失敗: {e}")
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
            log("錯誤：GitHub Release 中找不到 Updater.exe")
            return

        save_path = os.path.join(app_path, "Updater.exe")
        log(f"正在下載更新程式: {download_url}")
        
        # 下載檔案
        urllib.request.urlretrieve(download_url, save_path)
        
        # 下載完後啟動並關閉主程式
        subprocess.Popen([save_path], cwd=app_path)
        sys.exit(0)
    except Exception as e:
        log(f"下載或執行 Updater 失敗: {e}")

def start_updater(version_info):
    """根據版本啟動更新程式"""
    app_path = get_app_path()
    latest_version = version_info["latest_version"]
    
    # 判斷是否符合特定前綴的強制更新條件
    Forced_update = latest_version.startswith("v1.1.0-bate.3")
    updater_exe = os.path.join(app_path, "Updater.exe")

    if Forced_update:
        # 1. 符合強制更新：只要 Updater.exe 存在就強制刪除
        if os.path.exists(updater_exe):
            try:
                os.remove(updater_exe)
                log("成功刪除舊版 Updater.exe")
            except OSError as e:
                log(f"刪除舊版 Updater 失敗: {e}")
        
        # 2. 重新下載並執行新的 Updater.exe
        download_and_run_updater(version_info, app_path)
        
    else:
        # 非強制更新：若 Updater.exe 存在則直接啟動，不存在才下載
        if os.path.exists(updater_exe):
            subprocess.Popen([updater_exe], cwd=app_path)
            sys.exit(0)
        else:
            download_and_run_updater(version_info, app_path)

def show_update_dialog(root, version_info):
    """顯示更新提示視窗"""
    latest_version = version_info["latest_version"]
    release_notes = version_info["release_notes"]
    
    Forced_update = latest_version.startswith("v1.1.0-bate.3")

    dialog = ctk.CTkToplevel(root)
    dialog.geometry("450x380")
    dialog.title("發現新版本")
    dialog.attributes("-topmost", True)

    # 根據是否為強制更新修改提示文字
    if Forced_update:
        msg = f"版本 {latest_version} 為必要更新，\n請點擊「立即更新」重裝更新程式。"
        btn_text = "重新安裝並更新"
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

    # 若非強制更新才顯示「稍後再說」
    if not Forced_update:
        close_btn = ctk.CTkButton(
            btn_frame, 
            text="稍後再說", 
            command=dialog.destroy,
            font=("Arial", 14)
        )
        close_btn.pack(side="right", padx=5)

    dialog.grab_set()

# ---------------------------------------------------------------------------
# 外部工具更新：ffmpeg、Node.js、yt-dlp
# ---------------------------------------------------------------------------
TOOLS_BIN_FOLDER = "bin"
TOOLS_STATE_FILE = "tool_versions.json"
DENO_RELATIVE_PATH = os.path.join("deno", "deno.exe")
DENO_RELEASE_API = "https://api.github.com/repos/denoland/deno/releases/latest"
TOOL_RELATIVE_PATHS = {
    "ffmpeg.exe": os.path.join("ffmpeg", "ffmpeg.exe"),
    "node.exe": os.path.join("nodejs", "node.exe"),
    "yt-dlp.exe": os.path.join("yt_dlp", "yt-dlp.exe"),
}
TOOL_RELEASE_APIS = {
    "ffmpeg.exe": "https://api.github.com/repos/BtbN/FFmpeg-Builds/releases/latest",
    "yt-dlp.exe": "https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest",
}
NODE_INDEX_URL = "https://nodejs.org/dist/index.json"


def _http_json(url):
    request = urllib.request.Request(url, headers={"User-Agent": "Downloader"})
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def _tool_version(exe_path, args):
    """執行工具的版本參數；找不到或版本格式異常時回傳空字串。"""
    try:
        completed = subprocess.run(
            [exe_path, *args], capture_output=True, text=True, timeout=10,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        output = (completed.stdout or completed.stderr).strip()
        if exe_path.lower().endswith("ffmpeg.exe"):
            match = __import__("re").search(r"ffmpeg version\s+([^\s]+)", output)
            return match.group(1) if match else output.splitlines()[0][:80]
        return output.splitlines()[0].strip() if output else ""
    except (OSError, subprocess.SubprocessError, IndexError):
        return ""


def _latest_tool_releases():
    """取得三項工具的官方最新版本與下載資訊。"""
    releases = {}
    ffmpeg_release = _http_json(TOOL_RELEASE_APIS["ffmpeg.exe"])
    ffmpeg_asset = next(
        (asset for asset in ffmpeg_release.get("assets", [])
         if asset.get("name") == "ffmpeg-master-latest-win64-gpl.zip"), None
    )
    if ffmpeg_asset:
        releases["ffmpeg.exe"] = {
            "version": ffmpeg_release.get("tag_name", "latest"),
            "url": ffmpeg_asset["browser_download_url"],
            "archive": True,
        }

    node_releases = _http_json(NODE_INDEX_URL)
    node_release = next((item for item in node_releases if item.get("lts")), None)
    if node_release:
        node_version = node_release["version"]
        releases["node.exe"] = {
            "version": node_version,
            "url": f"https://nodejs.org/dist/{node_version}/node-{node_version}-win-x64.zip",
            "archive": True,
        }

    yt_release = _http_json(TOOL_RELEASE_APIS["yt-dlp.exe"])
    yt_asset = next(
        (asset for asset in yt_release.get("assets", []) if asset.get("name") == "yt-dlp.exe"), None
    )
    if yt_asset:
        releases["yt-dlp.exe"] = {
            "version": yt_release.get("tag_name", "latest"),
            "url": yt_asset["browser_download_url"],
            "archive": False,
        }
    return releases


def _download_file(url, destination, progress_callback):
    request = urllib.request.Request(url, headers={"User-Agent": "Downloader"})
    with urllib.request.urlopen(request, timeout=30) as response, open(destination, "wb") as output:
        total = int(response.headers.get("Content-Length", 0))
        received = 0
        while True:
            chunk = response.read(1024 * 128)
            if not chunk:
                break
            output.write(chunk)
            received += len(chunk)
            progress_callback(received / total if total else 0.0)


def _extract_exe(archive_path, exe_name, destination, temp_folder):
    import zipfile
    with zipfile.ZipFile(archive_path) as archive:
        candidates = [name for name in archive.namelist() if name.lower().endswith("/" + exe_name.lower()) or name.lower() == exe_name.lower()]
        if not candidates:
            raise FileNotFoundError(f"壓縮檔中找不到 {exe_name}")
        extracted = archive.extract(candidates[0], temp_folder)
        shutil.copyfile(extracted, destination)


def _download_tool(tool_name, release, destination, progress_callback):
    import shutil
    folder = os.path.dirname(destination)
    os.makedirs(folder, exist_ok=True)
    temporary = destination + ".download"
    archive_path = temporary + ".zip"
    try:
        if release["archive"]:
            _download_file(release["url"], archive_path, progress_callback)
            _extract_exe(archive_path, tool_name, temporary, folder)
            os.replace(temporary, destination)
        else:
            _download_file(release["url"], temporary, progress_callback)
            os.replace(temporary, destination)
        return True
    finally:
        for path in (temporary, archive_path):
            try:
                if os.path.exists(path):
                    os.remove(path)
            except OSError:
                pass


def _ensure_deno(down_path):
    """確認 Deno 可用；系統沒有時下載官方 Windows x64 版本。"""
    system_deno = shutil.which("deno")
    if system_deno:
        log(f"使用系統 Deno: {system_deno}")
        return system_deno

    deno_path = os.path.join(down_path, TOOLS_BIN_FOLDER, DENO_RELATIVE_PATH)
    deno_folder = os.path.dirname(deno_path)
    if not os.path.isfile(deno_path):
        release = _http_json(DENO_RELEASE_API)
        asset = next(
            (item for item in release.get("assets", [])
             if item.get("name") == "deno-x86_64-pc-windows-msvc.zip"), None
        )
        if not asset:
            raise FileNotFoundError("Deno 官方 Release 找不到 Windows x64 安裝檔")
        _download_tool(
            "deno.exe",
            {"url": asset["browser_download_url"], "archive": True, "version": release.get("tag_name", "latest")},
            deno_path,
            lambda _value: None,
        )
        log(f"Deno 已安裝至 {deno_path}")
    else:
        log(f"使用內建 Deno: {deno_path}")

    os.environ["PATH"] = deno_folder + os.pathsep + os.environ.get("PATH", "")
    return deno_path


def check_tool_updates(down_path, root=None):
    """逐一檢查並一次完成 ffmpeg、Node.js、yt-dlp 的必要更新。"""
    import shutil
    from tkinter import TclError

    bin_path = os.path.join(down_path, TOOLS_BIN_FOLDER)
    os.makedirs(bin_path, exist_ok=True)
    try:
        _ensure_deno(down_path)
    except Exception as error:
        log(f"Deno 檢查或安裝失敗: {error}")
    tool_names = ("ffmpeg.exe", "node.exe", "yt-dlp.exe")
    progress_window = None
    progress = None
    status = None
    if root is not None:
        progress_window = ctk.CTkToplevel(root)
        progress_window.title("檢查下載工具")
        progress_window.geometry("360x125")
        progress_window.resizable(False, False)
        progress_window.attributes("-topmost", True)
        status = ctk.CTkLabel(progress_window, text="正在檢查工具版本…", font=("Arial", 14))
        status.pack(pady=(18, 8))
        progress = ctk.CTkProgressBar(progress_window, width=300, height=12)
        progress.set(0)
        progress.pack(pady=4)
        progress_window.update_idletasks()

    try:
        releases = _latest_tool_releases()
        state_path = os.path.join(down_path, TOOLS_STATE_FILE)
        try:
            with open(state_path, "r", encoding="utf-8") as file:
                state = json.load(file)
            if not isinstance(state, dict):
                state = {}
        except (OSError, json.JSONDecodeError):
            state = {}
        updates = []
        for tool_name in tool_names:
            path = os.path.join(bin_path, TOOL_RELATIVE_PATHS[tool_name])
            local_version = _tool_version(path, ["-version"] if tool_name == "ffmpeg.exe" else ["--version"])
            remote = releases.get(tool_name)
            remote_version_key = f"{tool_name}遠端版本"
            recorded_remote_version = state.get(remote_version_key)
            if not os.path.exists(path) or (
                remote and recorded_remote_version and remote["version"] != recorded_remote_version
            ):
                updates.append((tool_name, remote))
            state[tool_name] = local_version
            if remote:
                state[remote_version_key] = remote["version"]

        for index, (tool_name, release) in enumerate(updates):
            if not release:
                log(f"找不到 {tool_name} 的官方下載資訊")
                continue
            if status:
                status.configure(text=f"正在更新 {tool_name}…")
            base = index / max(len(updates), 1)
            _download_tool(
                tool_name,
                release,
                os.path.join(bin_path, TOOL_RELATIVE_PATHS[tool_name]),
                lambda value: (
                    progress.set(base + value / max(len(updates), 1)),
                    progress_window.update_idletasks(),
                ) if progress else None,
            )
            state[tool_name] = _tool_version(os.path.join(bin_path, TOOL_RELATIVE_PATHS[tool_name]), ["-version"] if tool_name == "ffmpeg.exe" else ["--version"])
            state[f"{tool_name}遠端版本"] = release["version"]
            log(f"{tool_name} 已更新至 {state[tool_name] or release['version']}")

        with open(state_path, "w", encoding="utf-8") as file:
            json.dump(state, file, ensure_ascii=False, indent=4)
        return state
    except Exception as error:
        log(f"工具更新失敗: {error}")
        return {}
    finally:
        if progress_window:
            try:
                progress_window.destroy()
            except TclError:
                pass


def check_for_updates(root, manual=False):
    """主進入點：檢查更新"""
    local_data = load_local_data()
    local_version = local_data.get("版本", "0.0.0")
    
    version_info = check_remote_version()
    if not version_info:
        if manual:
            log("無法連線至更新伺服器")
        return "無法連線至更新伺服器"

    # 特殊版本只在 JSON 缺少欄位時下載一次 Updater.exe，且絕不執行。
    # 欄位一旦存在，後續啟動都跳過下載，避免使用者停留在 3.2 時重複下載。
    if (
        local_version == SPECIAL_UPDATER_VERSION
        and "Updater.exe版本" not in local_data
    ):
        log(f"偵測到 {SPECIAL_UPDATER_VERSION} 且 JSON 缺少 Updater.exe版本，直接下載但不執行")
        if download_updater_only(version_info, get_app_path(), local_data):
            return "已下載 Updater.exe（未執行）"
        return "下載 Updater.exe 失敗"

    if local_version == SPECIAL_UPDATER_VERSION and "Updater.exe版本" in local_data:
        log("JSON 已有 Updater.exe版本，跳過 Updater.exe 下載與執行")

    latest_version = version_info["latest_version"]
    
    if latest_version != local_version:
        # 有新版本時彈出對話框
        show_update_dialog(root, version_info)
   