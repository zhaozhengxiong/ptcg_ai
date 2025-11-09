#!/bin/bash
# 一键启动所有服务

set -e

# 获取脚本所在目录（项目根目录）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# PID文件目录
PID_DIR="$SCRIPT_DIR/.pids"
mkdir -p "$PID_DIR"

# 日志目录
LOG_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOG_DIR"

# 检查虚拟环境
if [ -z "$VIRTUAL_ENV" ]; then
    if [ -f .venv/bin/activate ]; then
        source .venv/bin/activate
        echo "✓ 已激活虚拟环境"
    else
        echo "✗ 错误: 虚拟环境未找到。请先创建虚拟环境:"
        echo "  python -m venv .venv"
        echo "  source .venv/bin/activate"
        echo "  pip install -e ."
        exit 1
    fi
fi

echo "=========================================="
echo "正在启动 PTCG Agents 服务..."
echo "=========================================="

# 检查服务是否已经在运行
check_service() {
    local service_name=$1
    local pid_file="$PID_DIR/${service_name}.pid"
    
    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        if ps -p "$pid" > /dev/null 2>&1; then
            echo "⚠️  ${service_name} 已在运行 (PID: $pid)"
            return 1
        else
            # PID文件存在但进程不存在，删除旧的PID文件
            rm -f "$pid_file"
        fi
    fi
    return 0
}

# 启动 Game Tools gRPC 服务
start_game_tools() {
    if ! check_service "game_tools"; then
        return
    fi
    
    echo "正在启动 Game Tools gRPC 服务 (端口: 50051)..."
    nohup python -m services.game_tools > "$LOG_DIR/game_tools.log" 2>&1 &
    local pid=$!
    echo $pid > "$PID_DIR/game_tools.pid"
    echo "✓ Game Tools gRPC 服务已启动 (PID: $pid)"
    sleep 2
}

# 启动 Simulator API
start_simulator_api() {
    if ! check_service "simulator_api"; then
        return
    fi
    
    echo "正在启动 Simulator API (端口: 8000)..."
    nohup python -m uvicorn apps.simulator_api.main:app --host 0.0.0.0 --port 8000 > "$LOG_DIR/simulator_api.log" 2>&1 &
    local pid=$!
    echo $pid > "$PID_DIR/simulator_api.pid"
    echo "✓ Simulator API 已启动 (PID: $pid)"
    sleep 2
}

# 启动 Rule KB 服务
start_rule_kb() {
    if ! check_service "rule_kb"; then
        return
    fi
    
    echo "正在启动 Rule KB 服务 (端口: 8001)..."
    nohup python -m uvicorn services.rule_kb.service:app --host 0.0.0.0 --port 8001 > "$LOG_DIR/rule_kb.log" 2>&1 &
    local pid=$!
    echo $pid > "$PID_DIR/rule_kb.pid"
    echo "✓ Rule KB 服务已启动 (PID: $pid)"
    sleep 2
}

# 启动所有服务
start_game_tools
start_simulator_api
start_rule_kb

echo ""
echo "=========================================="
echo "所有服务启动完成！"
echo "=========================================="
echo ""
echo "服务状态:"
echo "  - Game Tools gRPC:  http://localhost:50051"
echo "  - Simulator API:    http://localhost:8000"
echo "  - Rule KB API:      http://localhost:8001"
echo ""
echo "日志文件:"
echo "  - Game Tools:       $LOG_DIR/game_tools.log"
echo "  - Simulator API:    $LOG_DIR/simulator_api.log"
echo "  - Rule KB:          $LOG_DIR/rule_kb.log"
echo ""
echo "PID文件: $PID_DIR/"
echo ""
echo "使用 ./stop_services.sh 停止所有服务"
echo ""

