import os
import json
import time
import random
from typing import Dict, List, Tuple
import logging
from logging.handlers import RotatingFileHandler
import threading
from concurrent.futures import ThreadPoolExecutor
import s
from config import get_raw_data_file

# 配置預分拆日誌
presplit_logger = logging.getLogger('presplit')
presplit_logger.setLevel(logging.INFO)

# 創建日誌目錄
log_dir = os.path.join(os.path.dirname(__file__), 'logs')
os.makedirs(log_dir, exist_ok=True)

# 設置日誌處理器
log_file = os.path.join(log_dir, 'presplit.log')
handler = RotatingFileHandler(log_file, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8')
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
presplit_logger.addHandler(handler)

class PreSplitManager:
    def __init__(self):
        self.cache_file = os.path.join(os.path.dirname(__file__), 'data', 'processed', 'presplit_cache.json')
        self.lock = threading.Lock()
        self.cache: Dict[float, List[List[Dict[str, str | float]]]] = {}
        self.load_cache()
        self.running = False
        self._worker_thread = None
    
    def load_cache(self):
        """載入預分拆快取"""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    # 將字符串鍵轉換為浮點數
                    data = json.load(f)
                    self.cache = {float(k): v for k, v in data.items()}
                presplit_logger.info(f"已載入 {len(self.cache)} 個預分拆組合")
        except Exception as e:
            presplit_logger.error(f"載入快取失敗: {str(e)}")
    
    def save_cache(self):
        """保存預分拆快取"""
        try:
            os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, ensure_ascii=False, indent=2)
            presplit_logger.info(f"已保存 {len(self.cache)} 個預分拆組合")
        except Exception as e:
            presplit_logger.error(f"保存快取失敗: {str(e)}")
    
    def get_split(self, target_value: float) -> List[List[Dict[str, str | float]]]:
        """獲取預分拆結果"""
        with self.lock:
            return self.cache.get(target_value, [])
    
    def add_split(self, target_value: float, splits: List[Dict[str, str | float]]):
        """添加預分拆結果"""
        with self.lock:
            if target_value not in self.cache:
                self.cache[target_value] = []
            if splits not in self.cache[target_value]:
                self.cache[target_value].append(splits)
                presplit_logger.info(f"新增預分拆組合: {target_value} -> {splits}")
    
    def generate_splits(self, target_value: float, max_attempts: int = 5) -> List[List[Dict[str, str | float]]]:
        """為指定目標值生成多個可能的分拆組合"""
        splits = []
        attempts = 0
        file_paths = [get_raw_data_file(i) for i in range(10, 500, 10)]
        
        while attempts < max_attempts:
            # 隨機調整拆分數量
            base_parts = s.calculate_optimal_parts(target_value)
            num_parts = random.randint(max(2, base_parts-1), min(8, base_parts+1))
            
            # 拆分值
            parts = s.split_target_value(target_value, num_parts)
            if not parts:
                attempts += 1
                continue
            
            # 查找匹配值
            results = []
            success = True
            for part in parts:
                result = s.find_similar_in_files(part, file_paths)
                if result:
                    results.append({
                        "name": result[0],
                        "value": result[1],
                        "url": result[2]
                    })
                else:
                    success = False
                    break
            
            if success and results not in splits:
                splits.append(results)
                presplit_logger.debug(f"生成新的分拆組合: {target_value} -> {results}")
            
            attempts += 1
        
        return splits
    
    def start_background_task(self):
        """啟動後台預分拆任務"""
        if self.running:
            return
        
        self.running = True
        self._worker_thread = threading.Thread(target=self._background_task)
        self._worker_thread.daemon = True
        self._worker_thread.start()
        presplit_logger.info("後台預分拆任務已啟動")
    
    def stop_background_task(self):
        """停止後台預分拆任務"""
        self.running = False
        if self._worker_thread:
            self._worker_thread.join()
        self.save_cache()
        presplit_logger.info("後台預分拆任務已停止")
    
    def _background_task(self):
        """後台預分拆任務的主循環"""
        while self.running:
            try:
                # 生成一個隨機目標值
                target_value = random.uniform(300, 5000)
                target_value = round(target_value, 2)  # 四捨五入到2位小數
                
                # 檢查是否已有足夠的分拆組合
                existing_splits = self.get_split(target_value)
                if len(existing_splits) >= 5:  # 每個目標值最多保存5個組合
                    continue
                
                # 生成新的分拆組合
                new_splits = self.generate_splits(target_value)
                if new_splits:
                    # 驗證總和不超過目標值
                    for split_combination in new_splits:
                        total = sum(item["value"] for item in split_combination)
                        if total <= target_value:
                            self.add_split(target_value, split_combination)
                            presplit_logger.info(f"成功添加預分拆組合: {target_value} -> 總和: {total}")
                            break
                    
                    # 每生成10個新組合就保存一次
                    if len(self.cache) % 10 == 0:
                        self.save_cache()
                
                # 休眠一小段時間
                time.sleep(0.1)
                
            except Exception as e:
                presplit_logger.error(f"預分拆任務執行錯誤: {str(e)}")
                time.sleep(1)  # 發生錯誤時等待較長時間
    
    def get_statistics(self) -> Dict:
        """獲取預分拆統計信息"""
        with self.lock:
            total_combinations = sum(len(splits) for splits in self.cache.values())
            return {
                "total_target_values": len(self.cache),
                "total_combinations": total_combinations,
                "average_combinations": total_combinations / len(self.cache) if self.cache else 0
            }

# 創建全局預分拆管理器實例
presplit_manager = PreSplitManager() 