# LAN Share

局域网文件共享服务器，基于Flask实现，提供文件上传下载和剪切板功能。

## 功能

- 文件上传/下载
- 临时剪切板
- Web界面操作
- 最大上传限制：1GB

## 依赖

Python 3 + Flask

安装Flask：
```sh
# Linux
pip3 install flask

# Windows
pip install flask
```

## 使用

运行服务器：
```sh
# Linux
python3 ShareServer.py

# Windows
python ShareServer.py
# 或双击 StartServer.bat
```

启动后访问 `http://localhost:5000` 或局域网IP地址即可使用。
