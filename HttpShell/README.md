# HTTP Shell

基于HTTP协议的Web Shell工具，提供网页界面执行系统命令，支持文件上传下载。

## 功能

- Web界面执行系统命令
- 实时显示命令输出
- 文件上传/下载功能
- Token认证机制
- 支持Windows/Linux

## 使用

安装Python 3，运行：
```sh
python http_shell.py
```

或使用脚本快速启动：
- Windows: `start_http_shell.bat`
- Linux: `start_http_shell.sh`

启动后访问控制台输出的URL（包含认证Token）即可使用。