import os
import logging
from logging.handlers import RotatingFileHandler

# 基礎路徑
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')

# 數據目錄
RAW_DATA_DIR = os.path.join(DATA_DIR, 'raw')
PROCESSED_DATA_DIR = os.path.join(DATA_DIR, 'processed')
LOGS_DIR = os.path.join(DATA_DIR, 'logs')

# 文件路徑
def get_raw_data_file(i):
    return os.path.join(RAW_DATA_DIR, f'less_than_{i}.csv')

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

# 日誌配置
def setup_logger(name, log_file, level=logging.INFO):
    """設置日誌記錄器"""
    formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    handler = RotatingFileHandler(
        log_file,
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    handler.setFormatter(formatter)
    
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.addHandler(handler)
    
    return logger

# 創建日誌記錄器
api_logger = setup_logger('api', get_log_file('api'))
split_logger = setup_logger('split', get_log_file('split'))
error_logger = setup_logger('error', get_log_file('error')) 