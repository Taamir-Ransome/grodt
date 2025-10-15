#!/bin/bash

# GRODT Docker Development Workflow Script
# This script provides convenient commands for Docker development

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
ENVIRONMENT="dev"
COMPOSE_FILE="docker-compose.yml"
COMPOSE_OVERRIDE=""

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

# Function to show usage
show_usage() {
    echo "GRODT Docker Development Workflow"
    echo ""
    echo "Usage: $0 [COMMAND] [OPTIONS]"
    echo ""
    echo "Commands:"
    echo "  start [env]     Start services (dev|staging|prod)"
    echo "  stop            Stop all services"
    echo "  restart [env]   Restart services"
    echo "  build           Build GRODT application"
    echo "  logs [service]  Show logs for service"
    echo "  shell [service] Open shell in service container"
    echo "  health          Check service health"
    echo "  clean           Clean up containers and volumes"
    echo "  test            Run integration tests"
    echo ""
    echo "Options:"
    echo "  -f, --force     Force operation without confirmation"
    echo "  -v, --verbose   Verbose output"
    echo ""
    echo "Examples:"
    echo "  $0 start dev"
    echo "  $0 logs grodt"
    echo "  $0 shell prometheus"
    echo "  $0 test"
}

# Function to set environment
set_environment() {
    local env=$1
    case $env in
        dev|development)
            ENVIRONMENT="dev"
            COMPOSE_OVERRIDE="-f docker/docker-compose.dev.yml"
            ;;
        staging)
            ENVIRONMENT="staging"
            COMPOSE_OVERRIDE="-f docker/docker-compose.staging.yml"
            ;;
        prod|production)
            ENVIRONMENT="prod"
            COMPOSE_OVERRIDE="-f docker/docker-compose.prod.yml"
            ;;
        *)
            print_error "Invalid environment: $env"
            print_error "Valid environments: dev, staging, prod"
            exit 1
            ;;
    esac
}

# Function to start services
start_services() {
    local env=${1:-dev}
    set_environment $env
    
    print_status "Starting GRODT services in $ENVIRONMENT environment..."
    
    # Create necessary directories
    mkdir -p data logs configs
    
    # Start services
    docker-compose -f docker/docker-compose.yml $COMPOSE_OVERRIDE up -d
    
    print_success "Services started successfully!"
    print_status "GRODT: http://localhost:8000"
    print_status "Prometheus: http://localhost:9091"
    print_status "Grafana: http://localhost:3000"
}

# Function to stop services
stop_services() {
    print_status "Stopping GRODT services..."
    docker-compose -f docker/docker-compose.yml $COMPOSE_OVERRIDE down
    print_success "Services stopped successfully!"
}

# Function to restart services
restart_services() {
    local env=${1:-dev}
    print_status "Restarting GRODT services in $env environment..."
    stop_services
    start_services $env
}

# Function to build application
build_application() {
    print_status "Building GRODT application..."
    docker-compose -f docker/docker-compose.yml build --no-cache grodt
    print_success "Application built successfully!"
}

# Function to show logs
show_logs() {
    local service=${1:-}
    if [ -n "$service" ]; then
        print_status "Showing logs for $service..."
        docker-compose -f docker/docker-compose.yml $COMPOSE_OVERRIDE logs -f $service
    else
        print_status "Showing logs for all services..."
        docker-compose -f docker/docker-compose.yml $COMPOSE_OVERRIDE logs -f
    fi
}

# Function to open shell
open_shell() {
    local service=${1:-grodt}
    print_status "Opening shell in $service container..."
    docker-compose -f docker/docker-compose.yml $COMPOSE_OVERRIDE exec $service /bin/bash
}

# Function to check health
check_health() {
    print_status "Checking service health..."
    
    # Check GRODT
    if curl -f http://localhost:8000/health >/dev/null 2>&1; then
        print_success "GRODT is healthy"
    else
        print_error "GRODT is not responding"
    fi
    
    # Check Prometheus
    if curl -f http://localhost:9091/-/healthy >/dev/null 2>&1; then
        print_success "Prometheus is healthy"
    else
        print_error "Prometheus is not responding"
    fi
    
    # Check Grafana
    if curl -f http://localhost:3000/api/health >/dev/null 2>&1; then
        print_success "Grafana is healthy"
    else
        print_error "Grafana is not responding"
    fi
}

# Function to clean up
clean_up() {
    print_warning "This will remove all containers, volumes, and networks. Are you sure? (y/N)"
    read -r response
    if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
        print_status "Cleaning up Docker resources..."
        docker-compose -f docker/docker-compose.yml $COMPOSE_OVERRIDE down -v --remove-orphans
        docker system prune -f
        print_success "Cleanup completed!"
    else
        print_status "Cleanup cancelled."
    fi
}

# Function to run tests
run_tests() {
    print_status "Running integration tests..."
    cd tests/integration/test_docker
    python -m pytest -v
    print_success "Tests completed!"
}

# Main script logic
case ${1:-} in
    start)
        start_services $2
        ;;
    stop)
        stop_services
        ;;
    restart)
        restart_services $2
        ;;
    build)
        build_application
        ;;
    logs)
        show_logs $2
        ;;
    shell)
        open_shell $2
        ;;
    health)
        check_health
        ;;
    clean)
        clean_up
        ;;
    test)
        run_tests
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