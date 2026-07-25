#!/usr/bin/env python3
"""
批次圖片分析工具
支援 Ollama Moondream 和 Qwen3-VL 模型

功能：
1. 支援 Google Drive 連結下載
2. 使用 Moondream 或 Qwen3-VL 分析圖片
3. 可選：要求模型輸出關鍵字，或從描述自動抽取
4. 支援自訂 prompt
5. 輸出結果為 JSON manifest

用法:
    # Qwen3-VL 模式 + 關鍵字 pipeline（呼叫另一個 text model 生成關鍵字）
    python3 batch_image_analyzer.py ~/photos/ \\
        --ollama-api http://localhost:8000/v1 \\
        --model Qwen3-VL-4B-Instruct-MLX-4bit \\
        --api-key omlx \\
        --keywords 20 \\
        --kw-model Qwen3-8B-Instruct-MLX-4bit

    # 只做描述分析（不生成關鍵字）
    python3 batch_image_analyzer.py ~/photos/ \\
        --ollama-api http://localhost:8000/v1 \\
        --model Qwen3-VL-4B-Instruct-MLX-4bit

    # 開啟關鍵字但只用本地抽取（不呼叫關鍵字模型）
    python3 batch_image_analyzer.py ~/photos/ --keywords 15
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
from typing import Optional
from PIL import Image
import io


# ============ 設定區 ============
# 沒設定環境變數就為 None（由 argparse 必填或 --model/--ollama-api 指定）
DEFAULT_MODEL_API = os.environ.get("MODEL_API") or None
DEFAULT_MODEL_NAME = os.environ.get("MODEL_NAME") or None
DEFAULT_API_KEY = os.environ.get("MODEL_API_KEY") or os.environ.get("OPENAI_API_KEY") or "omlx"
# 關鍵字生成模型（另一個 text model），未設定則不生成關鍵字
DEFAULT_KW_MODEL = os.environ.get("KEYWORD_MODEL") or None
DEFAULT_KW_API = os.environ.get("KEYWORD_API") or None  # 預設沿用主 API
DEFAULT_KW_API_KEY = os.environ.get("KEYWORD_API_KEY") or None  # 預設沿用主 API key
DEFAULT_NUM_CTX = 8192          # 預設 context length（避免 KV Cache 佔用過多記憶體）
DEFAULT_MAX_IMAGE_PIXELS = 2048  # 圖片最大邊長（超過會自動縮圖）
# ================================


def detect_model_type(model_name: str) -> str:
    """根據模型名稱自動偵測類型"""
    name_lower = model_name.lower()
    if "qwen" in name_lower or "vl" in name_lower:
        return "qwen"
    return "moondream"


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


def encode_image(image_path: str, max_pixels: int = DEFAULT_MAX_IMAGE_PIXELS) -> tuple[str, str]:
    """將圖片轉為 base64，回傳 (b64字串, MIME類型)
    
    - webp 格式會自動轉為 jpg（部分模型不支援 webp）
    - 超過 max_pixels 的圖片會自動縮圖
    - 大圖會先壓縮再編碼，避免 payload 過大
    """
    ext = image_path.lower().split('.')[-1]
    
    # 判斷是否需要用 PIL 處理（webp 或需要縮圖）
    needs_pil = ext == "webp"  # webp 一律轉 jpg
    
    if not needs_pil:
        # 先檢查圖片尺寸是否需要縮圖
        try:
            with Image.open(image_path) as img:
                w, h = img.size
                if max(w, h) > max_pixels:
                    needs_pil = True
        except Exception:
            pass  # 如果 PIL 無法開啟，就用原始方式
    
    if needs_pil:
        # 用 PIL 開啟、縮圖、轉 jpg
        with Image.open(image_path) as img:
            # 處理 RGBA/P 模式（轉 RGB）
            if img.mode in ("RGBA", "P", "LA"):
                background = Image.new("RGB", img.size, (255, 255, 255))
                if img.mode == "P":
                    img = img.convert("RGBA")
                background.paste(img, mask=img.split()[-1] if "A" in img.mode else None)
                img = background
            elif img.mode != "RGB":
                img = img.convert("RGB")
            
            # 縮圖
            w, h = img.size
            if max(w, h) > max_pixels:
                ratio = max_pixels / max(w, h)
                new_w, new_h = int(w * ratio), int(h * ratio)
                img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                print(f"  📐 圖片已縮圖: {w}x{h} → {new_w}x{new_h}")
            
            # 轉為 JPEG bytes
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=85)
            b64 = base64.b64encode(buf.getvalue()).decode()
            return b64, "image/jpeg"
    
    # 不需要處理，直接讀取
    with open(image_path, "rb") as f:
        data = f.read()
        b64 = base64.b64encode(data).decode()
        if ext in ("jpg", "jpeg"):
            mime = "image/jpeg"
        elif ext == "png":
            mime = "image/png"
        elif ext == "gif":
            mime = "image/gif"
        else:
            mime = "image/jpeg"
        return b64, mime


def analyze_image_moondream(img_b64: str, ollama_api: str, model_name: str, num_ctx: int = DEFAULT_NUM_CTX, api_key: Optional[str] = None) -> str:
    """Moondream 模型分析（舊版 API）"""
    payload = {
        "model": model_name,
        "messages": [
            {"role": "user", "content": "", "images": [img_b64]}
        ],
        "stream": False,
        "options": {
            "num_ctx": num_ctx
        }
    }

    data = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = urllib.request.Request(
        f"{ollama_api}/api/chat",
        data=data,
        headers=headers
    )

    with urllib.request.urlopen(req, timeout=120) as response:
        result = json.loads(response.read().decode("utf-8"))
        return result["message"]["content"]


def analyze_image_qwen(
    img_b64: str,
    mime: str,
    ollama_api: str,
    model_name: str,
    prompt: Optional[str] = None,
    ask_keywords: bool = False,
    num_keywords: int = 5,
    detail: str = "low",
    num_ctx: int = DEFAULT_NUM_CTX,
    api_key: Optional[str] = None
) -> tuple[str, str]:
    """
    Qwen3-VL 模型分析（OpenAI 相容 /v1/chat/completions API）
    測試：若傳入 prompt 會一併送出 text+image，看模型是否遵循語言指令。
    回傳 (內容, 推理過程)
    """
    # 組裝 content：若有 prompt 就把 text 放在 image 前（測試能否控制語言）
    content_list = []
    if prompt:
        content_list.append({"type": "text", "text": prompt})
    content_list.append({"type": "image_url", "image_url": {"url": f"data:{mime};base64,{img_b64}", "detail": detail}})

    payload = {
        "model": model_name,
        "messages": [{
            "role": "user",
            "content": content_list
        }],
        # 不設定 max_tokens，讓模型自然生成至完成（由模型/伺服器決定上限）
        "stream": False
    }

    data = json.dumps(payload).encode("utf-8")
    # 使用 OpenAI 相容端點 /v1/chat/completions
    api_url = ollama_api.rstrip("/")
    if not api_url.endswith("/v1"):
        # 若傳入的是基底 URL（如 http://localhost:8000），自動補 /v1
        if not api_url.endswith("/v1/chat/completions"):
            api_url = api_url + "/v1"
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = urllib.request.Request(
        f"{api_url}/chat/completions",
        data=data,
        headers=headers
    )

    with urllib.request.urlopen(req, timeout=300) as response:
        raw = response.read().decode("utf-8")
        result = json.loads(raw)
        if "error" in result:
            raise Exception(f"API Error: {result['error']}")
        # OpenAI 相容格式：choices[0].message.content
        choices = result.get("choices", [])
        if choices:
            msg = choices[0].get("message", {})
            content = msg.get("content", "") or ""
            reasoning = msg.get("reasoning_content", "") or msg.get("reasoning", "") or ""
        else:
            # fallback：Ollama 原生格式
            msg = result.get("message", {})
            content = msg.get("content", "") or ""
            reasoning = msg.get("reasoning", "") or ""
        return content, reasoning


def generate_keywords_with_model(
    description: str,
    api_url: str,
    model_name: str,
    num_keywords: int = 15,
    api_key: Optional[str] = None,
    num_ctx: int = DEFAULT_NUM_CTX
) -> tuple[list[str], list[str]]:
    """
    呼叫另一個文字模型，從圖片描述生成中英對照關鍵字。
    這是「關鍵字 pipeline」：VL 模型生描述 → text 模型生關鍵字。
    回傳 (zh_kw, en_kw)
    """
    if not description or not model_name:
        return [], []

    prompt = (
        f"以下是對一張圖片的描述，請從中萃取出最多 {num_keywords} 個精準關鍵字/標籤。\n"
        "規則：\n"
        "1. 涵蓋主體、物體、場景、動作、時間、天氣、顏色、材質、情緒等。\n"
        "2. 每個標籤 1-6 字（中文）或 1-3 字（英文單字），不要長句。\n"
        "3. 要具體明確，避免「東西」「物品」「場景」這類模糊詞。\n"
        "4. 同一概念不要重複。\n"
        "5. 輸出格式：每行一組「中文|english」，例如：貓|cat。\n"
        "6. 只輸出標籤清單，不要解釋、不要前言、不要編號。\n\n"
        f"描述：\n{description}\n"
    )

    payload = {
        "model": model_name,
        "messages": [{"role": "user", "content": prompt}],
        # 不設定 max_tokens，讓模型自然生成至完成
        "stream": False,
        "temperature": 0.3,
    }

    data = json.dumps(payload).encode("utf-8")
    url = api_url.rstrip("/")
    if not url.endswith("/v1"):
        url = url + "/v1"
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = urllib.request.Request(
        f"{url}/chat/completions",
        data=data,
        headers=headers
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            raw = response.read().decode("utf-8")
            result = json.loads(raw)
            if "error" in result:
                raise Exception(f"API Error: {result['error']}")
            choices = result.get("choices", [])
            content = ""
            if choices:
                content = choices[0].get("message", {}).get("content", "") or ""
            zh_kw, en_kw = parse_keyword_output(content)
            return zh_kw, en_kw
    except Exception as e:
        print(f"  ⚠️  關鍵字模型呼叫失敗: {e}")
        return [], []


def parse_keyword_output(content: str) -> tuple[list[str], list[str]]:
    """解析文字模型輸出的關鍵字（支援 中|en 格式、逗號、頓號、換行）。
    回傳 (zh_kw, en_kw)
    """
    zh_kw = []
    en_kw = []
    seen = set()

    if not content:
        return en_kw, zh_kw

    raw_lines = re.split(r'[\n\r;；]+', content)
    for line in raw_lines:
        line = line.strip()
        if not line:
            continue
        line = re.sub(r'^[\d\.\-\*•、\s]+', '', line)
        # 處理「中文|english」
        m = re.match(r'^([^\s|（()／\/]+)\s*[|｜／/（(]?\s*([a-zA-Z][a-zA-Z\s\-]{0,20})?[)）]?\s*$', line)
        if m:
            zh = m.group(1).strip()
            en = (m.group(2) or "").strip()
            key = zh.lower()
            if zh and key not in seen and 1 <= len(zh) <= 12:
                seen.add(key)
                zh_kw.append(zh)
                if en:
                    en_kw.append(en.split()[0].lower())
        else:
            parts = re.split(r'[,，、]', line)
            for p in parts:
                p = p.strip()
                if not p:
                    continue
                key = p.lower()
                if key in seen:
                    continue
                if re.search(r'[\u4e00-\u9fa5]', p) and 1 <= len(p) <= 12:
                    seen.add(key)
                    zh_kw.append(p)
                elif re.search(r'^[a-zA-Z][a-zA-Z\-]{0,20}$', p):
                    seen.add(key)
                    en_kw.append(p.lower())

    return zh_kw, en_kw


def merge_unique(*lists) -> list:
    """合併多個清單並去重，保留順序。"""
    seen = set()
    merged = []
    for lst in lists:
        for item in lst:
            key = item.lower().strip()
            if not key or key in seen:
                continue
            seen.add(key)
            merged.append(item)
    return merged


def extract_keywords_from_reasoning(reasoning: str, num_keywords: int = 5) -> list[str]:
    """從 Qwen3-VL 的 reasoning 欄位中解析出關鍵字"""
    if not reasoning:
        return []

    text = re.sub(r'\s+', ' ', reasoning)
    keywords = []

    # 策略1: 找 "关键元素：" 之後的列舉
    colon_match = re.search(r'关键元素[：:]\s*([^。\n]+)', text)
    if colon_match:
        items = colon_match.group(1)
        parts = re.split(r'[,，、]', items)
        for p in parts:
            p = p.strip()
            if 1 < len(p) < 20:
                keywords.append(p)

    # 策略2: 找 3 個相連的短詞（物體列舉模式）
    for pattern in [
        r'([^，。\s]{2,8})[,，]([^，。\s]{2,8})[,，]([^，。\s]{2,8})',
    ]:
        for match in re.findall(pattern, text):
            for item in match:
                item = item.strip()
                if 1 < len(item) < 15:
                    keywords.append(item)

    # 策略3: 找 "有X" 或 "是X" 的模式
    for pattern in [
        r'(?:有|看到|发现|识别出|检测到)[^\w][\u4e00-\u9fa5a-zA-Z0-9]{1,15}',
    ]:
        for m in re.findall(pattern, text):
            item = re.sub(r'^(有|看到|发现|识别出|检测出)\s*', '', m).strip()
            if 1 < len(item) < 15:
                keywords.append(item)

    # 過濾
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


def process_image(
    image_path: str,
    ollama_api: str,
    model_name: str,
    model_type: str,
    use_keywords: bool,
    num_keywords: int,
    detail: str,
    custom_prompt: Optional[str] = None,
    num_ctx: int = DEFAULT_NUM_CTX,
    max_image_pixels: int = DEFAULT_MAX_IMAGE_PIXELS,
    api_key: Optional[str] = None,
    kw_api: Optional[str] = None,
    kw_model: Optional[str] = None,
    kw_api_key: Optional[str] = None
) -> dict:
    """處理單張圖片
    
    Pipeline:
    1. VL 模型分析圖片 → 產生描述
    2. (可選) 呼叫另一個 text model 從描述生成關鍵字
    """
    print(f"\n📷 處理中: {image_path}")

    try:
        img_b64, mime = encode_image(image_path, max_pixels=max_image_pixels)
        description = ""
        en_kw = []
        zh_kw = []

        if model_type == "qwen":
            # 測試：若使用者指定 --prompt 就帶入，看模型是否遵循語言指令
            prompt = custom_prompt

            content, reasoning = analyze_image_qwen(
                img_b64, mime, ollama_api, model_name,
                prompt=prompt,
                ask_keywords=use_keywords,
                num_keywords=num_keywords,
                detail=detail,
                num_ctx=num_ctx,
                api_key=api_key
            )

            # Qwen3-VL 模式：模型自由生成描述文字
            description = content.strip() if content.strip() else (reasoning or "")
            print(f"  📝 描述: {description[:80]}{'...' if len(description) > 80 else ''}")

        else:
            # Moondream 模式
            description = analyze_image_moondream(img_b64, ollama_api, model_name, num_ctx=num_ctx, api_key=api_key)
            print(f"  📝 描述: {description[:80]}{'...' if len(description) > 80 else ''}")

        # 關鍵字 pipeline：呼叫另一個 text model 生成關鍵字
        if use_keywords:
            if kw_model:
                print(f"  🏷️  呼叫關鍵字模型 {kw_model} 生成關鍵字...")
                zh_kw, en_kw = generate_keywords_with_model(
                    description=description,
                    api_url=kw_api or ollama_api,
                    model_name=kw_model,
                    num_keywords=num_keywords,
                    api_key=kw_api_key or api_key,
                    num_ctx=num_ctx
                )
            else:
                print(f"  ⚠️  未指定關鍵字模型（--kw-model），略過關鍵字生成")

            print(f"      中文標籤: {', '.join(zh_kw) if zh_kw else '無'}")
            print(f"      英文標籤: {', '.join(en_kw) if en_kw else '無'}")

        return {
            "path": image_path,
            "description": description,
            "keywords_en": en_kw if use_keywords else [],
            "keywords_zh": zh_kw if use_keywords else [],
            "status": "success"
        }

    except Exception as e:
        print(f"  ❌ 處理失敗: {e}")
        return {
            "path": image_path,
            "description": None,
            "keywords_en": [],
            "keywords_zh": [],
            "status": "error",
            "error": str(e)
        }


def scan_images(folder: str, extensions: list) -> list:
    """掃描資料夾取得圖片列表"""
    images = []
    for ext in extensions:
        images.extend(Path(folder).rglob(f"*.{ext}"))
        images.extend(Path(folder).rglob(f"*.{ext.upper()}"))
    return sorted(set(images))


def main():
    parser = argparse.ArgumentParser(
        description="批次圖片分析工具（支援 Moondream / Qwen3-VL）"
    )
    parser.add_argument("folder", nargs="?", help="要處理的資料夾路徑")
    parser.add_argument("--drive-url", "-d",
                        help="Google Drive 資料夾連結（會下載到 -O 指定的路徑）")
    parser.add_argument("--output", "-O", default=None,
                        help="資料夾輸出路徑（使用 --drive-url 時為必填）")
    parser.add_argument("--extensions", nargs="+", default=["jpg", "jpeg", "png", "webp"],
                        help="要處理的副檔名 (預設: jpg jpeg png webp)")
    parser.add_argument("--result-output", default=None,
                        help="結果 JSON 輸出檔案 (預設: <資料夾>/analysis_result.json)")
    parser.add_argument("--ollama-api", default=DEFAULT_MODEL_API,
                        help=f"API URL，OpenAI 相容端點基底 (預設: {DEFAULT_MODEL_API or '未設定，必填'}，例如 http://localhost:8000/v1)")
    parser.add_argument("--model", "-m", default=DEFAULT_MODEL_NAME,
                        help=f"模型名稱 (預設: {DEFAULT_MODEL_NAME or '未設定，必填'}，例如 Qwen3-VL-4B-Instruct-MLX-4bit)")
    parser.add_argument("--api-key", default=DEFAULT_API_KEY,
                        help="API key（預設: omlx 或環境變數 MODEL_API_KEY/OPENAI_API_KEY）")
    parser.add_argument("--prompt", "-p", default=None,
                        help="自訂 prompt 帶入 VL 模型（可用來控制語言／風格）")
    parser.add_argument("--keywords", "-k", nargs="?", type=int, const=15, default=None,
                        help="開啟關鍵字 pipeline，可指定數量（預設: 15）。會呼叫 --kw-model 從描述生成關鍵字；未指定 --kw-model 則從描述本地抽取。")
    parser.add_argument("--kw-model", default=DEFAULT_KW_MODEL,
                        help="關鍵字生成模型（另一個 text model），未指定則只從描述本地抽取")
    parser.add_argument("--kw-api", default=DEFAULT_KW_API,
                        help="關鍵字模型 API URL（預設沿用主 --ollama-api）")
    parser.add_argument("--kw-api-key", default=DEFAULT_KW_API_KEY,
                        help="關鍵字模型 API key（預設沿用主 --api-key）")
    parser.add_argument("--detail", choices=["low", "high", "auto"], default="low",
                        help="Qwen3-VL 圖片解析度：low=快、high=精細 (預設: low)")
    parser.add_argument("--num-ctx", type=int, default=DEFAULT_NUM_CTX,
                        help=f"Ollama context length / KV Cache 大小 (預設: {DEFAULT_NUM_CTX}，降低可減少記憶體使用)")
    parser.add_argument("--max-image-pixels", type=int, default=DEFAULT_MAX_IMAGE_PIXELS,
                        help=f"圖片最大邊長，超過會自動縮圖 (預設: {DEFAULT_MAX_IMAGE_PIXELS})")
    args = parser.parse_args()

    model_type = detect_model_type(args.model)
    use_keywords = args.keywords is not None
    num_keywords = args.keywords if use_keywords else 0
    custom_prompt = args.prompt

    # 檢查必要參數（環境變數未設定時必須由 CLI 提供）
    if not args.ollama_api:
        print("❌ 請指定 API URL，例如 --ollama-api http://localhost:8000/v1")
        print("   或設定環境變數 MODEL_API")
        return
    if not args.model:
        print("❌ 請指定模型名稱，例如 --model Qwen3-VL-4B-Instruct-MLX-4bit")
        print("   或設定環境變數 MODEL_NAME")
        return

    print(f"🔧 設定:")
    print(f"   模型: {args.model}")
    print(f"   類型: {model_type}")
    print(f"   API: {args.ollama_api}")
    print(f"   API Key: {'已設定' if args.api_key else '無'}")
    if custom_prompt:
        print(f"   Prompt: {custom_prompt}")
    if use_keywords:
        print(f"   關鍵字 pipeline: 開啟 ({num_keywords} 個)")
        if args.kw_model:
            print(f"   關鍵字模型: {args.kw_model} @ {args.kw_api or args.ollama_api}")
        else:
            print(f"   關鍵字模型: 未指定（從描述本地抽取）")
    else:
        print(f"   關鍵字: 關閉（只做描述分析）")
    if model_type == "qwen":
        print(f"   圖片解析度: {args.detail}")
    print(f"   Context Length: {args.num_ctx}")
    print(f"   圖片最大邊長: {args.max_image_pixels}px")

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
            ollama_api=args.ollama_api,
            model_name=args.model,
            model_type=model_type,
            use_keywords=use_keywords,
            num_keywords=num_keywords,
            detail=args.detail,
            custom_prompt=custom_prompt,
            num_ctx=args.num_ctx,
            max_image_pixels=args.max_image_pixels,
            api_key=args.api_key,
            kw_api=args.kw_api,
            kw_model=args.kw_model,
            kw_api_key=args.kw_api_key
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
