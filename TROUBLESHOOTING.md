# 故障排除指南

## 常见问题及解决方案

### 1. ModuleNotFoundError: No module named 'grpc'

**问题原因**：
- `grpcio` 包未安装在虚拟环境中
- 可能使用了系统 Python 而不是虚拟环境

**解决方案**：

```bash
# 1. 激活虚拟环境
source .venv/bin/activate  # Linux/Mac
# 或
.venv\Scripts\activate  # Windows

# 2. 安装 grpcio
pip install grpcio grpcio-tools

# 或者安装所有项目依赖
pip install -e .
```

**验证**：
```bash
python -c "import grpc; print('grpc imported successfully')"
```

---

### 2. ModuleNotFoundError: No module named 'fastapi'

**问题原因**：
- 没有激活虚拟环境就运行了 uvicorn
- 虚拟环境中没有安装 fastapi 和 uvicorn
- 使用了系统 Python 的 uvicorn（在 `/usr/bin/uvicorn`），而不是虚拟环境中的

**解决方案**：

```bash
# 1. 激活虚拟环境（重要！）
source .venv/bin/activate

# 2. 安装依赖
pip install fastapi uvicorn[standard]

# 或者安装所有项目依赖
pip install -e .

# 3. 从项目根目录运行（使用虚拟环境中的 uvicorn）
python -m uvicorn apps.simulator_api.main:app --host 0.0.0.0 --port 8000
```

**推荐运行方式**：

```bash
# 方式 1: 使用启动脚本（自动处理虚拟环境）
./apps/simulator_api/run.sh

# 方式 2: 使用 Python 模块
source .venv/bin/activate
python -m apps.simulator_api

# 方式 3: 使用 uvicorn 模块（确保在虚拟环境中）
source .venv/bin/activate
python -m uvicorn apps.simulator_api.main:app --host 0.0.0.0 --port 8000
```

**避免的错误方式**：
```bash
# ❌ 错误：直接使用系统 uvicorn（没有激活虚拟环境）
uvicorn main:app --host 0.0.0.0 --port 8000

# ❌ 错误：在错误的目录下运行
cd apps/simulator_api
uvicorn main:app  # 这样无法正确导入模块
```

---

### 3. ImportError: cannot import name 'game_tools_pb2'

**问题原因**：
- Proto 文件尚未生成
- 导入路径不正确

**解决方案**：

```bash
# 1. 生成 proto 文件
python -m grpc_tools.protoc -I services/game_tools/proto \
    --python_out=services/game_tools \
    --grpc_python_out=services/game_tools \
    services/game_tools/proto/game_tools.proto

# 2. 验证文件已生成
ls services/game_tools/game_tools_pb2*.py
```

---

### 4. 测试失败：Card not found in database

**问题原因**：
- E2E 测试尝试从数据库加载不存在的测试卡牌

**解决方案**：
- 已修复：测试现在使用 `create_test_deck()` 函数直接创建测试套牌，不依赖数据库
- 运行测试时不需要真实的数据库连接

---

### 5. 依赖版本冲突

**问题原因**：
- `pyproject.toml` 中某些包的版本号不正确（如 `opentelemetry-exporter-prometheus`）

**解决方案**：
- 已修复：更新了 `pyproject.toml` 中的版本号
- 如果仍有问题，可以单独安装有问题的包：
  ```bash
  pip install opentelemetry-exporter-prometheus==0.59b0
  ```

---

## 通用解决步骤

当遇到 `ModuleNotFoundError` 时，按以下步骤排查：

1. **检查虚拟环境是否激活**：
   ```bash
   which python  # 应该指向 .venv/bin/python
   echo $VIRTUAL_ENV  # 应该显示虚拟环境路径
   ```

2. **激活虚拟环境**：
   ```bash
   source .venv/bin/activate
   ```

3. **安装项目依赖**：
   ```bash
   pip install -e .
   ```

4. **验证安装**：
   ```bash
   python -c "import fastapi, grpc, uvicorn; print('All imports successful')"
   ```

5. **从项目根目录运行**：
   ```bash
   # 确保在项目根目录
   pwd  # 应该显示 /home/zzx/ptcg_agents
   
   # 使用正确的模块路径
   python -m uvicorn apps.simulator_api.main:app
   ```

---

## 快速检查清单

在运行任何服务前，确保：

- [ ] 虚拟环境已激活（`which python` 指向 `.venv`）
- [ ] 已安装所有依赖（`pip install -e .`）
- [ ] 在项目根目录运行命令
- [ ] 使用正确的模块路径（如 `apps.simulator_api.main:app`）
- [ ] Proto 文件已生成（对于 gRPC 服务）

---

## 获取帮助

如果问题仍未解决：

1. 检查错误信息的完整堆栈跟踪
2. 确认 Python 版本（需要 Python 3.11+）
3. 检查 `pyproject.toml` 中的依赖版本
4. 查看相关服务的 README 文件：
   - `services/game_tools/README.md`
   - `apps/simulator_api/README.md`

