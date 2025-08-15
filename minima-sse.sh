#!/bin/bash
# minima-sse.sh - Unified Minima SSE Management Script
# Usage: ./minima-sse.sh [start|stop|restart|status|logs|install|uninstall|help]

set -e

# Configuration
SERVICE_NAME="minima-sse"
SERVICE_FILE="minima-sse.service"
SYSTEMD_DIR="/etc/systemd/system"
WORKDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_FILE="docker-compose-mcp-sse.yml"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

check_docker() {
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed. Please install Docker first."
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        log_error "Docker Compose is not installed. Please install Docker Compose first."
        exit 1
    fi
}

check_env_file() {
    if [[ ! -f "$WORKDIR/.env" ]]; then
        log_error ".env file not found in $WORKDIR"
        log_info "Please create .env file with required variables:"
        log_info "  LOCAL_FILES_PATH=/path/to/your/documents"
        log_info "  EMBEDDING_MODEL_ID=sentence-transformers/all-mpnet-base-v2"
        log_info "  EMBEDDING_SIZE=768"
        exit 1
    fi
}

create_directories() {
    log_info "Creating necessary directories..."
    mkdir -p "$WORKDIR/qdrant_data"
    mkdir -p "$WORKDIR/indexer_data"
    chmod 755 "$WORKDIR/qdrant_data"
    chmod 755 "$WORKDIR/indexer_data"
}

# Service management functions
start_service() {
    log_info "Starting Minima SSE services..."
    
    if systemctl is-active --quiet "${SERVICE_NAME}.service" 2>/dev/null; then
        log_info "Using systemd service..."
        sudo systemctl start "${SERVICE_NAME}.service"
    else
        log_info "Using Docker Compose directly..."
        check_docker
        check_env_file
        create_directories
        
        cd "$WORKDIR"
        docker compose -f "$COMPOSE_FILE" --env-file .env up -d
    fi
    
    log_success "Services started successfully!"
    log_info "- Indexer: http://localhost:8002"
    log_info "- SSE Server: http://localhost:8003"
}

stop_service() {
    log_info "Stopping Minima SSE services..."
    
    if systemctl is-active --quiet "${SERVICE_NAME}.service" 2>/dev/null; then
        log_info "Using systemd service..."
        sudo systemctl stop "${SERVICE_NAME}.service"
    else
        log_info "Using Docker Compose directly..."
        cd "$WORKDIR"
        docker compose -f "$COMPOSE_FILE" down
    fi
    
    log_success "Services stopped successfully!"
}

restart_service() {
    log_info "Restarting Minima SSE services..."
    
    if systemctl is-active --quiet "${SERVICE_NAME}.service" 2>/dev/null; then
        log_info "Using systemd service..."
        sudo systemctl restart "${SERVICE_NAME}.service"
    else
        log_info "Using Docker Compose directly..."
        stop_service
        sleep 2
        start_service
        return
    fi
    
    log_success "Services restarted successfully!"
    log_info "- Indexer: http://localhost:8002"
    log_info "- SSE Server: http://localhost:8003"
}

status_service() {
    log_info "Checking Minima SSE status..."
    
    if systemctl is-enabled --quiet "${SERVICE_NAME}.service" 2>/dev/null; then
        log_info "Systemd service status:"
        sudo systemctl status "${SERVICE_NAME}.service" --no-pager || true
        echo ""
    fi
    
    log_info "Docker Compose status:"
    cd "$WORKDIR"
    if docker compose -f "$COMPOSE_FILE" ps 2>/dev/null; then
        echo ""
        log_info "Service URLs:"
        log_info "- Indexer: http://localhost:8002"
        log_info "- SSE Server: http://localhost:8003"
    else
        log_warning "No Docker Compose services found"
    fi
}

show_logs() {
    if systemctl is-active --quiet "${SERVICE_NAME}.service" 2>/dev/null; then
        log_info "Showing systemd logs (press Ctrl+C to exit)..."
        sudo journalctl -u "${SERVICE_NAME}.service" -f
    else
        log_info "Showing Docker Compose logs (press Ctrl+C to exit)..."
        cd "$WORKDIR"
        docker compose -f "$COMPOSE_FILE" logs -f
    fi
}

install_systemd() {
    log_info "Installing Minima SSE systemd service..."
    
    # Check if running as root
    if [[ $EUID -ne 0 ]]; then
        log_error "Systemd installation requires root privileges"
        log_info "Usage: sudo $0 install"
        exit 1
    fi
    
    check_docker
    
    # Create service file with correct paths
    log_info "Creating systemd service file..."
    cat > "${SYSTEMD_DIR}/${SERVICE_NAME}.service" << EOF
[Unit]
Description=Minima SSE Server with Docker Compose
Requires=docker.service
After=docker.service
Wants=network-online.target
After=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
User=root
Group=docker
WorkingDirectory=${WORKDIR}
Environment=PATH=/usr/local/bin:/usr/bin:/bin

# Start command
ExecStart=/bin/bash -c 'cd ${WORKDIR} && docker compose -f ${COMPOSE_FILE} --env-file .env up -d'

# Stop command  
ExecStop=/bin/bash -c 'cd ${WORKDIR} && docker compose -f ${COMPOSE_FILE} down'

# Reload command
ExecReload=/bin/bash -c 'cd ${WORKDIR} && docker compose -f ${COMPOSE_FILE} --env-file .env restart'

# Restart settings
Restart=on-failure
RestartSec=10
TimeoutStartSec=300
TimeoutStopSec=120

# Security settings
PrivateTmp=false
ProtectSystem=false
ProtectHome=false

[Install]
WantedBy=multi-user.target
EOF
    
    # Set proper permissions
    chmod 644 "${SYSTEMD_DIR}/${SERVICE_NAME}.service"
    
    # Reload systemd daemon
    log_info "Reloading systemd daemon..."
    systemctl daemon-reload
    
    # Enable service (start on boot)
    log_info "Enabling ${SERVICE_NAME} service..."
    systemctl enable "${SERVICE_NAME}.service"
    
    log_success "Systemd service installed successfully!"
    log_info "Service will auto-start on boot"
    log_info "Use: $0 start|stop|restart|status to manage the service"
}

uninstall_systemd() {
    log_info "Uninstalling Minima SSE systemd service..."
    
    # Check if running as root
    if [[ $EUID -ne 0 ]]; then
        log_error "Systemd uninstallation requires root privileges"
        log_info "Usage: sudo $0 uninstall"
        exit 1
    fi
    
    # Stop service if running
    log_info "Stopping ${SERVICE_NAME} service..."
    systemctl stop "${SERVICE_NAME}.service" 2>/dev/null || true
    
    # Disable service
    log_info "Disabling ${SERVICE_NAME} service..."
    systemctl disable "${SERVICE_NAME}.service" 2>/dev/null || true
    
    # Remove service file
    log_info "Removing service file..."
    rm -f "${SYSTEMD_DIR}/${SERVICE_NAME}.service"
    
    # Reload systemd daemon
    log_info "Reloading systemd daemon..."
    systemctl daemon-reload
    
    # Reset failed state
    systemctl reset-failed 2>/dev/null || true
    
    log_success "Systemd service uninstalled successfully!"
    log_warning "Docker containers may still be running."
    log_info "Use: $0 stop to stop them manually"
}

show_help() {
    echo "Minima SSE Management Script"
    echo ""
    echo "USAGE:"
    echo "  $0 [COMMAND]"
    echo ""
    echo "COMMANDS:"
    echo "  start      Start Minima SSE services"
    echo "  stop       Stop Minima SSE services" 
    echo "  restart    Restart Minima SSE services"
    echo "  status     Show service status"
    echo "  logs       Show service logs (follow mode)"
    echo "  install    Install as systemd service (requires sudo)"
    echo "  uninstall  Uninstall systemd service (requires sudo)"
    echo "  help       Show this help message"
    echo ""
    echo "EXAMPLES:"
    echo "  $0 start                    # Start services"
    echo "  $0 status                   # Check status"
    echo "  sudo $0 install             # Install systemd service"
    echo "  $0 logs                     # Follow logs"
    echo ""
    echo "SERVICES:"
    echo "  - Indexer: http://localhost:8002"
    echo "  - SSE Server: http://localhost:8003"
}

# Main execution
case "${1:-help}" in
    start)
        start_service
        ;;
    stop)
        stop_service
        ;;
    restart)
        restart_service
        ;;
    status)
        status_service
        ;;
    logs)
        show_logs
        ;;
    install)
        install_systemd
        ;;
    uninstall)
        uninstall_systemd
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        log_error "Unknown command: $1"
        echo ""
        show_help
        exit 1
        ;;
esac