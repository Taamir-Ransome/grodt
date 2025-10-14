"""
Command-line interface for backup operations.

Provides CLI tools for manual backup creation, restoration, and management.
"""

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from grodtd.storage.backup_manager import (
    BackupManager,
    create_backup_manager,
    create_backup_scheduler
)


def setup_logging(verbose: bool = False):
    """Set up logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


async def create_backup_command(args):
    """Create a new backup."""
    backup_manager = create_backup_manager(args.config, args.database)
    
    print(f"Creating backup from database: {args.database}")
    print(f"Backup directory: {backup_manager.config.backup_directory}")
    
    backup_metadata = await backup_manager.create_backup(args.backup_id)
    
    if backup_metadata.status == 'success':
        print(f"✅ Backup created successfully: {backup_metadata.backup_id}")
        print(f"   Tables backed up: {', '.join(backup_metadata.tables_backed_up)}")
        print(f"   Total records: {backup_metadata.total_records:,}")
        print(f"   Backup size: {backup_metadata.backup_size_bytes / 1024 / 1024:.2f} MB")
        print(f"   Compression ratio: {backup_metadata.compression_ratio:.2f}")
        print(f"   Checksum: {backup_metadata.checksum[:16]}...")
    else:
        print(f"❌ Backup failed: {backup_metadata.error_message}")
        sys.exit(1)


async def restore_backup_command(args):
    """Restore from a backup."""
    backup_manager = create_backup_manager(args.config, args.database)
    
    print(f"Restoring backup: {args.backup_id}")
    print(f"Target database: {args.target_database}")
    
    success = await backup_manager.restore_backup(args.backup_id, args.target_database)
    
    if success:
        print(f"✅ Backup restored successfully: {args.backup_id}")
    else:
        print(f"❌ Backup restoration failed")
        sys.exit(1)


async def list_backups_command(args):
    """List available backups."""
    backup_manager = create_backup_manager(args.config, args.database)
    
    backups = backup_manager.list_backups()
    
    if not backups:
        print("No backups found.")
        return
    
    print(f"Found {len(backups)} backup(s):")
    print()
    
    for backup in backups:
        timestamp = backup.get('timestamp', 'Unknown')
        status = backup.get('status', 'Unknown')
        size_mb = backup.get('backup_size_bytes', 0) / 1024 / 1024
        records = backup.get('total_records', 0)
        
        print(f"📦 {backup['backup_id']}")
        print(f"   Timestamp: {timestamp}")
        print(f"   Status: {status}")
        print(f"   Size: {size_mb:.2f} MB")
        print(f"   Records: {records:,}")
        print(f"   Tables: {', '.join(backup.get('tables_backed_up', []))}")
        print()


async def backup_status_command(args):
    """Show backup system status."""
    backup_manager = create_backup_manager(args.config, args.database)
    
    status = backup_manager.get_backup_status()
    
    print("🔍 Backup System Status")
    print("=" * 50)
    print(f"Backup Directory: {status['backup_directory']}")
    print(f"Total Backups: {status['total_backups']}")
    print(f"Total Size: {status['total_size_mb']:.2f} MB")
    print()
    
    print("⚙️  Configuration:")
    config = status['config']
    print(f"   Enabled: {config['enabled']}")
    print(f"   Backup Time: {config['backup_time']}")
    print(f"   Retention Days: {config['retention_days']}")
    print(f"   Compression: {config['compression']}")
    print()
    
    if status.get('latest_backup'):
        latest = status['latest_backup']
        print("📦 Latest Backup:")
        print(f"   ID: {latest['backup_id']}")
        print(f"   Timestamp: {latest['timestamp']}")
        print(f"   Status: {latest['status']}")
        print(f"   Size: {latest['backup_size_bytes'] / 1024 / 1024:.2f} MB")
        print(f"   Records: {latest['total_records']:,}")


async def cleanup_backups_command(args):
    """Clean up old backups according to retention policy."""
    backup_manager = create_backup_manager(args.config, args.database)
    
    print("🧹 Cleaning up old backups...")
    
    await backup_manager.cleanup_old_backups()
    
    print("✅ Backup cleanup completed")


async def verify_backup_command(args):
    """Verify backup integrity."""
    backup_manager = create_backup_manager(args.config, args.database)
    
    print(f"🔍 Verifying backup: {args.backup_id}")
    
    # Get backup metadata
    backups = backup_manager.list_backups()
    backup_metadata = None
    
    for backup in backups:
        if backup['backup_id'] == args.backup_id:
            backup_metadata = backup
            break
    
    if not backup_metadata:
        print(f"❌ Backup not found: {args.backup_id}")
        sys.exit(1)
    
    # Verify backup
    backup_path = Path(backup_manager.config.backup_directory) / args.backup_id
    
    if not backup_path.exists():
        print(f"❌ Backup directory not found: {backup_path}")
        sys.exit(1)
    
    # Load metadata
    metadata_file = backup_path / 'metadata.json'
    if not metadata_file.exists():
        print(f"❌ Backup metadata not found: {metadata_file}")
        sys.exit(1)
    
    with open(metadata_file, 'r') as f:
        metadata = json.load(f)
    
    # Verify integrity
    from grodtd.storage.backup_manager import BackupMetadata
    backup_metadata_obj = BackupMetadata(**metadata)
    
    integrity_result = await backup_manager._verify_backup_integrity(
        backup_path, backup_metadata_obj
    )
    
    if integrity_result:
        print(f"✅ Backup integrity verification passed: {args.backup_id}")
    else:
        print(f"❌ Backup integrity verification failed: {args.backup_id}")
        sys.exit(1)


async def start_scheduler_command(args):
    """Start the backup scheduler."""
    backup_manager = create_backup_manager(args.config, args.database)
    scheduler = create_backup_scheduler(backup_manager)
    
    print("🚀 Starting backup scheduler...")
    print(f"   Backup time: {backup_manager.config.backup_time}")
    print(f"   Enabled: {backup_manager.config.enabled}")
    print("   Press Ctrl+C to stop")
    
    try:
        await scheduler.start_scheduler()
        
        # Keep running until interrupted
        while True:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        print("\n🛑 Stopping backup scheduler...")
        await scheduler.stop_scheduler()
        print("✅ Backup scheduler stopped")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="GRODT Backup System CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create a backup
  python -m grodtd.storage.backup_cli create --database data/grodt.db

  # List all backups
  python -m grodtd.storage.backup_cli list --database data/grodt.db

  # Restore a backup
  python -m grodtd.storage.backup_cli restore --backup-id backup_20240101_020000 --database data/grodt.db

  # Start backup scheduler
  python -m grodtd.storage.backup_cli scheduler --database data/grodt.db
        """
    )
    
    parser.add_argument(
        '--config',
        default='configs/backup.yaml',
        help='Path to backup configuration file (default: configs/backup.yaml)'
    )
    parser.add_argument(
        '--database',
        default='data/grodt.db',
        help='Path to SQLite database (default: data/grodt.db)'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Create backup command
    create_parser = subparsers.add_parser('create', help='Create a new backup')
    create_parser.add_argument(
        '--backup-id',
        help='Custom backup ID (default: auto-generated)'
    )
    
    # Restore backup command
    restore_parser = subparsers.add_parser('restore', help='Restore from a backup')
    restore_parser.add_argument(
        '--backup-id',
        required=True,
        help='Backup ID to restore'
    )
    restore_parser.add_argument(
        '--target-database',
        help='Target database path (default: same as source)'
    )
    
    # List backups command
    list_parser = subparsers.add_parser('list', help='List available backups')
    
    # Status command
    status_parser = subparsers.add_parser('status', help='Show backup system status')
    
    # Cleanup command
    cleanup_parser = subparsers.add_parser('cleanup', help='Clean up old backups')
    
    # Verify command
    verify_parser = subparsers.add_parser('verify', help='Verify backup integrity')
    verify_parser.add_argument(
        '--backup-id',
        required=True,
        help='Backup ID to verify'
    )
    
    # Scheduler command
    scheduler_parser = subparsers.add_parser('scheduler', help='Start backup scheduler')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Set up logging
    setup_logging(args.verbose)
    
    # Set default target database for restore
    if args.command == 'restore' and not hasattr(args, 'target_database'):
        args.target_database = args.database
    
    # Execute command
    try:
        if args.command == 'create':
            asyncio.run(create_backup_command(args))
        elif args.command == 'restore':
            asyncio.run(restore_backup_command(args))
        elif args.command == 'list':
            asyncio.run(list_backups_command(args))
        elif args.command == 'status':
            asyncio.run(backup_status_command(args))
        elif args.command == 'cleanup':
            asyncio.run(cleanup_backups_command(args))
        elif args.command == 'verify':
            asyncio.run(verify_backup_command(args))
        elif args.command == 'scheduler':
            asyncio.run(start_scheduler_command(args))
        else:
            parser.print_help()
            sys.exit(1)
            
    except Exception as e:
        print(f"❌ Error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
