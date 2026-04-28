#!/usr/bin/env python3
"""
EXIF 寫入工具
從 JSON 分析結果寫入圖片的 EXIF UserComment

用法:
    # 寫入所有圖片
    python3 write_exif.py analysis_result.json

    # 指定輸出資料夾
    python3 write_exif.py analysis_result.json -O ~/photos/

    # 只寫入有描述的圖片
    python3 write_exif.py analysis_result.json --require-description
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


def write_exif(image_path: str, description: str, en_keywords: list, zh_keywords: list) -> bool:
    """將描述和關鍵字寫入圖片的 EXIF"""
    try:
        exif_dict = piexif.load(image_path)
    except ValueError:
        exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}

    keywords_str = format_keywords_for_exif(en_keywords, zh_keywords)
    full_text = f"{description}\n\n[{keywords_str}]"

    comment_bytes = b"UTF-8\x00\x00\x00" + full_text.encode("utf-8")
    exif_dict["0th"][37510] = comment_bytes

    now = datetime.now().strftime("%Y:%m:%d %H:%M:%S")
    exif_dict["0th"][306] = now.encode("utf-8")

    try:
        exif_bytes = piexif.dump(exif_dict)
        piexif.insert(exif_bytes, image_path)
        return True
    except Exception as e:
        print(f"  ❌ EXIF 寫入失敗: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="EXIF 寫入工具（從 JSON 分析結果寫入圖片）"
    )
    parser.add_argument("json_file", help="分析結果 JSON 檔案")
    parser.add_argument("--output", "-O", default=None,
                        help="圖片所在資料夾（用於驗證檔案路徑）")
    parser.add_argument("--require-description", action="store_true",
                        help="只寫入有 description 的圖片")
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

        print(f"📷 寫入 EXIF: {image_path}")
        if description:
            print(f"  📝 {description[:60]}{'...' if len(description) > 60 else ''}")

        success = write_exif(image_path, description or "", en_kw, zh_kw)
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
