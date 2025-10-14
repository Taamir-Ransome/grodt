"""
Retention CLI for GRODT Trading System.

This module provides command-line interface for managing data retention
and cleanup operations.
"""

import argparse
import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from retention_manager import RetentionManager, create_retention_manager


def setup_logging(verbose: bool = False):
    """Setup logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('logs/retention/retention_cli.log')
        ]
    )


async def run_cleanup(args):
    """Run data cleanup operation."""
    retention_manager = create_retention_manager(args.config, args.db)
    
    try:
        print(f"Starting data cleanup (dry_run={args.dry_run})...")
        
        # Determine data types to clean up
        data_types = args.data_types if args.data_types else None
        
        operations = await retention_manager.run_cleanup(
            data_types=data_types,
            dry_run=args.dry_run
        )
        
        # Display results
        print(f"\nCleanup completed: {len(operations)} operations")
        
        total_deleted = sum(op.records_deleted for op in operations)
        total_freed = sum(op.storage_freed_bytes for op in operations)
        
        print(f"Total records deleted: {total_deleted}")
        print(f"Total storage freed: {total_freed / 1024 / 1024:.2f} MB")
        
        # Show operation details
        for operation in operations:
            status_icon = "✓" if operation.status == 'success' else "✗"
            print(f"{status_icon} {operation.data_type}: {operation.records_deleted} records, {operation.storage_freed_bytes / 1024 / 1024:.2f} MB")
            
            if operation.error_message:
                print(f"  Error: {operation.error_message}")
        
        return len([op for op in operations if op.status == 'success'])
        
    except Exception as e:
        print(f"Cleanup failed: {e}")
        return 0


async def show_status(args):
    """Show retention system status."""
    retention_manager = create_retention_manager(args.config, args.db)
    
    try:
        status = retention_manager.get_retention_status()
        
        print("Data Retention System Status")
        print("=" * 40)
        print(f"Enabled: {status['enabled']}")
        print(f"Policies: {status['active_policies']}/{status['policies_count']} active")
        print(f"Last cleanup: {status['last_cleanup'] or 'Never'}")
        print(f"Cleanup operations: {status['cleanup_operations_count']}")
        
        print(f"\nStorage Usage")
        print(f"Total size: {status['storage_stats']['total_size_mb']:.2f} MB")
        
        print(f"\nData Type Breakdown:")
        for data_type, size_mb in status['storage_stats']['data_type_breakdown'].items():
            records = status['storage_stats']['record_counts'].get(data_type, 0)
            print(f"  {data_type}: {size_mb / (1024 * 1024):.2f} MB, {records:,} records")
        
        print(f"\nConfiguration:")
        print(f"  Dry run: {status['config']['dry_run']}")
        print(f"  Max storage: {status['config']['max_storage_gb']} GB")
        print(f"  Cleanup schedule: {status['config']['cleanup_schedule']}")
        
    except Exception as e:
        print(f"Failed to get status: {e}")


async def show_policies(args):
    """Show retention policies."""
    retention_manager = create_retention_manager(args.config, args.db)
    
    try:
        print("Data Retention Policies")
        print("=" * 50)
        
        for data_type, policy in retention_manager.policies.items():
            status = "ENABLED" if policy.enabled else "DISABLED"
            priority = policy.priority.value.upper()
            
            print(f"\n{data_type.upper()} ({status})")
            print(f"  Priority: {priority}")
            print(f"  Description: {policy.description}")
            print(f"  Retention:")
            print(f"    Days: {policy.retention_days}")
            print(f"    Weeks: {policy.retention_weeks}")
            print(f"    Months: {policy.retention_months}")
            print(f"    Years: {policy.retention_years}")
        
    except Exception as e:
        print(f"Failed to show policies: {e}")


async def show_storage(args):
    """Show detailed storage information."""
    retention_manager = create_retention_manager(args.config, args.db)
    
    try:
        storage_stats = await retention_manager.get_storage_stats()
        
        print("Storage Information")
        print("=" * 30)
        print(f"Total size: {storage_stats.total_size_bytes / 1024 / 1024:.2f} MB")
        print(f"Oldest record: {storage_stats.oldest_record_date or 'Unknown'}")
        print(f"Newest record: {storage_stats.newest_record_date or 'Unknown'}")
        print(f"Last cleanup: {storage_stats.last_cleanup_date or 'Never'}")
        
        print(f"\nData Type Details:")
        for data_type, size_bytes in storage_stats.data_type_breakdown.items():
            records = storage_stats.record_counts.get(data_type, 0)
            size_mb = size_bytes / 1024 / 1024
            avg_size = size_bytes / records if records > 0 else 0
            
            print(f"  {data_type}:")
            print(f"    Records: {records:,}")
            print(f"    Size: {size_mb:.2f} MB")
            print(f"    Avg size per record: {avg_size:.2f} bytes")
        
    except Exception as e:
        print(f"Failed to get storage info: {e}")


async def test_cleanup(args):
    """Test cleanup operation without actual deletion."""
    print("Running cleanup test (dry run)...")
    
    # Override dry_run to True for testing
    args.dry_run = True
    
    success_count = await run_cleanup(args)
    
    if success_count > 0:
        print(f"\nTest completed successfully: {success_count} operations would be performed")
    else:
        print("\nTest completed: No cleanup operations needed")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="GRODT Data Retention Management CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run cleanup for all data types
  python retention_cli.py cleanup --config configs/retention.yaml --db data/trading.db
  
  # Test cleanup without actual deletion
  python retention_cli.py test-cleanup --config configs/retention.yaml --db data/trading.db
  
  # Clean up specific data types
  python retention_cli.py cleanup --data-types trades orders --config configs/retention.yaml --db data/trading.db
  
  # Show system status
  python retention_cli.py status --config configs/retention.yaml --db data/trading.db
  
  # Show retention policies
  python retention_cli.py policies --config configs/retention.yaml --db data/trading.db
        """
    )
    
    # Global arguments
    parser.add_argument('--config', default='configs/retention.yaml',
                       help='Path to retention configuration file')
    parser.add_argument('--db', default='data/trading.db',
                       help='Path to SQLite database file')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose logging')
    
    # Subcommands
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Cleanup command
    cleanup_parser = subparsers.add_parser('cleanup', help='Run data cleanup')
    cleanup_parser.add_argument('--data-types', nargs='+',
                               help='Specific data types to clean up (default: all)')
    cleanup_parser.add_argument('--dry-run', action='store_true',
                               help='Simulate cleanup without actual deletion')
    
    # Test cleanup command
    test_parser = subparsers.add_parser('test-cleanup', help='Test cleanup operation')
    test_parser.add_argument('--data-types', nargs='+',
                           help='Specific data types to test cleanup for')
    
    # Status command
    subparsers.add_parser('status', help='Show retention system status')
    
    # Policies command
    subparsers.add_parser('policies', help='Show retention policies')
    
    # Storage command
    subparsers.add_parser('storage', help='Show detailed storage information')
    
    # Parse arguments
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    # Setup logging
    setup_logging(args.verbose)
    
    # Create logs directory
    Path('logs/retention').mkdir(parents=True, exist_ok=True)
    
    # Run command
    try:
        if args.command == 'cleanup':
            success_count = asyncio.run(run_cleanup(args))
            return 0 if success_count > 0 else 1
        elif args.command == 'test-cleanup':
            asyncio.run(test_cleanup(args))
            return 0
        elif args.command == 'status':
            asyncio.run(show_status(args))
            return 0
        elif args.command == 'policies':
            asyncio.run(show_policies(args))
            return 0
        elif args.command == 'storage':
            asyncio.run(show_storage(args))
            return 0
        else:
            print(f"Unknown command: {args.command}")
            return 1
            
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
