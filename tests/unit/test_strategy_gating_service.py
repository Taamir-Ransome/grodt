"""
Unit tests for Strategy Gating Service.

Tests the regime-based strategy gating functionality including
gating decisions, fallback behavior, and manual overrides.
"""

import pytest
import tempfile
import yaml
from unittest.mock import Mock, patch
from pathlib import Path

from grodtd.execution.strategy_gating_service import (
    StrategyGatingService, 
    GatingDecision, 
    GatingConfig,
    create_strategy_gating_service
)
from grodtd.regime.classifier import RegimeType


class TestGatingConfig:
    """Test GatingConfig dataclass."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = GatingConfig(
            regime_strategy_mappings={'trending': ['S1TrendStrategy']},
            manual_overrides={},
            override_enabled=True,
            fallback_enabled=True,
            fallback_strategies=[],
            max_decision_latency_ms=10.0,
            confidence_threshold=0.5
        )
        
        assert config.regime_strategy_mappings == {'trending': ['S1TrendStrategy']}
        assert config.manual_overrides == {}
        assert config.override_enabled is True
        assert config.fallback_enabled is True
        assert config.fallback_strategies == []
        assert config.max_decision_latency_ms == 10.0
        assert config.confidence_threshold == 0.5


class TestGatingDecision:
    """Test GatingDecision dataclass."""
    
    def test_decision_creation(self):
        """Test creating a gating decision."""
        decision = GatingDecision(
            strategy_name="S1TrendStrategy",
            enabled=True,
            regime=RegimeType.TRENDING,
            confidence=0.8,
            reasoning="Strategy enabled for trending regime",
            override_applied=False,
            timestamp="2024-12-19 10:00:00"
        )
        
        assert decision.strategy_name == "S1TrendStrategy"
        assert decision.enabled is True
        assert decision.regime == RegimeType.TRENDING
        assert decision.confidence == 0.8
        assert decision.reasoning == "Strategy enabled for trending regime"
        assert decision.override_applied is False
        assert decision.timestamp == "2024-12-19 10:00:00"


class TestStrategyGatingService:
    """Test StrategyGatingService functionality."""
    
    @pytest.fixture
    def mock_regime_service(self):
        """Create a mock regime service."""
        mock_service = Mock()
        mock_service.get_current_regime.return_value = RegimeType.TRENDING
        mock_service.get_regime_confidence.return_value = 0.8
        mock_service.is_regime_stale.return_value = False
        return mock_service
    
    @pytest.fixture
    def temp_config_file(self):
        """Create a temporary config file."""
        config_data = {
            'regime_strategy_mappings': {
                'trending': ['S1TrendStrategy', 'S3TrendStrategy'],
                'ranging': ['S2RangingStrategy'],
                'transition': [],
                'high_volatility': []
            },
            'manual_overrides': {},
            'override_enabled': True,
            'fallback_enabled': True,
            'fallback_strategies': [],
            'max_decision_latency_ms': 10.0,
            'confidence_threshold': 0.5
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            return f.name
    
    def test_service_initialization(self, mock_regime_service):
        """Test service initialization."""
        service = StrategyGatingService(regime_service=mock_regime_service)
        
        assert service.regime_service == mock_regime_service
        assert service.config is not None
        assert len(service._decision_history) == 0
    
    def test_load_config_from_file(self, temp_config_file, mock_regime_service):
        """Test loading configuration from file."""
        service = StrategyGatingService(config_path=temp_config_file, regime_service=mock_regime_service)
        
        assert service.config.regime_strategy_mappings['trending'] == ['S1TrendStrategy', 'S3TrendStrategy']
        assert service.config.regime_strategy_mappings['ranging'] == ['S2RangingStrategy']
        assert service.config.override_enabled is True
        assert service.config.fallback_enabled is True
    
    def test_create_default_config(self, mock_regime_service):
        """Test creating default configuration."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "test_config.yaml"
            
            service = StrategyGatingService(config_path=str(config_path), regime_service=mock_regime_service)
            
            assert config_path.exists()
            assert service.config.regime_strategy_mappings['trending'] == ['S1TrendStrategy', 'S3TrendStrategy']
    
    def test_validate_config_valid(self, mock_regime_service):
        """Test configuration validation with valid config."""
        service = StrategyGatingService(regime_service=mock_regime_service)
        
        valid_config = {
            'regime_strategy_mappings': {
                'trending': ['S1TrendStrategy'],
                'ranging': ['S2RangingStrategy']
            },
            'manual_overrides': {},
            'override_enabled': True,
            'fallback_enabled': True,
            'max_decision_latency_ms': 5.0,
            'confidence_threshold': 0.7
        }
        
        # Should not raise exception
        service._validate_config(valid_config)
    
    def test_validate_config_invalid(self, mock_regime_service):
        """Test configuration validation with invalid config."""
        service = StrategyGatingService(regime_service=mock_regime_service)
        
        invalid_configs = [
            # Invalid regime_strategy_mappings type
            {'regime_strategy_mappings': 'not_a_dict'},
            
            # Invalid strategy list
            {'regime_strategy_mappings': {'trending': 'not_a_list'}},
            
            # Invalid numeric values
            {'regime_strategy_mappings': {}, 'max_decision_latency_ms': -1},
            {'regime_strategy_mappings': {}, 'confidence_threshold': 1.5},
            
            # Invalid boolean values
            {'regime_strategy_mappings': {}, 'override_enabled': 'not_bool'}
        ]
        
        for invalid_config in invalid_configs:
            with pytest.raises(ValueError):
                service._validate_config(invalid_config)
    
    def test_is_strategy_enabled_trending_regime(self, mock_regime_service):
        """Test strategy enabled for trending regime."""
        service = StrategyGatingService(regime_service=mock_regime_service)
        # Clear any existing overrides
        service.clear_manual_override("S1TrendStrategy")
        
        decision = service.is_strategy_enabled("S1TrendStrategy", "BTC")
        
        assert decision.enabled is True
        assert decision.regime == RegimeType.TRENDING
        assert decision.confidence == 0.8
        assert "trending" in decision.reasoning.lower()
        assert decision.override_applied is False
    
    def test_is_strategy_enabled_ranging_regime(self, mock_regime_service):
        """Test strategy disabled for ranging regime."""
        mock_regime_service.get_current_regime.return_value = RegimeType.RANGING
        
        service = StrategyGatingService(regime_service=mock_regime_service)
        # Clear any existing overrides
        service.clear_manual_override("S1TrendStrategy")
        
        decision = service.is_strategy_enabled("S1TrendStrategy", "BTC")
        
        assert decision.enabled is False
        assert decision.regime == RegimeType.RANGING
        assert "ranging" in decision.reasoning.lower()
    
    def test_is_strategy_enabled_manual_override(self, mock_regime_service):
        """Test manual override functionality."""
        service = StrategyGatingService(regime_service=mock_regime_service)
        
        # Set manual override
        service.set_manual_override("S1TrendStrategy", True)
        
        decision = service.is_strategy_enabled("S1TrendStrategy", "BTC")
        
        assert decision.enabled is True
        assert decision.override_applied is True
        assert "manual override" in decision.reasoning.lower()
    
    def test_is_strategy_enabled_stale_regime(self, mock_regime_service):
        """Test fallback behavior with stale regime."""
        mock_regime_service.is_regime_stale.return_value = True
        
        service = StrategyGatingService(regime_service=mock_regime_service)
        # Clear any existing overrides
        service.clear_manual_override("S1TrendStrategy")
        
        decision = service.is_strategy_enabled("S1TrendStrategy", "BTC")
        
        assert decision.enabled is False  # Conservative fallback
        assert "stale" in decision.reasoning.lower()
    
    def test_is_strategy_enabled_low_confidence(self, mock_regime_service):
        """Test fallback behavior with low confidence."""
        mock_regime_service.get_regime_confidence.return_value = 0.3  # Below threshold
        
        service = StrategyGatingService(regime_service=mock_regime_service)
        # Clear any existing overrides
        service.clear_manual_override("S1TrendStrategy")
        
        decision = service.is_strategy_enabled("S1TrendStrategy", "BTC")
        
        assert decision.enabled is False  # Conservative fallback
        assert "low confidence" in decision.reasoning.lower()
    
    def test_is_strategy_enabled_no_regime(self, mock_regime_service):
        """Test fallback behavior with no regime data."""
        mock_regime_service.get_current_regime.return_value = None
        
        service = StrategyGatingService(regime_service=mock_regime_service)
        # Clear any existing overrides
        service.clear_manual_override("S1TrendStrategy")
        
        decision = service.is_strategy_enabled("S1TrendStrategy", "BTC")
        
        assert decision.enabled is False  # Conservative fallback
        assert "no regime data" in decision.reasoning.lower()
    
    def test_get_enabled_strategies(self, mock_regime_service):
        """Test getting enabled strategies list."""
        service = StrategyGatingService(regime_service=mock_regime_service)
        
        available_strategies = ["S1TrendStrategy", "S2RangingStrategy", "S3TrendStrategy"]
        enabled = service.get_enabled_strategies("BTC", available_strategies)
        
        # S1TrendStrategy should be enabled for trending regime
        assert "S1TrendStrategy" in enabled
        # S2RangingStrategy should not be enabled for trending regime
        assert "S2RangingStrategy" not in enabled
    
    def test_manual_override_management(self, mock_regime_service):
        """Test manual override management."""
        service = StrategyGatingService(regime_service=mock_regime_service)
        
        # Set override
        service.set_manual_override("S1TrendStrategy", False)
        assert service.config.manual_overrides["S1TrendStrategy"] is False
        
        # Clear override
        service.clear_manual_override("S1TrendStrategy")
        assert "S1TrendStrategy" not in service.config.manual_overrides
    
    def test_decision_history(self, mock_regime_service):
        """Test decision history tracking."""
        service = StrategyGatingService(regime_service=mock_regime_service)
        
        # Make some decisions
        service.is_strategy_enabled("S1TrendStrategy", "BTC")
        service.is_strategy_enabled("S2RangingStrategy", "BTC")
        
        # Check history
        history = service.get_decision_history()
        assert len(history) == 2
        
        # Check filtered history
        s1_history = service.get_decision_history("S1TrendStrategy")
        assert len(s1_history) == 1
        assert s1_history[0].strategy_name == "S1TrendStrategy"
    
    def test_gating_summary(self, mock_regime_service):
        """Test gating summary generation."""
        service = StrategyGatingService(regime_service=mock_regime_service)
        
        summary = service.get_gating_summary("BTC")
        
        assert summary['symbol'] == "BTC"
        assert summary['current_regime'] == "trending"
        assert summary['regime_confidence'] == 0.8
        assert summary['regime_stale'] is False
        assert 'manual_overrides' in summary
        assert 'recent_decisions' in summary
    
    def test_config_update(self, mock_regime_service):
        """Test configuration update."""
        service = StrategyGatingService(regime_service=mock_regime_service)
        
        new_config = {
            'regime_strategy_mappings': {
                'trending': ['S1TrendStrategy'],
                'ranging': ['S2RangingStrategy']
            },
            'confidence_threshold': 0.7
        }
        
        service.update_config(new_config)
        
        assert service.config.confidence_threshold == 0.7
        assert service.config.regime_strategy_mappings['trending'] == ['S1TrendStrategy']
    
    def test_config_save(self, mock_regime_service):
        """Test configuration save."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "test_save.yaml"
            
            service = StrategyGatingService(regime_service=mock_regime_service)
            service.save_config(str(config_path))
            
            assert config_path.exists()
            
            # Verify saved content
            with open(config_path, 'r') as f:
                saved_config = yaml.safe_load(f)
            
            assert 'regime_strategy_mappings' in saved_config
            assert 'override_enabled' in saved_config
    
    def test_performance_requirement(self, mock_regime_service):
        """Test that gating decisions meet performance requirements."""
        service = StrategyGatingService(regime_service=mock_regime_service)
        
        # Make multiple decisions and measure time
        import time
        start_time = time.time()
        
        for _ in range(100):
            service.is_strategy_enabled("S1TrendStrategy", "BTC")
        
        total_time = time.time() - start_time
        avg_time_ms = (total_time / 100) * 1000
        
        # Should be well under 10ms per decision
        assert avg_time_ms < 10.0, f"Average decision time {avg_time_ms:.2f}ms exceeds 10ms limit"
    
    def test_error_handling(self, mock_regime_service):
        """Test error handling in gating decisions."""
        # Mock regime service to raise exception
        mock_regime_service.get_current_regime.side_effect = Exception("Regime service error")
        
        service = StrategyGatingService(regime_service=mock_regime_service)
        # Clear any existing overrides
        service.clear_manual_override("S1TrendStrategy")
        
        decision = service.is_strategy_enabled("S1TrendStrategy", "BTC")
        
        # Should return fallback decision
        assert decision.enabled is False
        assert "fallback" in decision.reasoning.lower()


class TestFactoryFunction:
    """Test factory function for creating gating service."""
    
    def test_create_strategy_gating_service(self):
        """Test factory function."""
        service = create_strategy_gating_service()
        
        assert isinstance(service, StrategyGatingService)
        assert service.config is not None
    
    def test_create_strategy_gating_service_with_config(self):
        """Test factory function with custom config path."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "custom_config.yaml"
            
            # Create a custom config
            custom_config = {
                'regime_strategy_mappings': {
                    'trending': ['S1TrendStrategy']
                },
                'confidence_threshold': 0.8
            }
            
            with open(config_path, 'w') as f:
                yaml.dump(custom_config, f)
            
            service = create_strategy_gating_service(str(config_path))
            
            assert service.config.confidence_threshold == 0.8
            assert service.config.regime_strategy_mappings['trending'] == ['S1TrendStrategy']


if __name__ == "__main__":
    pytest.main([__file__])
