import os
import customtkinter as ctk
from tkinter import filedialog, messagebox
from pdf2docx import Converter
from docx2pdf import convert
import threading
# PDF 轉 Word 函數
def pdf_to_word(in_path, out_path, wordstart_button):
    if os.path.isdir(in_path):
        for root, _, files in os.walk(in_path):
            for file in files:
                if file.lower().endswith(".pdf"):
                    in_file = os.path.join(root, file)
                    out_file = os.path.join(out_path, file.replace(".pdf", "_converted.docx"))
                    single_pdf_to_word(in_file, out_file)
    elif in_path.lower().endswith(".pdf"):
        out_file = os.path.join(out_path, os.path.basename(in_path).replace(".pdf", "_converted.docx"))
        single_pdf_to_word(in_path, out_file)
        wordstart_button.configure(state=ctk.NORMAL)
    else:
        messagebox.showerror("錯誤", "選擇的不是 PDF 文件！")

def single_pdf_to_word(in_file, out_file):
    cv = Converter(in_file)
    try:
        cv.convert(out_file, start=0, end=None) # type: ignore
        messagebox.showinfo("成功", f"PDF 成功轉換為 Word：{out_file}")
    except Exception as e:
        messagebox.showerror("錯誤", f"轉換過程中發生錯誤：{e}")
    finally:
        cv.close()

# Word 轉 PDF 函數
def word_to_pdf(in_path, out_path, wordstart_button):
    if os.path.isdir(in_path):
        for root, _, files in os.walk(in_path):
            for file in files:
                if file.lower().endswith(".docx"):
                    in_file = os.path.join(root, file)
                    out_file = os.path.join(out_path, file.replace(".docx", "_converted.pdf"))
                    single_word_to_pdf(in_file, out_file)
    elif in_path.lower().endswith(".docx"):
        out_file = os.path.join(out_path, os.path.basename(in_path).replace(".docx", "_converted.pdf"))
        single_word_to_pdf(in_path, out_file)
        wordstart_button.configure(state=ctk.NORMAL)
    else:
        messagebox.showerror("錯誤", "選擇的不是 Word 文件！")

def single_word_to_pdf(in_file, out_file):
    try:
        convert(in_file, out_file)
        messagebox.showinfo("成功", f"Word 成功轉換為 PDF：{out_file}")
    except Exception as e:
        messagebox.showerror("錯誤", f"轉換過程中發生錯誤：{e}")

# 瀏覽檔案按鈕動作
def browse_file(wordlabel, wordstart_button, first_open):
    global file_path
    
    if first_open != 1:
        first_open = 1
        print(first_open)
        return
    else:
        file_path = filedialog.askopenfilename(
            title="選擇檔案",
            filetypes=[("所有支持檔案", "*.pdf *.docx"), ("PDF 檔案", "*.pdf"), ("Word 檔案", "*.docx")]
        )
        if file_path:
            wordlabel.configure(text=f"選擇的檔案：{file_path}")
            wordstart_button.configure(state=ctk.NORMAL)

# 瀏覽資料夾按鈕動作
def browse_folder(wordlabel,wordstart_button, first_open):
    global folder_path
    
    if first_open != 1:
        first_open = 1
        print(first_open)
        return
    else:
        folder_path = filedialog.askdirectory(title="選擇資料夾")
        if folder_path:
            wordlabel.configure(text=f"選擇的資料夾：{folder_path}")
            wordstart_button.configure(state=ctk.NORMAL)

# 開始按鈕的功能
def start_conversion(wordlabel, wordstart_button, first_open):
    wordstart_button.configure(state=ctk.DISABLED)  # 避免重複點擊
    if first_open != 1:
        first_open = 1
        print(first_open)
        return
    else:
        if not file_path:
            messagebox.showerror("錯誤", "請先選擇檔案！")
            return
        if file_path.endswith(".pdf"):
    out_file = os.path.dirname(file_path)
    threading.Thread(target=lambda: pdf_to_word(file_path, out_file, wordstart_button), daemon=True).start()
    wordlabel.configure(text="轉換中")
        elif file_path.endswith(".docx"):
    out_file = os.path.dirname(file_path)
    threading.Thread(target=lambda: word_to_pdf(file_path, out_file, wordstart_button), daemon=True).start()
    wordlabel.configure(text="轉換中")
        else:

            messagebox.showerror("錯誤", "不支援的檔案類型！")
