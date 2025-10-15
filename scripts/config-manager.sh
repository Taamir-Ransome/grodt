#!/bin/bash

# GRODT Configuration Management Script
# This script manages environment-specific configurations

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
CONFIG_DIR="docker"
ENV_DIR="configs"

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to validate environment
validate_environment() {
    local env=$1
    
    case $env in
        dev|development)
            return 0
            ;;
        staging)
            return 0
            ;;
        prod|production)
            return 0
            ;;
        *)
            print_error "Invalid environment: $env"
            print_error "Valid environments: dev, staging, prod"
            return 1
            ;;
    esac
}

# Function to generate environment configuration
generate_env_config() {
    local env=$1
    local config_file="$CONFIG_DIR/.env.$env"
    
    print_status "Generating configuration for $env environment..."
    
    case $env in
        dev|development)
            cat > "$config_file" << EOF
# Development Environment Configuration
ENV=dev
LOG_LEVEL=DEBUG
DEBUG=true
RELOAD=true

# Database Configuration
DATABASE_URL=sqlite:///app/data/grodt_dev.db

# Grafana Configuration
GRAFANA_ADMIN_USER=dev_admin
GRAFANA_ADMIN_PASSWORD=dev_admin
GRAFANA_SECRET_KEY=dev-secret-key

# Monitoring Configuration
PROMETHEUS_RETENTION_DAYS=7
PROMETHEUS_RETENTION_SIZE=1GB

# Security Configuration
ENCRYPTION_KEY=dev-encryption-key

# Network Configuration
NETWORK_SUBNET=172.20.0.0/16
NETWORK_GATEWAY=172.20.0.1

# Resource Limits (Development)
GRODT_MEMORY_LIMIT=1G
GRODT_CPU_LIMIT=0.5
PROMETHEUS_MEMORY_LIMIT=512M
PROMETHEUS_CPU_LIMIT=0.25
GRAFANA_MEMORY_LIMIT=256M
GRAFANA_CPU_LIMIT=0.25

# Logging Configuration
LOG_MAX_SIZE=5m
LOG_MAX_FILES=2

# Health Check Configuration
HEALTH_CHECK_INTERVAL=15s
HEALTH_CHECK_TIMEOUT=5s
HEALTH_CHECK_RETRIES=3
HEALTH_CHECK_START_PERIOD=30s
EOF
            ;;
        staging)
            cat > "$config_file" << EOF
# Staging Environment Configuration
ENV=staging
LOG_LEVEL=INFO
DEBUG=false
RELOAD=false

# Database Configuration
DATABASE_URL=sqlite:///app/data/grodt_staging.db

# Grafana Configuration
GRAFANA_ADMIN_USER=staging_admin
GRAFANA_ADMIN_PASSWORD=staging_admin
GRAFANA_SECRET_KEY=staging-secret-key

# Monitoring Configuration
PROMETHEUS_RETENTION_DAYS=15
PROMETHEUS_RETENTION_SIZE=5GB

# Security Configuration
ENCRYPTION_KEY=staging-encryption-key

# Network Configuration
NETWORK_SUBNET=172.20.0.0/16
NETWORK_GATEWAY=172.20.0.1

# Resource Limits (Staging)
GRODT_MEMORY_LIMIT=1.5G
GRODT_CPU_LIMIT=0.75
PROMETHEUS_MEMORY_LIMIT=768M
PROMETHEUS_CPU_LIMIT=0.5
GRAFANA_MEMORY_LIMIT=384M
GRAFANA_CPU_LIMIT=0.5

# Logging Configuration
LOG_MAX_SIZE=10m
LOG_MAX_FILES=3

# Health Check Configuration
HEALTH_CHECK_INTERVAL=30s
HEALTH_CHECK_TIMEOUT=10s
HEALTH_CHECK_RETRIES=3
HEALTH_CHECK_START_PERIOD=45s
EOF
            ;;
        prod|production)
            cat > "$config_file" << EOF
# Production Environment Configuration
ENV=prod
LOG_LEVEL=WARNING
DEBUG=false
RELOAD=false

# Database Configuration
DATABASE_URL=sqlite:///app/data/grodt.db

# Grafana Configuration
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=\${GRAFANA_ADMIN_PASSWORD}
GRAFANA_SECRET_KEY=\${GRAFANA_SECRET_KEY}

# Monitoring Configuration
PROMETHEUS_RETENTION_DAYS=30
PROMETHEUS_RETENTION_SIZE=10GB

# Security Configuration
ENCRYPTION_KEY=\${ENCRYPTION_KEY}

# Network Configuration
NETWORK_SUBNET=172.20.0.0/16
NETWORK_GATEWAY=172.20.0.1

# Resource Limits (Production)
GRODT_MEMORY_LIMIT=2G
GRODT_CPU_LIMIT=1.0
PROMETHEUS_MEMORY_LIMIT=1G
PROMETHEUS_CPU_LIMIT=0.5
GRAFANA_MEMORY_LIMIT=512M
GRAFANA_CPU_LIMIT=0.5

# Logging Configuration
LOG_MAX_SIZE=50m
LOG_MAX_FILES=5

# Health Check Configuration
HEALTH_CHECK_INTERVAL=30s
HEALTH_CHECK_TIMEOUT=10s
HEALTH_CHECK_RETRIES=5
HEALTH_CHECK_START_PERIOD=60s
EOF
            ;;
    esac
    
    print_success "Configuration generated: $config_file"
}

# Function to deploy configuration
deploy_config() {
    local env=$1
    
    if ! validate_environment "$env"; then
        return 1
    fi
    
    print_status "Deploying configuration for $env environment..."
    
    # Generate environment configuration
    generate_env_config "$env"
    
    # Copy configuration files
    local config_file="$CONFIG_DIR/.env.$env"
    if [ -f "$config_file" ]; then
        cp "$config_file" "$CONFIG_DIR/.env"
        print_success "Configuration deployed: $env"
    else
        print_error "Configuration file not found: $config_file"
        return 1
    fi
}

# Function to validate configuration
validate_config() {
    local env=$1
    
    if ! validate_environment "$env"; then
        return 1
    fi
    
    print_status "Validating configuration for $env environment..."
    
    local config_file="$CONFIG_DIR/.env.$env"
    if [ ! -f "$config_file" ]; then
        print_error "Configuration file not found: $config_file"
        return 1
    fi
    
    # Check required variables
    local required_vars=("ENV" "LOG_LEVEL" "DATABASE_URL" "GRAFANA_ADMIN_USER" "GRAFANA_ADMIN_PASSWORD")
    
    for var in "${required_vars[@]}"; do
        if ! grep -q "^$var=" "$config_file"; then
            print_error "Required variable not found: $var"
            return 1
        fi
    done
    
    print_success "Configuration validation passed"
}

# Function to show configuration
show_config() {
    local env=$1
    
    if ! validate_environment "$env"; then
        return 1
    fi
    
    local config_file="$CONFIG_DIR/.env.$env"
    if [ -f "$config_file" ]; then
        print_status "Configuration for $env environment:"
        echo ""
        cat "$config_file"
    else
        print_error "Configuration file not found: $config_file"
        return 1
    fi
}

# Function to list configurations
list_configs() {
    print_status "Available configurations:"
    echo ""
    
    for config in "$CONFIG_DIR"/.env.*; do
        if [ -f "$config" ]; then
            local env=$(basename "$config" | sed 's/\.env\.//')
            echo "  $env: $config"
        fi
    done
}

# Function to backup configuration
backup_config() {
    local env=$1
    local backup_dir="$CONFIG_DIR/backups"
    local timestamp=$(date +%Y%m%d_%H%M%S)
    local backup_file="$backup_dir/${env}_${timestamp}.env"
    
    if ! validate_environment "$env"; then
        return 1
    fi
    
    print_status "Backing up configuration for $env environment..."
    
    mkdir -p "$backup_dir"
    
    local config_file="$CONFIG_DIR/.env.$env"
    if [ -f "$config_file" ]; then
        cp "$config_file" "$backup_file"
        print_success "Configuration backed up: $backup_file"
    else
        print_error "Configuration file not found: $config_file"
        return 1
    fi
}

# Function to restore configuration
restore_config() {
    local env=$1
    local backup_file=$2
    
    if ! validate_environment "$env"; then
        return 1
    fi
    
    if [ -z "$backup_file" ]; then
        print_error "Backup file not specified"
        return 1
    fi
    
    local backup_path="$CONFIG_DIR/backups/$backup_file"
    if [ ! -f "$backup_path" ]; then
        print_error "Backup file not found: $backup_path"
        return 1
    fi
    
    print_status "Restoring configuration for $env environment from $backup_file..."
    
    local config_file="$CONFIG_DIR/.env.$env"
    cp "$backup_path" "$config_file"
    print_success "Configuration restored: $config_file"
}

# Function to show usage
show_usage() {
    echo "GRODT Configuration Manager"
    echo ""
    echo "Usage: $0 [COMMAND] [OPTIONS]"
    echo ""
    echo "Commands:"
    echo "  generate <env>     Generate configuration for environment"
    echo "  deploy <env>       Deploy configuration for environment"
    echo "  validate <env>     Validate configuration for environment"
    echo "  show <env>         Show configuration for environment"
    echo "  list               List all configurations"
    echo "  backup <env>       Backup configuration for environment"
    echo "  restore <env> <file> Restore configuration from backup"
    echo ""
    echo "Environments:"
    echo "  dev, development   Development environment"
    echo "  staging            Staging environment"
    echo "  prod, production   Production environment"
    echo ""
    echo "Examples:"
    echo "  $0 generate dev"
    echo "  $0 deploy staging"
    echo "  $0 validate prod"
    echo "  $0 backup dev"
    echo "  $0 restore dev dev_20240127_120000.env"
}

# Main script logic
case ${1:-} in
    generate)
        if [ -n "$2" ]; then
            generate_env_config "$2"
        else
            print_error "Usage: $0 generate <environment>"
            exit 1
        fi
        ;;
    deploy)
        if [ -n "$2" ]; then
            deploy_config "$2"
        else
            print_error "Usage: $0 deploy <environment>"
            exit 1
        fi
        ;;
    validate)
        if [ -n "$2" ]; then
            validate_config "$2"
        else
            print_error "Usage: $0 validate <environment>"
            exit 1
        fi
        ;;
    show)
        if [ -n "$2" ]; then
            show_config "$2"
        else
            print_error "Usage: $0 show <environment>"
            exit 1
        fi
        ;;
    list)
        list_configs
        ;;
    backup)
        if [ -n "$2" ]; then
            backup_config "$2"
        else
            print_error "Usage: $0 backup <environment>"
            exit 1
        fi
        ;;
    restore)
        if [ -n "$2" ] && [ -n "$3" ]; then
            restore_config "$2" "$3"
        else
            print_error "Usage: $0 restore <environment> <backup_file>"
            exit 1
        fi
        ;;
    help|--help|-h)
        show_usage
        ;;
    *)
        print_error "Unknown command: ${1:-}"
        echo ""
        show_usage
        exit 1
        ;;
esac
