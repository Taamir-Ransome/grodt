# Docker Deployment Guide

## Overview

This guide covers the Docker containerization of the GRODT trading system, including build processes, security considerations, and deployment strategies.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Docker Configuration](#docker-configuration)
3. [Security Features](#security-features)
4. [Development Workflow](#development-workflow)
5. [Production Deployment](#production-deployment)
6. [Monitoring and Health Checks](#monitoring-and-health-checks)
7. [Troubleshooting](#troubleshooting)

## Quick Start

### Prerequisites

- Docker 20.10+
- Docker Compose 2.0+
- 4GB RAM minimum
- 10GB disk space

### Build and Run

```bash
# Build the Docker image
./scripts/docker-dev.sh build

# Start all services
./scripts/docker-dev.sh up

# Check service status
./scripts/docker-dev.sh status

# View logs
./scripts/docker-dev.sh logs-app
```

### Access Points

- **GRODT Application**: http://localhost:8000
- **Prometheus Metrics**: http://localhost:9091
- **Grafana Dashboards**: http://localhost:3000 (admin/admin)

## Docker Configuration

### Multi-Stage Build

The Dockerfile uses a multi-stage build process for optimization:

```dockerfile
# Stage 1: Build environment
FROM python:3.12-slim as builder
# Install dependencies and build

# Stage 2: Runtime environment  
FROM python:3.12-slim as runtime
# Copy only necessary files for runtime
```

**Benefits:**
- Smaller final image size
- Reduced attack surface
- Better layer caching
- Separation of build and runtime dependencies

### Security Features

#### Non-Root User
```dockerfile
# Create non-root user for security
RUN groupadd -r grodt && useradd -r -g grodt grodt
USER grodt
```

#### File Permissions
```dockerfile
# Set proper file permissions
RUN chmod -R 755 /app \
    && chmod -R 777 /app/data /app/logs
```

#### Health Checks
```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1
```

### Container Orchestration

The `docker-compose.yml` provides:

- **Service Dependencies**: Proper startup order
- **Health Checks**: Container health monitoring
- **Logging**: Structured logging with rotation
- **Networking**: Isolated network for services
- **Volumes**: Persistent data storage
- **Restart Policies**: Automatic recovery

## Security Features

### Container Security

1. **Non-Root Execution**: Container runs as `grodt` user
2. **Minimal Base Image**: Python 3.12-slim for reduced attack surface
3. **File Permissions**: Proper ownership and permissions
4. **Health Monitoring**: Regular health checks
5. **Logging**: Structured JSON logging

### Security Scanning

Run comprehensive security scans:

```bash
# Run security scan
./scripts/docker-security-scan.sh

# Check for vulnerabilities
trivy image grodt-trading:latest

# Security benchmark
docker-bench-security
```

### Security Best Practices

- **Image Scanning**: Regular vulnerability scans
- **Base Image Updates**: Keep base images current
- **Secret Management**: Use environment variables or secrets
- **Network Isolation**: Custom networks for services
- **Resource Limits**: CPU and memory constraints

## Development Workflow

### Development Commands

```bash
# Build image
./scripts/docker-dev.sh build

# Start services
./scripts/docker-dev.sh up

# View logs
./scripts/docker-dev.sh logs-app

# Open shell in container
./scripts/docker-dev.sh shell

# Run tests
./scripts/docker-dev.sh test

# Stop services
./scripts/docker-dev.sh down

# Clean up
./scripts/docker-dev.sh clean
```

### Development Environment

1. **Hot Reload**: Mount source code as volume
2. **Debug Mode**: Enable debug logging
3. **Test Environment**: Isolated test containers
4. **Code Quality**: Pre-commit hooks for Docker files

### Testing

```bash
# Run integration tests
pytest tests/integration/test_docker/ -v

# Run security tests
./scripts/docker-security-scan.sh

# Performance tests
docker stats grodt-trading
```

## Production Deployment

### Production Configuration

```yaml
# docker-compose.prod.yml
version: '3.8'
services:
  grodt:
    image: grodt-trading:latest
    restart: always
    environment:
      - ENV=production
      - LOG_LEVEL=INFO
    deploy:
      resources:
        limits:
          memory: 2G
          cpus: '1.0'
        reservations:
          memory: 1G
          cpus: '0.5'
```

### Production Considerations

1. **Resource Limits**: Set CPU and memory limits
2. **Health Checks**: Configure proper health monitoring
3. **Logging**: Centralized logging with rotation
4. **Backup**: Regular data backups
5. **Updates**: Rolling updates strategy
6. **Monitoring**: Comprehensive monitoring setup

### Deployment Strategies

#### Single Host Deployment
```bash
# Deploy on single host
docker-compose -f docker-compose.yml up -d
```

#### Multi-Host Deployment
```bash
# Deploy with Docker Swarm
docker stack deploy -c docker-compose.yml grodt-stack
```

#### Kubernetes Deployment
```yaml
# kubernetes-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: grodt-trading
spec:
  replicas: 3
  selector:
    matchLabels:
      app: grodt-trading
  template:
    metadata:
      labels:
        app: grodt-trading
    spec:
      containers:
      - name: grodt
        image: grodt-trading:latest
        ports:
        - containerPort: 8000
        env:
        - name: ENV
          value: "production"
```

## Monitoring and Health Checks

### Health Endpoints

- **Health Check**: `GET /health` - Basic health status
- **Readiness**: `GET /ready` - Service readiness
- **Metrics**: `GET /metrics` - Prometheus metrics

### Monitoring Stack

1. **Prometheus**: Metrics collection
2. **Grafana**: Visualization and dashboards
3. **Alerting**: Performance and error alerts
4. **Logging**: Structured JSON logs

### Health Check Configuration

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 40s
```

## Troubleshooting

### Common Issues

#### Container Won't Start
```bash
# Check container logs
docker logs grodt-trading

# Check container status
docker ps -a

# Check resource usage
docker stats grodt-trading
```

#### Health Check Failures
```bash
# Test health endpoint manually
curl http://localhost:8000/health

# Check container health
docker inspect grodt-trading --format='{{.State.Health.Status}}'
```

#### Performance Issues
```bash
# Monitor resource usage
docker stats grodt-trading

# Check container limits
docker inspect grodt-trading --format='{{.HostConfig.Memory}}'
```

### Debug Commands

```bash
# Open shell in running container
docker exec -it grodt-trading /bin/bash

# Check container processes
docker exec grodt-trading ps aux

# Check container environment
docker exec grodt-trading env

# Check container network
docker network ls
docker network inspect grodt-network
```

### Log Analysis

```bash
# View application logs
docker-compose logs grodt

# Follow logs in real-time
docker-compose logs -f grodt

# Export logs
docker-compose logs grodt > grodt-logs.txt
```

## Configuration Files

### Docker Configuration

- **Dockerfile**: `docker/Dockerfile` - Multi-stage build configuration
- **Docker Compose**: `docker/docker-compose.yml` - Service orchestration
- **Docker Config**: `configs/docker.yaml` - Container-specific settings
- **Docker Ignore**: `.dockerignore` - Build context exclusions

### Scripts

- **Development**: `scripts/docker-dev.sh` - Development workflow
- **Security**: `scripts/docker-security-scan.sh` - Security scanning
- **Testing**: `tests/integration/test_docker/` - Container tests

## Best Practices

### Development

1. **Use Multi-Stage Builds**: Separate build and runtime environments
2. **Minimize Layers**: Combine RUN commands when possible
3. **Use .dockerignore**: Exclude unnecessary files
4. **Security First**: Run as non-root user
5. **Health Checks**: Implement proper health monitoring

### Production

1. **Resource Limits**: Set appropriate CPU and memory limits
2. **Logging**: Implement structured logging with rotation
3. **Monitoring**: Comprehensive health and performance monitoring
4. **Backup**: Regular data and configuration backups
5. **Updates**: Rolling update strategies

### Security

1. **Regular Scanning**: Automated vulnerability scanning
2. **Base Image Updates**: Keep base images current
3. **Secret Management**: Use proper secret management
4. **Network Security**: Isolate services with custom networks
5. **Access Control**: Implement proper access controls

## Conclusion

The Docker containerization provides a robust, secure, and scalable deployment solution for the GRODT trading system. The multi-stage build process, security features, and comprehensive monitoring ensure production-ready containerized applications.

For additional support or questions, refer to the project documentation or contact the development team.
