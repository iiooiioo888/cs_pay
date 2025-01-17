# 智能數值拆分服務

一個高性能的數值拆分服務，能夠智能地將目標值拆分為多個合適的部分。

## 系統特點

- 高性能：平均響應時間 < 4秒
- 高可靠：成功率 > 88%
- 高並發：支持多用戶同時訪問
- 智能快取：使用多層快取策略
- 自動重試：內建錯誤重試機制

## 系統要求

- Python 3.8+
- Windows/Linux/MacOS
- 8GB+ RAM 建議

## 安裝步驟

1. 創建並激活虛擬環境：

Windows:
```bash
python -m venv venv
.\venv\Scripts\activate
```

Linux/MacOS:
```bash
python3 -m venv venv
source venv/bin/activate
```

2. 安裝依賴：
```bash
pip install -r requirements.txt
```

3. 準備數據目錄：
```bash
mkdir -p data/raw
mkdir -p data/processed
```

## 配置

主要配置項在 `config.py` 中：

- 文件路徑配置
- 日誌配置
- 快取配置
- 性能調優參數

## 運行服務

啟動服務：
```bash
python run.py
```

服務將在 http://localhost:8000 運行，API 文檔可在 http://localhost:8000/docs 查看。

## API 使用說明

### 拆分值 API

- 端點：`/split/{target_value}`
- 方法：GET
- 參數：
  - target_value：要拆分的目標值（300-5000）
- 業務邏輯限制：
  - 拆分結果的總和不能超過目標值
  - 建議總和略小於目標值
- 返回：JSON 格式的拆分結果

示例請求：
```bash
curl http://localhost:8000/split/388
```

示例響應：
```json
{
    "target_value": 388,
    "results": [
        {
            "name": "value1",
            "value": 194,
            "url": "url1"
        },
        {
            "name": "value2",
            "value": 194,
            "url": "url2"
        }
    ],
    "total_value": 388,
    "error": 0
}
```

## 性能指標

- P50 響應時間：3.6秒
- P95 響應時間：5.7秒
- P99 響應時間：5.8秒
- 每秒請求數 (QPS)：~1.3
- 並發支持：20+ 同時請求

## 錯誤處理

系統會返回以下 HTTP 狀態碼：

- 200：成功
- 404：找不到合適的拆分結果
- 400：請求參數錯誤
- 500：服務器內部錯誤

## 數據文件

### 格式要求

CSV 文件格式：
```
name,value,url
value1,194.0,url1
value2,194.0,url2
```

### 文件分類

- `data/raw/`：原始數據文件
- `data/processed/`：
  - `used_values.csv`：已使用的值
  - `unused_values.csv`：未使用的值

## 優化特性

1. 多層快取機制：
   - 內存快取
   - 文件快取
   - 預排序快取

2. 智能查找算法：
   - 二分查找
   - 預排序優化
   - 動態調整策略

3. 並發處理：
   - 線程安全設計
   - 原子操作
   - 鎖機制優化

4. 錯誤處理：
   - 自動重試機制
   - 錯誤日誌記錄
   - 異常恢復

## 監控和日誌

- 詳細的操作日誌 (`logs/`)
- 性能監控指標
- 錯誤追蹤
- 狀態報告

## 注意事項

1. 首次運行可能需要初始化數據文件
2. 建議定期備份數據文件
3. 監控系統資源使用情況
4. 適時清理日誌文件 