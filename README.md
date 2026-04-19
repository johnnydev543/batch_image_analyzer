# Batch Image Analyzer

批次圖片分析工具，使用 Ollama 本地 Moondream 模型自動分析圖片內容並寫入 EXIF。

## 功能

- 🔍 批次掃描資料夾內的圖片
- 🤖 使用 Moondream 模型分析圖片
- 📝 自動寫入 EXIF UserComment（完整描述）
- 📄 結果輸出為 JSON manifest

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

### 環境變數（推薦）

```bash
# 設定 API 位址
export OLLAMA_API=http://my-custom-host:11434/api/chat
export MODEL_NAME=moondream

# 執行
python3 batch_image_analyzer.py ~/sshd/data/pics/test/ --dry-run
```

### 命令列引數

```bash
# 直接指定
python3 batch_image_analyzer.py ~/sshd/data/pics/test/ \
  --ollama-api http://my-custom-host:11434/api/chat \
  --model moondream \
  --dry-run
```

### 全部範例

```bash
# 基本用法（分析並寫入 EXIF）
python3 batch_image_analyzer.py /path/to/photos

# 僅測試，不寫入 EXIF
python3 batch_image_analyzer.py /path/to/photos --dry-run

# 指定副檔名
python3 batch_image_analyzer.py /path/to/photos --extensions jpg png webp

# 指定輸出檔名
python3 batch_image_analyzer.py /path/to/photos -o my_results.json
```

## 輸出格式

執行完成後會產生 `analysis_result.json`，格式如下：

```json
[
  {
    "path": "/path/to/photo1.jpg",
    "description": "一隻黑貓坐在木架上...",
    "status": "success"
  },
  {
    "path": "/path/to/photo2.jpg",
    "description": null,
    "status": "error",
    "error": "錯誤訊息"
  }
]
```

## EXIF 寫入欄位

- `UserComment` (0th, tag 37510): 圖片描述
- `DateTime` (0th, tag 306): 處理時間

## 設定優先順序

命令行引數 > 環境變數 > 預設值

| 設定方式 | 環境變數 | 命令列引數 |
|----------|----------|------------|
| API URL | `OLLAMA_API` | `--ollama-api` |
| 模型名稱 | `MODEL_NAME` | `--model`, `-m` |
