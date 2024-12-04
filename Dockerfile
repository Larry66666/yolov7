# 使用官方 Python 镜像作为基础镜像
FROM python:3.6

# 将当前目录下的文件复制到容器的 /app 目录中
COPY . /app

# 设置工作目录
WORKDIR /app

# 安装 Python 依赖
RUN pip install -r requirements.txt -i https://mirrors.ustc.edu.cn/pypi/simple

# 定义启动命令
CMD ["python", "predict.py"]
