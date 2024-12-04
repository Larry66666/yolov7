import threading
import time
import requests
import json
import os
from concurrent.futures import ThreadPoolExecutor

class MovementData:
    def __init__(self, image_path):
        self.image_path = image_path  # 图像路径

    def to_dict(self):
        # 根据要求构造请求体
        return {
            "encodePackageSize": 5000,
            "clientFilePath": os.path.dirname(self.image_path) + "\\",  # 文件夹路径
            "fileName": [os.path.basename(self.image_path)],  # 仅包含文件名
            "ipAndPortInfoSend": [
                {
                    # "ip": "10.16.102.42",  # 根据实际情况修改，zerotier
                    # "ip": "192.168.22.6",
                    "ip": "25.25.25.2",
                    "port": 9000,
                    "probability": 1
                }
            ],
            "maxRate": 2097152
        }

def send_movement_data(movement_data):
    url = "http://localhost:8887/file/send"  # 发送端服务的 IP 和端口
    headers = {"Content-Type": "application/json"}

    request_body = movement_data.to_dict()
    print("发送的数据:", request_body)  # 打印发送的数据以供调试

    response = requests.post(url, json=request_body, headers=headers)

    if response.status_code == 200:
        print("数据发送成功:", response.json())
    else:
        print("发送失败，状态码:", response.status_code, response.text)

# 封装为线程启动函数
def send_single_movement(movement_data):
    # 创建并启动线程
    thread = threading.Thread(target=send_movement_data, args=(movement_data,))
    thread.start()
    thread.join()  # 等待线程完成