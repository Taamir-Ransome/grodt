"""
Unit tests for storage monitoring functionality.

Tests storage monitoring, trend analysis, and reporting capabilities.
"""

import asyncio
import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import yaml

# Import the modules to test
import sys
sys.path.append('grodtd/storage')
from retention_monitoring import StorageMonitor


class TestStorageMonitor(unittest.TestCase):
    """Test storage monitoring functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test.db"
        self.logs_dir = Path(self.temp_dir) / "logs"
        
        # Create test database
        self._create_test_database()
        
        # Create storage monitor
        self.monitor = StorageMonitor(str(self.db_path), str(self.logs_dir))
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def _create_test_database(self):
        """Create test database with sample data."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Create test tables
            cursor.execute("""
                CREATE TABLE trades (
                    id INTEGER PRIMARY KEY,
                    timestamp TEXT,
                    symbol TEXT,
                    quantity REAL,
                    price REAL
                )
            """)
            
            cursor.execute("""
                CREATE TABLE orders (
                    id INTEGER PRIMARY KEY,
                    timestamp TEXT,
                    symbol TEXT,
                    side TEXT,
                    quantity REAL
                )
            """)
            
            cursor.execute("""
                CREATE TABLE market_data (
                    id INTEGER PRIMARY KEY,
                    timestamp TEXT,
                    symbol TEXT,
                    price REAL,
                    volume REAL
                )
            """)
            
            # Insert sample data
            base_time = datetime.now() - timedelta(days=30)
            
            for i in range(100):
                timestamp = (base_time + timedelta(hours=i)).isoformat()
                cursor.execute(
                    "INSERT INTO trades (timestamp, symbol, quantity, price) VALUES (?, ?, ?, ?)",
                    (timestamp, "AAPL", 100.0, 150.0 + i)
                )
                
                cursor.execute(
                    "INSERT INTO orders (timestamp, symbol, side, quantity) VALUES (?, ?, ?, ?)",
                    (timestamp, "AAPL", "BUY", 100.0)
                )
                
                cursor.execute(
                    "INSERT INTO market_data (timestamp, symbol, price, volume) VALUES (?, ?, ?, ?)",
                    (timestamp, "AAPL", 150.0 + i, 1000.0)
                )
            
            conn.commit()
    
    @pytest.mark.asyncio
    async def test_get_current_storage_stats(self):
        """Test getting current storage statistics."""
        stats = await self.monitor.get_current_storage_stats()
        
        self.assertIsNotNone(stats)
        self.assertGreater(stats.total_size_bytes, 0)
        self.assertIsInstance(stats.data_type_breakdown, dict)
        self.assertIsInstance(stats.record_counts, dict)
        self.assertIn('trades', stats.record_counts)
        self.assertIn('orders', stats.record_counts)
        self.assertIn('market_data', stats.record_counts)
    
    @pytest.mark.asyncio
    async def test_record_storage_snapshot(self):
        """Test recording storage snapshot."""
        await self.monitor.record_storage_snapshot()
        
        # Check that history was recorded
        self.assertGreater(len(self.monitor.storage_history), 0)
        
        # Check snapshot structure
        snapshot = self.monitor.storage_history[-1]
        self.assertIn('timestamp', snapshot)
        self.assertIn('total_size_bytes', snapshot)
        self.assertIn('total_size_mb', snapshot)
        self.assertIn('data_type_breakdown', snapshot)
        self.assertIn('record_counts', snapshot)
    
    @pytest.mark.asyncio
    async def test_analyze_storage_trends(self):
        """Test storage trend analysis."""
        # Record multiple snapshots
        for i in range(5):
            await self.monitor.record_storage_snapshot()
            await asyncio.sleep(0.1)  # Small delay to ensure different timestamps
        
        # Analyze trends
        trends = await self.monitor.analyze_storage_trends(days=7)
        
        self.assertIsNotNone(trends)
        self.assertIn('analysis_period_days', trends)
        self.assertIn('data_points', trends)
        self.assertIn('current_size_mb', trends)
        self.assertIn('size_trend', trends)
        self.assertIn('growth_rate_mb_per_day', trends)
        self.assertIn('data_type_trends', trends)
        self.assertIn('recommendations', trends)
    
    @pytest.mark.asyncio
    async def test_generate_storage_report(self):
        """Test generating storage report."""
        # Record a snapshot first
        await self.monitor.record_storage_snapshot()
        
        # Generate report
        report = await self.monitor.generate_storage_report(include_trends=True)
        
        self.assertIsNotNone(report)
        self.assertIn('report_metadata', report)
        self.assertIn('current_storage', report)
        self.assertIn('storage_health', report)
        self.assertIn('trend_analysis', report)
        
        # Check report structure
        self.assertIn('generated_at', report['report_metadata'])
        self.assertIn('total_size_mb', report['current_storage'])
        self.assertIn('status', report['storage_health'])
        self.assertIn('recommendations', report['storage_health'])
    
    @pytest.mark.asyncio
    async def test_check_storage_thresholds(self):
        """Test storage threshold checking."""
        # Test with normal size
        result = await self.monitor.check_storage_thresholds(
            warning_threshold_mb=1000,
            critical_threshold_mb=5000
        )
        
        self.assertIsNotNone(result)
        self.assertIn('status', result)
        self.assertIn('alert_level', result)
        self.assertIn('current_size_mb', result)
        self.assertIn('message', result)
        self.assertIn('timestamp', result)
        
        # Should be normal for small test database
        self.assertEqual(result['status'], 'normal')
        self.assertIsNone(result['alert_level'])
    
    def test_calculate_trend(self):
        """Test trend calculation."""
        # Test increasing trend
        increasing_values = [100, 110, 120, 130, 140]
        trend = self.monitor._calculate_trend(increasing_values)
        self.assertEqual(trend, 'increasing')
        
        # Test decreasing trend
        decreasing_values = [140, 130, 120, 110, 100]
        trend = self.monitor._calculate_trend(decreasing_values)
        self.assertEqual(trend, 'decreasing')
        
        # Test stable trend
        stable_values = [100, 102, 98, 101, 99]
        trend = self.monitor._calculate_trend(stable_values)
        self.assertEqual(trend, 'stable')
    
    def test_calculate_growth_rate(self):
        """Test growth rate calculation."""
        sizes = [1000, 1100, 1200, 1300, 1400]  # 100 bytes per day
        growth_rate = self.monitor._calculate_growth_rate(sizes)
        self.assertEqual(growth_rate, 100.0)
        
        # Test with decreasing sizes
        sizes = [1400, 1300, 1200, 1100, 1000]  # -100 bytes per day
        growth_rate = self.monitor._calculate_growth_rate(sizes)
        self.assertEqual(growth_rate, -100.0)
    
    def test_predict_future_size(self):
        """Test future size prediction."""
        sizes = [1000, 1100, 1200, 1300, 1400]  # 100 bytes per day
        predicted = self.monitor._predict_future_size(sizes, days=7)
        self.assertEqual(predicted, 2100.0)  # 1400 + (100 * 7)
    
    def test_assess_storage_health(self):
        """Test storage health assessment."""
        # Test healthy
        health = self.monitor._assess_storage_health(100)  # 100MB
        self.assertEqual(health, 'healthy')
        
        # Test caution
        health = self.monitor._assess_storage_health(600)  # 600MB
        self.assertEqual(health, 'caution')
        
        # Test warning
        health = self.monitor._assess_storage_health(1500)  # 1.5GB
        self.assertEqual(health, 'warning')
        
        # Test critical
        health = self.monitor._assess_storage_health(6000)  # 6GB
        self.assertEqual(health, 'critical')
    
    def test_get_basic_recommendations(self):
        """Test basic recommendations generation."""
        # Test with small database
        recommendations = self.monitor._get_basic_recommendations(
            100,  # 100MB total
            {'trades': 50, 'orders': 30, 'market_data': 20}  # MB per type
        )
        self.assertIn('✅ Storage usage is within normal limits', recommendations)
        
        # Test with large database
        recommendations = self.monitor._get_basic_recommendations(
            1500,  # 1.5GB total
            {'trades': 800, 'orders': 400, 'market_data': 300}  # MB per type
        )
        self.assertIn('💾 Database size exceeds 1GB', recommendations[0])
        self.assertIn('📊 trades is using', recommendations[1])


if __name__ == '__main__':
    unittest.main()
