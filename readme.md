# 數值拆分服務 (Value Splitting Service)

這是一個基於FastAPI的Web服務，用於將目標值智能拆分。

## 功能特點

- 支持300-5000範圍內的目標值拆分
- 智能計算最佳拆分數量
- 自動補償誤差
- JSON格式的響應數據
- RESTful API接口
- 自動API文檔

## 系統要求

- Python 3.8+
- Windows/Linux/MacOS

## 安裝步驟

1. 克隆倉庫：
```bash
git clone https://github.com/iiooiioo888/igex.git
cd igex
```

2. 創建並激活虛擬環境（可選但推薦）：
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/MacOS
python3 -m venv venv
source venv/bin/activate
```

3. 安裝依賴：
```bash
pip install -r requirements.txt
```

4. 準備數據目錄：
```bash
# Windows
mkdir data\raw data\processed data\logs

# Linux/MacOS
mkdir -p data/raw data/processed data/logs
```

## 配置

服務配置位於 `config.py`，可以根據需要修改以下參數：

- `API_HOST`: API 服務監聽地址（默認: "0.0.0.0"）
- `API_PORT`: API 服務端口（默認: 8000）
- `API_RELOAD`: 是否啟用熱重載（默認: True）
- `MIN_VALUE`: 最小拆分值（默認: 300）
- `MAX_VALUE`: 最大拆分值（默認: 5000）

## 運行服務

1. 啟動服務：
```bash
python run.py
```

服務啟動後可以通過以下地址訪問：

- API文檔：http://localhost:8000/docs
- 健康檢查：http://localhost:8000/
- 拆分請求：http://localhost:8000/split/{target_value}

## API使用說明

### GET /split/{target_value}

將目標值拆分並返回結果。

參數：
- `target_value` (float): 要拆分的目標值（300-5000）

返回：
- JSON格式的響應數據，包含：
  ```json
  {
    "target_value": 654.0,
    "results": [
      {
        "name": "item1",
        "value": 220.5,
        "url": "http://example.com/item1"
      },
      {
        "name": "item2",
        "value": 433.5,
        "url": "http://example.com/item2"
      }
    ],
    "total_value": 654.0,
    "error": 0.0
  }
  ```

示例請求：
```bash
curl http://localhost:8000/split/654
```

## 錯誤處理

服務會返回以下錯誤碼：

- 400 Bad Request: 目標值超出範圍（300-5000）
- 400 Bad Request: 無法完成拆分
- 404 Not Found: 未找到匹配結果
- 500 Internal Server Error: 服務器內部錯誤

## 數據文件

服務需要在 `data/raw/` 目錄下準備以下格式的CSV文件：

```csv
name,value,url
item1,95.5,http://example.com/item1
item2,85.3,http://example.com/item2
```

文件命名規則：`less_than_{N}.csv`，其中 N 為 10 的倍數（10-490）。

## 開發環境

- Python 3.8+
- FastAPI
- Uvicorn
- Pydantic

## 授權

MIT License 