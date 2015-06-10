import logging

def setup_logger(logger_name, log_file=None, level=logging.INFO):
    l = logging.getLogger(logger_name)
    formatter = logging.Formatter('%(asctime)s : %(message)s')
    if log_file:
        fileHandler = logging.FileHandler(log_file, mode='w')
        fileHandler.setFormatter(formatter)
    streamHandler = logging.StreamHandler()
    streamHandler.setFormatter(formatter)

    l.setLevel(level)
    if log_file:
        l.addHandler(fileHandler)
    l.addHandler(streamHandler)   
    return l
