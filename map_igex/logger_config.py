import os
import logging
from logging.handlers import RotatingFileHandler

# 創建日誌目錄
log_dir = os.path.join(os.path.dirname(__file__), 'logs')
os.makedirs(log_dir, exist_ok=True)

# 設置日誌格式
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def setup_logger(name, log_file, level=logging.INFO):
    """設置日誌記錄器"""
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

# 創建各種日誌記錄器
error_logger = setup_logger('error', os.path.join(log_dir, 'error.log'))
presplit_logger = setup_logger('presplit', os.path.join(log_dir, 'presplit.log'))
api_logger = setup_logger('api', os.path.join(log_dir, 'api.log'))
config_logger = setup_logger('config', os.path.join(log_dir, 'config.log'))
split_logger = setup_logger('split', os.path.join(log_dir, 'split.log'))

# 主日誌記錄器（用於通用日誌）
logger = setup_logger('map_igex', os.path.join(log_dir, 'map_igex.log')) 