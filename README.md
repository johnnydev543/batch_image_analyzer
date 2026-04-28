# Batch Image Analyzer

批次圖片分析工具，支援 Ollama 本地 Moondream 和 Qwen3-VL 模型，自動分析圖片內容並寫入 EXIF。

## 功能

- 🔍 批次掃描資料夾內的圖片
- 🤖 支援 Moondream 和 Qwen3-VL 模型（自動偵測）
- 🏷️ 可選：要求模型輸出關鍵字，或從描述自動抽取英中對照關鍵字
- 📝 將描述與關鍵字寫入 EXIF UserComment
- 📄 結果輸出為 JSON manifest
- ☁️ 支援 Google Drive 掛載資料夾

## 需求

- Python 3.8+
- Ollama 運行中
- piexif 套件

## 安裝

```bash
pip install piexif
```

## 使用方式

### 基本用法（只做描述分析）

```bash
# Moondream 模式（預設）
python3 batch_image_analyzer.py ~/photos/

# 指定模型（自動偵測是否為 Qwen3-VL）
python3 batch_image_analyzer.py ~/photos/ --model qwen3-vl:2b
```

### 開啟關鍵字抽取

```bash
# Moondream 模式 + 自動抽取關鍵字（5 個）
python3 batch_image_analyzer.py ~/photos/ --keywords

# 指定關鍵字數量
python3 batch_image_analyzer.py ~/photos/ --keywords 8

# Qwen3-VL 模式 + 要求模型直接輸出關鍵字
python3 batch_image_analyzer.py ~/photos/ --model qwen3-vl:2b --keywords 5

# Qwen3-VL + 高解析度
python3 batch_image_analyzer.py ~/photos/ --model qwen3-vl:2b --keywords --detail high
```

## 命令列引數

| 引數 | 說明 | 預設值 |
|------|------|--------|
| `folder` | 要處理的資料夾路徑 | - |
| `--model`, `-m` | 模型名稱（自動偵測類型） | `moondream` |
| `--keywords`, `-k` | 開啟關鍵字輸出（可指定數量） | 關閉 |
| `--detail` | Qwen3-VL 圖片解析度：`low`, `high`, `auto` | `low` |
| `--ollama-api` | Ollama API URL | `http://ollama:11434` |
| `--dry-run` | 僅分析，不寫入 EXIF | `False` |
| `--extensions` | 要處理的副檔名 | `jpg jpeg png webp` |

## 實用範例

```bash
# 快速批次分析（描述模式）
python3 batch_image_analyzer.py ./photos/

# 用 2B 模型快速提取關鍵字
python3 batch_image_analyzer.py ./photos/ --model qwen3-vl:2b --keywords

# 用 2B 模型提取 8 個關鍵字
python3 batch_image_analyzer.py ./photos/ --model qwen3-vl:2b --keywords 8

# 高解析度模式處理精細圖片
python3 batch_image_analyzer.py ./photos/ --model qwen3-vl:8b --keywords --detail high

# 批次處理多個資料夾
for dir in ./photos/*/; do
    python3 batch_image_analyzer.py "$dir" --model qwen3-vl:2b --keywords
done
```

## 速度 vs 精確度（Qwen3-VL）

| 模型 | 速度 | 適用場景 |
|------|------|----------|
| `qwen3-vl:2b` | ⚡ 最快 (~2-5s/圖) | 快速篩選、大量圖片 |
| `qwen3-vl:4b` | ⚡ 快 (~3-7s/圖) | 一般批次處理 |
| `qwen3-vl:8b` | 🐢 中等 (~5-12s/圖) | 需要較高精確度 |

### 解析度設定

| 設定 | 速度 | 適用場景 |
|------|------|----------|
| `low` | ⚡ 最快 | 文件、截圖、監控畫面 |
| `high` | 🐢 較慢 | 照片、風景、細節圖片 |

## 環境變數

```bash
export OLLAMA_API=http://my-custom-host:11434
export MODEL_NAME=qwen3-vl:2b
```

## 輸出位置

- **結果 JSON**：預設放在圖片資料夾底下，命名為 `analysis_result.json`
- **EXIF**：直接寫入每張圖片檔案

## EXIF 輸出格式

```
[描述文字]

[EN: keyword1, keyword2 | 中: 關鍵字1, 關鍵字2]
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

## Google Drive 支援

```bash
python3 batch_image_analyzer.py --drive-url https://drive.google.com/drive/folders/xxxxx -O ~/downloads/photos/
```

## 自訂關鍵字翻譯（僅 Moondream 模式）

修改 `keywords.py` 檔案即可新增或編輯關鍵字對照。
