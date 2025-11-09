# Simulator API

FastAPI 服务，提供对局管理、状态查询和回放功能。

## 安装依赖

确保已安装所有依赖：

```bash
# 激活虚拟环境
source .venv/bin/activate  # 或 .venv\Scripts\activate (Windows)

# 安装项目依赖
pip install -e .
```

或者单独安装 FastAPI 和 Uvicorn：

```bash
pip install fastapi uvicorn[standard]
```

## 运行服务

### 方式 1: 使用启动脚本（推荐）

```bash
# 确保在项目根目录
cd /home/zzx/ptcg_agents

# 运行启动脚本
./apps/simulator_api/run.sh
```

### 方式 2: 使用 Python 模块

```bash
# 激活虚拟环境
source .venv/bin/activate

# 从项目根目录运行
python -m uvicorn apps.simulator_api.main:app --host 0.0.0.0 --port 8000
```

### 方式 3: 直接运行模块

```bash
# 激活虚拟环境
source .venv/bin/activate

# 从项目根目录运行
python -m apps.simulator_api
```

### 方式 4: 使用 uvicorn 命令（需要激活虚拟环境）

```bash
# 激活虚拟环境
source .venv/bin/activate

# 从项目根目录运行
uvicorn apps.simulator_api.main:app --host 0.0.0.0 --port 8000
```

## 访问 API

服务启动后，访问：

- API 文档（Swagger UI）: http://localhost:8000/docs
- API 文档（ReDoc）: http://localhost:8000/redoc
- 健康检查: http://localhost:8000/health

## 故障排除

### ModuleNotFoundError: No module named 'fastapi'

**原因**：
1. 没有激活虚拟环境
2. 虚拟环境中没有安装 fastapi

**解决方案**：

```bash
# 1. 激活虚拟环境
source .venv/bin/activate

# 2. 安装依赖
pip install -e .
# 或
pip install fastapi uvicorn[standard]
```

### ImportError: cannot import name 'app' from 'main'

**原因**：运行 uvicorn 时的工作目录不正确

**解决方案**：
- 确保从项目根目录运行命令
- 使用 `apps.simulator_api.main:app` 作为模块路径（不是 `main:app`）

### 端口已被占用

**解决方案**：
- 更改端口：`--port 8001`
- 或停止占用端口的进程

