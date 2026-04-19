#!/usr/bin/env python3
"""
批次圖片分析 + EXIF 寫入工具
使用 Ollama Moondream 模型

功能：
1. 支援 Google Drive 連結下載
2. 使用 Moondream 分析圖片取得描述
3. 從描述自動抽出英中對照關鍵字
4. 將描述與關鍵字寫入 EXIF UserComment

用法:
    # 本地資料夾
    python3 batch_image_analyzer.py ~/photos/

    # Google Drive 資料夾連結
    python3 batch_image_analyzer.py --drive-url https://drive.google.com/drive/folders/xxxxx -O ~/downloads/photos/
"""

import os
import re
import json
import base64
import shutil
import urllib.request
import argparse
import subprocess
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
DEFAULT_TEMP_DIR = os.environ.get("TEMP_DIR", "/tmp/batch_image_analyzer")
# ================================


def ensure_gdown():
    """檢查並安裝 gdown"""
    if shutil.which("gdown"):
        return True
    print("⚠️  gdown 未安裝，正在安裝...")
    result = os.system("pip install gdown -q")
    if result != 0:
        print("❌ gdown 安裝失敗，請手動執行: pip install gdown")
        return False
    return True


def download_from_drive(drive_url: str, output_dir: str) -> bool:
    """從 Google Drive 連結下載資料夾"""
    if not ensure_gdown():
        return False

    os.makedirs(output_dir, exist_ok=True)

    print(f"📥 正在從 Google Drive 下載...")
    print(f"   URL: {drive_url}")
    print(f"   目標: {output_dir}")

    try:
        # 使用 gdown 下載整個資料夾
        result = subprocess.run(
            ["gdown", "--folder", drive_url, "-O", output_dir, "--fuzzy"],
            capture_output=True,
            text=True,
            timeout=600
        )
        if result.returncode != 0:
            print(f"❌ 下載失敗: {result.stderr}")
            return False

        print(f"✅ 下載完成")
        return True

    except subprocess.TimeoutExpired:
        print(f"❌ 下載超時")
        return False
    except Exception as e:
        print(f"❌ 下載錯誤: {e}")
        return False


def encode_image(image_path: str) -> str:
    """將圖片轉為 base64"""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def analyze_image(image_path: str, ollama_api: str, model_name: str, extract_keywords: bool = False) -> str:
    """送圖片到模型，取得描述或直接取得關鍵字"""
    img_b64 = encode_image(image_path)

    # 如果開啟 keywords 模式，直接要求模型輸出關鍵字列表
    if extract_keywords:
        prompt = "List the main keywords or tags for this image, separated by commas. Only output keywords, no full sentences."
    else:
        prompt = ""

    payload = {
        "model": model_name,
        "messages": [
            {"role": "user", "content": prompt, "images": [img_b64]}
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


def extract_keywords_from_text(text: str) -> tuple[list[str], list[str]]:
    """從文字中抽出關鍵字"""
    text_lower = text.lower()
    found_en = []
    found_zh = []

    for en_word, zh_word in KEYWORD_MAP.items():
        if len(en_word) <= 2 and en_word not in ("tv", "pc"):
            continue
        pattern = r'\b' + re.escape(en_word) + r'(s)?\b'
        if re.search(pattern, text_lower):
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


def process_image(image_path: str, dry_run: bool, ollama_api: str, model_name: str, extract_keywords: bool) -> dict:
    """處理單張圖片"""
    print(f"\n📷 處理中: {image_path}")

    try:
        print(f"  🔍 正在分析圖片...")
        raw_result = analyze_image(image_path, ollama_api, model_name, extract_keywords)
        
        if extract_keywords:
            # 模式 A: 由模型直接提供關鍵字
            print(f"  📝 模型提供關鍵字: {raw_result}")
            description = "AI Generated Keywords"
            en_kw = [k.strip() for k in raw_result.split(",")]
            _, zh_kw = extract_keywords_from_text(raw_result) # 嘗試匹配中文翻譯
        else:
            # 模式 B: 模型提供描述，由程式抽出關鍵字
            description = raw_result
            print(f"  📝 描述: {description[:80]}{'...' if len(description) > 80 else ''}")
            print(f"  🏷️  正在由描述抽取關鍵字...")
            en_kw, zh_kw = extract_keywords_from_text(description)
        
        print(f"      英文標籤: {', '.join(en_kw) if en_kw else '無'}")
        print(f"      中文標籤: {', '.join(zh_kw) if zh_kw else '無'}")

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
    parser.add_argument("folder", nargs="?", help="要處理的資料夾路徑")
    parser.add_argument("--drive-url", "-d", 
                        help="Google Drive 資料夾連結（會下載到 -O 指定的路徑）")
    parser.add_argument("--output", "-O", default=None,
                        help="資料夾輸出路徑（使用 --drive-url 時為必填）")
    parser.add_argument("--extensions", nargs="+", default=["jpg", "jpeg", "png", "webp"],
                        help="要處理的副檔名 (預設: jpg png webp)")
    parser.add_argument("--dry-run", action="store_true",
                        help="僅分析，不寫入 EXIF")
    parser.add_argument("--result-output", default=None,
                        help="結果 JSON 輸出檔案 (預設: <資料夾>/analysis_result.json)")
    parser.add_argument("--ollama-api", default=DEFAULT_OLLAMA_API,
                        help=f"Ollama API URL (預設: {DEFAULT_OLLAMA_API})")
    parser.add_argument("--model", "-m", default=DEFAULT_MODEL_NAME,
                        help=f"模型名稱 (預設: {DEFAULT_MODEL_NAME})")
    parser.add_argument("--keywords", "-k", action="store_true",
                        help="直接要求模型輸出關鍵字 (適用於較大的模型)")
    args = parser.parse_args()

    # Google Drive 模式
    if args.drive_url:
        if not args.output:
            print("❌ 使用 --drive-url 時必須指定 -O <路徑>")
            return
        folder_path = args.output
        if download_from_drive(args.drive_url, folder_path):
            print(f"✅ 已下載到: {folder_path}")
        else:
            print("❌ 下載失敗")
            return
    elif args.folder:
        folder_path = args.folder
    else:
        print("❌ 請指定 folder 或使用 --drive-url")
        return

    # 預設輸出到圖片資料夾底下
    if args.result_output is None:
        args.result_output = os.path.join(os.path.abspath(folder_path), "analysis_result.json")

    # 確保輸出資料夾存在
    output_dir = os.path.dirname(args.result_output)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # 掃描圖片
    print(f"\n🔍 掃描資料夾: {folder_path}")
    images = scan_images(folder_path, args.extensions)
    print(f"📁 找到 {len(images)} 張圖片\n")

    if not images:
        print("❌ 沒有找到任何圖片")
        return

    # 處理每張圖片
    results = []
    for i, img_path in enumerate(images, 1):
        print(f"\n[{i}/{len(images)}]", end="")
        result = process_image(str(img_path), dry_run=args.dry_run, ollama_api=args.ollama_api, model_name=args.model, extract_keywords=args.keywords)
        results.append(result)

    # 輸出結果
    output_file = args.result_output
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    success_count = sum(1 for r in results if r["status"] == "success")
    print(f"\n{'='*50}")
    print(f"✅ 完成！成功: {success_count}/{len(results)}")
    print(f"📄 結果已儲存至: {output_file}")

    if args.drive_url:
        print(f"\n💡 提示：分析結果在本地資料夾，如需同步回雲端請使用 rclone 或手動上傳")


if __name__ == "__main__":
    main()
