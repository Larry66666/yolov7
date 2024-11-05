import time
import requests
import json
import os

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
                    "ip": "192.168.165.118",  # 根据实际情况修改
                    "port": 9000,
                    "probability": 1
                }
            ],
            "maxRate": 2097152
        }

def send_movement_data(movement_data):
    # url = "http://172.21.13.210:8887/file/send"  # 发送端服务的 IP 和端口
    url = "http://localhost:8887/file/send"
    headers = {"Content-Type": "application/json"}

    request_body = movement_data.to_dict()
    print("发送的数据:", request_body)  # 打印发送的数据以供调试

    response = requests.post(url, json=request_body, headers=headers)

    if response.status_code == 200:
        print("数据发送成功:", response.json())
    else:
        print("发送失败，状态码:", response.status_code, response.text)
