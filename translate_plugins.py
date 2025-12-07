# translate_plugins.py
import os
import re
import json
import time
import requests
import zipfile
import io
import hashlib

# ----------------------------
# 配置
# ----------------------------
MAIN_ZIP_URL = "https://dl.awa.cool/hahappify/xlcj/qun.zip"
TEMP_DIR = "./temp"           # 臨時下載與解壓
OUTPUT_DIR_HANS = "./Hans"    # 原始簡體 ZIP
OUTPUT_DIR_HANT = "./Hant"    # 繁體 ZIP

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
    ensure_dir(OUTPUT_DIR_HANT)

    dict_string = load_json(DICT_STRING_FILE)
    dict_url = load_json(DICT_URL_FILE)

    # ----------------------------
    # 下載主 qun.zip
    # ----------------------------
    main_zip_content = download_file(MAIN_ZIP_URL)
    temp_main_dir = os.path.join(TEMP_DIR, "qun")
    extract_zip(main_zip_content, temp_main_dir)

    # ----------------------------
    # 找出內部 URL
    # ----------------------------
    url_set = set()
    url_pattern = re.compile(r"https://dl\.awa\.cool/[^\s\"']+")
    for root, _, files in os.walk(temp_main_dir):
        for f in files:
            path = os.path.join(root, f)
            try:
                with open(path, "r", encoding="utf8") as file:
                    content = file.read()
                for match in url_pattern.findall(content):
                    if match != "https://dl.awa.cool/" and match.startswith("https://dl.awa.cool/hahappify/nro/"):
                        url_set.add(match)
                        if url not in dict_url:
                            dict_url[url] = url
            except:
                continue

    # ----------------------------
    # 下載所有 URL 並繁化
    # ----------------------------
    for url in url_set:
        print(f"\nProcessing URL: {url}")
        url_path = url.replace("https://dl.awa.cool/", "")
        local_path_hans = os.path.join(OUTPUT_DIR_HANS, url_path)
        ensure_dir(os.path.dirname(local_path_hans))

        etag_file = local_path_hans + ".etag"
        etag_local = load_etag(etag_file)

        # 判斷是否需要下載
        need_download = True
        etag_remote = None

        try:
            head_resp = requests.head(url, timeout=10)
            etag_remote = head_resp.headers.get("ETag")
            if etag_remote:
                etag_remote = etag_remote.strip('"')  # 去掉雙引號
                if etag_remote == etag_local:
                    print("No update, skipping download")
                    need_download = False
        except Exception as e:
            print(f"HEAD request failed: {e}, will download")
        
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

        # 解壓 ZIP
        temp_dir = os.path.join(TEMP_DIR, hashlib.md5(url.encode()).hexdigest())
        extract_zip(content, temp_dir)

        # 處理每個文字檔
        for root, _, files in os.walk(temp_dir):
            for f in files:
                path = os.path.join(root, f)
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

        # 保存 dict_url.json
        if url not in dict_url:
            dict_url[url] = url
        save_json(DICT_STRING_FILE, dict_string)
        save_json(DICT_URL_FILE, dict_url)

        # 壓縮回 ZIP (繁體)
        zip_output_path_hant = os.path.join(OUTPUT_DIR_HANT, url_path)
        zip_dir(temp_dir, zip_output_path_hant)
        print(f"Saved translated ZIP: {zip_output_path_hant}")

if __name__ == "__main__":
    main()
