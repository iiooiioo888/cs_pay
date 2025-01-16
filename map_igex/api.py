from fastapi import FastAPI, HTTPException, Request
from typing import List, Dict
from pydantic import BaseModel
import s  # 直接導入同目錄下的s.py
from config import get_raw_data_file, api_logger, error_logger  # 導入配置和日誌記錄器
import time
import json

app = FastAPI(
    title="數值拆分服務",
    description="輸入一個目標值，返回拆分結果",
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

@app.middleware("http")
async def log_requests(request: Request, call_next):
    """記錄所有請求和響應"""
    start_time = time.time()
    
    # 記錄請求信息
    api_logger.info(f"Request: {request.method} {request.url}")
    
    try:
        response = await call_next(request)
        
        # 計算處理時間
        process_time = time.time() - start_time
        
        # 記錄響應信息
        api_logger.info(
            f"Response: status_code={response.status_code}, "
            f"process_time={process_time:.3f}s"
        )
        
        return response
    except Exception as e:
        # 記錄錯誤信息
        error_logger.error(f"Error processing request: {str(e)}", exc_info=True)
        raise

@app.get("/")
async def root():
    api_logger.info("Health check request received")
    return {"message": "數值拆分服務已啟動"}

@app.get("/split/{target_value}", response_model=SplitResponse)
async def split_value(target_value: float):
    """處理拆分請求並返回結果"""
    api_logger.info(f"Processing split request for target_value: {target_value}")
    
    try:
        if not (300 <= target_value <= 5000):
            error_msg = f"目標值 {target_value} 超出範圍 (300-5000)"
            api_logger.warning(error_msg)
            raise HTTPException(
                status_code=400, 
                detail=error_msg
            )
        
        # 使用配置中定義的文件路徑
        file_paths = [get_raw_data_file(i) for i in range(10, 500, 10)]
        api_logger.debug(f"Using file paths: {file_paths}")
        
        # 預先加載文件內容
        file_contents = s.load_file_contents(file_paths)
        s.load_file_contents.cache['contents'] = file_contents
        
        # 計算拆分數量
        num_parts = s.calculate_optimal_parts(target_value)
        api_logger.info(f"Calculated optimal parts: {num_parts}")
        
        # 拆分值
        parts = s.split_target_value(target_value, num_parts)
        if not parts:
            error_msg = f"無法將目標值 {target_value} 拆分為 {num_parts} 份"
            api_logger.warning(error_msg)
            raise HTTPException(
                status_code=400,
                detail=error_msg
            )
        
        api_logger.info(f"Split values: {parts}")
        
        # 查找匹配值
        results = []
        failed_parts = []
        for part in parts:
            result = s.find_similar_in_files(part, file_paths)
            if result:
                results.append(Result(
                    name=result[0],
                    value=result[1],
                    url=result[2]
                ))
                api_logger.info(f"Found match for {part}: {result}")
            else:
                failed_parts.append(part)
        
        if failed_parts:
            error_msg = f"無法找到以下值的匹配項: {failed_parts}"
            api_logger.warning(error_msg)
            raise HTTPException(
                status_code=404,
                detail=error_msg
            )
        
        # 計算總和與誤差
        total_value = sum(r.value for r in results)
        error = target_value - total_value
        api_logger.info(f"Initial total: {total_value}, error: {error}")
        
        # 如果誤差過大，嘗試補償
        if error > 0.5:
            api_logger.info(f"Attempting to compensate error: {error}")
            compensation = s.find_compensation_value(error, file_paths)
            if not compensation:
                error_msg = f"無法找到合適的補償值來修正誤差 {error}"
                api_logger.warning(error_msg)
                raise HTTPException(
                    status_code=422,
                    detail=error_msg
                )
            
            results.append(Result(
                name=compensation[0],
                value=compensation[1],
                url=compensation[2]
            ))
            total_value += compensation[1]
            error = target_value - total_value
            api_logger.info(f"Added compensation: {compensation}")
            api_logger.info(f"Final total: {total_value}, error: {error}")
        
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
        
        # 記錄完整的響應數據
        api_logger.info(f"Response data: {json.dumps(response_data.dict(), ensure_ascii=False)}")
        
        return response_data
        
    except Exception as e:
        error_logger.error(f"Error processing split request: {str(e)}", exc_info=True)
        raise