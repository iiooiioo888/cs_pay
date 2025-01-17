import os
import csv
import random
import math
from typing import List, Tuple, Dict, Optional
from functools import lru_cache
from config import get_processed_file  # 導入配置
from logger_config import split_logger  # 導入日誌記錄器

# 全局快取
_file_contents_cache = {}

def load_file_contents(file_paths: Tuple[str, ...]) -> Dict[str, List[Tuple[str, float, str]]]:
    """載入並緩存文件內容"""
    global _file_contents_cache
    
    # 檢查快取
    cache_key = ','.join(file_paths)
    if cache_key in _file_contents_cache:
        return _file_contents_cache[cache_key]
    
    contents = {}
    for file_path in file_paths:
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    reader = csv.reader(f)
                    next(reader)  # 跳過標題行
                    contents[file_path] = [(row[0], float(row[1]), row[2]) for row in reader]
                split_logger.info(f"已載入文件: {file_path}")
            except Exception as e:
                split_logger.error(f"載入文件失敗 {file_path}: {str(e)}")
                contents[file_path] = []
        else:
            split_logger.warning(f"文件不存在: {file_path}")
            contents[file_path] = []
    
    # 更新快取
    _file_contents_cache[cache_key] = contents
    return contents

# 提供一個獲取快取的函數
def get_file_contents_cache():
    global _file_contents_cache
    return _file_contents_cache

@lru_cache(maxsize=1024)
def calculate_optimal_parts(target_value: float, min_value: float = 2, max_value: float = 499) -> int:
    """計算最佳拆分數量（使用LRU快取）"""
    min_parts = max(2, math.ceil(target_value / max_value))
    max_parts = min(4, math.floor(target_value / (min_value * 1.2)))
    if min_parts > max_parts:
        return min_parts
    optimal_parts = min(
        max_parts,
        max(
            min_parts,
            math.ceil(target_value / 350)
        )
    )
    return optimal_parts

def split_target_value(target_value: float, num_parts: int = 4, retry_count: int = 0) -> Optional[Tuple[float, ...]]:
    """將目標值智能拆分為指定數量的部分"""
    split_logger.info(f"拆分目標值 {target_value} 為 {num_parts} 份 (重試次數: {retry_count})")
    
    if retry_count >= 3:  # 限制重試次數
        split_logger.warning("達到最大重試次數")
        return None
    
    min_value = 50
    max_value = 499
    
    # 預先檢查是否可行
    if min_value * num_parts > target_value:
        split_logger.warning(f"目標值 {target_value} 太小，無法拆分為 {num_parts} 份")
        if num_parts > 2:
            return split_target_value(target_value, num_parts - 1, retry_count + 1)
        return None
    
    # 計算基本參數
    base_value = target_value / num_parts
    
    # 如果平均值太小，減少拆分數
    if base_value < min_value * 1.1:  # 稍微放寬限制
        if num_parts > 2:
            return split_target_value(target_value, num_parts - 1, retry_count + 1)
        return None
    
    # 如果平均值太大，增加拆分數
    if base_value > max_value * 0.95 and num_parts < 8:  # 放寬最大拆分數限制
        return split_target_value(target_value, num_parts + 1, retry_count + 1)
    
    # 使用動態規劃找到最佳的第一個值
    def find_best_first_value():
        best_value = None
        min_diff = float('inf')
        target_remaining = target_value
        
        # 在合理範圍內尋找最佳的第一個值
        for first_value in range(
            max(min_value, int(base_value * 0.85)),  # 調整下限
            min(max_value, int(base_value * 0.98)) + 1  # 調整上限
        ):
            remaining = target_remaining - first_value
            if remaining < min_value * (num_parts - 1):
                continue
            
            avg_remaining = remaining / (num_parts - 1)
            if min_value <= avg_remaining <= max_value:
                diff = abs(avg_remaining - base_value)
                if diff < min_diff:
                    min_diff = diff
                    best_value = first_value
        
        return best_value
    
    # 使用貪婪算法分配剩餘值
    def distribute_remaining(first_value):
        parts = [first_value]
        remaining = target_value - first_value
        parts_left = num_parts - 1
        
        while parts_left > 1:
            # 計算當前的理想值
            current_base = remaining / parts_left
            current_base = current_base * 0.98  # 調整縮減比例
            
            # 在合理範圍內尋找最接近的值
            current_value = min(
                max_value,
                max(
                    min_value,
                    min(
                        math.floor(current_base + 0.5),  # 使用四捨五入
                        remaining - (min_value * (parts_left - 1))
                    )
                )
            )
            
            parts.append(current_value)
            remaining -= current_value
            parts_left -= 1
        
        # 添加最後一個值
        if min_value <= remaining <= max_value:
            parts.append(remaining)
            return parts
        return None
    
    # 嘗試不同的起始值
    best_first_value = find_best_first_value()
    if best_first_value is None:
        split_logger.warning("無法找到合適的第一個值")
        if num_parts > 2:
            return split_target_value(target_value, num_parts - 1, retry_count + 1)
        return None
    
    # 嘗試分配剩餘值
    result = distribute_remaining(best_first_value)
    if result is None:
        split_logger.warning("無法分配剩餘值")
        if num_parts > 2:
            return split_target_value(target_value, num_parts - 1, retry_count + 1)
        return None
    
    # 驗證結果
    total = sum(result)
    if total <= target_value and (target_value - total) <= 2.0:  # 稍微放寬誤差限制
        split_logger.info(f"成功拆分: {result}")
        return tuple(result)
    
    # 如果總和不正確，嘗試調整
    diff = target_value - total
    if diff > 0 and diff <= 3.0:  # 放寬調整範圍
        # 嘗試調整值
        for i in range(len(result)):
            if diff > 0 and result[i] < max_value:
                adjustment = min(1, diff)
                result[i] = math.floor(result[i] + adjustment + 0.5)  # 使用四捨五入
                diff -= adjustment
            
            if abs(diff) <= 0.01:
                break
        
        # 再次檢查總和
        total = sum(result)
        if total <= target_value and (target_value - total) <= 2.0:
            split_logger.info(f"調整後成功拆分: {result}")
            return tuple(result)
    
    # 如果仍然失敗，嘗試減少拆分數
    if num_parts > 2:
        return split_target_value(target_value, num_parts - 1, retry_count + 1)
    
    split_logger.warning("無法找到有效的拆分")
    return None

def find_similar_in_files(value: float, file_paths: List[str]) -> Optional[Tuple[str, float, str]]:
    """在文件中尋找最接近的值"""
    split_logger.info(f"尋找接近的值: {value}")
    
    # 使用快取的文件內容
    contents = load_file_contents(tuple(file_paths))
    
    best_match = None
    min_diff = float('inf')
    
    for file_path, content in contents.items():
        for name, val, url in content:
            diff = abs(val - value)
            if diff < min_diff:
                min_diff = diff
                best_match = (name, val, url)
    
    if best_match and min_diff <= 0.5:
        split_logger.info(f"找到匹配: {best_match[0]} 值為 {best_match[1]}")
        return best_match
    
    split_logger.warning(f"未找到合適的匹配值: {value}")
    return None

def find_compensation_value(target_diff: float, file_paths: List[str]) -> Optional[Tuple[str, float, str]]:
    """尋找補償值"""
    if target_diff <= 0:
        return None
    
    split_logger.info(f"尋找補償值: {target_diff}")
    
    # 使用快取的文件內容
    contents = load_file_contents(tuple(file_paths))
    
    best_match = None
    min_diff = float('inf')
    
    for file_path, content in contents.items():
        for name, val, url in content:
            if val <= target_diff:
                diff = target_diff - val
                if diff < min_diff:
                    min_diff = diff
                    best_match = (name, val, url)
    
    if best_match and min_diff <= 0.5:
        split_logger.info(f"找到補償值: {best_match[0]} 值為 {best_match[1]}")
        return best_match
    
    split_logger.warning(f"未找到合適的補償值: {target_diff}")
    return None 