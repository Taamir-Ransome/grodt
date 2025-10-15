#!/bin/bash

# GRODT Scaling Management Script
# This script manages service scaling and load balancing

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
COMPOSE_FILE="docker/docker-compose.yml"
SCALE_FILE="docker/docker-compose.scale.yml"
MAX_INSTANCES=5
MIN_INSTANCES=1

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

# Function to scale service
scale_service() {
    local service=$1
    local replicas=$2
    
    if [ -z "$service" ] || [ -z "$replicas" ]; then
        print_error "Usage: $0 scale <service> <replicas>"
        return 1
    fi
    
    if [ "$replicas" -lt "$MIN_INSTANCES" ] || [ "$replicas" -gt "$MAX_INSTANCES" ]; then
        print_error "Replicas must be between $MIN_INSTANCES and $MAX_INSTANCES"
        return 1
    fi
    
    print_status "Scaling $service to $replicas instances..."
    
    docker-compose -f "$COMPOSE_FILE" up -d --scale "$service=$replicas"
    
    if [ $? -eq 0 ]; then
        print_success "Service $service scaled to $replicas instances"
    else
        print_error "Failed to scale service $service"
        return 1
    fi
}

# Function to check service health
check_service_health() {
    local service=$1
    
    print_status "Checking health of $service service..."
    
    # Get running instances
    local instances=$(docker-compose -f "$COMPOSE_FILE" ps "$service" | grep -c "Up")
    
    if [ "$instances" -eq 0 ]; then
        print_error "No instances of $service are running"
        return 1
    fi
    
    print_status "Found $instances running instances of $service"
    
    # Check each instance
    for i in $(seq 1 $instances); do
        local container_name="grodt_${service}_${i}"
        if docker ps --filter "name=$container_name" --filter "status=running" | grep -q "$container_name"; then
            print_success "Instance $i is running"
        else
            print_error "Instance $i is not running"
        fi
    done
}

# Function to show service status
show_service_status() {
    print_status "Service Status:"
    echo ""
    
    # Show running services
    docker-compose -f "$COMPOSE_FILE" ps
    echo ""
    
    # Show resource usage
    print_status "Resource Usage:"
    docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}"
    echo ""
    
    # Show load balancer status
    if docker ps --filter "name=grodt-lb" --filter "status=running" | grep -q "grodt-lb"; then
        print_success "Load balancer is running"
    else
        print_warning "Load balancer is not running"
    fi
}

# Function to start load balancer
start_load_balancer() {
    print_status "Starting load balancer..."
    
    # Start Nginx load balancer
    docker-compose -f "$SCALE_FILE" up -d grodt-lb
    
    if [ $? -eq 0 ]; then
        print_success "Load balancer started"
    else
        print_error "Failed to start load balancer"
        return 1
    fi
}

# Function to stop load balancer
stop_load_balancer() {
    print_status "Stopping load balancer..."
    
    docker-compose -f "$SCALE_FILE" stop grodt-lb
    
    if [ $? -eq 0 ]; then
        print_success "Load balancer stopped"
    else
        print_error "Failed to stop load balancer"
        return 1
    fi
}

# Function to restart load balancer
restart_load_balancer() {
    print_status "Restarting load balancer..."
    
    stop_load_balancer
    start_load_balancer
}

# Function to test load balancing
test_load_balancing() {
    print_status "Testing load balancing..."
    
    # Test multiple requests
    for i in {1..10}; do
        local response=$(curl -s http://localhost/health)
        if [ "$response" = "healthy" ]; then
            print_success "Request $i: OK"
        else
            print_error "Request $i: Failed"
        fi
        sleep 1
    done
}

# Function to monitor performance
monitor_performance() {
    print_status "Monitoring performance..."
    
    # Monitor for 60 seconds
    local duration=60
    local start_time=$(date +%s)
    
    while [ $(($(date +%s) - start_time)) -lt $duration ]; do
        # Get current metrics
        local cpu_usage=$(docker stats --no-stream --format "{{.CPUPerc}}" grodt_grodt_1 2>/dev/null | sed 's/%//' || echo "0")
        local memory_usage=$(docker stats --no-stream --format "{{.MemUsage}}" grodt_grodt_1 2>/dev/null | cut -d'/' -f1 | sed 's/MiB//' || echo "0")
        
        print_status "CPU: ${cpu_usage}%, Memory: ${memory_usage}MB"
        sleep 10
    done
}

# Function to auto-scale based on metrics
auto_scale() {
    print_status "Auto-scaling based on metrics..."
    
    # Get current CPU usage
    local cpu_usage=$(docker stats --no-stream --format "{{.CPUPerc}}" grodt_grodt_1 2>/dev/null | sed 's/%//' || echo "0")
    local current_replicas=$(docker-compose -f "$COMPOSE_FILE" ps grodt | grep -c "Up")
    
    print_status "Current CPU usage: ${cpu_usage}%"
    print_status "Current replicas: $current_replicas"
    
    # Scale up if CPU usage is high
    if [ "$cpu_usage" -gt 80 ] && [ "$current_replicas" -lt "$MAX_INSTANCES" ]; then
        local new_replicas=$((current_replicas + 1))
        print_status "CPU usage is high, scaling up to $new_replicas instances"
        scale_service "grodt" "$new_replicas"
    fi
    
    # Scale down if CPU usage is low
    if [ "$cpu_usage" -lt 30 ] && [ "$current_replicas" -gt "$MIN_INSTANCES" ]; then
        local new_replicas=$((current_replicas - 1))
        print_status "CPU usage is low, scaling down to $new_replicas instances"
        scale_service "grodt" "$new_replicas"
    fi
}

# Function to show usage
show_usage() {
    echo "GRODT Scaling Manager"
    echo ""
    echo "Usage: $0 [COMMAND] [OPTIONS]"
    echo ""
    echo "Commands:"
    echo "  scale <service> <replicas>  Scale service to specified replicas"
    echo "  health <service>            Check service health"
    echo "  status                      Show service status"
    echo "  lb-start                    Start load balancer"
    echo "  lb-stop                     Stop load balancer"
    echo "  lb-restart                  Restart load balancer"
    echo "  test                        Test load balancing"
    echo "  monitor                     Monitor performance"
    echo "  auto-scale                  Auto-scale based on metrics"
    echo ""
    echo "Services:"
    echo "  grodt                       GRODT application"
    echo "  prometheus                  Prometheus monitoring"
    echo "  grafana                     Grafana visualization"
    echo ""
    echo "Examples:"
    echo "  $0 scale grodt 3"
    echo "  $0 health grodt"
    echo "  $0 lb-start"
    echo "  $0 test"
}

# Main script logic
case ${1:-} in
    scale)
        scale_service "$2" "$3"
        ;;
    health)
        check_service_health "$2"
        ;;
    status)
        show_service_status
        ;;
    lb-start)
        start_load_balancer
        ;;
    lb-stop)
        stop_load_balancer
        ;;
    lb-restart)
        restart_load_balancer
        ;;
    test)
        test_load_balancing
        ;;
    monitor)
        monitor_performance
        ;;
    auto-scale)
        auto_scale
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
