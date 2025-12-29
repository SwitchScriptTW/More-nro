# translate_plugins.py
import os
import re
import json
import time
import requests
import zipfile
import io
import hashlib
import subprocess
import shutil

# ----------------------------
# 配置
# ----------------------------
MAIN_ZIP_URL = "https://dl.awa.cool/hahappify/xlcj/qun.zip"
REMOTE_DICT_U_URL = "https://raw.githubusercontent.com/SwitchScriptTW/More/refs/heads/main/dict_url.json"
# REMOTE_DICT_S_URL = "https://raw.githubusercontent.com/SwitchScriptTW/More/refs/heads/main/dict_string.json"
TEMP_DIR = "./temp"           # 臨時下載與解壓
OUTPUT_DIR_HANS = "./Hans"    # 原始簡體 ZIP
# OUTPUT_DIR_HANT = "./Hant"    # 繁體 ZIP
RELEASES_DIR = "./releases"      # 翻譯後 ZIP 檔案 (用於 Releases)

DICT_STRING_FILE = "./dict_string.json"
DICT_URL_FILE = "./dict_url.json"

# ----------------------------
# 輔助函數
# ----------------------------
def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)

def file_hash(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()

def download_file(url):
    print(f"Downloading {url}")
    time.sleep(30)
    r = requests.get(url)
    r.raise_for_status()
    return r.content

def zhconvert(text, lang="Taiwan"):
    # 詞語模組
    modules = '{"Computer":1,"Smooth":1,"Unit":1,"ProperNoun":1,"QuotationMark":1,"InternetSlang":1,"Repeat":1,"RepeatAutoFix":1,"GanToZuo":0}'
    # 保護字詞
    userProtectReplace = "用戶"
    # 轉換前替換
    userPreReplace = "插件=外掛"
    # 轉換後替換
    userPostReplace = "獲取=取得\n添加=新增\n下劃線=底線\n相冊=相簿"
    args = {
        "text": text,
        "converter": lang,
        "modules": modules,
        "userPreReplace": userPreReplace,
        "userPostReplace": userPostReplace,
        "userProtectReplace": userProtectReplace
    }
    url = "https://api.zhconvert.org/convert"
    response = requests.post(url, data=args, headers={'User-Agent': 'SwitchScriptTW_Bot/1.0 (+https://github.com/david082321)'}).content.decode("utf8")
    try:
        code = json.loads(response)["code"]
        if code == 0:
            return json.loads(response)["data"]["text"]
        else:
            print("Error:", response)
            return text
    except:
        print("Error:", response)
        return text

def extract_zip(content, extract_to):
    ensure_dir(extract_to)
    z = zipfile.ZipFile(io.BytesIO(content))
    z.extractall(extract_to)
    return [f.filename for f in z.infolist() if not f.is_dir()]

def zip_dir(folder_path, zip_path):
    ensure_dir(os.path.dirname(zip_path))
    with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for root, _, files in os.walk(folder_path):
            for f in files:
                fullpath = os.path.join(root, f)
                arcname = os.path.relpath(fullpath, folder_path)
                z.write(fullpath, arcname)

def load_json(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf8") as f:
            return json.load(f)
    return {}

def save_json(path, obj):
    ensure_dir(os.path.dirname(path))
    with open(path, "w", encoding="utf8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

def line_contains_chinese(line):
    return re.search(r"[\u4e00-\u9fa5]", line) is not None

def load_etag(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf8") as f:
            return f.read().strip()
    return None

def save_etag(path, etag):
    ensure_dir(os.path.dirname(path))
    with open(path, "w", encoding="utf8") as f:
        f.write(etag)

# ----------------------------
# 主程式
# ----------------------------
def main():
    ensure_dir(TEMP_DIR)
    ensure_dir(OUTPUT_DIR_HANS)
    # ensure_dir(OUTPUT_DIR_HANT)
    ensure_dir(RELEASES_DIR)
    ensure_dir("./translation")
    ensure_dir("./dict")

    dict_string = load_json(DICT_STRING_FILE)
    dict_url = load_json(DICT_URL_FILE)
    # 從 GitHub 取得最新 dict_url.json
    try:
        print("Fetching remote dict_url.json ...")
        r = requests.get(REMOTE_DICT_U_URL, timeout=10)
        r.raise_for_status()
        dict_url_remote = r.json()
        dict_url.update(dict_url_remote)   # 用遠端更新本地 dict_url
        print("Loaded remote dict_url.json")
    except Exception as e:
        print(f"Failed to fetch remote dict_url.json: {e}")

    black_url = []
    black_zip = [
        "emuiibo.zip", # 已有繁體
        "ftpsrv.zip", # 無簡體翻譯
        "KeyX.zip", # 已有繁體
        "dvr-patches.zip", # 不需要翻譯
        "DBI.zip", # 不使用，改用 ssky 的版本
        "Breeze.zip", # 無簡體翻譯
        "AtmoXL-Titel-Installer.zip", # 已有繁體
        "BBI.zip", # 無簡體翻譯

        "wiliwili.zip", # 已有繁體
        "Goldleaf.zip", # 已有繁體
        "aio-switch-updater.zip", # 已有繁體
        "battery_desync_fix.zip", # 無簡體翻譯
        "SwitchThemesNX.zip", # 不處理，字體問題
        "PPSSPP.zip", # 已有繁體
        "ppsspp.zip", # 已有繁體
        "Awoo-Installer.zip", # 已有繁體
        "Switchfin.zip", # 已有繁體

        "NX-Activity-Log.zip", # 已有繁體，但需要修正
        "NX-Mod-Manager.zip",  # 已有繁體，但需要修正
    ]
    balck_file = [
        "Fizeau.nro",
        "DClight.ovl",
        "SysDVR.nro",
    ]

    # ----------------------------
    # 找出內部 URL
    # ----------------------------
    url_set = set()
    for k in dict_url.keys():
        if k.startswith("https://dl.awa.cool/hahappify/nro/") and k not in black_url:
            url_set.add(k)

    # ----------------------------
    # 下載所有 URL 並繁化
    # ----------------------------
    for url in url_set:
        print(f"\n讀取網址: {url}")
        url_path = url.replace("https://dl.awa.cool/", "")
        local_path_hans = os.path.join(OUTPUT_DIR_HANS, url_path)
        ensure_dir(os.path.dirname(local_path_hans))

        etag_file = local_path_hans + ".etag"
        etag_local = load_etag(etag_file)

        # 判斷是否需要下載
        need_download = True
        etag_remote = None

        need_download = False
        # try:
        #     head_resp = requests.head(url, timeout=15)
        #     etag_remote = head_resp.headers.get("ETag")
        #     if etag_remote:
        #         etag_remote = etag_remote.strip('"')  # 去掉雙引號
        #         if etag_remote == etag_local:
        #             print("無更新，跳過下載")
        #             time.sleep(30) # 避免過快重複請求
        #             need_download = False
        # except Exception as e:
        #     print(f"HEAD request failed: {e}, will download")
        
        # 下載 ZIP
        if need_download:
            try:
                content = download_file(url)
                # 儲存 ETag
                if etag_remote:
                    save_etag(etag_file, etag_remote)
            except Exception as e:
                print(f"Download failed: {e}")
                continue
            # 保存原始簡體到 Hans
            with open(local_path_hans, "wb") as f:
                f.write(content)
            print(f"Saved original ZIP: {local_path_hans}")
        else:
            with open(local_path_hans, "rb") as f:
                content = f.read()

        # 取得 ZIP 檔案名稱 (例如 DBI.zip)
        zip_filename = os.path.basename(local_path_hans) 

        # 排除不需處理的 zip
        if zip_filename in black_zip:
            # zip 複製到 releases
            release_zip_path = os.path.join(RELEASES_DIR, url_path) # ./releases/hahappify/nro/DBI.zip
            ensure_dir(os.path.dirname(release_zip_path))
            shutil.copy2(local_path_hans, release_zip_path)
            print(f"✅ 儲存到 {release_zip_path}")
            continue

        # 設定 temp 資料夾路徑：
        # 這裡我們先解壓到一個臨時目錄，然後再移動到您指定的結構。
        temp_extract_dir = os.path.join(TEMP_DIR, zip_filename + "_extract") # 使用一個臨時解壓目錄
        extract_zip(content, temp_extract_dir)

        # 根據您的新結構，定義最終的 temp 路徑
        # url_path: hahappify/nro/DBI.zip
        final_temp_path = os.path.join(TEMP_DIR, url_path + "/")
        
        # 將解壓內容移動到 final_temp_path
        # 假設 ZIP 內容沒有頂層資料夾
        if os.path.exists(final_temp_path):
            shutil.rmtree(final_temp_path)
        shutil.move(temp_extract_dir, final_temp_path) # 將解壓內容移至新結構路徑
        
        # 設定後續處理的目錄為 final_temp_path
        temp_dir_for_processing = final_temp_path

        # 處理每個文字檔
        for root, _, files in os.walk(temp_dir_for_processing):
            for f in files:
                path = os.path.join(root, f)
                if f.lower() == "zh-hans.json":
                    continue  # 跳過簡體字典檔
                try:
                    with open(path, "r", encoding="utf8") as file:
                        lines = file.readlines()
                    new_lines = []
                    for line in lines:
                        # 替換 URL
                        def replace_url(m):
                            url = m.group(0)
                            if url not in dict_url:
                                dict_url[url] = url  # 預設 value 等於原 URL
                            return dict_url[url]        
                        line = re.sub(r"https://dl\.awa\.cool/[^\s\"']+", replace_url, line)

                        # 繁化中文
                        if line_contains_chinese(line):
                            if line in dict_string:
                                new_line = dict_string[line]
                            else:
                                new_line = zhconvert(line)
                                dict_string[line] = new_line
                                time.sleep(1)
                            new_lines.append(new_line)
                        else:
                            new_lines.append(line)
                    with open(path, "w", encoding="utf8") as file:
                        file.writelines(new_lines)
                except:
                    continue

        # ----------------------------
        # 自動翻譯 *.nro / *.ovl
        # ----------------------------
        for root, _, files in os.walk(temp_dir_for_processing):
            for f in files:
                path = os.path.join(root, f)
                if path.lower().endswith((".nro", ".ovl")) and f not in balck_file:
                    print(f"🔄 正在翻譯 {f} ...")
                    subprocess.run([
                        "python", "translate_nro.py", path
                    ], check=True)

        # 保存 dict_url.json
        if url not in dict_url:
            dict_url[url] = url
        save_json(DICT_STRING_FILE, dict_string)
        save_json(DICT_URL_FILE, dict_url)

        # ----------------------------
        # 將處理後的檔案從 Temp 複製/移動到 Hant
        # ----------------------------
        # hant_folder_path = os.path.join(OUTPUT_DIR_HANT, url_path + "/") # ./Hant/hahappify/nro/DBI.zip/
        # ensure_dir(os.path.dirname(hant_folder_path))
        # if os.path.exists(hant_folder_path):
        #     shutil.rmtree(hant_folder_path) # 先刪除舊的 Hant 資料夾
        # shutil.copytree(temp_dir_for_processing, hant_folder_path) # 複製到 Hant
        # print(f"✅ Copied translated files to Hant folder: {hant_folder_path}")

        # ----------------------------
        # 壓縮回 ZIP (Releases)
        # ----------------------------
        # zip_dir(folder_path, zip_path)
        release_zip_path = os.path.join(RELEASES_DIR, url_path) # ./releases/hahappify/nro/DBI.zip
        zip_dir(temp_dir_for_processing, release_zip_path) # <--- 從處理後的 temp 資料夾壓縮
        print(f"📦 儲存到 {release_zip_path}")

        # ----------------------------
        # 清理臨時資料夾
        # ----------------------------
        shutil.rmtree(temp_dir_for_processing)

if __name__ == "__main__":
    main()
