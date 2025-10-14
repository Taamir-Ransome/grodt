"""
Configuration management for the retention system.

This module handles loading, validation, and management of retention configurations.
"""

import yaml
from pathlib import Path
from typing import Dict, Any, Optional
import logging

try:
    from .retention_models import RetentionConfig, RetentionPolicy, DataPriority
except ImportError:
    from retention_models import RetentionConfig, RetentionPolicy, DataPriority

logger = logging.getLogger(__name__)


class RetentionConfigManager:
    """Manages retention system configuration."""
    
    def __init__(self, config_path: str):
        self.config_path = Path(config_path)
        self.config = self._load_config()
    
    def _load_config(self) -> RetentionConfig:
        """Load configuration from YAML file."""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r') as f:
                    config_data = yaml.safe_load(f)
            else:
                logger.warning(f"Config file not found at {self.config_path}. Using defaults.")
                config_data = self._get_default_config()
                self._save_config(config_data)
            
            return self._parse_config(config_data)
            
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            return self._parse_config(self._get_default_config())
    
    def _parse_config(self, config_data: Dict[str, Any]) -> RetentionConfig:
        """Parse configuration data into RetentionConfig object."""
        # Parse retention policies
        policies = {}
        for data_type, policy_data in config_data.get('retention_policies', {}).items():
            policies[data_type] = RetentionPolicy(
                enabled=policy_data.get('enabled', True),
                retention_days=policy_data.get('retention_days', 30),
                retention_weeks=policy_data.get('retention_weeks', 4),
                retention_months=policy_data.get('retention_months', 6),
                retention_years=policy_data.get('retention_years', 1),
                priority=DataPriority(policy_data.get('priority', 'operational')),
                description=policy_data.get('description', f'Retention policy for {data_type}')
            )
        
        return RetentionConfig(
            global_settings=config_data.get('global', {}),
            scheduler_settings=config_data.get('scheduler', {}),
            retention_policies=policies,
            cleanup_settings=config_data.get('cleanup', {}),
            storage_monitoring=config_data.get('storage_monitoring', {}),
            data_integrity=config_data.get('data_integrity', {}),
            notifications=config_data.get('notifications', {}),
            compliance=config_data.get('compliance', {})
        )
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration."""
        return {
            'global': {
                'enabled': True,
                'cleanup_schedule': '03:00',
                'dry_run': False,
                'max_storage_gb': 50
            },
            'scheduler': {
                'enabled': True,
                'cleanup_schedule': '03:00',
                'check_interval_minutes': 60,
                'max_cleanup_duration_hours': 4,
                'backup_before_cleanup': True,
                'notification_channels': ['log', 'console'],
                'log_level': 'INFO',
                'dry_run': False
            },
            'retention_policies': {
                'trades': {
                    'enabled': True,
                    'retention_days': 30,
                    'retention_weeks': 4,
                    'retention_months': 6,
                    'retention_years': 1,
                    'priority': 'critical',
                    'description': 'Trade records'
                },
                'orders': {
                    'enabled': True,
                    'retention_days': 30,
                    'retention_weeks': 4,
                    'retention_months': 6,
                    'retention_years': 1,
                    'priority': 'critical',
                    'description': 'Order records'
                },
                'positions': {
                    'enabled': True,
                    'retention_days': 30,
                    'retention_weeks': 4,
                    'retention_months': 6,
                    'retention_years': 1,
                    'priority': 'critical',
                    'description': 'Position records'
                },
                'equity_curve': {
                    'enabled': True,
                    'retention_days': 15,
                    'retention_weeks': 2,
                    'retention_months': 3,
                    'retention_years': 1,
                    'priority': 'important',
                    'description': 'Equity curve data'
                },
                'market_data': {
                    'enabled': True,
                    'retention_days': 7,
                    'retention_weeks': 1,
                    'retention_months': 1,
                    'retention_years': 1,
                    'priority': 'operational',
                    'description': 'Market data'
                }
            },
            'cleanup': {
                'batch_size': 100,
                'max_cleanup_time_hours': 1,
                'backup_before_cleanup': False,
                'verify_integrity': True,
                'rollback_on_failure': True,
                'log_cleanup_operations': True,
                'create_audit_trail': True,
                'send_notifications': False
            },
            'storage_monitoring': {
                'enabled': True,
                'check_interval_hours': 6,
                'warning_threshold_percent': 80,
                'critical_threshold_percent': 95,
                'auto_cleanup_on_warning': False,
                'auto_cleanup_on_critical': True,
                'generate_reports': True,
                'report_frequency': 'weekly',
                'include_trends': True
            },
            'data_integrity': {
                'verify_before_cleanup': True,
                'checksum_verification': True,
                'backup_verification': True,
                'enable_recovery': True,
                'recovery_window_days': 7,
                'test_recovery_procedures': True
            },
            'notifications': {
                'enabled': False,
                'channels': ['log'],
                'on_cleanup_start': True,
                'on_cleanup_complete': True,
                'on_cleanup_failure': True,
                'on_storage_warning': True,
                'on_storage_critical': True,
                'include_statistics': True,
                'include_storage_info': True,
                'include_error_details': True
            },
            'compliance': {
                'audit_enabled': True,
                'audit_retention_days': 2555,
                'log_data_access': True,
                'log_cleanup_decisions': True,
                'generate_compliance_reports': True,
                'report_frequency': 'monthly',
                'include_data_lineage': True
            }
        }
    
    def _save_config(self, config_data: Dict[str, Any]):
        """Save configuration to YAML file."""
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, 'w') as f:
                yaml.dump(config_data, f, default_flow_style=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
    
    def get_policy(self, data_type: str) -> Optional[RetentionPolicy]:
        """Get retention policy for a specific data type."""
        return self.config.retention_policies.get(data_type)
    
    def is_enabled(self) -> bool:
        """Check if retention system is enabled."""
        return self.config.global_settings.get('enabled', True)
    
    def get_cleanup_schedule(self) -> str:
        """Get cleanup schedule."""
        return self.config.global_settings.get('cleanup_schedule', '03:00')
    
    def get_retention_policies(self) -> Dict[str, RetentionPolicy]:
        """Get all retention policies."""
        return self.config.retention_policies
