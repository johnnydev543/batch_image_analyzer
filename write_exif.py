#!/usr/bin/env python3
"""
EXIF 寫入工具
從 JSON 分析結果寫入圖片的 EXIF UserComment

用法:
    # 寫入所有圖片（預設寫入 description）
    python3 write_exif.py analysis_result.json

    # 指定輸出資料夾
    python3 write_exif.py analysis_result.json -O ~/photos/

    # 只寫入有描述的圖片
    python3 write_exif.py analysis_result.json --require-description

    # 寫入 description + keywords（keywords 為簡寫，合併 keywords_en + keywords_zh）
    python3 write_exif.py analysis_result.json -f description keywords

    # 只寫入關鍵字（簡寫）
    python3 write_exif.py analysis_result.json -f keywords

    # 直接使用 JSON 實際欄位名
    python3 write_exif.py analysis_result.json -f keywords_en keywords_zh

    # 寫入任意 JSON 欄位
    python3 write_exif.py analysis_result.json -f description status path
"""

import os
import json
import argparse
from datetime import datetime

try:
    import piexif
except ImportError:
    print("⚠️  piexif 未安裝，正在安裝...")
    os.system("pip install piexif -q")
    import piexif


def format_keywords_for_exif(en_keywords: list, zh_keywords: list) -> str:
    """格式化關鍵字為 EXIF 寫入格式"""
    en_str = ", ".join(en_keywords) if en_keywords else "N/A"
    zh_str = ", ".join(zh_keywords) if zh_keywords else "N/A"
    return f"EN: {en_str} | 中: {zh_str}"


def compose_exif_text(item: dict, fields: list) -> str:
    """依指定的欄位組裝要寫入 EXIF 的文字內容。
    
    特殊欄位名（簡寫，會自動合併／格式化）：
      - description  → item["description"]
      - keywords     → 合併 keywords_en + keywords_zh，格式化為 "EN: ... | 中: ..."
      - path         → item["path"]
      - status       → item["status"]
    其他名稱會直接當作 JSON key 取值（如 keywords_en, keywords_zh, error 等）。
    """
    parts = []
    for f in fields:
        if f == "description":
            desc = item.get("description") or ""
            if desc:
                parts.append(desc)
        elif f == "keywords":
            en_kw = item.get("keywords_en", [])
            zh_kw = item.get("keywords_zh", [])
            if en_kw or zh_kw:
                parts.append(format_keywords_for_exif(en_kw, zh_kw))
        elif f == "path":
            p = item.get("path") or ""
            if p:
                parts.append(f"Path: {p}")
        elif f == "status":
            s = item.get("status") or ""
            if s:
                parts.append(f"Status: {s}")
        elif f in item:
            val = item.get(f)
            if val is not None:
                # list 類型用逗號串接，其他轉字串
                if isinstance(val, list):
                    val = ", ".join(str(v) for v in val) if val else ""
                if val:
                    parts.append(f"{f}: {val}")
    return "\n\n".join(parts)


def write_exif(image_path: str, full_text: str) -> bool:
    """將指定文字寫入圖片的 EXIF UserComment
    
    處理策略：
    - 載入既有 EXIF 失敗時，使用空白 dict
    - dump 失敗時，重建最小 EXIF 再試一次
    - webp/png 等不支援的格式，改用 PIL 重新儲存寫入
    """
    comment_bytes = b"UTF-8\x00\x00\x00" + full_text.encode("utf-8")
    now = datetime.now().strftime("%Y:%m:%d %H:%M:%S")

    ext = image_path.lower().split(".")[-1]

    # --- webp / png / 不支援格式：用 PIL 寫入 ---
    # piexif 只支援 JPEG/TIFF 的 EXIF；png/webp 改用 PIL 的 exif= 參數
    if ext in ("webp", "png"):
        try:
            from PIL import Image
            piexif_bytes = _build_exif_bytes(comment_bytes, now)
            with Image.open(image_path) as im:
                # png 要保留原格式與模式
                im.save(image_path, exif=piexif_bytes)
            return True
        except Exception as e:
            print(f"  ❌ {ext} EXIF 寫入失敗: {e}")
            return False

    # --- jpg / tiff：用 piexif ---
    # 嘗試載入既有 EXIF；任何錯誤都用空 dict
    exif_dict = None
    try:
        exif_dict = piexif.load(image_path)
    except Exception:
        exif_dict = None

    if not isinstance(exif_dict, dict):
        exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}

    # 確保各 IFD 是 dict
    if not isinstance(exif_dict.get("0th"), dict):
        exif_dict["0th"] = {}
    if not isinstance(exif_dict.get("Exif"), dict):
        exif_dict["Exif"] = {}

    # UserComment (37510) 屬於 Exif sub-IFD，不是 0th；放錯會 dump 失敗
    exif_dict["Exif"][37510] = comment_bytes
    # DateTime (306) 屬於 0th IFD
    exif_dict["0th"][306] = now.encode("utf-8")

    # 第一次嘗試 dump + insert
    try:
        exif_bytes = piexif.dump(exif_dict)
        piexif.insert(exif_bytes, image_path)
        return True
    except Exception as e:
        print(f"  ⚠️  既有 EXIF 寫入失敗（{e}），重建最小 EXIF 再試...")

    # fallback：重建最小 EXIF（丟掉原本可能有問題的欄位）
    try:
        fresh = {"0th": {306: now.encode("utf-8")},
                 "Exif": {37510: comment_bytes},
                 "GPS": {}, "1st": {}, "thumbnail": None}
        exif_bytes = piexif.dump(fresh)
        # 先移除舊 EXIF 再插入，避免重複
        try:
            piexif.remove(image_path)
        except Exception:
            pass
        piexif.insert(exif_bytes, image_path)
        return True
    except Exception as e:
        print(f"  ❌ EXIF 寫入失敗: {e}")
        return False


def _build_exif_bytes(comment_bytes: bytes, now: str) -> bytes:
    """組裝最小 EXIF bytes（供 PIL 寫入 webp 用）"""
    exif_dict = {
        "0th": {306: now.encode("utf-8")},
        "Exif": {37510: comment_bytes},
        "GPS": {}, "1st": {}, "thumbnail": None,
    }
    return piexif.dump(exif_dict)


def main():
    parser = argparse.ArgumentParser(
        description="EXIF 寫入工具（從 JSON 分析結果寫入圖片）"
    )
    parser.add_argument("json_file", help="分析結果 JSON 檔案")
    parser.add_argument("--output", "-O", default=None,
                        help="圖片所在資料夾（用於驗證檔案路徑）")
    parser.add_argument("--require-description", action="store_true",
                        help="只寫入有 description 的圖片")
    parser.add_argument("--field", "-f", nargs="+", default=["description"],
                        help="要寫入 EXIF 的欄位，可多選，預設 description。"
                             "特殊簡寫: description, keywords(=合併 keywords_en+keywords_zh), path, status。"
                             "或直接用 JSON 實際欄位名: keywords_en, keywords_zh, error 等。"
                             "多個欄位會以空行分隔合併寫入。範例: -f description keywords")
    args = parser.parse_args()

    # 讀取 JSON
    json_path = os.path.abspath(args.json_file)
    if not os.path.exists(json_path):
        print(f"❌ 找不到 JSON 檔案: {json_path}")
        return

    with open(json_path, "r", encoding="utf-8") as f:
        results = json.load(f)

    if not isinstance(results, list):
        print("❌ JSON 格式錯誤，應為陣列")
        return

    # 取得圖片資料夾（從 JSON 路徑推斷）
    json_dir = os.path.dirname(json_path)

    success_count = 0
    skip_count = 0

    for item in results:
        if item.get("status") != "success":
            print(f"⏭️  略過（處理失敗）: {item.get('path', 'unknown')}")
            skip_count += 1
            continue

        image_path = item.get("path")
        description = item.get("description")
        en_kw = item.get("keywords_en", [])
        zh_kw = item.get("keywords_zh", [])

        # 驗證檔案存在
        if not os.path.exists(image_path):
            print(f"⏭️  略過（檔案不存在）: {image_path}")
            skip_count += 1
            continue

        # 如果需要 description 但沒有，則跳過
        if args.require_description and not description:
            print(f"⏭️  略過（無 description）: {image_path}")
            skip_count += 1
            continue

        # 依 --field 組裝寫入內容
        full_text = compose_exif_text(item, args.field)
        if not full_text.strip():
            print(f"⏭️  略過（指定欄位無內容）: {image_path}")
            skip_count += 1
            continue

        print(f"📷 寫入 EXIF: {image_path}")
        print(f"  📝 欄位: {', '.join(args.field)} | {full_text[:60]}{'...' if len(full_text) > 60 else ''}")

        success = write_exif(image_path, full_text)
        if success:
            print(f"  ✅ 完成")
            success_count += 1
        else:
            print(f"  ⚠️  失敗")
            skip_count += 1

    print(f"\n{'='*50}")
    print(f"✅ 完成！成功: {success_count}, 略過: {skip_count}")
    print(f"📁 JSON: {json_path}")


if __name__ == "__main__":
    main()
