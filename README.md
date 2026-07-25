# Batch Image Analyzer

批次圖片分析工具，透過 OpenAI 相容 API（如 MLX server）呼叫視覺語言模型分析圖片，並可將結果寫入圖片 EXIF。

## 流程

```
Step 1: batch_image_analyzer.py  →  呼叫 VL 模型分析圖片，產生 analysis_result.json
Step 2: write_exif.py           →  將指定欄位寫入圖片 EXIF UserComment
```

## 功能

- 🔍 批次掃描資料夾內的圖片（jpg / jpeg / png / webp）
- 🤖 支援 OpenAI 相容 API 的視覺模型（Qwen3-VL 等）
- 📝 可用 `--prompt` 控制生成語言／風格
- 🏷️ 關鍵字 pipeline：可選擇呼叫另一個文字模型從描述生成關鍵字，或從描述本地抽取
- 📄 結果輸出為 JSON manifest
- 🖼️ 將分析結果（描述、關鍵字等）寫入圖片 EXIF，支援 jpg / webp / png

## 需求

- Python 3.8+
- 一個運行中的 OpenAI 相容 API server（如 [MLX server](https://github.com/ml-explore/mlx-examples)）
- 套件：`pillow`、`piexif`

## 安裝

```bash
pip install pillow piexif
```

## Step 1：分析圖片

```bash
# 基本用法（只做描述分析）
python3 batch_image_analyzer.py ~/photos/ \
  --ollama-api http://localhost:8000/v1 \
  --model Qwen3-VL-4B-Instruct-MLX-4bit \
  --api-key omlx

# 用 --prompt 控制生成語言
python3 batch_image_analyzer.py ~/photos/ \
  --ollama-api http://localhost:8000/v1 \
  --model Qwen3-VL-4B-Instruct-MLX-4bit \
  --api-key omlx \
  --prompt "用繁體中文描述這張圖片"

# 開啟關鍵字 pipeline（預設 15 個，呼叫 --kw-model 生成）
python3 batch_image_analyzer.py ~/photos/ \
  --ollama-api http://localhost:8000/v1 \
  --model Qwen3-VL-4B-Instruct-MLX-4bit \
  --api-key omlx \
  --keywords 20 \
  --kw-model Qwen3-8B-Instruct-MLX-4bit

# 開啟關鍵字但只用本地抽取（不呼叫關鍵字模型）
python3 batch_image_analyzer.py ~/photos/ \
  --ollama-api http://localhost:8000/v1 \
  --model Qwen3-VL-4B-Instruct-MLX-4bit \
  --api-key omlx \
  --keywords 15
```

輸出：`<資料夾>/analysis_result.json`

> **注意**：Qwen3-VL 透過 MLX server 時，API 呼叫只送圖片；`--prompt` 會以 text+image 形式送出，視模型是否遵循而定。若模型忽略 text，請改用支援 text+image 的模型，或事後用文字模型翻譯。

## Step 2：寫入 EXIF

```bash
# 預設寫入 description
python3 write_exif.py ~/photos/analysis_result.json

# 寫入 description + keywords（keywords 為簡寫，自動合併 keywords_en + keywords_zh）
python3 write_exif.py ~/photos/analysis_result.json -f description keywords

# 只寫入關鍵字
python3 write_exif.py ~/photos/analysis_result.json -f keywords

# 直接使用 JSON 實際欄位名
python3 write_exif.py ~/photos/analysis_result.json -f keywords_en keywords_zh

# 只寫入有 description 的圖片
python3 write_exif.py ~/photos/analysis_result.json --require-description
```

> 支援 jpg / webp / png 三種格式；webp 與 png 透過 PIL 寫入 EXIF。

## 命令列引數

### batch_image_analyzer.py

| 引數 | 說明 | 預設值 |
|------|------|--------|
| `folder` | 要處理的資料夾路徑 | - |
| `--ollama-api` | API URL（OpenAI 相容端點基底，如 `http://localhost:8000/v1`） | 環境變數 `MODEL_API`，未設定必填 |
| `--model`, `-m` | 模型名稱 | 環境變數 `MODEL_NAME`，未設定必填 |
| `--api-key` | API key | `omlx` 或環境變數 `MODEL_API_KEY`/`OPENAI_API_KEY` |
| `--prompt`, `-p` | 自訂 prompt 帶入 VL 模型（控制語言／風格） | 無 |
| `--keywords`, `-k` | 開啟關鍵字 pipeline（可指定數量） | 關閉（指定時預設 15） |
| `--kw-model` | 關鍵字生成模型（另一個文字模型） | 環境變數 `KEYWORD_MODEL`，未指定則只從描述本地抽取 |
| `--kw-api` | 關鍵字模型 API URL | 沿用主 `--ollama-api` |
| `--kw-api-key` | 關鍵字模型 API key | 沿用主 `--api-key` |
| `--detail` | 圖片解析度：`low`, `high`, `auto` | `low` |
| `--num-ctx` | context length / KV Cache 大小 | `8192` |
| `--max-image-pixels` | 圖片最大邊長，超過自動縮圖 | `2048` |
| `--extensions` | 要處理的副檔名 | `jpg jpeg png webp` |
| `--result-output` | 結果 JSON 輸出檔案 | `<資料夾>/analysis_result.json` |
| `--drive-url`, `-d` | Google Drive 資料夾連結（需搭配 `-O`） | 無 |
| `--output`, `-O` | 下載目標資料夾（使用 `--drive-url` 時必填） | 無 |

### write_exif.py

| 引數 | 說明 |
|------|------|
| `json_file` | 分析結果 JSON 檔案 |
| `--field`, `-f` | 要寫入 EXIF 的欄位，可多選，預設 `description`。特殊簡寫：`description`、`keywords`（合併 `keywords_en`+`keywords_zh`）、`path`、`status`；或直接用 JSON 實際欄位名 |
| `--output`, `-O` | 圖片所在資料夾 |
| `--require-description` | 只寫入有 description 的圖片 |

## 環境變數

| 變數 | 用途 | 預設 |
|------|------|------|
| `MODEL_API` | 主模型 API URL | 無（必填或用 `--ollama-api`） |
| `MODEL_NAME` | 主模型名稱 | 無（必填或用 `--model`） |
| `MODEL_API_KEY` / `OPENAI_API_KEY` | API key | `omlx` |
| `KEYWORD_MODEL` | 關鍵字生成模型 | 無 |
| `KEYWORD_API` | 關鍵字模型 API URL | 沿用 `MODEL_API` |
| `KEYWORD_API_KEY` | 關鍵字模型 API key | 沿用主 key |

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

## 實用範例

```bash
# 完整流程：分析 + 寫入描述與關鍵字
python3 batch_image_analyzer.py ./photos/ \
  --ollama-api http://localhost:8000/v1 \
  --model Qwen3-VL-4B-Instruct-MLX-4bit \
  --api-key omlx \
  --keywords 20 \
  --kw-model Qwen3-8B-Instruct-MLX-4bit

python3 write_exif.py ./photos/analysis_result.json -f description keywords

# 只做描述分析，不生成關鍵字
python3 batch_image_analyzer.py ./photos/ \
  --ollama-api http://localhost:8000/v1 \
  --model Qwen3-VL-4B-Instruct-MLX-4bit \
  --api-key omlx

python3 write_exif.py ./photos/analysis_result.json
```

## 資料夾結構

```
batch_image_analyzer/
├── batch_image_analyzer.py   # 主程式（分析圖片）
├── write_exif.py            # EXIF 寫入工具
├── keywords.py              # （舊版關鍵字對照表，目前已不再使用）
├── README.md                # 說明文件
└── .venv/                   # 虛擬環境
```
