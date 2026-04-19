#!/usr/bin/env python3
"""
批次圖片分析 + EXIF 寫入工具
使用 Ollama Moondream 模型

功能：
1. 使用 Moondream 分析圖片取得描述
2. 從描述自動抽出英中對照關鍵字
3. 將描述與關鍵字寫入 EXIF UserComment

用法:
    python3 batch_image_analyzer.py <資料夾路徑> [--extensions jpg png webp]
"""

import os
import re
import json
import base64
import urllib.request
import argparse
from pathlib import Path
from datetime import datetime

from keywords import KEYWORD_MAP

try:
    import piexif
except ImportError:
    print("⚠️  piexif 未安裝，正在安裝...")
    os.system("pip install piexif -q")
    import piexif


# ============ 設定區 ============
DEFAULT_OLLAMA_API = os.environ.get("OLLAMA_API", "http://ollama:11434/api/chat")
DEFAULT_MODEL_NAME = os.environ.get("MODEL_NAME", "moondream")
# ================================


def encode_image(image_path: str) -> str:
    """將圖片轉為 base64"""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def analyze_image(image_path: str, ollama_api: str, model_name: str) -> str:
    """送圖片到 Moondream，取得描述"""
    img_b64 = encode_image(image_path)

    payload = {
        "model": model_name,
        "messages": [
            {"role": "user", "content": "", "images": [img_b64]}
        ],
        "stream": False
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        ollama_api,
        data=data,
        headers={"Content-Type": "application/json"}
    )

    with urllib.request.urlopen(req, timeout=120) as response:
        result = json.loads(response.read().decode("utf-8"))
        return result["message"]["content"]


def extract_keywords(description: str) -> tuple[list[str], list[str]]:
    """
    從描述中抽出關鍵字
    回傳：(英文關鍵字列表, 中文關鍵字列表)
    """
    desc_lower = description.lower()
    found_en = []
    found_zh = []

    for en_word, zh_word in KEYWORD_MAP.items():
        if len(en_word) <= 2 and en_word not in ("tv", "pc"):
            continue
        pattern = r'\b' + re.escape(en_word) + r'(s)?\b'
        if re.search(pattern, desc_lower):
            if zh_word not in found_zh:
                found_zh.append(zh_word)
                found_en.append(en_word)

    return found_en, found_zh


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


def process_image(image_path: str, dry_run: bool, ollama_api: str, model_name: str) -> dict:
    """處理單張圖片"""
    print(f"\n📷 處理中: {image_path}")

    try:
        print(f"  🔍 正在分析圖片...")
        description = analyze_image(image_path, ollama_api, model_name)
        print(f"  📝 描述: {description[:80]}{'...' if len(description) > 80 else ''}")

        print(f"  🏷️  正在抽取關鍵字...")
        en_kw, zh_kw = extract_keywords(description)
        print(f"      英文: {', '.join(en_kw) if en_kw else '無'}")
        print(f"      中文: {', '.join(zh_kw) if zh_kw else '無'}")

        if not dry_run:
            success = write_exif(image_path, description, en_kw, zh_kw)
            if success:
                print(f"  ✅ EXIF 已寫入")
            else:
                print(f"  ⚠️  跳過 EXIF 寫入")
        else:
            print(f"  ⏭️  Dry run: 略過 EXIF 寫入")

        return {
            "path": image_path,
            "description": description,
            "keywords_en": en_kw,
            "keywords_zh": zh_kw,
            "status": "success"
        }

    except Exception as e:
        print(f"  ❌ 處理失敗: {e}")
        return {"path": image_path, "description": None, "keywords_en": [], "keywords_zh": [], "status": "error", "error": str(e)}


def scan_images(folder: str, extensions: list) -> list:
    """掃描資料夾取得圖片列表"""
    images = []
    for ext in extensions:
        images.extend(Path(folder).rglob(f"*.{ext}"))
        images.extend(Path(folder).rglob(f"*.{ext.upper()}"))
    return sorted(set(images))


def main():
    parser = argparse.ArgumentParser(description="批次圖片分析 + EXIF 寫入工具")
    parser.add_argument("folder", help="要處理的資料夾路徑（支援本地資料夾或 Google Drive 掛載路徑）")
    parser.add_argument("--extensions", nargs="+", default=["jpg", "jpeg", "png", "webp"],
                        help="要處理的副檔名 (預設: jpg png webp)")
    parser.add_argument("--dry-run", action="store_true",
                        help="僅分析，不寫入 EXIF")
    parser.add_argument("--output", "-o", default=None,
                        help="結果輸出檔案 (預設: <圖片資料夾>/analysis_result.json)")
    parser.add_argument("--ollama-api", default=DEFAULT_OLLAMA_API,
                        help=f"Ollama API URL (預設: {DEFAULT_OLLAMA_API})")
    parser.add_argument("--model", "-m", default=DEFAULT_MODEL_NAME,
                        help=f"模型名稱 (預設: {DEFAULT_MODEL_NAME})")
    args = parser.parse_args()

    # 預設輸出到圖片資料夾底下
    if args.output is None:
        args.output = os.path.join(os.path.abspath(args.folder), "analysis_result.json")

    # 確保輸出資料夾存在
    output_dir = os.path.dirname(args.output)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # 掃描圖片
    print(f"🔍 掃描資料夾: {args.folder}")
    images = scan_images(args.folder, args.extensions)
    print(f"📁 找到 {len(images)} 張圖片\n")

    if not images:
        print("❌ 沒有找到任何圖片")
        return

    # 處理每張圖片
    results = []
    for i, img_path in enumerate(images, 1):
        print(f"\n[{i}/{len(images)}]", end="")
        result = process_image(str(img_path), dry_run=args.dry_run, ollama_api=args.ollama_api, model_name=args.model)
        results.append(result)

    # 輸出結果
    output_file = args.output
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    success_count = sum(1 for r in results if r["status"] == "success")
    print(f"\n{'='*50}")
    print(f"✅ 完成！成功: {success_count}/{len(results)}")
    print(f"📄 結果已儲存至: {output_file}")


if __name__ == "__main__":
    main()
