# Batch Image Analyzer

批次圖片分析工具，使用 Ollama 本地 Moondream 模型自動分析圖片內容並寫入 EXIF。

## 功能

- 🔍 批次掃描資料夾內的圖片
- 🤖 使用 Moondream 模型分析圖片取得描述
- 🏷️ 從描述自動抽取英中對照關鍵字
- 📝 將描述與關鍵字寫入 EXIF UserComment
- 📄 結果輸出為 JSON manifest
- ☁️ 支援 Google Drive 掛載資料夾

## 需求

- Python 3.8+
- Ollama 運行中，且已下載 `moondream` 模型
- piexif 套件

## 安裝

```bash
# 安裝依賴
pip install piexif
```

## 使用方式

### 環境變數

```bash
export OLLAMA_API=http://my-custom-host:11434/api/chat
export MODEL_NAME=moondream
```

### 命令列引數

```bash
# 基本用法（分析並寫入 EXIF）
python3 batch_image_analyzer.py ~/sshd/data/pics/test/

# 僅測試，不寫入 EXIF
python3 batch_image_analyzer.py ~/sshd/data/pics/test/ --dry-run

# 指定 API 和模型
python3 batch_image_analyzer.py ~/sshd/data/pics/test/ \
  --ollama-api http://my-custom-host:11434/api/chat \
  --model moondream

# 指定副檔名
python3 batch_image_analyzer.py ~/sshd/data/pics/test/ --extensions jpg png webp

# 指定輸出檔名
python3 batch_image_analyzer.py ~/sshd/data/pics/test/ -o custom_results.json
```

## 輸出位置

- **結果 JSON**：預設放在圖片資料夾底下，命名為 `analysis_result.json`
- **EXIF**：直接寫入每張圖片檔案

## EXIF 輸出格式

EXIF UserComment 寫入內容：
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

## 設定優先順序

命令行引數 > 環境變數 > 預設值

| 設定方式 | 環境變數 | 命令列引數 |
|----------|----------|------------|
| API URL | `OLLAMA_API` | `--ollama-api` |
| 模型名稱 | `MODEL_NAME` | `--model`, `-m` |

## 自訂關鍵字翻譯

修改 `keywords.py` 檔案即可新增或編輯關鍵字對照。

## Google Drive 支援

直接指定 Google Drive 掛載路徑即可：
```bash
python3 batch_image_analyzer.py ~/Google\ Drive/My\ Drive/Photos/
```

## 資料夾結構

```
batch_image_analyzer/
├── batch_image_analyzer.py   # 主程式
├── keywords.py              # 關鍵字對照表（可自行編輯）
├── README.md                # 說明文件
└── .gitignore              # Git 忽略設定
```
