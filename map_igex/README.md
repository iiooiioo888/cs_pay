# 數值拆分服務 (Value Splitting Service)

這是一個基於FastAPI的Web服務，用於將目標值智能拆分並生成QR碼。

## 功能特點

- 支持300-5000範圍內的目標值拆分
- 智能計算最佳拆分數量
- 自動補償誤差
- 生成包含完整結果的QR碼
- RESTful API接口
- 自動API文檔

## 安裝

1. 克隆倉庫：
```bash
git clone https://github.com/your-username/value-splitting-service.git
cd value-splitting-service
```

2. 安裝依賴：
```bash
pip install -r requirements.txt
```

## 使用方法

1. 啟動服務：
```bash
python api.py
```

2. 訪問服務：
- API文檔：http://localhost:8000/docs
- 健康檢查：http://localhost:8000/
- 拆分請求：http://localhost:8000/split/{target_value}

## API端點

### GET /split/{target_value}
將目標值拆分並返回QR碼。

參數：
- target_value (float): 要拆分的目標值（300-5000）

返回：
- PNG格式的QR碼圖片
- QR碼內容包含：
  - 目標值
  - 拆分結果列表（ID、值、URL）
  - 總和
  - 誤差

## 錯誤處理

- 400 Bad Request: 目標值超出範圍
- 400 Bad Request: 無法完成拆分
- 404 Not Found: 未找到匹配結果

## 開發環境

- Python 3.8+
- FastAPI
- Uvicorn
- QRCode
- Pillow
- Pydantic

## 授權

MIT License 