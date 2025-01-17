import os
from logger_config import config_logger

# 基礎路徑
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')

# 數據目錄
RAW_DATA_DIR = os.path.join(DATA_DIR, 'raw')
PROCESSED_DATA_DIR = os.path.join(DATA_DIR, 'processed')
LOGS_DIR = os.path.join(DATA_DIR, 'logs')

# 文件路徑
def get_raw_data_file(i):
    """獲取原始數據文件路徑"""
    base_dir = os.path.dirname(__file__)
    file_path = os.path.join(base_dir, 'data', 'raw', f'less_than_{i}.csv')
    if not os.path.exists(file_path):
        config_logger.warning(f"文件不存在: {file_path}")
    return file_path

def get_processed_file(name):
    return os.path.join(PROCESSED_DATA_DIR, f'{name}.csv')

def get_log_file(name):
    return os.path.join(LOGS_DIR, f'{name}.log')

# 創建必要的目錄
for dir_path in [RAW_DATA_DIR, PROCESSED_DATA_DIR, LOGS_DIR]:
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)

# API配置
API_HOST = "0.0.0.0"
API_PORT = 8000
API_RELOAD = True

# 數據處理配置
MIN_VALUE = 300
MAX_VALUE = 5000
ERROR_THRESHOLD = 0.5
CACHE_ENABLED = True 