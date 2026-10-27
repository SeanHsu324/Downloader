<div align="center">

# Downloader

**免費、無次數限制的 YouTube 影片下載工具**

支援 Shorts、單一影片、播放清單與整個頻道

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Platform](https://img.shields.io/badge/platform-Windows%2010%2B-0078D6.svg)
![Python](https://img.shields.io/badge/python-3.12.9-3776AB.svg)

[軟體教學](https://sites.google.com/view/yt-to-dowload/%E6%95%99%E5%AD%B8) ·
[官方網站（Beta）](https://seanhsu324.github.io/Downloader/) ·
[下載最新版本](https://github.com/SeanHsu324/Downloader/releases)

</div>

---

## 目錄

- [簡介](#簡介)
- [功能特色](#功能特色)
- [系統需求](#系統需求)
- [安裝方式](#安裝方式)
  - [Windows 安裝程式（推薦）](#windows-安裝程式推薦)
  - [從原始碼執行](#從原始碼執行)
- [安全性與隱私](#安全性與隱私)
- [免責聲明](#免責聲明)
- [程式碼分享](#程式碼分享)
- [開發與貢獻](#開發與貢獻)
- [授權](#授權)

---

## 簡介

Downloader 是一套介面簡潔、操作直覺的影片下載工具，適用於單支影片到整個頻道的各種下載情境，可進行大量下載。

> **注意**
> 短時間內連續下載 100 部以上影片，可能會被平台暫時限制。此為平台端的行為，通常於隔天即可恢復。

---

## 功能特色

| 特色 | 說明 |
| --- | --- |
| 完全免費 | 沒有下載次數限制，無須付費或註冊 |
| 多種下載模式 | 支援 Shorts、單一影片、播放清單、整個頻道 |
| 簡潔介面 | 沒有繁雜設定，開啟即可使用 |
| 自訂主題 | 可自由更換喜好的顏色主題 |
| 本機執行 | 所有下載與處理皆在本機完成 |

---

## 系統需求

| 項目 | 需求 |
| --- | --- |
| 作業系統 | Windows 10 或以上 |
| Python | 3.12.9（僅限從原始碼執行時需要） |

---

## 安裝方式

### Windows 安裝程式（推薦）

1. 前往下列任一位置，下載 `DownloaderSetup.exe`：

   | 來源 | 連結 |
   | --- | --- |
   | 新網站（Beta） | https://seanhsu324.github.io/Downloader/ |
   | 舊網站 | https://sites.google.com/view/yt-to-dowload |
   | GitHub Releases | https://github.com/SeanHsu324/Downloader/releases |

2. 將檔案解壓縮至任意資料夾。
3. 雙擊 `DownloaderSetup.exe`，安裝程式將自動下載並安裝主程式。

完整的操作說明請參閱 [軟體教學](https://sites.google.com/view/yt-to-dowload/%E6%95%99%E5%AD%B8)。

---

### 從原始碼執行

> **注意**
> 此方式無法自動更新，需自行手動更新 `.py` 檔案。

#### 1. 安裝必要工具

| 工具 | 說明 | 下載連結 |
| --- | --- | --- |
| Visual Studio Code | 程式碼編輯器 | https://code.visualstudio.com/download |
| Python 3.12.9 | 執行環境 | https://www.python.org/downloads/windows/ |
| Git | 版本控制工具 | https://git-scm.com/downloads |
| Visual Studio Build Tools | 編譯 `.pyd` 所需 | https://visualstudio.microsoft.com/zh-hant/visual-cpp-build-tools/ |

安裝 Visual Studio Build Tools 時，請勾選「**使用 C++ 的桌面開發**（Desktop development with C++）」，安裝完成後重新啟動 Visual Studio Code。

#### 2. 準備外部相依檔案

| 檔案 | 放置位置 | 下載連結 |
| --- | --- | --- |
| Node.js | `Downloader/nodsjs/` | https://nodejs.org/zh-tw/download |
| FFmpeg | `Downloader/bin/ffmpeg/` | https://github.com/SeanHsu324/FFmpeg/releases/download/v1.00/ffmpeg.rar |

Node.js 需將 `node.exe` 加入系統環境變數，可參考
[教學影片](https://drive.google.com/file/d/1DIcaG8Bd0rJ-_edpc0w6HeFnIPU4SUjs/view?usp=drive_link)。

#### 3. 取得原始碼並建立環境

於 CMD 或 VS Code 終端機中執行：

```bash
git clone https://github.com/SeanHsu324/Downloader.git
cd Downloader

# 建立虛擬環境
python -m venv venv

# 允許執行虛擬環境（PowerShell）
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# 啟動虛擬環境
.\venv\Scripts\Activate

# 更新 pip 並安裝相依套件
pip install --upgrade pip
pip install -r requirements.txt

# 編譯 .pyd
python py2pyd.py build_ext
```

#### 4. 建立 cookie.txt

在與 `main.py` 相同的資料夾中建立 `cookie.txt`。即使為空白檔案，程式仍可正常執行。

```bash
# Linux / macOS
touch cookie.txt

# Windows CMD
type nul > cookie.txt

# Windows PowerShell
New-Item cookie.txt -ItemType File -Force
```

> **警告**
> 請勿將 `cookie.txt` 分享給任何人。本程式不會上傳或傳送 cookie，所有行為皆於本機執行。

#### 5. 建立更新資料夾

在 `C:\` 建立資料夾 `C:\downloadsitt`，並於其中建立 `renew.json`。此步驟僅用於避免錯誤訊息，實際上不影響功能。

```json
{
    "檔案名稱": "Downloader.exe",
    "版本": "(自行填寫版本)",
    "下載位置": "(main.py 所在資料夾路徑，例如：C:\\Downloader)",
    "最後更新時間": ""
}
```

#### 6. 執行程式

```bash
python main.py
```

---

## 安全性與隱私

### 程式碼簽章

執行 `.exe` 時，Windows 可能顯示安全性警告。這是正常現象，原因在於本專案尚未進行程式碼簽章（Code Signing）。程式碼簽章需支付額外費用，為了讓使用者能夠免費下載與使用本工具，目前未辦理簽章，因此 Windows 可能將其標示為未知來源。

本專案為開源專案，所有程式碼皆公開於 GitHub，歡迎自行檢視。若仍有安全性疑慮，也可以自行從原始碼打包與執行。

### 隱私與資料安全

- 本程式不會蒐集、上傳或傳送任何使用者資料。
- 所有下載與處理行為皆於本機端執行。
- `cookie.txt` 僅供本地使用，請勿分享給任何人。

---

## 免責聲明

本專案僅供技術交流、學術研究及個人學習用途。

- **用途限制**：請勿將本工具用於下載受版權保護、未經授權的內容，或進行任何商業用途。
- **服務條款**：使用者應自行確保使用行為符合 YouTube 服務條款以及所在地區的相關法律規定。
- **法律責任**：本專案開發者對於使用者因不當使用本工具而導致的任何法律問題、帳號封禁或損失，概不承擔任何責任。

---

## 程式碼分享

以下為專案中實用的程式碼片段，歡迎自由取用。

### HEX 顏色變暗（按鈕 hover 效果）

```python
import colorsys

def darken_color(color: str, percent: float):
    color = color.lstrip("#")
    r, g, b = int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)

    h, l, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
    l = max(0, l - (percent / 100))

    r, g, b = colorsys.hls_to_rgb(h, l, s)
    return f"#{int(r*255):02X}{int(g*255):02X}{int(b*255):02X}"
```

使用方式：

```python
darken_color("#80ff42", 20)
```

### 判斷顏色是否為淺色（文字自動切換黑 / 白）

```python
def is_light_color(hex_color):
    hex_color = hex_color.lstrip('#')
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    brightness = (r * 299 + g * 587 + b * 114) / 1000
    return brightness > 127
```

---

## 開發與貢獻

作者：[SeanHsu324](https://github.com/SeanHsu324)

歡迎透過 Issue、Pull Request 或 Fork 參與本專案。

---

## 授權

本專案採用 [MIT License](LICENSE) 授權，你可以自由使用、修改與散布此程式碼。

Copyright (c) 2026 [SeanHsu324](https://github.com/SeanHsu324)
