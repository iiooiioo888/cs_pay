import random
import math
import time
from concurrent.futures import ProcessPoolExecutor
import csv
import os
from config import get_processed_file, split_logger  # 導入配置和日誌記錄器
from functools import lru_cache
from typing import Dict, List, Tuple, Set
import threading

def split_target_value(target_value, num_parts=4, retry_count=0):
    """將目標值智能拆分為指定數量的部分，使用動態規劃和貪婪算法的混合方法"""
    split_logger.info(f"Splitting target value {target_value} into {num_parts} parts (retry: {retry_count})")
    
    if retry_count >= 3:  # 限制重試次數
        split_logger.warning("Maximum retry count reached")
        return None
    
    min_value = 50
    max_value = 499
    
    # 預先檢查是否可行
    if min_value * num_parts > target_value:
        split_logger.warning(f"Target value {target_value} too small for {num_parts} parts")
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
        
        # 在合理範圍內尋找最佳的第一個值（確保略小於目標值）
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
            # 計算當前的理想值（確保略小於平均值）
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
        split_logger.warning("Could not find suitable first value")
        if num_parts > 2:
            return split_target_value(target_value, num_parts - 1, retry_count + 1)
        return None
    
    # 嘗試分配剩餘值
    result = distribute_remaining(best_first_value)
    if result is None:
        split_logger.warning("Failed to distribute remaining values")
        if num_parts > 2:
            return split_target_value(target_value, num_parts - 1, retry_count + 1)
        return None
    
    # 驗證結果
    total = sum(result)
    if total <= target_value and (target_value - total) <= 2.0:  # 稍微放寬誤差限制
        split_logger.info(f"Successfully split: {result}")
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
            split_logger.info(f"Successfully split after adjustment: {result}")
            return tuple(result)
    
    # 如果仍然失敗，嘗試減少拆分數
    if num_parts > 2:
        return split_target_value(target_value, num_parts - 1, retry_count + 1)
    
    split_logger.warning("Failed to find valid split")
    return None

# 全局快取
class GlobalCache:
    def __init__(self):
        self._cache = {}
        self._lock = threading.Lock()
        self._used_values: Set[str] = set()
        self._file_contents: List[Tuple[str, List[Tuple]]] = []
        self._sorted_values: Dict[str, List[Tuple]] = {}  # 預排序的值
        self._initialized = False
    
    def get(self, key, default=None):
        with self._lock:
            return self._cache.get(key, default)
    
    def set(self, key, value):
        with self._lock:
            self._cache[key] = value
    
    def clear(self):
        with self._lock:
            self._cache.clear()
            self._used_values.clear()
            self._file_contents.clear()
            self._sorted_values.clear()
            self._initialized = False
    
    @property
    def used_values(self) -> Set[str]:
        return self._used_values
    
    @property
    def file_contents(self) -> List[Tuple[str, List[Tuple]]]:
        return self._file_contents
    
    def get_sorted_values(self, file_path: str) -> List[Tuple]:
        """獲取預排序的值"""
        return self._sorted_values.get(file_path, [])
    
    def initialize(self, file_paths):
        """初始化快取"""
        if self._initialized:
            return
        
        with self._lock:
            # 載入文件內容
            self._file_contents = load_file_contents(file_paths)
            # 載入已使用的值
            self._used_values = load_used_values()
            
            # 預處理並排序值
            for file_path, content in self._file_contents:
                sorted_content = sorted(
                    [item for item in content if item[0] not in self._used_values],
                    key=lambda x: x[1]
                )
                self._sorted_values[file_path] = sorted_content
            
            self._initialized = True

# 創建全局快取實例
global_cache = GlobalCache()

@lru_cache(maxsize=1024)
def calculate_optimal_parts(target_value, min_value=2, max_value=499):
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

def load_file_contents(file_paths):
    """加載文件內容（優化版本）"""
    split_logger.info("Loading file contents")
    file_contents = []
    
    for file_path in file_paths:
        try:
            full_path = os.path.join(os.path.dirname(__file__), file_path)
            if not os.path.exists(full_path):
                split_logger.error(f"File not found: {full_path}")
                continue
            
            # 使用緩衝讀取
            with open(full_path, 'r', encoding='utf-8-sig', buffering=8192) as file:
                # 跳過標題行
                next(file)
                processed_lines = []
                
                # 批量處理行
                for line in file:
                    try:
                        name, val, url = line.strip().split(',')
                        val = float(val)
                        processed_lines.append((name, val, url, line, False))
                    except (ValueError, IndexError):
                        split_logger.warning(f"Invalid line format: {line}")
                        continue
                
                file_contents.append((file_path, processed_lines))
                split_logger.debug(f"Loaded {len(processed_lines)} lines from {file_path}")
        except Exception as e:
            split_logger.error(f"Error reading file {file_path}: {str(e)}")
            continue
    
    return file_contents

def get_processed_file_path(file_name):
    """獲取處理後文件的完整路徑"""
    base_dir = os.path.dirname(__file__)
    return os.path.join(base_dir, 'data', 'processed', f'{file_name}.csv')

def get_raw_file_path(file_name):
    """獲取原始文件的完整路徑"""
    base_dir = os.path.dirname(__file__)
    return os.path.join(base_dir, 'data', 'raw', file_name)

# 初始化快取
load_file_contents.cache = {}

def find_similar_in_files(value, file_paths):
    """在文件中尋找最接近的值（優化版本）"""
    split_logger.info(f"Finding similar value to {value}")
    
    # 確保快取已初始化
    global_cache.initialize(file_paths)
    
    best_match = None
    min_diff = float('inf')
    best_line = None
    
    # 使用預排序的值進行二分查找
    for file_path, _ in global_cache.file_contents:
        sorted_content = global_cache.get_sorted_values(file_path)
        
        if not sorted_content:
            continue
        
        # 二分查找最接近的值
        left, right = 0, len(sorted_content) - 1
        while left <= right:
            mid = (left + right) // 2
            current_val = sorted_content[mid][1]
            
            if current_val == value:
                best_match = sorted_content[mid]
                min_diff = 0
                break
            elif current_val < value:
                left = mid + 1
            else:
                right = mid - 1
            
            # 更新最佳匹配
            current_diff = abs(current_val - value)
            if current_diff < min_diff:
                min_diff = current_diff
                best_match = sorted_content[mid]
                best_line = sorted_content[mid][3]
        
        # 如果找到完全匹配，直接返回
        if min_diff == 0:
            break
    
    if best_match and min_diff <= 0.5:
        split_logger.info(f"Found match: {best_match[0]} with value {best_match[1]}")
        
        # 批量更新文件
        with threading.Lock():
            try:
                # 更新已使用值文件
                used_file = get_processed_file('used_values')
                os.makedirs(os.path.dirname(used_file), exist_ok=True)
                with open(used_file, 'a', newline='', encoding='utf-8-sig') as f:
                    f.write(best_line)
                
                # 更新未使用值文件
                unused_file = get_processed_file('unused_values')
                if os.path.exists(unused_file):
                    with open(unused_file, 'r', encoding='utf-8-sig') as f:
                        lines = f.readlines()
                    
                    with open(unused_file, 'w', newline='', encoding='utf-8-sig') as f:
                        f.write(lines[0])  # 寫入標題行
                        for line in lines[1:]:
                            if not line.startswith(f"{best_match[0]},"):
                                f.write(line)
                
                # 更新快取
                global_cache.used_values.add(best_match[0])
                
                # 更新預排序的值
                for file_path in global_cache._sorted_values:
                    global_cache._sorted_values[file_path] = [
                        item for item in global_cache._sorted_values[file_path]
                        if item[0] != best_match[0]
                    ]
                
                return best_match[0], best_match[1], best_match[2]
            
            except Exception as e:
                split_logger.error(f"Error updating files: {str(e)}")
                return None
    
    split_logger.warning(f"No suitable match found for value {value}")
    return None

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

def mark_value_as_used(value_name, file_contents):
    """標記值為已使用並更新文件"""
    # 首先在內存中更新狀態
    updated = False
    for file_path, content in file_contents:
        for i, (name, val, url, line, used) in enumerate(content):
            if name == value_name and not used:
                content[i] = (name, val, url, line, True)
                updated = True
                break
        if updated:
            break
    
    # 如果內存中更新成功，則更新文件
    if updated:
        return update_value_status(value_name, True)
    
    return False

def get_unused_values(file_contents, max_value=None):
    """獲取未使用的值"""
    unused_values = []
    for _, content in file_contents:
        for name, val, url, _, used in content:
            if not used and (max_value is None or val <= max_value):
                unused_values.append((name, val, url))
    return unused_values

def find_compensation_value(target_diff, file_paths, max_combine=2):
    """尋找補償值的優化版本"""
    if target_diff <= 0:
        return None
    
    # 使用快取的文件內容
    file_contents = load_file_contents.cache.get('contents')
    if not file_contents:
        file_contents = load_file_contents(file_paths)
        load_file_contents.cache['contents'] = file_contents
    
    # 收集所有未使用的值
    available_values = get_unused_values(file_contents, target_diff)
    
    # 按值的大小排序
    available_values.sort(key=lambda x: x[1], reverse=True)  # 從大到小排序，優先使用大值
    
    # 先嘗試單個值（從大到小）
    for name, val, url in available_values:
        final_error = target_diff - val
        if 0 <= final_error <= 0.5:
            # 標記為已使用
            mark_value_as_used(name, file_contents)
            return (name, val, url)
    
    # 如果單個值不行，嘗試組合（優先嘗試大值組合）
    if max_combine >= 2:
        finder = CombinationFinder(max_combine)
        finder.try_combinations(target_diff, available_values, [], 0, 0)
        
        if finder.best_combination:
            # 標記所有組合中的值為已使用
            for match in finder.best_combination:
                mark_value_as_used(match[0], file_contents)
            
            # 返回組合結果
            total_val = sum(match[1] for match in finder.best_combination)
            combined_name = "+".join(match[0] for match in finder.best_combination)
            combined_url = "|".join(match[2] for match in finder.best_combination)
            return (combined_name, total_val, combined_url)
    
    return None

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

def test_split_success_rate(num_tests=1000):
    """測試拆分成功率"""
    split_logger.info(f"Starting split success rate test with {num_tests} cases")
    
    successes = 0
    failures = []
    
    # 測試不同範圍的值
    ranges = [
        (300, 1000),   # 小值範圍
        (1000, 2000),  # 中值範圍
        (2000, 3500),  # 中大值範圍
        (3500, 5000)   # 大值範圍
    ]
    
    for min_val, max_val in ranges:
        range_tests = num_tests // len(ranges)
        split_logger.info(f"Testing range {min_val}-{max_val} with {range_tests} cases")
        
        for _ in range(range_tests):
            target = random.uniform(min_val, max_val)
            num_parts = calculate_optimal_parts(target)
            result = split_target_value(target, num_parts)
            
            if result:
                total = sum(result)
                if abs(total - target) <= 1.0:
                    successes += 1
                else:
                    failures.append((target, "總和誤差過大", total))
            else:
                failures.append((target, "拆分失敗", None))
    
    success_rate = (successes / num_tests) * 100
    split_logger.info(f"Test completed. Success rate: {success_rate:.3f}%")
    
    if failures:
        split_logger.warning("Failed cases:")
        for target, reason, total in failures[:10]:  # 只顯示前10個失敗案例
            split_logger.warning(f"Target: {target}, Reason: {reason}, Total: {total}")
    
    return success_rate, failures

def test_edge_cases():
    """測試邊界情況"""
    test_cases = [
        300,    # 最小值
        5000,   # 最大值
        301,    # 接近最小值
        4999,   # 接近最大值
        1000,   # 整數值
        999.9,  # 小數值
        2500,   # 中間值
        3333.33 # 重複小數
    ]
    
    successes = 0
    failures = []
    
    for target in test_cases:
        split_logger.info(f"\nTesting edge case: {target}")
        num_parts = calculate_optimal_parts(target)
        result = split_target_value(target, num_parts)
        
        if result:
            total = sum(result)
            if abs(total - target) <= 1.0:
                successes += 1
                split_logger.info(f"Success: {target} -> {result}")
            else:
                failures.append((target, "總和誤差過大", total))
                split_logger.warning(f"Failed (sum error): {target} -> {result}")
        else:
            failures.append((target, "拆分失敗", None))
            split_logger.warning(f"Failed (no result): {target}")
    
    success_rate = (successes / len(test_cases)) * 100
    split_logger.info(f"\nEdge cases test completed. Success rate: {success_rate:.3f}%")
    
    if failures:
        split_logger.warning("\nFailed cases:")
        for target, reason, total in failures:
            split_logger.warning(f"Target: {target}, Reason: {reason}, Total: {total}")
    
    return success_rate, failures

def initialize_used_values():
    """初始化已使用值的文件"""
    used_file = get_processed_file('used_values')
    if not os.path.exists(used_file):
        os.makedirs(os.path.dirname(used_file), exist_ok=True)
        with open(used_file, 'w', newline='', encoding='utf-8-sig') as f:
            f.write("name,value,url\n")  # 寫入標題行

def load_used_values():
    """載入已使用的值"""
    used_file = get_processed_file('used_values')
    used_values = set()
    if os.path.exists(used_file):
        with open(used_file, 'r', encoding='utf-8-sig') as f:
            for line in f.readlines()[1:]:  # 跳過標題行
                parts = line.strip().split(',')
                if len(parts) >= 1:
                    used_values.add(parts[0])  # 只需要名稱來標識
    return used_values

def sync_used_values(file_contents):
    """同步已使用值的狀態"""
    used_values = load_used_values()
    for _, content in file_contents:
        for i, (name, val, url, line, used) in enumerate(content):
            if name in used_values and not used:
                content[i] = (name, val, url, line, True)

# 在程序啟動時初始化
initialize_used_values()

def separate_used_unused_values(file_paths):
    """分離已使用和未使用的值，並更新相應的文件"""
    # 載入所有數據
    file_contents = load_file_contents(file_paths)
    used_values = load_used_values()
    
    # 準備文件路徑
    unused_file = get_processed_file('unused_values')
    used_file = get_processed_file('used_values')
    os.makedirs(os.path.dirname(unused_file), exist_ok=True)
    os.makedirs(os.path.dirname(used_file), exist_ok=True)
    
    # 分離數據
    used_data = []
    unused_data = []
    
    for _, content in file_contents:
        for name, val, url, line, _ in content:
            if name in used_values:
                used_data.append(line)
            else:
                unused_data.append(line)
    
    # 寫入未使用的值
    with open(unused_file, 'w', newline='', encoding='utf-8-sig') as f:
        f.write("name,value,url\n")  # 寫入標題行
        for line in unused_data:
            f.write(line)
    
    # 寫入已使用的值
    with open(used_file, 'w', newline='', encoding='utf-8-sig') as f:
        f.write("name,value,url\n")  # 寫入標題行
        for line in used_data:
            f.write(line)
    
    split_logger.info(f"Separated values: {len(used_data)} used, {len(unused_data)} unused")
    return len(used_data), len(unused_data)

def get_value_status(value_name):
    """檢查值是否已被使用"""
    used_file = get_processed_file('used_values')
    if not os.path.exists(used_file):
        return False
    
    try:
        with open(used_file, 'r', encoding='utf-8-sig') as f:
            for line in f:
                if line.startswith(f"{value_name},"):
                    return True
    except Exception as e:
        split_logger.error(f"Error checking value status: {str(e)}")
    
    return False

def get_available_values_count():
    """獲取可用（未使用）值的數量"""
    unused_file = get_processed_file('unused_values')
    if not os.path.exists(unused_file):
        return 0
    
    with open(unused_file, 'r', encoding='utf-8-sig') as f:
        # 減去標題行
        return sum(1 for _ in f) - 1

def update_value_status(value_name, is_used=True):
    """更新值的使用狀態"""
    # 首先更新未使用值文件
    unused_file = get_processed_file('unused_values')
    used_file = get_processed_file('used_values')
    
    if not os.path.exists(unused_file):
        split_logger.error("Unused values file not found")
        return False
    
    try:
        # 讀取未使用值
        with open(unused_file, 'r', encoding='utf-8-sig') as f:
            lines = f.readlines()
            header = lines[0]
            data_lines = lines[1:]
        
        found_line = None
        remaining_lines = []
        
        # 查找目標值
        for line in data_lines:
            if line.startswith(f"{value_name},"):
                found_line = line
            else:
                remaining_lines.append(line)
        
        if found_line and is_used:
            # 更新未使用值文件
            with open(unused_file, 'w', newline='', encoding='utf-8-sig') as f:
                f.write(header)
                f.writelines(remaining_lines)
            
            # 更新已使用值文件
            os.makedirs(os.path.dirname(used_file), exist_ok=True)
            with open(used_file, 'a', newline='', encoding='utf-8-sig') as f:
                f.write(found_line)
            
            split_logger.info(f"Successfully marked {value_name} as used")
            return True
        
        split_logger.warning(f"Value {value_name} not found or already in desired state")
        return False
        
    except Exception as e:
        split_logger.error(f"Error updating value status: {str(e)}")
        return False

if __name__ == "__main__":
    try:
        # 初始化數據分離
        print("\nSeparating used and unused values...")
        file_paths = [
            get_raw_file_path('less_than_490.csv'),  # 使用最大值的文件
            get_raw_file_path('less_than_100.csv')   # 使用較小值的文件
        ]
        
        # 檢查文件是否存在
        for path in file_paths:
            if not os.path.exists(path):
                print(f"Error: File not found: {path}")
                exit(1)
        
        used_count, unused_count = separate_used_unused_values(file_paths)
        print(f"Found {used_count} used values and {unused_count} unused values")
        
        # 測試值的使用狀態更新
        print("\nTesting value status update...")
        file_contents = load_file_contents(file_paths)
        if file_contents and file_contents[0][1]:
            test_value = file_contents[0][1][0]
            test_name = test_value[0]
            
            print(f"Initial status of {test_name}: {'Used' if get_value_status(test_name) else 'Unused'}")
            print(f"Marking {test_name} as used...")
            update_value_status(test_name, True)
            print(f"Updated status of {test_name}: {'Used' if get_value_status(test_name) else 'Unused'}")
            
            available_count = get_available_values_count()
            print(f"Available values count: {available_count}")
        
        # 運行測試
        print("\nRunning regular tests...")
        success_rate, failures = test_split_success_rate(100)
        print(f"Regular test success rate: {success_rate:.3f}%")
        if failures:
            print(f"Number of failures: {len(failures)}")
            print("Sample failures:")
            for target, reason, total in failures[:5]:
                print(f"Target: {target:.2f}, Reason: {reason}, Total: {total}")
        
        print("\nRunning edge case tests...")
        edge_success_rate, edge_failures = test_edge_cases()
        print(f"Edge case test success rate: {edge_success_rate:.3f}%")
        if edge_failures:
            print("Edge case failures:")
            for target, reason, total in edge_failures:
                print(f"Target: {target}, Reason: {reason}, Total: {total}")
        
        # 顯示最終統計
        print("\nFinal data statistics:")
        used_count = len(load_used_values())
        available_count = get_available_values_count()
        print(f"Used values: {used_count}")
        print(f"Available values: {available_count}")
        print(f"Total values: {used_count + available_count}")
        
    except Exception as e:
        print(f"\nError: {str(e)}")
        split_logger.error(f"Program error: {str(e)}")
        exit(1) 