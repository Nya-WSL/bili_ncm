import logging

def setup_logger():
    # 创建logger对象
    logger = logging.getLogger('bili_ncm')
    logger.setLevel(logging.DEBUG)  # 设置最低日志级别

    # 创建formatter
    formatter = logging.Formatter('%(asctime)s [%(levelname)s]: %(message)s', '%Y-%m-%d %H:%M:%S')

    # 创建文件处理器并设置级别和格式
    file_handler = logging.FileHandler('bili_ncm.log', encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)  # 文件记录所有DEBUG及以上级别的日志
    file_handler.setFormatter(formatter)

    # 创建控制台处理器并设置级别和格式
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)  # 控制台只记录INFO及以上级别的日志
    console_handler.setFormatter(formatter)

    # 将处理器添加到logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger

logger = setup_logger()