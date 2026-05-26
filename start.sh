#!/bin/bash

# 选股策略跟踪工具 - 启动脚本
# 适用于 Ubuntu 系统

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$PROJECT_ROOT"
FRONTEND_DIR="$PROJECT_ROOT/frontend"

# 配置
BACKEND_PORT=1145
FRONTEND_PORT=19198
BACKEND_HOST="0.0.0.0"
FRONTEND_HOST="0.0.0.0"

# PID 文件
BACKEND_PID_FILE="$PROJECT_ROOT/.backend.pid"
FRONTEND_PID_FILE="$PROJECT_ROOT/.frontend.pid"

# 日志文件
BACKEND_LOG_FILE="$PROJECT_ROOT/backend.log"
FRONTEND_LOG_FILE="$PROJECT_ROOT/frontend.log"

# 打印带颜色的消息
print_message() {
    local color=$1
    local message=$2
    echo -e "${color}${message}${NC}"
}

# 检查命令是否存在
check_command() {
    if ! command -v "$1" &> /dev/null; then
        print_message "$RED" "错误: $1 未安装"
        return 1
    fi
    return 0
}

# 检查系统依赖
check_system_deps() {
    print_message "$YELLOW" "检查系统依赖..."
    
    local missing_deps=()
    
    # 检查Python3
    if ! check_command python3; then
        missing_deps+=("python3")
    fi
    
    # 检查npm
    if ! check_command npm; then
        missing_deps+=("npm")
    fi
    
    # 检查python3-venv
    if ! python3 -m venv --help &> /dev/null; then
        missing_deps+=("python3-venv")
    fi
    
    if [ ${#missing_deps[@]} -gt 0 ]; then
        print_message "$RED" "缺少以下系统依赖: ${missing_deps[*]}"
        print_message "$YELLOW" "请运行以下命令安装:"
        echo "  sudo apt update"
        echo "  sudo apt install -y python3 python3-venv python3-full nodejs npm"
        exit 1
    fi
    
    print_message "$GREEN" "系统依赖检查通过"
}

# 检查并创建虚拟环境
setup_venv() {
    cd "$BACKEND_DIR"
    
    # 检查虚拟环境是否完整
    local venv_complete=true
    if [ -d "$BACKEND_DIR/.venv" ]; then
        if [ ! -f "$BACKEND_DIR/.venv/bin/python" ] || [ ! -f "$BACKEND_DIR/.venv/bin/pip" ]; then
            venv_complete=false
        fi
    else
        venv_complete=false
    fi
    
    # 如果虚拟环境不完整，删除并重新创建
    if [ "$venv_complete" = false ]; then
        if [ -d "$BACKEND_DIR/.venv" ]; then
            print_message "$YELLOW" "检测到虚拟环境不完整，正在重新创建..."
            rm -rf "$BACKEND_DIR/.venv"
        fi
        
        print_message "$YELLOW" "创建 Python 虚拟环境..."
        
        # 检查python3-venv是否安装
        if ! python3 -m venv --help &> /dev/null; then
            print_message "$RED" "错误: python3-venv 未安装"
            print_message "$YELLOW" "请运行: sudo apt install python3-venv python3-full"
            exit 1
        fi
        
        python3 -m venv .venv
        
        if [ ! -d "$BACKEND_DIR/.venv" ]; then
            print_message "$RED" "虚拟环境创建失败"
            exit 1
        fi
        
        # 验证虚拟环境是否创建成功
        if [ ! -f "$BACKEND_DIR/.venv/bin/python" ]; then
            print_message "$RED" "虚拟环境创建失败: python 不存在"
            rm -rf "$BACKEND_DIR/.venv"
            exit 1
        fi
        
        if [ ! -f "$BACKEND_DIR/.venv/bin/pip" ]; then
            print_message "$RED" "虚拟环境创建失败: pip 不存在"
            rm -rf "$BACKEND_DIR/.venv"
            exit 1
        fi
        
        # 测试虚拟环境是否可以执行
        if ! "$BACKEND_DIR/.venv/bin/python" --version &> /dev/null; then
            print_message "$RED" "虚拟环境创建失败: python 无法执行"
            rm -rf "$BACKEND_DIR/.venv"
            exit 1
        fi
        
        print_message "$GREEN" "虚拟环境创建成功"
    else
        print_message "$GREEN" "虚拟环境已存在且完整"
    fi
}

# 安装后端依赖
install_backend_deps() {
    print_message "$YELLOW" "检查后端依赖..."
    cd "$BACKEND_DIR"
    
    # 确保虚拟环境存在
    if [ ! -d "$BACKEND_DIR/.venv" ]; then
        print_message "$RED" "错误: 虚拟环境不存在"
        exit 1
    fi
    
    # 使用虚拟环境中的pip
    local venv_pip="$BACKEND_DIR/.venv/bin/pip"
    local venv_python="$BACKEND_DIR/.venv/bin/python"
    
    if [ ! -f "$venv_pip" ]; then
        print_message "$RED" "错误: 虚拟环境中的pip不存在"
        exit 1
    fi
    
    if [ -f "requirements.txt" ]; then
        "$venv_pip" install -r requirements.txt -q
        print_message "$GREEN" "后端依赖安装完成"
    else
        print_message "$RED" "错误: requirements.txt 不存在"
        exit 1
    fi
}

# 安装前端依赖
install_frontend_deps() {
    print_message "$YELLOW" "检查前端依赖..."
    cd "$FRONTEND_DIR"
    
    if [ ! -d "node_modules" ]; then
        if [ -f "package.json" ]; then
            npm install
            print_message "$GREEN" "前端依赖安装完成"
        else
            print_message "$RED" "错误: package.json 不存在"
            exit 1
        fi
    else
        print_message "$GREEN" "前端依赖已存在"
    fi
}

# 检查端口是否被占用
check_port() {
    local port=$1
    local service=$2
    
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        print_message "$RED" "错误: 端口 $port 已被占用 ($service)"
        return 1
    fi
    return 0
}

# 启动后端服务
start_backend() {
    print_message "$BLUE" "启动后端服务..."
    
    if [ -f "$BACKEND_PID_FILE" ]; then
        local pid=$(cat "$BACKEND_PID_FILE")
        if ps -p $pid > /dev/null 2>&1; then
            print_message "$YELLOW" "后端服务已在运行 (PID: $pid)"
            return 0
        else
            rm -f "$BACKEND_PID_FILE"
        fi
    fi
    
    if ! check_port $BACKEND_PORT "后端服务"; then
        exit 1
    fi
    
    cd "$BACKEND_DIR"
    
    # 确保虚拟环境存在
    if [ ! -d "$BACKEND_DIR/.venv" ]; then
        print_message "$RED" "错误: 虚拟环境不存在"
        exit 1
    fi
    
    local venv_python="$BACKEND_DIR/.venv/bin/python"
    local venv_uvicorn="$BACKEND_DIR/.venv/bin/uvicorn"
    
    if [ ! -f "$venv_uvicorn" ]; then
        print_message "$RED" "错误: 虚拟环境中的uvicorn不存在，请先安装依赖"
        exit 1
    fi
    
    nohup "$venv_python" -m uvicorn app.main:app --reload --host $BACKEND_HOST --port $BACKEND_PORT > "$BACKEND_LOG_FILE" 2>&1 &
    local pid=$!
    echo $pid > "$BACKEND_PID_FILE"
    
    sleep 2
    
    if ps -p $pid > /dev/null 2>&1; then
        print_message "$GREEN" "后端服务启动成功 (PID: $pid, 端口: $BACKEND_PORT)"
        print_message "$BLUE" "后端日志: $BACKEND_LOG_FILE"
        print_message "$BLUE" "API 文档: http://localhost:$BACKEND_PORT/docs"
    else
        print_message "$RED" "后端服务启动失败，请检查日志: $BACKEND_LOG_FILE"
        rm -f "$BACKEND_PID_FILE"
        exit 1
    fi
}

# 启动前端服务
start_frontend() {
    print_message "$BLUE" "启动前端服务..."
    
    if [ -f "$FRONTEND_PID_FILE" ]; then
        local pid=$(cat "$FRONTEND_PID_FILE")
        if ps -p $pid > /dev/null 2>&1; then
            print_message "$YELLOW" "前端服务已在运行 (PID: $pid)"
            return 0
        else
            rm -f "$FRONTEND_PID_FILE"
        fi
    fi
    
    if ! check_port $FRONTEND_PORT "前端服务"; then
        exit 1
    fi
    
    cd "$FRONTEND_DIR"
    
    nohup npm run dev > "$FRONTEND_LOG_FILE" 2>&1 &
    local pid=$!
    echo $pid > "$FRONTEND_PID_FILE"
    
    sleep 3
    
    if ps -p $pid > /dev/null 2>&1; then
        print_message "$GREEN" "前端服务启动成功 (PID: $pid, 端口: $FRONTEND_PORT)"
        print_message "$BLUE" "前端日志: $FRONTEND_LOG_FILE"
        print_message "$BLUE" "前端页面: http://localhost:$FRONTEND_PORT"
    else
        print_message "$RED" "前端服务启动失败，请检查日志: $FRONTEND_LOG_FILE"
        rm -f "$FRONTEND_PID_FILE"
        exit 1
    fi
}

# 停止后端服务
stop_backend() {
    print_message "$YELLOW" "停止后端服务..."
    
    if [ -f "$BACKEND_PID_FILE" ]; then
        local pid=$(cat "$BACKEND_PID_FILE")
        if ps -p $pid > /dev/null 2>&1; then
            kill $pid
            rm -f "$BACKEND_PID_FILE"
            print_message "$GREEN" "后端服务已停止"
        else
            print_message "$YELLOW" "后端服务未运行"
            rm -f "$BACKEND_PID_FILE"
        fi
    else
        print_message "$YELLOW" "后端服务未运行"
    fi
}

# 停止前端服务
stop_frontend() {
    print_message "$YELLOW" "停止前端服务..."
    
    if [ -f "$FRONTEND_PID_FILE" ]; then
        local pid=$(cat "$FRONTEND_PID_FILE")
        if ps -p $pid > /dev/null 2>&1; then
            kill $pid
            rm -f "$FRONTEND_PID_FILE"
            print_message "$GREEN" "前端服务已停止"
        else
            print_message "$YELLOW" "前端服务未运行"
            rm -f "$FRONTEND_PID_FILE"
        fi
    else
        print_message "$YELLOW" "前端服务未运行"
    fi
}

# 检查服务状态
check_status() {
    print_message "$BLUE" "检查服务状态..."
    
    if [ -f "$BACKEND_PID_FILE" ]; then
        local pid=$(cat "$BACKEND_PID_FILE")
        if ps -p $pid > /dev/null 2>&1; then
            print_message "$GREEN" "后端服务: 运行中 (PID: $pid, 端口: $BACKEND_PORT)"
        else
            print_message "$RED" "后端服务: 未运行"
            rm -f "$BACKEND_PID_FILE"
        fi
    else
        print_message "$RED" "后端服务: 未运行"
    fi
    
    if [ -f "$FRONTEND_PID_FILE" ]; then
        local pid=$(cat "$FRONTEND_PID_FILE")
        if ps -p $pid > /dev/null 2>&1; then
            print_message "$GREEN" "前端服务: 运行中 (PID: $pid, 端口: $FRONTEND_PORT)"
        else
            print_message "$RED" "前端服务: 未运行"
            rm -f "$FRONTEND_PID_FILE"
        fi
    else
        print_message "$RED" "前端服务: 未运行"
    fi
}

# 查看日志
view_logs() {
    local service=$1
    
    if [ "$service" = "backend" ] || [ "$service" = "all" ]; then
        if [ -f "$BACKEND_LOG_FILE" ]; then
            print_message "$BLUE" "=== 后端日志 ==="
            tail -f "$BACKEND_LOG_FILE"
        else
            print_message "$RED" "后端日志文件不存在"
        fi
    fi
    
    if [ "$service" = "frontend" ] || [ "$service" = "all" ]; then
        if [ -f "$FRONTEND_LOG_FILE" ]; then
            print_message "$BLUE" "=== 前端日志 ==="
            tail -f "$FRONTEND_LOG_FILE"
        else
            print_message "$RED" "前端日志文件不存在"
        fi
    fi
}

# 显示帮助信息
show_help() {
    cat << EOF
选股策略跟踪工具 - 启动脚本

用法: $0 [命令] [选项]

命令:
    start           启动后端和前端服务
    stop            停止后端和前端服务
    restart         重启后端和前端服务
    status          查看服务状态
    backend         仅启动后端服务
    frontend        仅启动前端服务
    install         安装依赖
    logs [service]  查看日志 (service: backend|frontend|all)
    help            显示此帮助信息

系统要求:
    - Ubuntu 20.04+ 或其他 Linux 发行版
    - Python 3.8+
    - Node.js 16+
    - npm

首次使用前请安装系统依赖:
    sudo apt update
    sudo apt install -y python3 python3-venv python3-full nodejs npm

示例:
    $0 start              # 启动所有服务
    $0 stop               # 停止所有服务
    $0 backend            # 仅启动后端
    $0 frontend           # 仅启动前端
    $0 logs backend       # 查看后端日志
    $0 status             # 查看服务状态

EOF
}

# 主函数
main() {
    local command=${1:-help}
    
    case $command in
        start)
            print_message "$BLUE" "启动选股策略跟踪工具..."
            check_system_deps
            setup_venv
            install_backend_deps
            install_frontend_deps
            start_backend
            start_frontend
            print_message "$GREEN" "所有服务启动完成！"
            print_message "$BLUE" "前端页面: http://localhost:$FRONTEND_PORT"
            print_message "$BLUE" "API 文档: http://localhost:$BACKEND_PORT/docs"
            ;;
        stop)
            stop_backend
            stop_frontend
            print_message "$GREEN" "所有服务已停止"
            ;;
        restart)
            stop_backend
            stop_frontend
            sleep 2
            main start
            ;;
        status)
            check_status
            ;;
        backend)
            check_system_deps
            setup_venv
            install_backend_deps
            start_backend
            ;;
        frontend)
            install_frontend_deps
            start_frontend
            ;;
        install)
            check_system_deps
            setup_venv
            install_backend_deps
            install_frontend_deps
            print_message "$GREEN" "依赖安装完成"
            ;;
        logs)
            local service=${2:-all}
            view_logs "$service"
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            print_message "$RED" "未知命令: $command"
            show_help
            exit 1
            ;;
    esac
}

# 执行主函数
main "$@"