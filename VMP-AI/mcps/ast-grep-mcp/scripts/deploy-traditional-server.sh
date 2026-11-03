#!/bin/bash
#
# Traditional Server Deployment Script
# Automates deployment of AlephAuto Dashboard to a server (macOS or Linux)
#
# Usage:
#   ./scripts/deploy-traditional-server.sh [--setup|--update|--rollback]
#
# Options:
#   --setup     Initial server setup (dependencies, PM2, Nginx)
#   --update    Update application code and restart services
#   --rollback  Rollback to previous version
#

set -e  # Exit on error
set -u  # Exit on undefined variable

# Detect OS
OS="$(uname -s)"
IS_MACOS=false
IS_LINUX=false

case "$OS" in
    Darwin*)
        IS_MACOS=true
        ;;
    Linux*)
        IS_LINUX=true
        ;;
    *)
        echo "Unsupported OS: $OS"
        exit 1
        ;;
esac

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration - Platform specific
if $IS_MACOS; then
    APP_NAME="aleph-dashboard"
    APP_DIR="$HOME/code/jobs"  # Use current project directory on macOS
    BACKUP_DIR="$HOME/.aleph-backups"
    NGINX_SITE="/usr/local/etc/nginx/servers/${APP_NAME}"
    LOG_FILE="$HOME/.aleph-logs/${APP_NAME}-deploy.log"
    DEPLOY_USER="$USER"
else
    # Linux configuration
    APP_NAME="aleph-dashboard"
    APP_DIR="/var/www/${APP_NAME}"
    BACKUP_DIR="/var/backups/${APP_NAME}"
    NGINX_SITE="/etc/nginx/sites-available/${APP_NAME}"
    LOG_FILE="/var/log/${APP_NAME}-deploy.log"
    DEPLOY_USER="aleph"
fi

# Functions
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$LOG_FILE"
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING:${NC} $1" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1" | tee -a "$LOG_FILE"
    exit 1
}

info() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$LOG_FILE"
}

# Check if running as root or with sudo (Linux only)
check_sudo() {
    if $IS_LINUX && [[ $EUID -ne 0 ]]; then
        error "This script must be run with sudo privileges on Linux"
    fi

    if $IS_MACOS && [[ $EUID -eq 0 ]]; then
        warn "Running as root on macOS is not recommended. Run without sudo."
    fi
}

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Initial setup
setup_server() {
    log "Starting initial server setup for $(uname -s)..."

    if $IS_MACOS; then
        setup_macos
    else
        setup_linux
    fi

    log "✅ Server setup completed successfully!"
    info "Next steps:"
    info "  1. Login to Doppler: doppler login"
    info "  2. Set up Doppler project: cd $APP_DIR && doppler setup"
    if $IS_LINUX; then
        info "  3. Clone repository to $APP_DIR"
        info "  4. Run: sudo $0 --update"
    else
        info "  3. Run: $0 --update"
    fi
}

# macOS-specific setup
setup_macos() {
    log "Setting up macOS environment..."

    # Check for Homebrew
    if ! command_exists brew; then
        error "Homebrew is required but not installed. Install from: https://brew.sh"
    fi

    # Update Homebrew
    log "Updating Homebrew..."
    brew update

    # Install Node.js
    if ! command_exists node; then
        log "Installing Node.js..."
        brew install node@25
        brew link node@25
    else
        info "Node.js already installed: $(node --version)"
    fi

    # Install Python 3
    if ! command_exists python3; then
        log "Installing Python 3..."
        brew install python@3.11
    else
        info "Python already installed: $(python3 --version)"
    fi

    # Install Redis
    if ! command_exists redis-cli; then
        log "Installing Redis..."
        brew install redis
        log "Starting Redis service..."
        brew services start redis
    else
        info "Redis already installed: $(redis-cli --version)"
        # Ensure Redis is running
        if ! brew services list | grep -q "redis.*started"; then
            log "Starting Redis service..."
            brew services start redis
        fi
    fi

    # Install PM2
    if ! command_exists pm2; then
        log "Installing PM2..."
        npm install -g pm2
        # macOS uses launchd, not systemd
        pm2 startup launchd
    else
        info "PM2 already installed: $(pm2 --version)"
    fi

    # Install Doppler
    if ! command_exists doppler; then
        log "Installing Doppler CLI..."
        brew install dopplerhq/cli/doppler
    else
        info "Doppler already installed: $(doppler --version)"
    fi

    # Install Nginx (optional on macOS)
    if ! command_exists nginx; then
        log "Installing Nginx..."
        brew install nginx
        log "Starting Nginx service..."
        brew services start nginx
    else
        info "Nginx already installed: $(nginx -v 2>&1)"
        # Ensure Nginx is running
        if ! brew services list | grep -q "nginx.*started"; then
            log "Starting Nginx service..."
            brew services start nginx
        fi
    fi

    # Create directories
    log "Creating application directories..."
    mkdir -p "$BACKUP_DIR"
    mkdir -p "$(dirname "$LOG_FILE")"

    # macOS doesn't need UFW firewall
    info "Note: macOS firewall configuration should be done through System Preferences > Security & Privacy"
}

# Linux-specific setup
setup_linux() {
    log "Setting up Linux environment..."

    # Update system
    log "Updating system packages..."
    apt-get update && apt-get upgrade -y

    # Install Node.js
    if ! command_exists node; then
        log "Installing Node.js 25.x..."
        curl -fsSL https://deb.nodesource.com/setup_25.x | bash -
        apt-get install -y nodejs
    else
        info "Node.js already installed: $(node --version)"
    fi

    # Install Python 3.11
    if ! command_exists python3.11; then
        log "Installing Python 3.11..."
        apt-get install -y software-properties-common
        add-apt-repository -y ppa:deadsnakes/ppa
        apt-get update
        apt-get install -y python3.11 python3.11-venv python3.11-dev python3-pip build-essential
    else
        info "Python 3.11 already installed: $(python3.11 --version)"
    fi

    # Install Redis
    if ! command_exists redis-cli; then
        log "Installing Redis..."
        apt-get install -y redis-server
        systemctl enable redis-server
        systemctl start redis-server
    else
        info "Redis already installed: $(redis-cli --version)"
    fi

    # Install PM2
    if ! command_exists pm2; then
        log "Installing PM2..."
        npm install -g pm2
        pm2 startup systemd -u $(logname) --hp /home/$(logname)
    else
        info "PM2 already installed: $(pm2 --version)"
    fi

    # Install Doppler
    if ! command_exists doppler; then
        log "Installing Doppler CLI..."
        curl -sLf --retry 3 --tlsv1.2 --proto "=https" 'https://packages.doppler.com/public/cli/gpg.DE2A7741.key' | apt-key add -
        echo "deb https://packages.doppler.com/public/cli/deb/debian any-version main" | tee /etc/apt/sources.list.d/doppler-cli.list
        apt-get update
        apt-get install -y doppler
    else
        info "Doppler already installed: $(doppler --version)"
    fi

    # Install Nginx
    if ! command_exists nginx; then
        log "Installing Nginx..."
        apt-get install -y nginx
        systemctl enable nginx
        systemctl start nginx
    else
        info "Nginx already installed: $(nginx -v 2>&1)"
    fi

    # Install UFW firewall
    if ! command_exists ufw; then
        log "Installing UFW firewall..."
        apt-get install -y ufw
    fi

    # Configure firewall
    log "Configuring firewall..."
    ufw --force enable
    ufw allow OpenSSH
    ufw allow 80/tcp
    ufw allow 443/tcp
    ufw status

    # Create application directory
    log "Creating application directory..."
    mkdir -p "$APP_DIR"
    mkdir -p "$BACKUP_DIR"
    mkdir -p "$(dirname "$LOG_FILE")"

    # Create deployment user (if not exists)
    if ! id -u "$DEPLOY_USER" >/dev/null 2>&1; then
        log "Creating deployment user '$DEPLOY_USER'..."
        adduser "$DEPLOY_USER" --disabled-password --gecos ""
        chown -R "$DEPLOY_USER:$DEPLOY_USER" "$APP_DIR"
    fi
}

# Update application
update_application() {
    log "Starting application update..."

    # Check if application directory exists
    if [[ ! -d "$APP_DIR" ]]; then
        error "Application directory not found: $APP_DIR"
    fi

    cd "$APP_DIR"

    # Create backup
    log "Creating backup..."
    BACKUP_FILE="$BACKUP_DIR/backup-$(date +%Y%m%d_%H%M%S).tar.gz"
    tar -czf "$BACKUP_FILE" \
        --exclude='node_modules' \
        --exclude='venv' \
        --exclude='logs' \
        -C "$(dirname "$APP_DIR")" "$(basename "$APP_DIR")"
    log "Backup created: $BACKUP_FILE"

    # Pull latest code
    if [[ -d .git ]]; then
        log "Pulling latest code from git..."
        if $IS_MACOS; then
            git pull origin main || warn "Git pull failed, using existing code"
        else
            sudo -u "$DEPLOY_USER" git pull origin main || warn "Git pull failed, using existing code"
        fi
    else
        warn "Not a git repository, skipping git pull"
    fi

    # Install Node.js dependencies
    log "Installing Node.js dependencies..."
    if $IS_MACOS; then
        pnpm install --frozen-lockfile
    else
        sudo -u "$DEPLOY_USER" pnpm install --frozen-lockfile
    fi

    # Build frontend
    log "Building frontend..."
    if $IS_MACOS; then
        npm run build:frontend
    else
        sudo -u "$DEPLOY_USER" npm run build:frontend
    fi

    # Install/Update Python dependencies
    log "Setting up Python virtual environment..."
    PYTHON_CMD="python3"
    if $IS_LINUX && command_exists python3.11; then
        PYTHON_CMD="python3.11"
    fi

    if [[ ! -d venv ]]; then
        if $IS_MACOS; then
            $PYTHON_CMD -m venv venv
        else
            sudo -u "$DEPLOY_USER" $PYTHON_CMD -m venv venv
        fi
    fi

    log "Installing Python dependencies..."
    if $IS_MACOS; then
        source venv/bin/activate && pip install --upgrade pip && pip install -r requirements.txt
    else
        sudo -u "$DEPLOY_USER" bash -c "source venv/bin/activate && pip install --upgrade pip && pip install -r requirements.txt"
    fi

    # Set correct permissions (Linux only)
    if $IS_LINUX; then
        log "Setting permissions..."
        chown -R "$DEPLOY_USER:$DEPLOY_USER" "$APP_DIR"
        chmod -R 755 "$APP_DIR"
    fi

    # Normalize critical entrypoint modes to match runtime policy (node interpreter + non-executable TS files)
    log "Normalizing critical entrypoint file modes..."
    if $IS_MACOS; then
        node --strip-types scripts/validate-permissions.ts --fix
    else
        sudo -u "$DEPLOY_USER" bash -c "cd $APP_DIR && node --strip-types scripts/validate-permissions.ts --fix"
    fi

    # Restart PM2 processes
    log "Restarting PM2 processes..."
    if $IS_MACOS; then
        cd "$APP_DIR" && pm2 restart all || pm2 start config/ecosystem.config.cjs
        pm2 save
    else
        sudo -u "$DEPLOY_USER" bash -c "cd $APP_DIR && pm2 restart all || pm2 start config/ecosystem.config.cjs"
        sudo -u "$DEPLOY_USER" pm2 save
    fi

    # Reload Nginx
    log "Reloading Nginx..."
    if $IS_MACOS; then
        nginx -t && brew services restart nginx
    else
        nginx -t && systemctl reload nginx
    fi

    # Health check
    log "Performing health check..."
    sleep 3
    if curl -f http://localhost:8080/health >/dev/null 2>&1; then
        log "✅ Health check passed!"
    else
        warn "Health check failed, check logs with: pm2 logs"
    fi

    # Check PM2 status
    log "PM2 Status:"
    if $IS_MACOS; then
        pm2 status
    else
        sudo -u "$DEPLOY_USER" pm2 status
    fi

    log "✅ Application updated successfully!"
}

# Rollback to previous version
rollback_application() {
    log "Starting rollback..."

    # Check if backup directory exists
    if [[ ! -d "$BACKUP_DIR" ]]; then
        error "Backup directory not found: $BACKUP_DIR"
    fi

    # Find latest backup
    LATEST_BACKUP=$(ls -t "$BACKUP_DIR"/backup-*.tar.gz 2>/dev/null | head -1)

    if [[ -z "$LATEST_BACKUP" ]]; then
        error "No backup found in $BACKUP_DIR"
    fi

    log "Rolling back to: $LATEST_BACKUP"

    # Stop PM2 processes
    log "Stopping PM2 processes..."
    if $IS_MACOS; then
        pm2 stop all
    else
        sudo -u "$DEPLOY_USER" pm2 stop all
    fi

    # Remove current application
    log "Removing current application..."
    rm -rf "${APP_DIR:?}"/*

    # Restore from backup
    log "Restoring from backup..."
    tar -xzf "$LATEST_BACKUP" -C "$(dirname "$APP_DIR")"

    cd "$APP_DIR"

    # Reinstall dependencies
    log "Reinstalling dependencies..."
    if $IS_MACOS; then
        pnpm install --frozen-lockfile
        npm run build:frontend
        source venv/bin/activate && pip install -r requirements.txt
    else
        sudo -u "$DEPLOY_USER" pnpm install --frozen-lockfile
        sudo -u "$DEPLOY_USER" npm run build:frontend
        sudo -u "$DEPLOY_USER" bash -c "source venv/bin/activate && pip install -r requirements.txt"
    fi

    # Restart PM2 processes
    log "Restarting PM2 processes..."
    if $IS_MACOS; then
        cd "$APP_DIR" && pm2 restart all
        pm2 save
    else
        sudo -u "$DEPLOY_USER" bash -c "cd $APP_DIR && pm2 restart all"
        sudo -u "$DEPLOY_USER" pm2 save
    fi

    # Reload Nginx
    log "Reloading Nginx..."
    if $IS_MACOS; then
        brew services restart nginx
    else
        systemctl reload nginx
    fi

    # Health check
    log "Performing health check..."
    sleep 3
    if curl -f http://localhost:8080/health >/dev/null 2>&1; then
        log "✅ Health check passed!"
    else
        warn "Health check failed, check logs with: pm2 logs"
    fi

    log "✅ Rollback completed successfully!"
}

# Show status
show_status() {
    log "=== System Status ($(uname -s)) ==="

    info "PM2 Processes:"
    if $IS_MACOS; then
        pm2 status
    else
        sudo -u "$DEPLOY_USER" pm2 status
    fi

    info ""
    info "Nginx Status:"
    if $IS_MACOS; then
        brew services list | grep nginx || echo "Nginx not running as service"
    else
        systemctl status nginx --no-pager -l
    fi

    info ""
    info "Redis Status:"
    if $IS_MACOS; then
        brew services list | grep redis || echo "Redis not running as service"
        redis-cli ping 2>/dev/null && echo "Redis is responding" || echo "Redis not responding"
    else
        systemctl status redis-server --no-pager -l
    fi

    info ""
    info "Health Check:"
    curl -s http://localhost:8080/health | jq . 2>/dev/null || curl -s http://localhost:8080/health

    info ""
    info "Disk Usage:"
    df -h "$APP_DIR"

    info ""
    info "Memory Usage:"
    if $IS_MACOS; then
        vm_stat | head -10
        echo "---"
        top -l 1 | grep PhysMem
    else
        free -h
    fi

    info ""
    info "Recent Logs:"
    if $IS_MACOS; then
        pm2 logs --nostream --lines 10
    else
        sudo -u "$DEPLOY_USER" pm2 logs --nostream --lines 10
    fi
}

# Main script
main() {
    case "${1:-}" in
        --setup)
            check_sudo
            setup_server
            ;;
        --update)
            check_sudo
            update_application
            ;;
        --rollback)
            check_sudo
            rollback_application
            ;;
        --status)
            show_status
            ;;
        *)
            echo "AlephAuto Dashboard - Traditional Server Deployment"
            echo "Platform: $(uname -s)"
            echo ""
            echo "Usage: $0 [OPTION]"
            echo ""
            echo "Options:"
            echo "  --setup      Initial server setup (install dependencies)"
            echo "  --update     Update application and restart services"
            echo "  --rollback   Rollback to previous backup"
            echo "  --status     Show current system status"
            echo ""
            if $IS_MACOS; then
                echo "Examples (macOS):"
                echo "  $0 --setup      # First-time setup (requires Homebrew)"
                echo "  $0 --update     # Deploy new version"
                echo "  $0 --rollback   # Revert to previous version"
                echo "  $0 --status     # Check current status"
            else
                echo "Examples (Linux):"
                echo "  sudo $0 --setup     # First-time server setup"
                echo "  sudo $0 --update    # Deploy new version"
                echo "  sudo $0 --rollback  # Revert to previous version"
                echo "  $0 --status         # Check current status"
            fi
            echo ""
            exit 1
            ;;
    esac
}

# Run main function
main "$@"
