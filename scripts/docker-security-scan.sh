#!/bin/bash

# Docker Security Scanning Script for GRODT Trading System
# This script performs comprehensive security scanning of Docker containers

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
IMAGE_NAME="grodt-trading"
IMAGE_TAG="latest"
FULL_IMAGE_NAME="${IMAGE_NAME}:${IMAGE_TAG}"
SCAN_RESULTS_DIR="./security-scan-results"
TRIVY_RESULTS_FILE="${SCAN_RESULTS_DIR}/trivy-results.json"
DOCKER_BENCH_RESULTS_FILE="${SCAN_RESULTS_DIR}/docker-bench-results.txt"

# Functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_tool() {
    local tool=$1
    if ! command -v $tool &> /dev/null; then
        log_error "$tool is not installed. Please install it first."
        return 1
    fi
    return 0
}

# Create results directory
mkdir -p "$SCAN_RESULTS_DIR"

log_info "Starting Docker security scanning for $FULL_IMAGE_NAME"

# Check if Docker is running
if ! docker info &> /dev/null; then
    log_error "Docker is not running. Please start Docker first."
    exit 1
fi

# Build the image if it doesn't exist
if ! docker image inspect "$FULL_IMAGE_NAME" &> /dev/null; then
    log_info "Building Docker image..."
    docker build -f docker/Dockerfile -t "$FULL_IMAGE_NAME" .
    if [ $? -ne 0 ]; then
        log_error "Failed to build Docker image"
        exit 1
    fi
    log_info "Docker image built successfully"
else
    log_info "Using existing Docker image: $FULL_IMAGE_NAME"
fi

# 1. Trivy vulnerability scanning
log_info "Running Trivy vulnerability scan..."
if check_tool "trivy"; then
    trivy image --format json --output "$TRIVY_RESULTS_FILE" "$FULL_IMAGE_NAME"
    
    # Check for high and critical vulnerabilities
    HIGH_CRITICAL_COUNT=$(jq '[.Results[]?.Vulnerabilities[]? | select(.Severity == "HIGH" or .Severity == "CRITICAL")] | length' "$TRIVY_RESULTS_FILE")
    
    if [ "$HIGH_CRITICAL_COUNT" -gt 0 ]; then
        log_warn "Found $HIGH_CRITICAL_COUNT HIGH/CRITICAL vulnerabilities"
        jq '.Results[]?.Vulnerabilities[]? | select(.Severity == "HIGH" or .Severity == "CRITICAL") | {VulnerabilityID, Severity, Title}' "$TRIVY_RESULTS_FILE"
    else
        log_info "No HIGH/CRITICAL vulnerabilities found"
    fi
    
    # Generate human-readable report
    trivy image --format table "$FULL_IMAGE_NAME" > "${SCAN_RESULTS_DIR}/trivy-table.txt"
    log_info "Trivy scan completed. Results saved to $TRIVY_RESULTS_FILE"
else
    log_warn "Trivy not available, skipping vulnerability scan"
fi

# 2. Docker Bench Security
log_info "Running Docker Bench Security..."
if check_tool "docker-bench-security"; then
    docker-bench-security > "$DOCKER_BENCH_RESULTS_FILE" 2>&1
    log_info "Docker Bench Security completed. Results saved to $DOCKER_BENCH_RESULTS_FILE"
else
    log_warn "Docker Bench Security not available, skipping security benchmark"
fi

# 3. Container runtime security check
log_info "Running container runtime security check..."

# Start container for runtime checks
CONTAINER_NAME="grodt-security-test-$(date +%s)"
docker run -d --name "$CONTAINER_NAME" -p 8000:8000 "$FULL_IMAGE_NAME"

# Wait for container to start
sleep 10

# Check if container is running as non-root user
USER_CHECK=$(docker exec "$CONTAINER_NAME" whoami 2>/dev/null || echo "unknown")
if [ "$USER_CHECK" = "grodt" ]; then
    log_info "✓ Container is running as non-root user: $USER_CHECK"
else
    log_warn "⚠ Container is running as user: $USER_CHECK (expected: grodt)"
fi

# Check file permissions
PERM_CHECK=$(docker exec "$CONTAINER_NAME" ls -la /app 2>/dev/null | head -5)
log_info "Container file permissions:"
echo "$PERM_CHECK"

# Check for unnecessary packages
PACKAGES=$(docker exec "$CONTAINER_NAME" dpkg -l 2>/dev/null | wc -l)
log_info "Number of installed packages: $PACKAGES"

# Check for exposed ports
EXPOSED_PORTS=$(docker port "$CONTAINER_NAME" 2>/dev/null || echo "No exposed ports")
log_info "Exposed ports: $EXPOSED_PORTS"

# Check environment variables
ENV_VARS=$(docker exec "$CONTAINER_NAME" env 2>/dev/null | grep -E "(PASSWORD|SECRET|KEY|TOKEN)" || echo "No sensitive environment variables found")
if [ "$ENV_VARS" != "No sensitive environment variables found" ]; then
    log_warn "⚠ Potential sensitive environment variables found"
    echo "$ENV_VARS"
else
    log_info "✓ No obvious sensitive environment variables found"
fi

# Clean up test container
docker stop "$CONTAINER_NAME" >/dev/null 2>&1
docker rm "$CONTAINER_NAME" >/dev/null 2>&1

# 4. Image size analysis
log_info "Analyzing image size..."
IMAGE_SIZE=$(docker images --format "table {{.Size}}" "$FULL_IMAGE_NAME" | tail -1)
log_info "Image size: $IMAGE_SIZE"

# Check if image is reasonable size (less than 1GB)
SIZE_BYTES=$(docker images --format "{{.Size}}" "$FULL_IMAGE_NAME" | sed 's/[^0-9.]*//g' | head -1)
if [ -n "$SIZE_BYTES" ]; then
    if (( $(echo "$SIZE_BYTES < 1000" | bc -l) )); then
        log_info "✓ Image size is reasonable: $IMAGE_SIZE"
    else
        log_warn "⚠ Image size is large: $IMAGE_SIZE"
    fi
fi

# 5. Generate security report
log_info "Generating security report..."
REPORT_FILE="${SCAN_RESULTS_DIR}/security-report.md"

cat > "$REPORT_FILE" << EOF
# Docker Security Scan Report

**Image:** $FULL_IMAGE_NAME  
**Scan Date:** $(date)  
**Scanner:** Docker Security Scan Script  

## Summary

- **Image Size:** $IMAGE_SIZE
- **Runtime User:** $USER_CHECK
- **Installed Packages:** $PACKAGES
- **High/Critical Vulnerabilities:** $HIGH_CRITICAL_COUNT

## Scan Results

### Vulnerability Scan (Trivy)
EOF

if [ -f "$TRIVY_RESULTS_FILE" ]; then
    echo "- **Status:** Completed" >> "$REPORT_FILE"
    echo "- **High/Critical Issues:** $HIGH_CRITICAL_COUNT" >> "$REPORT_FILE"
    echo "- **Details:** See trivy-results.json" >> "$REPORT_FILE"
else
    echo "- **Status:** Skipped (Trivy not available)" >> "$REPORT_FILE"
fi

cat >> "$REPORT_FILE" << EOF

### Security Benchmark (Docker Bench)
EOF

if [ -f "$DOCKER_BENCH_RESULTS_FILE" ]; then
    echo "- **Status:** Completed" >> "$REPORT_FILE"
    echo "- **Details:** See docker-bench-results.txt" >> "$REPORT_FILE"
else
    echo "- **Status:** Skipped (Docker Bench not available)" >> "$REPORT_FILE"
fi

cat >> "$REPORT_FILE" << EOF

### Runtime Security
- **Non-root User:** $([ "$USER_CHECK" = "grodt" ] && echo "✓ Yes" || echo "⚠ No")
- **File Permissions:** Checked
- **Environment Variables:** $([ "$ENV_VARS" != "No sensitive environment variables found" ] && echo "⚠ Issues found" || echo "✓ Clean")

## Recommendations

1. **Regular Updates:** Keep base images and dependencies updated
2. **Minimal Attack Surface:** Remove unnecessary packages and files
3. **Security Scanning:** Run this scan regularly in CI/CD pipeline
4. **Runtime Security:** Monitor container runtime behavior

## Files Generated

- \`trivy-results.json\` - Detailed vulnerability scan results
- \`trivy-table.txt\` - Human-readable vulnerability report
- \`docker-bench-results.txt\` - Security benchmark results
- \`security-report.md\` - This summary report

EOF

log_info "Security scan completed!"
log_info "Results saved to: $SCAN_RESULTS_DIR"
log_info "Summary report: $REPORT_FILE"

# Display summary
echo ""
echo "=== SECURITY SCAN SUMMARY ==="
echo "Image: $FULL_IMAGE_NAME"
echo "Size: $IMAGE_SIZE"
echo "User: $USER_CHECK"
echo "High/Critical Vulnerabilities: $HIGH_CRITICAL_COUNT"
echo "Results Directory: $SCAN_RESULTS_DIR"
echo ""

if [ "$HIGH_CRITICAL_COUNT" -gt 0 ]; then
    log_warn "⚠ Security issues found. Please review the scan results."
    exit 1
else
    log_info "✓ No critical security issues found."
fi
