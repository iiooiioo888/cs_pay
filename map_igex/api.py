from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
import qrcode
from io import BytesIO
import json
from typing import List, Dict
import uvicorn
from pydantic import BaseModel
import s  # 直接導入同目錄下的s.py
from config import get_raw_data_file  # 導入配置

app = FastAPI(
    title="數值拆分服務",
    description="輸入一個目標值，返回拆分結果的QR碼",
    version="1.0.0"
)

class Result(BaseModel):
    name: str
    value: float
    url: str

class SplitResponse(BaseModel):
    target_value: float
    results: List[Result]
    total_value: float
    error: float

def generate_qr(data: Dict) -> BytesIO:
    """生成QR碼"""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(json.dumps(data, ensure_ascii=False))
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    
    # 將圖片轉換為bytes
    img_byte_arr = BytesIO()
    img.save(img_byte_arr, format='PNG')
    img_byte_arr.seek(0)
    
    return img_byte_arr

@app.get("/")
async def root():
    return {"message": "數值拆分服務已啟動"}

@app.get("/split/{target_value}")
async def split_value(target_value: float):
    """處理拆分請求並返回QR碼"""
    if not (300 <= target_value <= 5000):
        raise HTTPException(
            status_code=400, 
            detail="目標值必須在300到5000之間"
        )
    
    # 使用配置中定義的文件路徑
    file_paths = [get_raw_data_file(i) for i in range(10, 500, 10)]
    
    # 預先加載文件內容
    file_contents = s.load_file_contents(file_paths)
    s.load_file_contents.cache['contents'] = file_contents
    
    # 計算拆分數量
    num_parts = s.calculate_optimal_parts(target_value)
    
    # 拆分值
    parts = s.split_target_value(target_value, num_parts)
    if not parts:
        raise HTTPException(
            status_code=400,
            detail="無法完成拆分"
        )
    
    # 查找匹配值
    results = []
    for part in parts:
        result = s.find_similar_in_files(part, file_paths)
        if result:
            results.append(Result(
                name=result[0],
                value=result[1],
                url=result[2]
            ))
    
    if not results:
        raise HTTPException(
            status_code=404,
            detail="未找到匹配結果"
        )
    
    # 計算總和與誤差
    total_value = sum(r.value for r in results)
    error = target_value - total_value
    
    # 如果誤差過大，嘗試補償
    if error > 0.5:
        compensation = s.find_compensation_value(error, file_paths)
        if compensation:
            results.append(Result(
                name=compensation[0],
                value=compensation[1],
                url=compensation[2]
            ))
            total_value += compensation[1]
            error = target_value - total_value
    
    # 準備響應數據
    response_data = SplitResponse(
        target_value=target_value,
        results=[{
            "name": r.name,
            "value": r.value,
            "url": r.url
        } for r in results],
        total_value=total_value,
        error=error
    )
    
    # 生成QR碼
    qr_image = generate_qr(response_data.dict())
    
    return StreamingResponse(
        qr_image,
        media_type="image/png",
        headers={
            "Content-Disposition": f"attachment; filename=split_result_{target_value}.png"
        }
    )