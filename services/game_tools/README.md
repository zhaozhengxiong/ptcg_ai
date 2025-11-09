# Game Tools gRPC Service

Game Tools 服务的 gRPC 实现。

## 安装依赖

确保已安装所有依赖：

```bash
# 激活虚拟环境
source .venv/bin/activate  # 或 .venv\Scripts\activate (Windows)

# 安装项目依赖（包括 grpcio）
pip install -e .
```

或者单独安装 grpcio：

```bash
pip install grpcio grpcio-tools
```

## 生成 Proto 文件

在首次使用前，需要生成 proto 文件：

```bash
python -m grpc_tools.protoc -I services/game_tools/proto \
    --python_out=services/game_tools \
    --grpc_python_out=services/game_tools \
    services/game_tools/proto/game_tools.proto
```

## 运行服务

```bash
# 方式 1: 使用模块运行
python -m services.game_tools

# 方式 2: 直接运行 __main__.py
python services/game_tools/__main__.py
```

## 故障排除

### ModuleNotFoundError: No module named 'grpc'

安装 grpcio：

```bash
pip install grpcio grpcio-tools
```

### ImportError: cannot import name 'game_tools_pb2'

生成 proto 文件（见上方"生成 Proto 文件"部分）。

