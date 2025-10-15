#!/bin/bash

# GRODT Docker Testing Script
# This script runs comprehensive tests for Docker Compose orchestration

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
TEST_DIR="tests/integration/test_docker"
PYTEST_OPTS="-v --tb=short --maxfail=5"

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

# Function to check prerequisites
check_prerequisites() {
    print_status "Checking prerequisites..."
    
    # Check Docker
    if ! command -v docker >/dev/null 2>&1; then
        print_error "Docker is not installed"
        return 1
    fi
    
    # Check Docker Compose
    if ! command -v docker-compose >/dev/null 2>&1; then
        print_error "Docker Compose is not installed"
        return 1
    fi
    
    # Check Python
    if ! command -v python >/dev/null 2>&1; then
        print_error "Python is not installed"
        return 1
    fi
    
    # Check pytest
    if ! python -m pytest --version >/dev/null 2>&1; then
        print_error "pytest is not installed"
        return 1
    fi
    
    print_success "Prerequisites check passed"
}

# Function to setup test environment
setup_test_environment() {
    print_status "Setting up test environment..."
    
    # Create test directories
    mkdir -p data logs configs
    
    # Set permissions
    chmod 755 data logs configs
    
    print_success "Test environment setup completed"
}

# Function to cleanup test environment
cleanup_test_environment() {
    print_status "Cleaning up test environment..."
    
    # Stop all services
    docker-compose -f docker/docker-compose.yml down -v 2>/dev/null || true
    docker-compose -f docker/docker-compose.scale.yml down -v 2>/dev/null || true
    docker-compose -f docker/volume-monitor.yml down -v 2>/dev/null || true
    
    # Remove test data
    rm -rf data logs configs
    
    # Clean up Docker resources
    docker system prune -f 2>/dev/null || true
    
    print_success "Test environment cleanup completed"
}

# Function to run orchestration tests
run_orchestration_tests() {
    print_status "Running orchestration tests..."
    
    python -m pytest "$TEST_DIR/test_orchestration.py" $PYTEST_OPTS
    
    if [ $? -eq 0 ]; then
        print_success "Orchestration tests passed"
    else
        print_error "Orchestration tests failed"
        return 1
    fi
}

# Function to run networking tests
run_networking_tests() {
    print_status "Running networking tests..."
    
    python -m pytest "$TEST_DIR/test_networking.py" $PYTEST_OPTS
    
    if [ $? -eq 0 ]; then
        print_success "Networking tests passed"
    else
        print_error "Networking tests failed"
        return 1
    fi
}

# Function to run volume tests
run_volume_tests() {
    print_status "Running volume tests..."
    
    python -m pytest "$TEST_DIR/test_volumes.py" $PYTEST_OPTS
    
    if [ $? -eq 0 ]; then
        print_success "Volume tests passed"
    else
        print_error "Volume tests failed"
        return 1
    fi
}

# Function to run scaling tests
run_scaling_tests() {
    print_status "Running scaling tests..."
    
    python -m pytest "$TEST_DIR/test_scaling.py" $PYTEST_OPTS
    
    if [ $? -eq 0 ]; then
        print_success "Scaling tests passed"
    else
        print_error "Scaling tests failed"
        return 1
    fi
}

# Function to run all tests
run_all_tests() {
    print_status "Running all Docker tests..."
    
    local failed_tests=0
    
    # Run orchestration tests
    if ! run_orchestration_tests; then
        failed_tests=$((failed_tests + 1))
    fi
    
    # Run networking tests
    if ! run_networking_tests; then
        failed_tests=$((failed_tests + 1))
    fi
    
    # Run volume tests
    if ! run_volume_tests; then
        failed_tests=$((failed_tests + 1))
    fi
    
    # Run scaling tests
    if ! run_scaling_tests; then
        failed_tests=$((failed_tests + 1))
    fi
    
    if [ $failed_tests -eq 0 ]; then
        print_success "All tests passed!"
        return 0
    else
        print_error "$failed_tests test suites failed"
        return 1
    fi
}

# Function to run specific test
run_specific_test() {
    local test_file=$1
    
    if [ -z "$test_file" ]; then
        print_error "Test file not specified"
        return 1
    fi
    
    if [ ! -f "$TEST_DIR/$test_file" ]; then
        print_error "Test file not found: $test_file"
        return 1
    fi
    
    print_status "Running specific test: $test_file"
    
    python -m pytest "$TEST_DIR/$test_file" $PYTEST_OPTS
    
    if [ $? -eq 0 ]; then
        print_success "Test $test_file passed"
    else
        print_error "Test $test_file failed"
        return 1
    fi
}

# Function to run tests with coverage
run_tests_with_coverage() {
    print_status "Running tests with coverage..."
    
    python -m pytest "$TEST_DIR" --cov=grodtd --cov-report=html --cov-report=term $PYTEST_OPTS
    
    if [ $? -eq 0 ]; then
        print_success "Tests with coverage completed"
        print_status "Coverage report generated in htmlcov/"
    else
        print_error "Tests with coverage failed"
        return 1
    fi
}

# Function to run performance tests
run_performance_tests() {
    print_status "Running performance tests..."
    
    # Start services
    docker-compose -f docker/docker-compose.yml up -d
    sleep 30
    
    # Run performance monitoring
    ./scripts/scale-manager.sh monitor &
    local monitor_pid=$!
    
    # Run load tests
    for i in {1..100}; do
        curl -s http://localhost:8000/health >/dev/null || true
        sleep 0.1
    done
    
    # Stop monitoring
    kill $monitor_pid 2>/dev/null || true
    
    # Cleanup
    docker-compose -f docker/docker-compose.yml down -v
    
    print_success "Performance tests completed"
}

# Function to show usage
show_usage() {
    echo "GRODT Docker Testing Script"
    echo ""
    echo "Usage: $0 [COMMAND] [OPTIONS]"
    echo ""
    echo "Commands:"
    echo "  orchestration    Run orchestration tests"
    echo "  networking       Run networking tests"
    echo "  volumes          Run volume tests"
    echo "  scaling          Run scaling tests"
    echo "  all              Run all tests"
    echo "  specific <file>  Run specific test file"
    echo "  coverage         Run tests with coverage"
    echo "  performance      Run performance tests"
    echo "  setup            Setup test environment"
    echo "  cleanup          Cleanup test environment"
    echo ""
    echo "Options:"
    echo "  -v, --verbose    Verbose output"
    echo "  -f, --fail-fast  Stop on first failure"
    echo ""
    echo "Examples:"
    echo "  $0 all"
    echo "  $0 orchestration"
    echo "  $0 specific test_orchestration.py"
    echo "  $0 coverage"
}

# Main script logic
case ${1:-} in
    orchestration)
        check_prerequisites
        setup_test_environment
        run_orchestration_tests
        cleanup_test_environment
        ;;
    networking)
        check_prerequisites
        setup_test_environment
        run_networking_tests
        cleanup_test_environment
        ;;
    volumes)
        check_prerequisites
        setup_test_environment
        run_volume_tests
        cleanup_test_environment
        ;;
    scaling)
        check_prerequisites
        setup_test_environment
        run_scaling_tests
        cleanup_test_environment
        ;;
    all)
        check_prerequisites
        setup_test_environment
        run_all_tests
        cleanup_test_environment
        ;;
    specific)
        check_prerequisites
        setup_test_environment
        run_specific_test "$2"
        cleanup_test_environment
        ;;
    coverage)
        check_prerequisites
        setup_test_environment
        run_tests_with_coverage
        cleanup_test_environment
        ;;
    performance)
        check_prerequisites
        setup_test_environment
        run_performance_tests
        cleanup_test_environment
        ;;
    setup)
        setup_test_environment
        ;;
    cleanup)
        cleanup_test_environment
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
