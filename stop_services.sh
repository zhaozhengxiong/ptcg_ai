#!/bin/bash
# 一键关闭所有服务

set -e

# 获取脚本所在目录（项目根目录）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# PID文件目录
PID_DIR="$SCRIPT_DIR/.pids"

echo "=========================================="
echo "正在停止 PTCG Agents 服务..."
echo "=========================================="

# 停止服务的函数
stop_service() {
    local service_name=$1
    local pid_file="$PID_DIR/${service_name}.pid"
    
    if [ ! -f "$pid_file" ]; then
        echo "⚠️  ${service_name} 未运行 (PID文件不存在)"
        return
    fi
    
    local pid=$(cat "$pid_file")
    
    if ! ps -p "$pid" > /dev/null 2>&1; then
        echo "⚠️  ${service_name} 未运行 (进程不存在)"
        rm -f "$pid_file"
        return
    fi
    
    echo "正在停止 ${service_name} (PID: $pid)..."
    kill "$pid" 2>/dev/null || true
    
    # 等待进程结束，最多等待5秒
    local count=0
    while ps -p "$pid" > /dev/null 2>&1 && [ $count -lt 10 ]; do
        sleep 0.5
        count=$((count + 1))
    done
    
    # 如果进程仍在运行，强制杀死
    if ps -p "$pid" > /dev/null 2>&1; then
        echo "  强制停止 ${service_name}..."
        kill -9 "$pid" 2>/dev/null || true
        sleep 1
    fi
    
    if ps -p "$pid" > /dev/null 2>&1; then
        echo "✗ 无法停止 ${service_name} (PID: $pid)"
    else
        echo "✓ ${service_name} 已停止"
        rm -f "$pid_file"
    fi
}

# 停止所有服务
stop_service "rule_kb"
stop_service "simulator_api"
stop_service "game_tools"

echo ""
echo "=========================================="
echo "所有服务已停止"
echo "=========================================="
echo ""

