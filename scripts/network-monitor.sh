#!/bin/bash

# GRODT Network Monitoring Script
# This script monitors network connectivity and security

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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

# Function to check network connectivity
check_network_connectivity() {
    print_status "Checking network connectivity..."
    
    # Check if containers are running
    if ! docker-compose -f docker/docker-compose.yml ps | grep -q "Up"; then
        print_error "No containers are running"
        return 1
    fi
    
    # Check GRODT service
    if curl -f http://localhost:8000/health >/dev/null 2>&1; then
        print_success "GRODT service is accessible"
    else
        print_error "GRODT service is not accessible"
    fi
    
    # Check Prometheus service
    if curl -f http://localhost:9091/-/healthy >/dev/null 2>&1; then
        print_success "Prometheus service is accessible"
    else
        print_error "Prometheus service is not accessible"
    fi
    
    # Check Grafana service
    if curl -f http://localhost:3000/api/health >/dev/null 2>&1; then
        print_success "Grafana service is accessible"
    else
        print_error "Grafana service is not accessible"
    fi
}

# Function to check network isolation
check_network_isolation() {
    print_status "Checking network isolation..."
    
    # Get container IPs
    GRODT_IP=$(docker inspect grodt_grodt_1 | jq -r '.[0].NetworkSettings.Networks."grodt_grodt-network".IPAddress')
    PROMETHEUS_IP=$(docker inspect grodt_prometheus_1 | jq -r '.[0].NetworkSettings.Networks."grodt_grodt-monitoring".IPAddress')
    GRAFANA_IP=$(docker inspect grodt_grafana_1 | jq -r '.[0].NetworkSettings.Networks."grodt_grodt-network".IPAddress')
    
    print_status "GRODT IP: $GRODT_IP"
    print_status "Prometheus IP: $PROMETHEUS_IP"
    print_status "Grafana IP: $GRAFANA_IP"
    
    # Check if services can communicate within their networks
    if docker exec grodt_grodt_1 ping -c 1 $GRAFANA_IP >/dev/null 2>&1; then
        print_success "GRODT can communicate with Grafana"
    else
        print_error "GRODT cannot communicate with Grafana"
    fi
    
    if docker exec grodt_grodt_1 ping -c 1 $PROMETHEUS_IP >/dev/null 2>&1; then
        print_success "GRODT can communicate with Prometheus"
    else
        print_error "GRODT cannot communicate with Prometheus"
    fi
}

# Function to check network security
check_network_security() {
    print_status "Checking network security..."
    
    # Check if unnecessary ports are exposed
    EXPOSED_PORTS=$(docker-compose -f docker/docker-compose.yml ps | grep -o '[0-9]*:[0-9]*' | sort -u)
    print_status "Exposed ports: $EXPOSED_PORTS"
    
    # Check for open ports that shouldn't be exposed
    for port in $EXPOSED_PORTS; do
        if [[ "$port" =~ ^(22|23|135|139|445|1433|3389): ]]; then
            print_warning "Potentially insecure port exposed: $port"
        fi
    done
    
    # Check network policies
    print_status "Checking network policies..."
    docker network ls --filter "name=grodt" --format "table {{.Name}}\t{{.Driver}}\t{{.Scope}}"
}

# Function to monitor network traffic
monitor_network_traffic() {
    print_status "Monitoring network traffic..."
    
    # Get network statistics
    docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}"
    
    # Monitor network connections
    print_status "Active network connections:"
    docker exec grodt_grodt_1 netstat -tuln 2>/dev/null || print_warning "netstat not available in container"
}

# Function to test network performance
test_network_performance() {
    print_status "Testing network performance..."
    
    # Test latency between services
    if docker exec grodt_grodt_1 ping -c 3 grodt_grafana_1 >/dev/null 2>&1; then
        print_success "Network latency test passed"
    else
        print_error "Network latency test failed"
    fi
    
    # Test bandwidth (if iperf is available)
    if command -v iperf3 >/dev/null 2>&1; then
        print_status "Running bandwidth test..."
        # This would require iperf3 in containers
        print_warning "Bandwidth testing requires iperf3 in containers"
    fi
}

# Function to show network topology
show_network_topology() {
    print_status "Network topology:"
    
    echo "GRODT Network Architecture:"
    echo "┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐"
    echo "│   GRODT App    │    │   Prometheus    │    │    Grafana      │"
    echo "│   (Port 8000)  │    │   (Port 9090)   │    │   (Port 3000)   │"
    echo "└─────────────────┘    └─────────────────┘    └─────────────────┘"
    echo "         │                       │                       │"
    echo "         └───────────────────────┼───────────────────────┘"
    echo "                                 │"
    echo "                    ┌─────────────────┐"
    echo "                    │  grodt-network  │"
    echo "                    │  (172.20.0.0/16)│"
    echo "                    └─────────────────┘"
    echo ""
    echo "Network Isolation:"
    echo "- GRODT: grodt-network + grodt-monitoring"
    echo "- Prometheus: grodt-monitoring only"
    echo "- Grafana: grodt-network + grodt-monitoring"
}

# Main script logic
case ${1:-} in
    connectivity)
        check_network_connectivity
        ;;
    isolation)
        check_network_isolation
        ;;
    security)
        check_network_security
        ;;
    traffic)
        monitor_network_traffic
        ;;
    performance)
        test_network_performance
        ;;
    topology)
        show_network_topology
        ;;
    all)
        check_network_connectivity
        echo ""
        check_network_isolation
        echo ""
        check_network_security
        echo ""
        monitor_network_traffic
        echo ""
        test_network_performance
        echo ""
        show_network_topology
        ;;
    *)
        echo "GRODT Network Monitor"
        echo ""
        echo "Usage: $0 [COMMAND]"
        echo ""
        echo "Commands:"
        echo "  connectivity  Check network connectivity"
        echo "  isolation     Check network isolation"
        echo "  security      Check network security"
        echo "  traffic       Monitor network traffic"
        echo "  performance   Test network performance"
        echo "  topology      Show network topology"
        echo "  all           Run all checks"
        echo ""
        echo "Examples:"
        echo "  $0 connectivity"
        echo "  $0 all"
        ;;
esac
