# Batch Image Analyzer

批次圖片分析工具，支援 Ollama 本地 Moondream 和 Qwen3-VL 模型，輸出分析結果為 JSON。

## 流程

```
Step 1: batch_image_analyzer.py  →  產生 analysis_result.json
Step 2: write_exif.py           →  將結果寫入圖片 EXIF
```

## 功能

- 🔍 批次掃描資料夾內的圖片
- 🤖 支援 Moondream 和 Qwen3-VL 模型（自動偵測）
- 🏷️ 可選：要求模型輸出關鍵字，或從描述自動抽取英中對照關鍵字
- 📄 結果輸出為 JSON manifest（交給其他程式做進一步處理）

## 需求

- Python 3.8+
- Ollama 運行中
- piexif 套件（僅 write_exif.py 需要）

## 安裝

```bash
pip install piexif
```

## Step 1：分析圖片

```bash
# 基本用法（只做描述分析）
python3 batch_image_analyzer.py ~/photos/

# 開啟關鍵字抽取（5 個）
python3 batch_image_analyzer.py ~/photos/ --keywords

# 指定關鍵字數量
python3 batch_image_analyzer.py ~/photos/ --keywords 8

# Qwen3-VL 模式 + 要求模型直接輸出關鍵字
python3 batch_image_analyzer.py ~/photos/ --model qwen3-vl:2b --keywords 5

# Qwen3-VL + 高解析度
python3 batch_image_analyzer.py ~/photos/ --model qwen3-vl:2b --keywords --detail high
```

輸出：`analysis_result.json`

## Step 2：寫入 EXIF

```bash
# 寫入所有圖片
python3 write_exif.py ~/photos/analysis_result.json

# 只寫入有 description 的圖片
python3 write_exif.py ~/photos/analysis_result.json --require-description
```

## 命令列引數

### batch_image_analyzer.py

| 引數 | 說明 | 預設值 |
|------|------|--------|
| `folder` | 要處理的資料夾路徑 | - |
| `--model`, `-m` | 模型名稱（自動偵測類型） | `moondream` |
| `--keywords`, `-k` | 開啟關鍵字輸出（可指定數量） | 關閉 |
| `--detail` | Qwen3-VL 圖片解析度：`low`, `high`, `auto` | `low` |
| `--ollama-api` | Ollama API URL | `http://ollama:11434` |
| `--result-output` | 結果 JSON 輸出檔案 | `<資料夾>/analysis_result.json` |
| `--extensions` | 要處理的副檔名 | `jpg jpeg png webp` |

### write_exif.py

| 引數 | 說明 |
|------|------|
| `json_file` | 分析結果 JSON 檔案 |
| `--require-description` | 只寫入有 description 的圖片 |

## 實用範例

```bash
# 批次分析（描述模式）
python3 batch_image_analyzer.py ./photos/

# 用 2B 模型快速提取關鍵字
python3 batch_image_analyzer.py ./photos/ --model qwen3-vl:2b --keywords

# 處理完後寫入 EXIF
python3 write_exif.py ./photos/analysis_result.json
```

## JSON 輸出格式

```json
[
  {
    "path": "/path/to/photo1.jpg",
    "description": "一隻黑貓坐在木架上...",
    "keywords_en": ["cat", "shelf", "wooden"],
    "keywords_zh": ["貓", "架子", "木製"],
    "status": "success"
  }
]
```

## 自訂關鍵字翻譯（僅 Moondream 模式）

修改 `keywords.py` 檔案即可新增或編輯關鍵字對照。

## 資料夾結構

```
batch_image_analyzer/
├── batch_image_analyzer.py   # 主程式（分析圖片）
├── write_exif.py            # EXIF 寫入工具
├── keywords.py              # 關鍵字對照表
├── README.md                # 說明文件
└── .gitignore               # Git 忽略設定
```
