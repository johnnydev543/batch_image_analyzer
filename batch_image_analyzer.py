#!/usr/bin/env python3
"""
批次圖片分析 + EXIF 寫入工具
使用 Ollama Moondream 模型

用法:
    python3 batch_image_analyzer.py <資料夾路徑> [--extensions jpg png webp]
"""

import os
import json
import base64
import urllib.request
import argparse
from pathlib import Path
from datetime import datetime

try:
    import piexif
except ImportError:
    print("⚠️  piexif 未安裝，正在安裝...")
    os.system("pip install piexif -q")
    import piexif


# ============ 設定區 ============
# 可透過環境變數 OLLAMA_API, MODEL_NAME 覆寫
# 或命令列引數 --ollama-api, --model
OLLAMA_API = os.environ.get("OLLAMA_API", "http://ollama:11434/api/chat")
MODEL_NAME = os.environ.get("MODEL_NAME", "moondream")
# ================================


def encode_image(image_path: str) -> str:
    """將圖片轉為 base64"""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def analyze_image(image_path: str) -> str:
    """送圖片到 Moondream，取得描述"""
    img_b64 = encode_image(image_path)

    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "user", "content": "", "images": [img_b64]}
        ],
        "stream": False
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        OLLAMA_API,
        data=data,
        headers={"Content-Type": "application/json"}
    )

    with urllib.request.urlopen(req, timeout=120) as response:
        result = json.loads(response.read().decode("utf-8"))
        return result["message"]["content"]


def write_exif_usercomment(image_path: str, description: str) -> bool:
    """將描述寫入圖片的 EXIF UserComment 欄位"""
    try:
        exif_dict = piexif.load(image_path)
    except ValueError:
        # 圖片沒有 EXIF，建立新的
        exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}

    # 寫入 UserComment (0th tag 37510)
    # UserComment 需要 8 bytes header + UTF-8 編碼
    comment_bytes = b"UTF-8\x00\x00\x00" + description.encode("utf-8")
    exif_dict["0th"][37510] = comment_bytes

    # 更新 DateTime (306 tag)
    now = datetime.now().strftime("%Y:%m:%d %H:%M:%S")
    exif_dict["0th"][306] = now.encode("utf-8")

    try:
        exif_bytes = piexif.dump(exif_dict)
        piexif.insert(exif_bytes, image_path)
        return True
    except Exception as e:
        print(f"  ❌ EXIF 寫入失敗: {e}")
        return False


def process_image(image_path: str, dry_run: bool = False) -> dict:
    """處理單張圖片"""
    print(f"\n📷 處理中: {image_path}")

    try:
        # 1. 分析圖片
        print(f"  🔍 正在分析圖片...")
        description = analyze_image(image_path)
        print(f"  📝 描述: {description[:100]}{'...' if len(description) > 100 else ''}")

        # 2. 寫入 EXIF
        if not dry_run:
            success = write_exif_usercomment(image_path, description)
            if success:
                print(f"  ✅ EXIF 已寫入")
            else:
                print(f"  ⚠️  跳過 EXIF 寫入")
        else:
            print(f"  �Dry run: 略過 EXIF 寫入")

        return {"path": image_path, "description": description, "status": "success"}

    except Exception as e:
        print(f"  ❌ 處理失敗: {e}")
        return {"path": image_path, "description": None, "status": "error", "error": str(e)}


def scan_images(folder: str, extensions: list) -> list:
    """掃描資料夾取得圖片列表"""
    images = []
    for ext in extensions:
        images.extend(Path(folder).rglob(f"*.{ext}"))
        images.extend(Path(folder).rglob(f"*.{ext.upper()}"))
    return sorted(set(images))


def main():
    parser = argparse.ArgumentParser(description="批次圖片分析 + EXIF 寫入工具")
    parser.add_argument("folder", help="要處理的資料夾路徑")
    parser.add_argument("--extensions", nargs="+", default=["jpg", "jpeg", "png", "webp"],
                        help="要處理的副檔名 (預設: jpg png webp)")
    parser.add_argument("--dry-run", action="store_true",
                        help="僅分析，不寫入 EXIF")
    parser.add_argument("--output", "-o", default="analysis_result.json",
                        help="結果輸出檔案 (預設: analysis_result.json)")
    parser.add_argument("--ollama-api", default=OLLAMA_API,
                        help=f"Ollama API URL (預設: {OLLAMA_API})")
    parser.add_argument("--model", "-m", default=MODEL_NAME,
                        help=f"模型名稱 (預設: {MODEL_NAME})")
    args = parser.parse_args()

    # 更新全域設定（支援 CLI 覆寫環境變數）
    global OLLAMA_API, MODEL_NAME
    OLLAMA_API = args.ollama_api
    MODEL_NAME = args.model

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
        result = process_image(str(img_path), dry_run=args.dry_run)
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
