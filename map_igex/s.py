import random
import math
import time
from concurrent.futures import ProcessPoolExecutor
import csv
import os
from config import get_processed_file, split_logger  # 導入配置和日誌記錄器

def split_target_value(target_value, num_parts=4):
    """將目標值智能拆分為指定數量的動態平衡值"""
    split_logger.info(f"Splitting target value {target_value} into {num_parts} parts")
    
    parts = []
    min_value = 50  # 調整最小值
    max_value = 2000  # 調整最大值
    remaining_value = target_value
    
    # 計算每份的理想平均值
    ideal_part = target_value / num_parts
    split_logger.debug(f"Ideal part value: {ideal_part}")
    
    # 根據目標值和拆分數動態調整參數
    volatility = min(0.15, target_value / (10000 * num_parts))
    split_logger.debug(f"Calculated volatility: {volatility}")
    
    # 預先檢查是否可行
    if min_value * num_parts > target_value:
        split_logger.warning(f"Target value {target_value} too small for {num_parts} parts")
        return None
    
    # 計算可用範圍
    max_allowed_per_part = min(max_value, (target_value - (min_value * (num_parts - 1))))
    split_logger.debug(f"Max allowed per part: {max_allowed_per_part}")
    
    # 使用更均勻的分配策略
    base_value = target_value / num_parts
    variation = base_value * 0.2  # 允許20%的變化範圍
    
    # 生成拆分值
    for i in range(num_parts - 1):
        # 計算當前部分的值，加入一些隨機變化
        current_value = base_value + random.uniform(-variation, variation)
        current_value = max(min_value, min(math.ceil(current_value), max_allowed_per_part))
        
        parts.append(current_value)
        remaining_value -= current_value
        max_allowed_per_part = min(max_value, remaining_value - (min_value * (num_parts - i - 2)))
        split_logger.debug(f"Part {i+1}: {current_value}, Remaining: {remaining_value}")
    
    # 處理最後一個部分
    last_value = math.ceil(remaining_value)
    if min_value <= last_value <= max_value:
        parts.append(last_value)
        split_logger.debug(f"Last part: {last_value}")
    else:
        split_logger.warning(f"Last value {last_value} out of range, rebalancing")
        # 重新平衡所有部分
        total = sum(parts)
        if total < target_value:
            # 向上調整
            diff = target_value - total
            while diff > 0 and any(p < max_value for p in parts):
                for i in range(len(parts)):
                    if parts[i] < max_value and diff > 0:
                        parts[i] += 1
                        diff -= 1
        else:
            # 向下調整
            diff = total - target_value
            while diff > 0 and any(p > min_value for p in parts):
                for i in range(len(parts)):
                    if parts[i] > min_value and diff > 0:
                        parts[i] -= 1
                        diff -= 1
        
        # 添加最後一個值
        parts.append(max(min_value, min(math.ceil(remaining_value), max_value)))
    
    # 最終檢查
    total = sum(parts)
    if abs(total - target_value) > 1.0:  # 放寬總和誤差限制
        split_logger.warning(f"Cannot achieve target precision, current error: {abs(total - target_value)}")
        return None
    
    split_logger.info(f"Split result: {parts}")
    return tuple(parts)

def load_file_contents(file_paths):
    """加載文件內容，並進行快取優化"""
    split_logger.info("Loading file contents")
    file_contents = []
    for file_path in file_paths:
        try:
            with open(file_path, 'r') as file:
                # 直接將內容轉換為列表並快取值
                lines = file.readlines()[1:]  # 跳過標題行
                processed_lines = []
                for line in lines:
                    parts = line.strip().split(',')
                    if len(parts) == 3:
                        try:
                            name, val, url = parts
                            val = float(val)
                            processed_lines.append((name, val, url, line))
                        except ValueError:
                            split_logger.warning(f"Invalid value in line: {line}")
                            continue
                file_contents.append((file_path, processed_lines))
                split_logger.debug(f"Loaded {len(processed_lines)} lines from {file_path}")
        except Exception as e:
            split_logger.error(f"Error reading file {file_path}: {e}")
            continue
    return file_contents

# 初始化快取
load_file_contents.cache = {}

def find_similar_in_files(value, file_paths):
    """在文件中查找小於給定值且差值不超過1.0的最接近值"""
    split_logger.info(f"Finding similar value for {value}")
    closest_match = None
    min_difference = float('inf')
    
    # 使用快取的文件內容
    file_contents = load_file_contents.cache.get('contents')
    if not file_contents:
        file_contents = load_file_contents(file_paths)
        load_file_contents.cache['contents'] = file_contents
    
    # 對每個誤差範圍進行嘗試
    for max_diff in [0.3, 0.6, 1.0]:
        split_logger.debug(f"Trying with max difference: {max_diff}")
        for file_path, content in file_contents:
            for name, val, url, line in content:
                difference = value - val
                # 確保值小於目標值且差距在允許範圍內
                if 0 <= difference <= max_diff and difference < min_difference:
                    min_difference = difference
                    closest_match = (name, val, url)
                    split_logger.debug(f"Found better match: {closest_match}")
        
        # 如果找到了足夠好的匹配，就不需要嘗試更大的誤差範圍
        if closest_match and min_difference <= max_diff:
            break
    
    # 如果找到合適的匹配
    if closest_match:
        split_logger.info(f"Found match: {closest_match}")
        closest_matches_file = get_processed_file('closest_matches')
        os.makedirs(os.path.dirname(closest_matches_file), exist_ok=True)
        with open(closest_matches_file, mode='a', newline='', encoding='utf-8-sig') as csvfile:
            csv_writer = csv.writer(csvfile)
            csv_writer.writerow([*closest_match, value, min_difference])
            
            # 從快取中移除已使用的值
            for file_path, content in file_contents:
                content[:] = [x for x in content if x[0] != closest_match[0]]
    else:
        split_logger.warning(f"No match found for value {value}")
    
    return closest_match

class CombinationFinder:
    def __init__(self, max_combine):
        self.best_combination = None
        self.min_combination_error = float('inf')
        self.max_combine = max_combine
    
    def try_combinations(self, target, values, current_combo, start_idx, current_sum):
        if len(current_combo) >= self.max_combine or current_sum > target + 0.5:
            return
        
        error = target - current_sum
        if 0 <= error <= 0.5 and error < self.min_combination_error:
            self.min_combination_error = error
            self.best_combination = current_combo[:]
            return
        
        for i in range(start_idx, len(values)):
            value = values[i]
            new_sum = current_sum + value[1]
            if new_sum <= target + 0.5:
                self.try_combinations(target, values, current_combo + [value], i + 1, new_sum)

def find_compensation_value(target_diff, file_paths, max_combine=2):
    """尋找補償值的優化版本"""
    if target_diff <= 0:
        return None
    
    # 使用快取的文件內容
    file_contents = load_file_contents.cache.get('contents')
    if not file_contents:
        file_contents = load_file_contents(file_paths)
        load_file_contents.cache['contents'] = file_contents
    
    # 收集所有可用的值
    available_values = []
    for _, content in file_contents:
        for name, val, url, _ in content:
            if val <= target_diff:  # 只收集小於目標差值的數
                available_values.append((name, val, url))
    
    # 按值的大小排序
    available_values.sort(key=lambda x: x[1], reverse=True)  # 從大到小排序，優先使用大值
    
    # 先嘗試單個值（從大到小）
    for name, val, url in available_values:
        final_error = target_diff - val
        if 0 <= final_error <= 0.5:
            # 更新快取
            for file_path, content in file_contents:
                content[:] = [x for x in content if x[0] != name]
            return (name, val, url)
    
    # 如果單個值不行，嘗試組合（優先嘗試大值組合）
    if max_combine >= 2:
        finder = CombinationFinder(max_combine)
        finder.try_combinations(target_diff, available_values, [], 0, 0)
        
        if finder.best_combination:
            # 更新快取
            for match in finder.best_combination:
                for file_path, content in file_contents:
                    content[:] = [x for x in content if x[0] != match[0]]
            
            # 返回組合結果
            total_val = sum(match[1] for match in finder.best_combination)
            combined_name = "+".join(match[0] for match in finder.best_combination)
            combined_url = "|".join(match[2] for match in finder.best_combination)
            return (combined_name, total_val, combined_url)
    
    return None

def calculate_optimal_parts(target_value, min_value=2, max_value=499, distribution=None, popular_values=None):
    """計算最佳拆分數量"""
    # 基礎拆分數計算 - 根據目標值大小動態調整
    if target_value < 1000:
        base_parts = max(3, min(6, math.ceil(target_value / 300)))
    elif target_value < 2000:
        base_parts = max(4, min(8, math.ceil(target_value / 400)))
    elif target_value < 3500:
        base_parts = max(5, min(10, math.ceil(target_value / 500)))
    else:  # 3500-5000
        base_parts = max(6, min(12, math.ceil(target_value / 600)))
    
    if distribution and popular_values:
        # 計算目標值所在範圍的數據密度
        range_size = 20
        target_range_start = (target_value // range_size) * range_size
        target_range = (target_range_start, target_range_start + range_size)
        
        # 獲取目標範圍的數據密度
        density = distribution.get(target_range, 0)
        
        # 檢查附近是否有熱門值
        has_popular_nearby = False
        for count, value in popular_values:
            if abs(target_value - value) < range_size:
                has_popular_nearby = True
                break
        
        # 根據數據密度和熱門值調整拆分數
        if density < 5:  # 極度稀疏區域
            base_parts = min(base_parts + 2, 12)
        elif density < 15:  # 稀疏區域
            base_parts = min(base_parts + 1, 12)
        elif density > 30:  # 密集區域
            if has_popular_nearby:
                base_parts = max(base_parts - 1, 3)
    
    # 確保每份的平均值在合理範圍內
    avg_value = target_value / base_parts
    if avg_value < min_value * 1.5:
        base_parts = max(3, math.floor(target_value / (min_value * 2)))
    elif avg_value > max_value * 0.8:
        base_parts = min(12, math.ceil(target_value / (max_value * 0.7)))
    
    return base_parts

def split_compensation_diff(target_diff):
    """將較大的誤差分拆成多個小額值"""
    if target_diff <= 3:
        return [target_diff]
    
    # 根據誤差大小決定分拆數量
    if target_diff <= 6:
        num_parts = 2
    elif target_diff <= 9:
        num_parts = 3
    else:
        num_parts = 4
    
    # 計算基礎值和餘數
    base_value = target_diff / num_parts
    parts = []
    remaining = target_diff
    
    # 生成分拆值
    for i in range(num_parts - 1):
        # 添加一些隨機變化，但確保總和不超過目標值
        variation = min(0.5, remaining * 0.1)  # 限制變化範圍
        current = base_value + random.uniform(-variation, variation)
        current = min(current, remaining - (num_parts - i - 1))  # 確保留足夠的值給剩餘部分
        parts.append(current)
        remaining -= current
    
    # 添加最後一個值
    parts.append(remaining)
    
    return parts 