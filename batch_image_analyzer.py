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


# ============ 關鍵字英中對照表 ============
KEYWORD_MAP = {
    # 動物
    "cat": "貓", "cats": "貓", "kitten": "小貓", "dog": "狗", "puppy": "小狗",
    "bird": "鳥", "parrot": "鸚鵡", "fish": "魚", "horse": "馬", "rabbit": "兔子",
    "turtle": "烏龜", "snake": "蛇", "chicken": "雞", "cow": "牛", "sheep": "羊",
    "monkey": "猴子", "bear": "熊", "lion": "獅子", "tiger": "老虎", "elephant": "大象",
    "panda": "熊貓", "giraffe": "長頸鹿", "zebra": "斑馬", "deer": "鹿",
    # 人
    "person": "人", "people": "人", "man": "男人", "woman": "女人", "child": "小孩",
    "boy": "男孩", "girl": "女孩", "baby": "嬰兒", "adult": "成人", "elderly": "老人",
    "people": "人", "crowd": "人群", "student": "學生", "worker": "工人",
    # 交通
    "bicycle": "腳踏車", "bike": "腳踏車", "car": "汽車", "cars": "汽車", "vehicle": "車輛",
    "truck": "卡車", "bus": "公車", "motorcycle": "摩托車", "scooter": "機車",
    "train": "火車", "subway": "地鐵", "metro": "捷運", "airplane": "飛機", "plane": "飛機",
    "boat": "船", "ship": "船", "ferry": "渡輪", "taxi": "計程車",
    # 建築與場景
    "building": "建築", "house": "房屋", "home": "家", "apartment": "公寓",
    "office": "辦公室", "school": "學校", "hospital": "醫院", "church": "教堂",
    "temple": "寺廟", "shrine": "神社", "castle": "城堡", "bridge": "橋",
    "road": "道路", "street": "街道", "highway": "高速公路", "sidewalk": "人行道",
    "path": "小路", "alley": "巷子", "avenue": "大道",
    # 自然與景觀
    "sky": "天空", "cloud": "雲", "clouds": "雲", "sun": "太陽", "moon": "月亮",
    "star": "星星", "mountain": "山", "hill": "小山", "beach": "海灘", "sea": "海",
    "ocean": "海洋", "river": "河", "lake": "湖", "water": "水", "waterfall": "瀑布",
    "forest": "森林", "tree": "樹", "trees": "樹", "flower": "花", "flowers": "花",
    "plant": "植物", "grass": "草", "leaf": "葉子", "garden": "花園", "park": "公園",
    "field": "田野", "desert": "沙漠", "island": "島嶼", "valley": "山谷",
    # 室內與物品
    "room": "房間", "bedroom": "臥室", "kitchen": "廚房", "bathroom": "浴室",
    "living room": "客廳", "dining": "餐廳", "table": "桌子", "chair": "椅子",
    "window": "窗戶", "door": "門", "floor": "地板", "wall": "牆", "ceiling": "天花板",
    "stairs": "樓梯", "bed": "床", "sofa": "沙發", "lamp": "燈", "light": "光",
    "mirror": "鏡子", "shelf": "架子", "cabinet": "櫃子", "desk": "書桌",
    "book": "書", "books": "書", "computer": "電腦", "laptop": "筆電", "phone": "手機",
    "tv": "電視", "television": "電視", "radio": "收音機", "camera": "相機",
    # 食物與飲料
    "food": "食物", "meal": "餐點", "breakfast": "早餐", "lunch": "午餐", "dinner": "晚餐",
    "fruit": "水果", "vegetable": "蔬菜", "meat": "肉", "fish": "魚", "rice": "米飯",
    "noodle": "麵", "noodles": "麵", "bread": "麵包", "cake": "蛋糕", "cookie": "餅乾",
    "coffee": "咖啡", "tea": "茶", "milk": "牛奶", "juice": "果汁", "wine": "酒",
    "beer": "啤酒", "water": "水", "soup": "湯", "salad": "沙拉", "egg": "蛋",
    # 活動與事件
    "event": "活動", "party": "派對", "wedding": "婚禮", "birthday": "生日",
    "concert": "演唱會", "festival": "節日", "ceremony": "典禮", "meeting": "會議",
    "sports": "運動", "game": "遊戲", "match": "比賽", "race": "賽跑",
    "swimming": "游泳", "running": "跑步", "walking": "走路", "hiking": "健行",
    "camping": "露營", "fishing": "釣魚", "shopping": "購物", "cooking": "烹飪",
    "eating": "吃", "drinking": "喝", "sleeping": "睡覺", "reading": "閱讀",
    "writing": "寫作", "painting": "畫畫", "singing": "唱歌", "dancing": "跳舞",
    # 顏色（常見描述）
    "red": "紅色", "blue": "藍色", "green": "綠色", "yellow": "黃色",
    "orange": "橙色", "purple": "紫色", "pink": "粉色", "black": "黑色",
    "white": "白色", "gray": "灰色", "grey": "灰色", "brown": "棕色",
    "colorful": "彩色", "bright": "明亮", "dark": "黑暗", "light": "淺色",
    # 時間與天氣
    "morning": "早上", "afternoon": "下午", "evening": "傍晚", "night": "晚上",
    "sunset": "日落", "sunrise": "日出", "sunny": "晴天", "rainy": "雨天",
    "cloudy": "陰天", "snowy": "雪天", "windy": "有風", "hot": "熱", "cold": "冷",
    "warm": "溫暖", "cool": "涼爽",
    # 材質與形狀
    "wooden": "木製", "metal": "金屬", "glass": "玻璃", "stone": "石頭",
    "plastic": "塑膠", "leather": "皮革", "round": "圓形", "square": "方形",
    "long": "長", "short": "短", "tall": "高", "big": "大", "small": "小",
    "large": "大", "tiny": "很小", "wide": "寬", "narrow": "窄",
    # 情緒與氛圍
    "happy": "開心", "sad": "悲傷", "angry": "生氣", "scared": "害怕",
    "surprised": "驚訝", "peaceful": "寧靜", "calm": "平靜", "busy": "忙碌",
    "quiet": "安靜", "noisy": "吵鬧", "beautiful": "美麗", "ugly": "醜",
    "cute": "可愛", "funny": "有趣", "scary": "恐怖", "dangerous": "危險",
    "safe": "安全", "clean": "乾淨", "dirty": "骯髒", "new": "新", "old": "舊",
    # 日常物品
    "bag": "包包", "backpack": "背包", "umbrella": "雨傘", "hat": "帽子",
    "cap": "棒球帽", "glasses": "眼鏡", "sunglasses": "太陽眼鏡", "watch": "手錶",
    "ring": "戒指", "necklace": "項鍊", "earring": "耳環", "shoe": "鞋",
    "shoes": "鞋", "boot": "靴子", "shirt": "上衣", "pants": "褲子",
    "dress": "洋裝", "skirt": "裙子", "jacket": "外套", "coat": "大衣",
    "uniform": "制服", "jeans": "牛仔褲", "tie": "領帶", "glove": "手套",
    # 公共設施
    "bench": "長凳", "pole": "電線桿", "lamppost": "路燈", "sign": "標誌",
    "signboard": "招牌", "traffic light": "紅綠燈", "stop sign": "停車標誌",
    "fence": "圍籬", "gate": "大門", "tower": "塔", "statue": "雕像",
    "graffiti": "塗鴉", "poster": "海報", "banner": "橫幅",
    # 植物細節
    "flower": "花", "rose": "玫瑰", "sunflower": "向日葵", "lotus": "蓮花",
    "cherry blossom": "櫻花", "tulip": "鬱金香", "leaf": "葉子",
    "branch": "樹枝", "root": "根", "stem": "莖", "grass": "草",
    "moss": "苔蘚", "bamboo": "竹子", "cactus": "仙人掌", "palm": "棕櫚樹",
}
# ==========================================


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

    # 先找中文關鍵字（直接匹配）
    for en_word, zh_word in KEYWORD_MAP.items():
        # 跳過單一字母
        if len(en_word) <= 2 and en_word not in ("tv", "pc"):
            continue
        # 用正規表示法匹配完整單詞
        pattern = r'\b' + re.escape(en_word) + r'(s)?\b'
        if re.search(pattern, desc_lower):
            if zh_word not in found_zh:
                found_zh.append(zh_word)
                found_en.append(en_word)

    return found_en, found_zh


def format_keywords_for_exif(en_keywords: list, zh_keywords: list) -> str:
    """
    格式化關鍵字為 EXIF 寫入格式
    格式: "EN: keyword1, keyword2 | 中: 關鍵字1, 關鍵字2"
    """
    en_str = ", ".join(en_keywords) if en_keywords else "N/A"
    zh_str = ", ".join(zh_keywords) if zh_keywords else "N/A"
    return f"EN: {en_str} | 中: {zh_str}"


def write_exif(image_path: str, description: str, en_keywords: list, zh_keywords: list) -> bool:
    """將描述和關鍵字寫入圖片的 EXIF"""
    try:
        exif_dict = piexif.load(image_path)
    except ValueError:
        exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}

    # 組合 EXIF 文字：描述 + 關鍵字
    keywords_str = format_keywords_for_exif(en_keywords, zh_keywords)
    full_text = f"{description}\n\n[{keywords_str}]"

    # UserComment (0th tag 37510)
    comment_bytes = b"UTF-8\x00\x00\x00" + full_text.encode("utf-8")
    exif_dict["0th"][37510] = comment_bytes

    # DateTime (306 tag)
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
        # 1. 分析圖片
        print(f"  🔍 正在分析圖片...")
        description = analyze_image(image_path, ollama_api, model_name)
        print(f"  📝 描述: {description[:80]}{'...' if len(description) > 80 else ''}")

        # 2. 抽出關鍵字
        print(f"  🏷️  正在抽取關鍵字...")
        en_kw, zh_kw = extract_keywords(description)
        print(f"      英文: {', '.join(en_kw) if en_kw else '無'}")
        print(f"      中文: {', '.join(zh_kw) if zh_kw else '無'}")

        # 3. 寫入 EXIF
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
    parser.add_argument("folder", help="要處理的資料夾路徑")
    parser.add_argument("--extensions", nargs="+", default=["jpg", "jpeg", "png", "webp"],
                        help="要處理的副檔名 (預設: jpg png webp)")
    parser.add_argument("--dry-run", action="store_true",
                        help="僅分析，不寫入 EXIF")
    parser.add_argument("--output", "-o", default="analysis_result.json",
                        help="結果輸出檔案 (預設: analysis_result.json)")
    parser.add_argument("--ollama-api", default=DEFAULT_OLLAMA_API,
                        help=f"Ollama API URL (預設: {DEFAULT_OLLAMA_API})")
    parser.add_argument("--model", "-m", default=DEFAULT_MODEL_NAME,
                        help=f"模型名稱 (預設: {DEFAULT_MODEL_NAME})")
    args = parser.parse_args()

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
