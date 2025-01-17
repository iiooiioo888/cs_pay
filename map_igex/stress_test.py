import time
import random
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

def test_single_request(target_value):
    """測試單個請求"""
    try:
        response = requests.get(
            f"http://localhost:8000/split/{target_value}",
            timeout=10  # 設置10秒超時
        )
        return response.status_code == 200, response.elapsed.total_seconds()
    except requests.Timeout:
        print(f"請求超時: {target_value}")
        return False, 10.0  # 超時記為10秒
    except Exception as e:
        print(f"請求錯誤: {target_value}, {str(e)}")
        return False, 0

def run_stress_test(num_requests=1000, concurrent_requests=50):
    """執行壓力測試"""
    print(f"\n開始壓力測試 - 總請求數: {num_requests}, 並發數: {concurrent_requests}")
    
    # 準備測試數據
    test_values = [
        int(random.uniform(300, 5000)) for _ in range(num_requests)
    ]
    
    success_count = 0
    total_time = 0
    response_times = []
    error_count = 0
    timeout_count = 0
    
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=concurrent_requests) as executor:
        futures = []
        for value in test_values:
            futures.append(executor.submit(test_single_request, value))
        
        with tqdm(total=num_requests, desc="處理請求") as pbar:
            for future in as_completed(futures):
                try:
                    success, response_time = future.result(timeout=15)  # 設置15秒超時
                    if success:
                        success_count += 1
                        total_time += response_time
                        response_times.append(response_time)
                    elif response_time == 10.0:
                        timeout_count += 1
                    else:
                        error_count += 1
                except Exception as e:
                    print(f"處理結果時發生錯誤: {str(e)}")
                    error_count += 1
                pbar.update(1)
    
    end_time = time.time()
    total_test_time = end_time - start_time
    
    # 計算統計數據
    success_rate = (success_count / num_requests) * 100
    avg_response_time = total_time / success_count if success_count > 0 else 0
    requests_per_second = num_requests / total_test_time
    
    # 計算響應時間百分位數
    if response_times:
        response_times.sort()
        p50 = response_times[len(response_times) // 2]
        p90 = response_times[int(len(response_times) * 0.9)]
        p95 = response_times[int(len(response_times) * 0.95)]
        p99 = response_times[int(len(response_times) * 0.99)]
    else:
        p50 = p90 = p95 = p99 = 0
    
    # 輸出結果
    print("\n測試結果:")
    print(f"總請求數: {num_requests}")
    print(f"成功請求數: {success_count}")
    print(f"超時請求數: {timeout_count}")
    print(f"錯誤請求數: {error_count}")
    print(f"成功率: {success_rate:.2f}%")
    print(f"總測試時間: {total_test_time:.2f} 秒")
    print(f"平均響應時間: {avg_response_time*1000:.2f} ms")
    print(f"每秒請求數 (QPS): {requests_per_second:.2f}")
    print("\n響應時間分佈:")
    print(f"50th 百分位 (P50): {p50*1000:.2f} ms")
    print(f"90th 百分位 (P90): {p90*1000:.2f} ms")
    print(f"95th 百分位 (P95): {p95*1000:.2f} ms")
    print(f"99th 百分位 (P99): {p99*1000:.2f} ms")

if __name__ == "__main__":
    # 執行三輪測試，逐步增加負載
    test_configs = [
        (300, 3),     # 輕負載測試
        (500, 5),   # 中負載測試
        (800, 8)    # 重負載測試
    ]
    
    for num_requests, concurrent_requests in test_configs:
        print(f"\n執行測試 - 請求數: {num_requests}, 並發數: {concurrent_requests}")
        run_stress_test(num_requests, concurrent_requests)
        time.sleep(5)  # 測試間隔休息5秒 