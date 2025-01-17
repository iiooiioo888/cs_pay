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
            # 將目標值轉換為兩位小數
            target_value = round(float(target_value), 2)
            results = self.cache.get(str(target_value), [])
            if results:
                presplit_logger.info(f"命中預分拆快取: {target_value} -> {results[0]}")
            return results
    
    def add_split(self, target_value: float, splits: List[Dict[str, str | float]]):
        """添加預分拆結果"""
        with self.lock:
            # 將目標值轉換為兩位小數
            target_value = round(float(target_value), 2)
            # 確保所有值都是兩位小數
            for item in splits:
                item["value"] = round(float(item["value"]), 2)
            
            if str(target_value) not in self.cache:
                self.cache[str(target_value)] = []
            if splits not in self.cache[str(target_value)]:
                self.cache[str(target_value)].append(splits)
                presplit_logger.info(f"新增預分拆組合: {target_value} -> {splits}")
    
    def generate_splits(self, target_value: float, max_attempts: int = 10) -> List[List[Dict[str, str | float]]]:
        """為指定目標值生成多個可能的分拆組合"""
        splits = []
        attempts = 0
        file_paths = [get_raw_data_file(i) for i in range(10, 500, 10)]
        
        # 將目標值轉換為兩位小數
        target_value = round(float(target_value), 2)
        
        while attempts < max_attempts:
            # 隨機調整拆分數量
            base_parts = s.calculate_optimal_parts(target_value)
            min_parts = max(2, base_parts-1)
            max_parts = max(min_parts + 1, min(8, base_parts+1))
            num_parts = random.randint(min_parts, max_parts)
            
            # 拆分值
            parts = s.split_target_value(target_value, num_parts)
            if not parts:
                attempts += 1
                continue
            
            # 將所有部分轉換為兩位小數
            parts = tuple(round(float(p), 2) for p in parts)
            
            # 檢查總和是否在允許範圍內
            total = round(sum(parts), 2)
            error = round(target_value - total, 2)
            if not (0 <= error <= 0.5):
                attempts += 1
                continue
            
            # 查找匹配值
            results = []
            success = True
            for part in parts:
                result = s.find_similar_in_files(part, file_paths)
                if result:
                    value = round(float(result[1]), 2)
                    # 檢查每個匹配值是否與目標值相差不超過0.5
                    if abs(value - part) > 0.5:
                        success = False
                        break
                    results.append({
                        "name": result[0],
                        "value": value,
                        "url": result[2]
                    })
                else:
                    success = False
                    break
            
            if success:
                # 再次驗證總和
                total = round(sum(item["value"] for item in results), 2)
                error = round(target_value - total, 2)
                if 0 <= error <= 0.5 and results not in splits:
                    splits.append(results)
                    presplit_logger.debug(f"生成新的分拆組合: {target_value} -> {results}, 誤差: {error}")
            
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
                # 生成一個隨機目標值（兩位小數）
                target_value = round(random.uniform(300, 5000), 2)
                
                # 檢查是否已有足夠的分拆組合
                existing_splits = self.get_split(target_value)
                if len(existing_splits) >= 5:  # 每個目標值最多保存5個組合
                    continue
                
                # 生成新的分拆組合
                new_splits = self.generate_splits(target_value)
                if new_splits:
                    # 驗證總和不超過目標值且誤差不超過0.5
                    for split_combination in new_splits:
                        total = round(sum(item["value"] for item in split_combination), 2)
                        error = round(target_value - total, 2)
                        if 0 <= error <= 0.5:  # 嚴格限制誤差範圍
                            # 確保所有值都是兩位小數
                            for item in split_combination:
                                item["value"] = round(float(item["value"]), 2)
                            self.add_split(target_value, split_combination)
                            presplit_logger.info(f"成功添加預分拆組合: {target_value} -> 總和: {total}, 誤差: {error}")
                            break
                        else:
                            presplit_logger.debug(f"跳過誤差過大的組合: {target_value} -> 總和: {total}, 誤差: {error}")
                    
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
    
    def test_presplit(self, test_values=None):
        """測試預分拆功能"""
        if test_values is None:
            # 生成一些測試值（兩位小數）
            test_values = [
                300.00,    # 最小值
                5000.00,   # 最大值
                1000.00,   # 中等值
                3881.00,   # 特定值
                2773.00,   # 特定值
                4999.00,   # 接近最大值
                301.00,    # 接近最小值
                2500.00,   # 中間值
            ]
        
        presplit_logger.info("開始預分拆測試")
        results = []
        
        for value in test_values:
            value = round(float(value), 2)  # 確保兩位小數
            presplit_logger.info(f"\n測試目標值: {value}")
            
            # 檢查是否有預分拆結果
            cached_splits = self.get_split(value)
            if cached_splits:
                presplit_logger.info(f"找到預分拆結果: {len(cached_splits)} 個組合")
                for i, split in enumerate(cached_splits):
                    total = round(sum(item["value"] for item in split), 2)
                    error = round(value - total, 2)
                    presplit_logger.info(f"組合 {i+1}: 總和={total}, 誤差={error}")
                    results.append({
                        "target": value,
                        "total": total,
                        "error": error,
                        "parts": len(split),
                        "from_cache": True
                    })
            else:
                presplit_logger.info("無預分拆結果，嘗試生成")
                new_splits = self.generate_splits(value)
                if new_splits:
                    split = new_splits[0]  # 使用第一個生成的組合
                    total = round(sum(item["value"] for item in split), 2)
                    error = round(value - total, 2)
                    presplit_logger.info(f"生成新組合: 總和={total}, 誤差={error}")
                    results.append({
                        "target": value,
                        "total": total,
                        "error": error,
                        "parts": len(split),
                        "from_cache": False
                    })
                    # 添加到快取
                    self.add_split(value, split)
                else:
                    presplit_logger.warning(f"無法為目標值 {value} 生成有效的分拆組合")
        
        # 輸出統計信息
        presplit_logger.info("\n測試結果統計:")
        total_tests = len(test_values)
        successful_tests = len(results)
        cached_hits = sum(1 for r in results if r["from_cache"])
        
        presplit_logger.info(f"總測試數: {total_tests}")
        presplit_logger.info(f"成功數: {successful_tests}")
        presplit_logger.info(f"快取命中數: {cached_hits}")
        presplit_logger.info(f"成功率: {(successful_tests/total_tests)*100:.2f}%")
        presplit_logger.info(f"快取命中率: {(cached_hits/total_tests)*100:.2f}%")
        
        if results:
            max_error = max(r["error"] for r in results)
            avg_error = sum(r["error"] for r in results) / len(results)
            presplit_logger.info(f"最大誤差: {max_error}")
            presplit_logger.info(f"平均誤差: {avg_error:.2f}")
        
        return results

# 創建全局預分拆管理器實例
presplit_manager = PreSplitManager() 

if __name__ == "__main__":
    try:
        # 創建預分拆管理器實例
        manager = PreSplitManager()
        
        # 運行測試
        print("開始預分拆測試...")
        test_results = manager.test_presplit()
        
        # 輸出詳細結果
        print("\n詳細測試結果:")
        for result in test_results:
            print(f"目標值: {result['target']}")
            print(f"總和: {result['total']}")
            print(f"誤差: {result['error']}")
            print(f"部分數: {result['parts']}")
            print(f"來自快取: {'是' if result['from_cache'] else '否'}")
            print("-" * 30)
        
    except Exception as e:
        print(f"測試過程中發生錯誤: {str(e)}")
        presplit_logger.error(f"測試錯誤: {str(e)}", exc_info=True) 