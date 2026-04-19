# ============ 關鍵字英中對照表 ============
# 此檔案為批次圖片分析工具的關鍵字對照表
# 修改此檔案即可自訂關鍵字翻譯

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
    "student": "學生", "worker": "工人", "crowd": "人群",
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
    "fruit": "水果", "vegetable": "蔬菜", "meat": "肉", "rice": "米飯",
    "noodle": "麵", "noodles": "麵", "bread": "麵包", "cake": "蛋糕", "cookie": "餅乾",
    "coffee": "咖啡", "tea": "茶", "milk": "牛奶", "juice": "果汁", "wine": "酒",
    "beer": "啤酒", "soup": "湯", "salad": "沙拉", "egg": "蛋",
    # 活動與事件
    "event": "活動", "party": "派對", "wedding": "婚禮", "birthday": "生日",
    "concert": "演唱會", "festival": "節日", "ceremony": "典禮", "meeting": "會議",
    "sports": "運動", "game": "遊戲", "match": "比賽", "race": "賽跑",
    "swimming": "游泳", "running": "跑步", "walking": "走路", "hiking": "健行",
    "camping": "露營", "fishing": "釣魚", "shopping": "購物", "cooking": "烹飪",
    "eating": "吃", "drinking": "喝", "sleeping": "睡覺", "reading": "閱讀",
    "writing": "寫作", "painting": "畫畫", "singing": "唱歌", "dancing": "跳舞",
    # 顏色
    "red": "紅色", "blue": "藍色", "green": "綠色", "yellow": "黃色",
    "orange": "橙色", "purple": "紫色", "pink": "粉色", "black": "黑色",
    "white": "白色", "gray": "灰色", "grey": "灰色", "brown": "棕色",
    "colorful": "彩色", "bright": "明亮", "dark": "黑暗",
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
    # 植物
    "rose": "玫瑰", "sunflower": "向日葵", "lotus": "蓮花",
    "cherry blossom": "櫻花", "tulip": "鬱金香", "bamboo": "竹子", "cactus": "仙人掌", "palm": "棕櫚樹",
}
