#!/usr/bin/env python3
"""
批次圖片分析 + EXIF 寫入工具
支援 Ollama Moondream 和 Qwen3-VL 模型

功能：
1. 支援 Google Drive 連結下載
2. 使用 Moondream 或 Qwen3-VL 分析圖片
3. 從描述自動抽出英中對照關鍵字
4. 將描述與關鍵字寫入 EXIF UserComment
5. Qwen3-VL 模式：自動解析 reasoning 欄位

用法:
    # Moondream 模式（預設）
    python3 batch_image_analyzer.py ~/photos/

    # Qwen3-VL 模式
    python3 batch_image_analyzer.py ~/photos/ --model qwen3-vl:2b --model-type qwen

    # Qwen3-VL + 調整輸出關鍵字數量
    python3 batch_image_analyzer.py ~/photos/ --model qwen3-vl:2b --model-type qwen --output-length 8
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
DEFAULT_OLLAMA_API = os.environ.get("OLLAMA_API", "http://ollama:11434")
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


def encode_image(image_path: str) -> tuple[str, str]:
    """將圖片轉為 base64，回傳 (b64字串, MIME類型)"""
    with open(image_path, "rb") as f:
        data = f.read()
        b64 = base64.b64encode(data).decode()
        # 判斷 MIME 類型
        ext = image_path.lower().split('.')[-1]
        if ext in ("jpg", "jpeg"):
            mime = "image/jpeg"
        elif ext == "png":
            mime = "image/png"
        elif ext == "webp":
            mime = "image/webp"
        elif ext == "gif":
            mime = "image/gif"
        else:
            mime = "image/jpeg"
        return b64, mime


def analyze_image_moondream(img_b64: str, ollama_api: str, model_name: str) -> str:
    """Moondream 模型分析（舊版 API）"""
    payload = {
        "model": model_name,
        "messages": [
            {"role": "user", "content": "", "images": [img_b64]}
        ],
        "stream": False
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{ollama_api}/api/chat",
        data=data,
        headers={"Content-Type": "application/json"}
    )

    with urllib.request.urlopen(req, timeout=120) as response:
        result = json.loads(response.read().decode("utf-8"))
        return result["message"]["content"]


def analyze_image_qwen(
    img_b64: str,
    mime: str,
    ollama_api: str,
    model_name: str,
    num_keywords: int = 5,
    detail: str = "low"
) -> tuple[str, str]:
    """
    Qwen3-VL 模型分析（V1 Chat Completions API）
    回傳 (內容, 推理過程)
    
    Args:
        img_b64: base64 編碼的圖片
        mime: MIME 類型
        ollama_api: API 端點
        model_name: 模型名稱
        num_keywords: 要輸出的關鍵字數量
        detail: 圖片解析度 ("low" | "high" | "auto")
    
    Returns:
        (content, reasoning) - content 可能是空字串，關鍵字可能在 reasoning 中
    """
    payload = {
        "model": model_name,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{img_b64}", "detail": detail}},
                {"type": "text", "text": f"輸出{num_keywords}個關鍵字，逗號分隔，別解釋。"}
            ]
        }],
        "max_tokens": 300,
        "stream": False
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{ollama_api}/v1/chat/completions",
        data=data,
        headers={"Content-Type": "application/json"}
    )

    with urllib.request.urlopen(req, timeout=120) as response:
        result = json.loads(response.read().decode("utf-8"))
        msg = result["choices"][0]["message"]
        content = msg.get("content", "")
        reasoning = msg.get("reasoning", "") or ""
        return content, reasoning


def extract_keywords_from_reasoning(reasoning: str, num_keywords: int = 5) -> list[str]:
    """
    從 Qwen3-VL 的 reasoning 欄位中解析出關鍵字
    
    策略：
    1. 找 "关键元素：" 之後的列舉（最準確）
    2. 找 3 個以上相連的短詞（物體列舉模式）
    3. 過濾掉描述性句子
    """
    if not reasoning:
        return []
    
    text = re.sub(r'\s+', ' ', reasoning)
    keywords = []
    
    # === 策略1: 找 "关键元素：" 之後的列舉 ===
    # 例如："关键元素：监控画面、自行车、SUV、摩托车、交通锥"
    colon_match = re.search(r'关键元素[：:]\s*([^。\n]+)', text)
    if colon_match:
        items = colon_match.group(1)
        parts = re.split(r'[,，、]', items)
        for p in parts:
            p = p.strip()
            if 1 < len(p) < 20:
                keywords.append(p)
    
    # === 策略2: 找 3 個相連的短詞（物體列舉模式）===
    # 例如 "自行车、SUV、摩托车"
    object_patterns = [
        r'([^，。\s]{2,8})[,，]([^，。\s]{2,8})[,，]([^，。\s]{2,8})',
    ]
    for pattern in object_patterns:
        matches = re.findall(pattern, text)
        for match in matches:
            for item in match:
                item = item.strip()
                if 1 < len(item) < 15:
                    keywords.append(item)
    
    # === 策略3: 找 "有X" 或 "是X" 的模式 ===
    have_patterns = [
        r'(?:有|看到|发现|识别出|检测到)[^\w][\u4e00-\u9fa5a-zA-Z0-9]{1,15}',
    ]
    for pattern in have_patterns:
        matches = re.findall(pattern, text)
        for m in matches:
            item = re.sub(r'^(有|看到|发现|识别出|检测出)\s*', '', m)
            item = item.strip()
            if 1 < len(item) < 15:
                keywords.append(item)
    
    # === 過濾 ===
    exclude_words = [
        "圖片", "图片", "首先", "然後", "最後", "所以", "可能", "這是", "這有",
        "看起來", "看見", "應該", "一個", "有的", "沒有", "旁邊", "遠處",
        "前面", "後面", "左邊", "右邊", "中間", "上方", "下方", "背景", "前景",
        "主要", "次要", "畫面", "場景", "監控", "時間", "左側", "右側",
        "用户", "需要", "输出", "关键词", "逗号", "分隔", "解释",
        "摄像头", "标识", "时间戳", "需要5", "首先确定", "这些都是",
        "可能更偏向于", "场景中的", "主要物体", "仔细看", "图片内容",
        "画面中有一个人", "一个人在骑", "路边有", "用户现在"
    ]
    
    seen = set()
    unique = []
    for kw in keywords:
        kw_clean = kw.lower().strip()
        if len(kw_clean) < 2 or len(kw_clean) > 15:
            continue
        if kw_clean in seen:
            continue
        if any(ex in kw_clean for ex in exclude_words):
            continue
        seen.add(kw_clean)
        unique.append(kw_clean)
    
    return unique[:num_keywords]


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


def analyze_image(image_path: str, ollama_api: str, model_name: str, model_type: str,
                 num_keywords: int = 5, detail: str = "low") -> dict:
    """
    統一的圖片分析介面
    回傳分析結果字典
    """
    img_b64, mime = encode_image(image_path)
    
    if model_type == "qwen":
        content, reasoning = analyze_image_qwen(
            img_b64, mime, ollama_api, model_name, 
            num_keywords=num_keywords, detail=detail
        )
        return {
            "content": content,
            "reasoning": reasoning,
            "model_type": "qwen"
        }
    else:
        # Moondream
        description = analyze_image_moondream(img_b64, ollama_api, model_name)
        return {
            "content": description,
            "reasoning": "",
            "model_type": "moondream"
        }


def process_image(image_path: str, dry_run: bool, ollama_api: str, model_name: str,
                  model_type: str, num_keywords: int, detail: str) -> dict:
    """處理單張圖片"""
    print(f"\n📷 處理中: {image_path}")

    try:
        print(f"  🔍 正在分析圖片 ({model_type})...")
        result = analyze_image(image_path, ollama_api, model_name, model_type,
                               num_keywords=num_keywords, detail=detail)
        
        description = ""
        en_kw = []
        zh_kw = []
        
        if model_type == "qwen":
            content = result["content"]
            reasoning = result["reasoning"]
            
            if content and len(content.strip()) > 5:
                # content 有實質內容，直接使用
                print(f"  📝 直接關鍵字: {content}")
                raw_kw = [k.strip() for k in content.split(",") if k.strip()]
                en_kw = raw_kw
                description = content
            elif reasoning:
                # content 為空，從 reasoning 解析
                print(f"  📝 從推理過程解析關鍵字...")
                parsed_kw = extract_keywords_from_reasoning(reasoning, num_keywords=num_keywords)
                print(f"  📝 解析關鍵字: {', '.join(parsed_kw)}")
                en_kw = parsed_kw
                description = f"[從推理解析] {reasoning[:100]}..."
            else:
                print(f"  ⚠️  無內容輸出")
        else:
            # Moondream 模式
            description = result["content"]
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
    parser = argparse.ArgumentParser(
        description="批次圖片分析 + EXIF 寫入工具（支援 Moondream / Qwen3-VL）"
    )
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
    parser.add_argument("--model-type", choices=["auto", "qwen", "moondream"], default="auto",
                        help="模型類型：auto 自動偵測 qwen 或 moondream (預設: auto)")
    parser.add_argument("--keywords", "-k", action="store_true",
                        help="直接要求模型輸出關鍵字 (適用於較大的模型)")
    parser.add_argument("--output-length", "-l", type=int, default=5,
                        help="輸出的關鍵字數量 (預設: 5)")
    parser.add_argument("--detail", choices=["low", "high", "auto"], default="low",
                        help="Qwen3-VL 圖片解析度：low=快、high=精細 (預設: low)")
    args = parser.parse_args()

    # 自動偵測模型類型
    if args.model_type == "auto":
        if "qwen" in args.model.lower():
            args.model_type = "qwen"
        else:
            args.model_type = "moondream"
    
    print(f"🔧 設定:")
    print(f"   模型: {args.model}")
    print(f"   類型: {args.model_type}")
    print(f"   API: {args.ollama_api}")
    print(f"   輸出關鍵字數: {args.output_length}")
    if args.model_type == "qwen":
        print(f"   圖片解析度: {args.detail}")

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
        result = process_image(
            str(img_path),
            dry_run=args.dry_run,
            ollama_api=args.ollama_api,
            model_name=args.model,
            model_type=args.model_type,
            num_keywords=args.output_length,
            detail=args.detail
        )
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
