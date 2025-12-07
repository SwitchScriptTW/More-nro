# -*- coding: utf-8 -*-
# Auther: david082321
# Co-Auther: ChatGPT
# Date: 2025-12-06
# Version: 1.0.0

import os
import re
import json

###############################################
# 工具區
###############################################

def extract_strings(nro_path):
    """從 NRO 讀取可打印字串 (UTF-8/ASCII)"""
    strings = {}
    with open(nro_path, "rb") as f:
        data = f.read()
    pattern = re.compile(
        b'(?:[\x20-\x7E]|[\xC2-\xF4][\x80-\xBF]+){2,}'
    )
    for match in pattern.finditer(data):
        offset = match.start()
        text = match.group().decode("utf-8", errors="ignore")
        strings[offset] = text
    return strings


def save_translation_file(strings, out_path):
    # """輸出 translation.txt 到資料夾"""
    # with open(out_path, "w", encoding="utf-8") as f:
    #     for offset, text in strings.items():
    #         f.write(f"{offset}:{text}\n")
    """輸出 translation.txt 到資料夾，略過不符合規則的字串"""
    skip_pattern = re.compile(r'[@{}\[\]\(\)#!\*`,\'^]+\|\<')  # 略過的奇怪字元

    with open(out_path, "w", encoding="utf-8") as f:
        for offset, text in strings.items():
            # if len(text.strip()) <= 3:
            #     continue

            # 包含奇怪字元略過
            if skip_pattern.search(text):
                # continue
                # 3 個字元內略過
                if len(text.strip()) <= 3:
                    continue
            f.write(f"{offset}:{text}\n")


def load_translation_file(path):
    """讀取 translation.txt"""
    trans = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if ":" not in line:
                continue
            offset, val = line.rstrip("\n").split(":", 1)
            trans[int(offset)] = val
    return trans


def apply_translation(nro_path, translations, out_path):
    """將翻譯套用到 NRO，支援長度超過截斷或推移"""
    with open(nro_path, "rb") as f:
        data = bytearray(f.read())

    offsets_sorted = sorted(translations.keys())
    shift = 0  # 累計推移量

    for offset in offsets_sorted:
        orig_offset = offset
        offset += shift  # 調整 offset

        new_text = translations[orig_offset]
        new_bytes = new_text.encode("utf-8")

        # 使用原始字串長度，而非遇到 \x00 停止
        old_text = translations.get(orig_offset, None)
        if old_text is None:
            # 若 translations 裡不存在原字串，就從 data 裡讀 1~255 bytes 假設長度
            old_len = 1
            while offset + old_len < len(data) and data[offset + old_len] != 0:
                old_len += 1
            old_bytes = data[offset:offset + old_len]
        else:
            old_bytes = translations[orig_offset].encode("utf-8")

        # 如果 new_bytes 長度超過原本
        if len(new_bytes) > len(old_bytes):
            print(f"\n⚠️ 長度超過原文（原:{len(old_bytes)} / 新:{len(new_bytes)}），offset {offset}")
            choice = input("是否截斷寫入？(Y=截斷, N=推移資料) [預設 Y]: ").strip().lower()

            if choice == "" or choice == "y":
                # 截斷寫入
                new_bytes = new_bytes[:len(old_bytes)]
                data[offset:offset + len(new_bytes)] = new_bytes
                continue
            else:
                # 推移資料模式
                diff = len(new_bytes) - len(old_bytes)
                data[offset + len(old_bytes):] = b"\x00" * diff + data[offset + len(old_bytes):]
                data[offset:offset + len(new_bytes)] = new_bytes
                shift += diff  # 累計偏移
                continue

        # 正常覆蓋（小於原長補零）
        if len(new_bytes) < len(old_bytes):
            new_bytes += b"\x00" * (len(old_bytes) - len(new_bytes))
        data[offset:offset + len(new_bytes)] = new_bytes

    with open(out_path, "wb") as f:
        f.write(data)


###############################################
# 字典機制
###############################################

def load_dict(dict_path):
    if os.path.isfile(dict_path):
        with open(dict_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_dict(dict_path, new_pairs):
    """新增/覆蓋詞典，不清空舊資料"""
    old = load_dict(dict_path)
    old.update(new_pairs)
    with open(dict_path, "w", encoding="utf-8") as f:
        json.dump(old, f, ensure_ascii=False, indent=2)


###############################################
# 主流程
###############################################

def main():
    script_folder = os.path.dirname(os.path.abspath(__file__))  # A 資料夾

    print("請將 NRO / OVL 檔案拖曳到此視窗，按 Enter:")
    nro_path = input().strip('"').strip()

    if not os.path.isfile(nro_path):
        print("❌ 檔案不存在！")
        return

    ext = os.path.splitext(nro_path)[1].lower()
    if ext not in [".nro", ".ovl"]:
        print("❌ 只能處理 .nro 或 .ovl！")
        return

    nro_folder = os.path.dirname(os.path.abspath(nro_path))     # B 資料夾
    base = os.path.splitext(os.path.basename(nro_path))[0]
    translation_txt = os.path.join(nro_folder, f"{base}_translation.txt")
    dict_path = os.path.join(script_folder, f"{base}_dict.json")

    print("🔍 正在讀取字串...")
    strings = extract_strings(nro_path)

    ###############################################
    # 若字典存在 → 問要不要自動套用
    ###############################################
    dict_data = load_dict(dict_path)
    use_dict = False

    if dict_data:
        print(f"偵測到字典 {base}_dict.json")
        print("是否使用字典自動替換？(Y/N)：")
        ans = input().strip().lower()
        use_dict = (ans == "y")

    ###############################################
    # 產生 translation.txt（必做）
    ###############################################
    merged_strings = strings.copy()

    # 若使用字典 → 完全符合行才會替換
    if use_dict:
        for off, text in merged_strings.items():
            if text in dict_data:
                merged_strings[off] = dict_data[text]

    save_translation_file(merged_strings, translation_txt)
    print(f"📄 已生成 {translation_txt}")
    print("⚠️ 請修改後拖回來，按 Enter:")

    ###############################################
    # 等待使用者匯入翻譯後的 txt
    ###############################################
    input_txt = input().strip('"').strip()
    if not os.path.isfile(input_txt):
        print("❌ 翻譯文件不存在！")
        return

    user_trans = load_translation_file(input_txt)

    ###############################################
    # 變更偵測：只有使用者有改的才加入 + 必須是可翻譯文字
    ###############################################
    final_apply = {}
    dict_add = {}

    def is_meaningful_text(s):
        if s.strip() == "":
            return False
        if re.search(r'[A-Za-z0-9\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]', s):
            return True
        return False

    for offset, orig_text in strings.items():
        if offset not in user_trans:
            continue  # 使用者刪掉 → 不修改

        new_text = user_trans[offset].rstrip("\n")

        # 只有「真正不同」才視為翻譯
        if new_text != orig_text:

            # 只對「可翻譯文字」加入字典
            if is_meaningful_text(orig_text):
                dict_add[orig_text] = new_text

            final_apply[offset] = new_text

    ###############################################
    # 存 dictionary（若有變更）
    ###############################################
    if dict_add:
        print(f"📘 準備更新字典: {dict_path}（新增/修改 {len(dict_add)} 筆）")
        ans = input("是否儲存更新到字典？(Y/N) [預設 Y]: ").strip().lower()
        if ans == "" or ans == "y":
            save_dict(dict_path, dict_add)
            print(f"✅ 已更新字典: {dict_path}")
        else:
            print("ℹ️ 已取消更新字典")
    else:
        print("ℹ️ 使用者無修改 → 不更新字典")

    ###############################################
    # 輸出 translated.nro
    ###############################################
    out_file = os.path.join(nro_folder, f"{base}_translated{ext}")
    apply_translation(nro_path, final_apply, out_file)
    print(f"✅ 已生成 {out_file}")

    ###############################################
    # 刪除 translation.txt
    ###############################################
    try:
        os.remove(translation_txt)
        print(f"🗑️ 已刪除 {translation_txt}")
    except:
        pass

    print("🎉 完成！")


if __name__ == "__main__":
    main()
