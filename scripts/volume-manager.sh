#!/bin/bash

# GRODT Volume Management Script
# This script manages Docker volumes for backup, recovery, and cleanup

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
BACKUP_DIR="/var/lib/docker/volumes/grodt_backups"
VOLUME_PREFIX="grodt_"
RETENTION_DAYS=30
CLEANUP_THRESHOLD=80  # Percentage

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

# Function to create backup directory
create_backup_dir() {
    if [ ! -d "$BACKUP_DIR" ]; then
        print_status "Creating backup directory: $BACKUP_DIR"
        sudo mkdir -p "$BACKUP_DIR"
        sudo chown $(whoami):$(whoami) "$BACKUP_DIR"
    fi
}

# Function to backup a volume
backup_volume() {
    local volume_name=$1
    local backup_name="${volume_name}_$(date +%Y%m%d_%H%M%S).tar.gz"
    local backup_path="$BACKUP_DIR/$backup_name"
    
    print_status "Backing up volume: $volume_name"
    
    # Create backup
    docker run --rm -v "$volume_name":/source -v "$BACKUP_DIR":/backup alpine tar czf "/backup/$backup_name" -C /source .
    
    if [ $? -eq 0 ]; then
        print_success "Backup created: $backup_name"
        echo "$backup_name" >> "$BACKUP_DIR/backup_manifest.txt"
    else
        print_error "Failed to backup volume: $volume_name"
        return 1
    fi
}

# Function to restore a volume
restore_volume() {
    local volume_name=$1
    local backup_file=$2
    
    if [ -z "$backup_file" ]; then
        print_error "Backup file not specified"
        return 1
    fi
    
    if [ ! -f "$BACKUP_DIR/$backup_file" ]; then
        print_error "Backup file not found: $backup_file"
        return 1
    fi
    
    print_status "Restoring volume: $volume_name from $backup_file"
    
    # Stop services that use the volume
    docker-compose -f docker/docker-compose.yml stop grodt prometheus grafana 2>/dev/null || true
    
    # Remove existing volume data
    docker volume rm "$volume_name" 2>/dev/null || true
    
    # Create new volume
    docker volume create "$volume_name"
    
    # Restore data
    docker run --rm -v "$volume_name":/target -v "$BACKUP_DIR":/backup alpine tar xzf "/backup/$backup_file" -C /target
    
    if [ $? -eq 0 ]; then
        print_success "Volume restored: $volume_name"
    else
        print_error "Failed to restore volume: $volume_name"
        return 1
    fi
}

# Function to list volumes
list_volumes() {
    print_status "GRODT Docker Volumes:"
    echo ""
    docker volume ls --filter "name=$VOLUME_PREFIX" --format "table {{.Name}}\t{{.Driver}}\t{{.Size}}"
    echo ""
    
    print_status "Volume Usage:"
    for volume in $(docker volume ls --filter "name=$VOLUME_PREFIX" --format "{{.Name}}"); do
        size=$(docker run --rm -v "$volume":/source alpine du -sh /source | cut -f1)
        echo "  $volume: $size"
    done
}

# Function to clean up old backups
cleanup_backups() {
    print_status "Cleaning up old backups..."
    
    # Remove backups older than retention period
    find "$BACKUP_DIR" -name "*.tar.gz" -type f -mtime +$RETENTION_DAYS -delete
    
    # Update manifest
    if [ -f "$BACKUP_DIR/backup_manifest.txt" ]; then
        # Remove entries for deleted backups
        for backup in $(cat "$BACKUP_DIR/backup_manifest.txt"); do
            if [ ! -f "$BACKUP_DIR/$backup" ]; then
                sed -i "/$backup/d" "$BACKUP_DIR/backup_manifest.txt"
            fi
        done
    fi
    
    print_success "Backup cleanup completed"
}

# Function to check disk usage
check_disk_usage() {
    print_status "Checking disk usage..."
    
    # Check backup directory usage
    if [ -d "$BACKUP_DIR" ]; then
        backup_usage=$(df "$BACKUP_DIR" | tail -1 | awk '{print $5}' | sed 's/%//')
        print_status "Backup directory usage: ${backup_usage}%"
        
        if [ "$backup_usage" -gt "$CLEANUP_THRESHOLD" ]; then
            print_warning "Backup directory usage is high: ${backup_usage}%"
            print_status "Running cleanup..."
            cleanup_backups
        fi
    fi
    
    # Check volume usage
    for volume in $(docker volume ls --filter "name=$VOLUME_PREFIX" --format "{{.Name}}"); do
        usage=$(docker run --rm -v "$volume":/source alpine df /source | tail -1 | awk '{print $5}' | sed 's/%//')
        print_status "Volume $volume usage: ${usage}%"
    done
}

# Function to backup all volumes
backup_all_volumes() {
    print_status "Backing up all GRODT volumes..."
    
    create_backup_dir
    
    for volume in $(docker volume ls --filter "name=$VOLUME_PREFIX" --format "{{.Name}}"); do
        backup_volume "$volume"
    done
    
    print_success "All volumes backed up successfully"
}

# Function to restore all volumes
restore_all_volumes() {
    local backup_date=$1
    
    if [ -z "$backup_date" ]; then
        print_error "Backup date not specified (format: YYYYMMDD_HHMMSS)"
        return 1
    fi
    
    print_status "Restoring all volumes from backup: $backup_date"
    
    for volume in $(docker volume ls --filter "name=$VOLUME_PREFIX" --format "{{.Name}}"); do
        backup_file="${volume}_${backup_date}.tar.gz"
        restore_volume "$volume" "$backup_file"
    done
    
    print_success "All volumes restored successfully"
}

# Function to show backup history
show_backup_history() {
    print_status "Backup History:"
    echo ""
    
    if [ -f "$BACKUP_DIR/backup_manifest.txt" ]; then
        cat "$BACKUP_DIR/backup_manifest.txt" | sort -r
    else
        print_warning "No backup history found"
    fi
}

# Function to validate volumes
validate_volumes() {
    print_status "Validating volumes..."
    
    for volume in $(docker volume ls --filter "name=$VOLUME_PREFIX" --format "{{.Name}}"); do
        print_status "Validating volume: $volume"
        
        # Check if volume is accessible
        if docker run --rm -v "$volume":/source alpine ls /source >/dev/null 2>&1; then
            print_success "Volume $volume is accessible"
        else
            print_error "Volume $volume is not accessible"
        fi
        
        # Check volume integrity
        if docker run --rm -v "$volume":/source alpine find /source -type f | head -1 >/dev/null 2>&1; then
            print_success "Volume $volume has data"
        else
            print_warning "Volume $volume appears to be empty"
        fi
    done
}

# Function to show usage
show_usage() {
    echo "GRODT Volume Manager"
    echo ""
    echo "Usage: $0 [COMMAND] [OPTIONS]"
    echo ""
    echo "Commands:"
    echo "  list                    List all volumes"
    echo "  backup [volume]         Backup specific volume or all volumes"
    echo "  restore <volume> <file> Restore volume from backup"
    echo "  cleanup                 Clean up old backups"
    echo "  usage                   Check disk usage"
    echo "  history                 Show backup history"
    echo "  validate                Validate all volumes"
    echo "  restore-all <date>      Restore all volumes from date"
    echo ""
    echo "Options:"
    echo "  -d, --date <date>       Specify backup date (YYYYMMDD_HHMMSS)"
    echo "  -f, --force             Force operation without confirmation"
    echo ""
    echo "Examples:"
    echo "  $0 list"
    echo "  $0 backup grodt_data"
    echo "  $0 restore grodt_data grodt_data_20240127_120000.tar.gz"
    echo "  $0 restore-all 20240127_120000"
    echo "  $0 cleanup"
}

# Main script logic
case ${1:-} in
    list)
        list_volumes
        ;;
    backup)
        if [ -n "$2" ]; then
            backup_volume "$2"
        else
            backup_all_volumes
        fi
        ;;
    restore)
        if [ -n "$2" ] && [ -n "$3" ]; then
            restore_volume "$2" "$3"
        else
            print_error "Usage: $0 restore <volume> <backup_file>"
            exit 1
        fi
        ;;
    cleanup)
        cleanup_backups
        ;;
    usage)
        check_disk_usage
        ;;
    history)
        show_backup_history
        ;;
    validate)
        validate_volumes
        ;;
    restore-all)
        if [ -n "$2" ]; then
            restore_all_volumes "$2"
        else
            print_error "Usage: $0 restore-all <backup_date>"
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
