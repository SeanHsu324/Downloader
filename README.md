# Downloader

## 📌 簡介

> 下載 YouTube 影片工具
支援 Shorts、單一影片、播放清單、整個頻道下載
可大量下載，但短時間內下載 100 部以上影片可能會被 YouTube 暫時限制，通常隔天即可恢復（屬於 YouTube 平台行為）




---

## 📂 目錄

- [功能特色](#✨ 功能特色)

- [系統需求](#💻 系統需求)

- [安裝方式](#🛠️ 安裝方式)

- [軟體教學和使用方法](https://sites.google.com/view/yt-to-dowload/%E6%95%99%E5%AD%B8)

- [程式碼分享](#💡 程式碼分享)

- [開發與貢獻](#👨‍💻 開發與貢獻)

- [授權](#📄 授權)



---

## ✨ 功能特色

1️⃣ 免費！免費！免費！ 沒有下載次數限制

2️⃣ 支援下載：

- YouTube Shorts

- 單一影片

- 播放清單

- 整個頻道


3️⃣ 介面簡單，沒有複雜設定

4️⃣ 可自由更換喜歡的顏色主題



---

## 💻 系統需求

- Windows 10 以上

- Python 3.13（原始碼執行時）



---

## 🛠️ 安裝方式

### 🪟 Windows（推薦）

#### 🔐 安全性說明

> 本程式（.exe）在執行時，Windows 可能會顯示安全性警告。

這是正常現象，原因在於本專案尚未進行「程式碼簽章（Code Signing）」。

程式碼簽章需支付額外費用，為了能夠讓使用者免費下載與使用本工具，目前未辦理簽章，因此 Windows 可能會顯示未知來源的警告提示。

本專案為開源專案，所有程式碼皆公開於 GitHub，可自行檢視。

#### 🔒 隱私與資料安全

本程式不會蒐集、上傳或傳送任何使用者資料

所有下載與處理行為皆於本機端執行

cookie.txt 僅供本地使用，請勿分享給任何人


若您對安全性仍有疑慮，可自行從原始碼進行打包與執行。


---

#### 📥 安裝步驟

1. 前往

https://sites.google.com/view/yt-to-dowload

或 https://github.com/SeanHsu324/Setup
下載 DownloaderSetup.exe



2. 解壓縮至任意資料夾


3. 雙擊 DownloaderSetup.exe，開始自動下載並安裝主程式




---

## 🐍 Python 原始碼版本

> ⚠️ 此方式 無法自動更新，需自行手動更新 .py 檔案


```
git clone https://github.com/SeanHsu324/Downloader.git
cd Downloader

# 建立虛擬環境
python -m venv venv

# 允許執行虛擬環境（PowerShell）
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# 啟動虛擬環境
.\venv\Scripts\Activate

# 更新 pip 並安裝依賴
pip install --upgrade pip
pip install pyinstaller
pip install -r requirements.txt
```

---

#### 🍪 建立 cookie.txt（與 main.py 放在同一資料夾）

⚠️ 請勿將 cookie.txt 分享給任何人
⚠️ 本程式不會上傳或傳送 cookie，所有行為皆於本機執行
⚠️ 即使為空白檔案，程式仍可正常執行

建立空白檔案：
```
# Linux / macOS
touch cookie.txt

# Windows CMD
type nul > cookie.txt

# Windows PowerShell
New-Item cookie.txt -ItemType File -Force
```

---

#### 🎬 FFmpeg 下載

請下載 FFmpeg 並與 main.py 放在同一資料夾：

> https://github.com/SeanHsu324/FFmpeg/releases/download/v1.00/ffmpeg.rar




---

#### 📁 建立更新資料夾（原始碼模式）

在 C:\ 建立資料夾：

C:\downloadsitt

並建立 renew.json（避免錯誤，實際上不影響功能）：
```

{
    "檔案名稱": "Downloader.exe",
    "版本": "(自行填寫版本)",
    "下載位置": "(main.py 所在資料夾路徑)"
}

```
---

## 📖 軟體教學和使用方法

👉 https://sites.google.com/view/yt-to-dowload/%E6%95%99%E5%AD%B8


---

## 💡 程式碼分享

#### 🎨 HEX 顏色變暗（按鈕 hover 效果）
```
import colorsys

def darken_color(color: str, percent: float):
    color = color.lstrip("#")
    r, g, b = int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)

    h, l, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
    l = max(0, l - (percent / 100))

    r, g, b = colorsys.hls_to_rgb(h, l, s)
    return f"#{int(r*255):02X}{int(g*255):02X}{int(b*255):02X}"

使用方式：
```
darken_color("#80ff42", 20)

```
---

#### 🌗 判斷顏色是否為淺色（文字自動變黑 / 白）
```
def is_light_color(hex_color):
    hex_color = hex_color.lstrip('#')
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    brightness = (r * 299 + g * 587 + b * 114) / 1000
    return brightness > 127

```
---

## 👨‍💻 開發與貢獻
>
作者：SeanHsu324

歡迎 Issue / PR / Fork



---

## 📄 授權

本專案採用 MIT License 授權。
你可以自由使用、修改與散布此程式碼，但必須保留原作者資訊。

© 2025 SeanHsu324
