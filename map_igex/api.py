from fastapi import FastAPI, HTTPException, Request
from typing import List, Dict
from pydantic import BaseModel
import s  # 直接導入同目錄下的s.py
from config import get_raw_data_file, api_logger, error_logger  # 導入配置和日誌記錄器
from presplit import presplit_manager  # 導入預分拆管理器
import time
import json

app = FastAPI(
    title="數值拆分服務",
    description="輸入一個目標值，返回拆分結果",
    version="1.0.0"
)

# 在應用啟動時啟動預分拆任務
@app.on_event("startup")
async def startup_event():
    presplit_manager.start_background_task()
    api_logger.info("預分拆服務已啟動")

# 在應用關閉時停止預分拆任務
@app.on_event("shutdown")
async def shutdown_event():
    presplit_manager.stop_background_task()
    api_logger.info("預分拆服務已停止")

class Result(BaseModel):
    name: str
    value: float
    url: str

class SplitResponse(BaseModel):
    target_value: float
    results: List[Result]
    total_value: float
    error: float

class PreSplitStats(BaseModel):
    total_target_values: int
    total_combinations: int
    average_combinations: float

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

@app.get("/presplit/stats", response_model=PreSplitStats)
async def get_presplit_stats():
    """獲取預分拆統計信息"""
    return presplit_manager.get_statistics()

@app.get("/split/{target_value}", response_model=SplitResponse)
async def split_value(target_value: float, retry_count: int = 0):
    """處理拆分請求並返回結果"""
    # 將目標值轉換為整數
    target_value = int(target_value)
    api_logger.info(f"Processing split request for target_value: {target_value}, retry: {retry_count}")
    
    try:
        if retry_count >= 3:  # 限制最大重試次數
            error_msg = f"達到最大重試次數 (3)"
            api_logger.warning(error_msg)
            raise HTTPException(
                status_code=400,
                detail=error_msg
            )

        if not (300 <= target_value <= 5000):
            error_msg = f"目標值 {target_value} 超出範圍 (300-5000)"
            api_logger.warning(error_msg)
            raise HTTPException(
                status_code=400, 
                detail=error_msg
            )
        
        # 首先嘗試使用預分拆結果
        presplit_results = presplit_manager.get_split(target_value)
        if presplit_results:
            api_logger.info(f"Found pre-split result for {target_value}")
            # 直接使用預分拆的結果
            results = [Result(**item) for item in presplit_results[0]]
            total_value = int(sum(r.value for r in results))
            error = target_value - total_value
            api_logger.info(f"Using pre-split result with total: {total_value}, error: {error}")
        else:
            # 如果沒有預分拆結果，使用實時分拆
            api_logger.info(f"No pre-split result found, using real-time split")
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
            
            # 將所有部分轉換為整數
            parts = tuple(int(p) for p in parts)
            api_logger.info(f"Split values: {parts}")
            
            # 查找匹配值
            results = []
            failed_parts = []
            for part in parts:
                result = s.find_similar_in_files(part, file_paths)
                if result:
                    results.append(Result(
                        name=result[0],
                        value=int(result[1]),  # 確保值為整數
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
            total_value = int(sum(r.value for r in results))
            error = target_value - total_value
            api_logger.info(f"Initial total: {total_value}, error: {error}")
            
            # 檢查總和是否超過目標值
            if total_value > target_value:
                api_logger.warning(f"Total value {total_value} exceeds target {target_value}, retrying...")
                # 遞迴調用自身進行重試，增加重試計數
                return await split_value(target_value, retry_count + 1)
            
            # 如果誤差過大，嘗試補償（只在總和小於目標值時）
            if error > 0:  # 對於整數，只要有誤差就嘗試補償
                api_logger.info(f"Attempting to compensate error: {error}")
                compensation = s.find_compensation_value(error, file_paths)
                if compensation:
                    # 檢查補償後的總和是否會超過目標值
                    new_total = total_value + int(compensation[1])
                    if new_total <= target_value:
                        results.append(Result(
                            name=compensation[0],
                            value=int(compensation[1]),  # 確保值為整數
                            url=compensation[2]
                        ))
                        total_value = new_total
                        error = target_value - total_value
                        api_logger.info(f"Added compensation: {compensation}")
                        api_logger.info(f"Final total: {total_value}, error: {error}")
                    else:
                        api_logger.warning(f"Skipped compensation as it would exceed target value")
            
            # 將成功的分拆結果添加到預分拆快取
            if total_value <= target_value:
                presplit_manager.add_split(target_value, [
                    {
                        "name": r.name,
                        "value": int(r.value),  # 確保值為整數
                        "url": r.url
                    } for r in results
                ])
        
        # 準備響應數據
        response_data = SplitResponse(
            target_value=target_value,
            results=results,
            total_value=total_value,
            error=error
        )
        
        # 記錄完整的響應數據
        api_logger.info(f"Response data: {json.dumps(response_data.dict(), ensure_ascii=False)}")
        
        return response_data
        
    except Exception as e:
        error_logger.error(f"Error processing split request: {str(e)}", exc_info=True)
        raise