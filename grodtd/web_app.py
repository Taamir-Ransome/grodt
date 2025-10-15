"""
Flask web application for GRODT with analytics endpoints.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from flask import Flask, jsonify, request
from flask_cors import CORS

from grodtd.analytics.regime_performance_service import RegimePerformanceService
from grodtd.regime.service import get_regime_service, RegimeType
from grodtd.monitoring.metrics_endpoint import create_metrics_endpoint


class GRODTWebApp:
    """GRODT Flask web application with analytics endpoints."""
    
    def __init__(self, db_path: str):
        self.app = Flask(__name__)
        self.db_path = db_path
        self.logger = logging.getLogger(__name__)
        
        # Initialize services
        self.regime_service = get_regime_service()
        self.analytics_service = RegimePerformanceService(db_path, self.regime_service)
        self.metrics_endpoint = create_metrics_endpoint(db_path)
        
        # Configure CORS for cross-origin requests
        CORS(self.app)
        
        # Register routes
        self._register_routes()
        
        self.logger.info("GRODT web application initialized")
    
    def _register_routes(self):
        """Register all API routes."""
        
        @self.app.route('/health', methods=['GET'])
        def health_check():
            """Health check endpoint."""
            return jsonify({
                'status': 'healthy',
                'timestamp': datetime.now().isoformat(),
                'service': 'grodt-analytics'
            })
        
        @self.app.route('/analytics/regime-performance', methods=['GET'])
        def get_regime_performance():
            """
            Get regime performance analytics.
            
            Query parameters:
            - symbol: Trading symbol (optional)
            - regime: Specific regime type (optional)
            - start_date: Start date for filtering (optional)
            - end_date: End date for filtering (optional)
            """
            try:
                symbol = request.args.get('symbol', 'BTC')
                regime_str = request.args.get('regime')
                start_date = request.args.get('start_date')
                end_date = request.args.get('end_date')
                
                # Parse regime if provided
                regime = None
                if regime_str:
                    try:
                        regime = RegimeType(regime_str)
                    except ValueError:
                        return jsonify({
                            'error': f'Invalid regime type: {regime_str}',
                            'valid_regimes': [r.value for r in RegimeType]
                        }), 400
                
                # Get performance data
                performance_data = self.analytics_service.get_regime_performance(symbol, regime)
                
                # Apply date filtering if provided
                if start_date or end_date:
                    performance_data = self._filter_by_date_range(performance_data, start_date, end_date)
                
                return jsonify({
                    'symbol': symbol,
                    'regime': regime.value if regime else 'all',
                    'performance_data': performance_data,
                    'timestamp': datetime.now().isoformat()
                })
                
            except Exception as e:
                self.logger.error(f"Error in regime performance endpoint: {e}")
                return jsonify({
                    'error': 'Internal server error',
                    'message': str(e)
                }), 500
        
        @self.app.route('/analytics/regime-accuracy', methods=['GET'])
        def get_regime_accuracy():
            """
            Get regime classification accuracy analytics.
            
            Query parameters:
            - symbol: Trading symbol (optional)
            - regime: Specific regime type (optional)
            - start_date: Start date for filtering (optional)
            - end_date: End date for filtering (optional)
            """
            try:
                symbol = request.args.get('symbol', 'BTC')
                regime_str = request.args.get('regime')
                start_date = request.args.get('start_date')
                end_date = request.args.get('end_date')
                
                # Parse regime if provided
                regime = None
                if regime_str:
                    try:
                        regime = RegimeType(regime_str)
                    except ValueError:
                        return jsonify({
                            'error': f'Invalid regime type: {regime_str}',
                            'valid_regimes': [r.value for r in RegimeType]
                        }), 400
                
                # Get accuracy data
                accuracy_data = self.analytics_service.get_regime_accuracy(symbol, regime)
                
                # Apply date filtering if provided
                if start_date or end_date:
                    accuracy_data = self._filter_by_date_range(accuracy_data, start_date, end_date)
                
                return jsonify({
                    'symbol': symbol,
                    'regime': regime.value if regime else 'all',
                    'accuracy_data': accuracy_data,
                    'timestamp': datetime.now().isoformat()
                })
                
            except Exception as e:
                self.logger.error(f"Error in regime accuracy endpoint: {e}")
                return jsonify({
                    'error': 'Internal server error',
                    'message': str(e)
                }), 500
        
        @self.app.route('/analytics/service-status', methods=['GET'])
        def get_analytics_service_status():
            """Get analytics service status including circuit breaker state."""
            try:
                status = self.analytics_service.get_service_status()
                return jsonify({
                    'service_status': status,
                    'timestamp': datetime.now().isoformat()
                })
                
            except Exception as e:
                self.logger.error(f"Error getting service status: {e}")
                return jsonify({
                    'error': 'Internal server error',
                    'message': str(e)
                }), 500
        
        @self.app.route('/analytics/update-trade', methods=['POST'])
        def update_trade_performance():
            """
            Update trade performance metrics.
            
            Expected JSON payload:
            {
                "symbol": "BTC",
                "pnl": 150.0,
                "timestamp": "2024-12-19T10:30:00Z",
                "regime": "trending"
            }
            """
            try:
                data = request.get_json()
                if not data:
                    return jsonify({'error': 'No JSON data provided'}), 400
                
                # Validate required fields
                required_fields = ['symbol', 'pnl']
                for field in required_fields:
                    if field not in data:
                        return jsonify({'error': f'Missing required field: {field}'}), 400
                
                # Update trade performance
                success = self.analytics_service.update_trade_performance(
                    data['symbol'], 
                    data
                )
                
                if success:
                    return jsonify({
                        'status': 'success',
                        'message': 'Trade performance updated successfully',
                        'timestamp': datetime.now().isoformat()
                    })
                else:
                    return jsonify({
                        'status': 'error',
                        'message': 'Failed to update trade performance',
                        'timestamp': datetime.now().isoformat()
                    }), 500
                
            except Exception as e:
                self.logger.error(f"Error updating trade performance: {e}")
                return jsonify({
                    'error': 'Internal server error',
                    'message': str(e)
                }), 500
        
        @self.app.route('/analytics/update-accuracy', methods=['POST'])
        def update_regime_accuracy():
            """
            Update regime classification accuracy.
            
            Expected JSON payload:
            {
                "symbol": "BTC",
                "predicted_regime": "trending",
                "actual_regime": "trending",
                "confidence": 0.85
            }
            """
            try:
                data = request.get_json()
                if not data:
                    return jsonify({'error': 'No JSON data provided'}), 400
                
                # Validate required fields
                required_fields = ['symbol', 'predicted_regime', 'actual_regime', 'confidence']
                for field in required_fields:
                    if field not in data:
                        return jsonify({'error': f'Missing required field: {field}'}), 400
                
                # Parse regime types
                try:
                    predicted_regime = RegimeType(data['predicted_regime'])
                    actual_regime = RegimeType(data['actual_regime'])
                except ValueError as e:
                    return jsonify({
                        'error': f'Invalid regime type: {e}',
                        'valid_regimes': [r.value for r in RegimeType]
                    }), 400
                
                # Update regime accuracy
                success = self.analytics_service.update_regime_accuracy(
                    data['symbol'],
                    predicted_regime,
                    actual_regime,
                    data['confidence']
                )
                
                if success:
                    return jsonify({
                        'status': 'success',
                        'message': 'Regime accuracy updated successfully',
                        'timestamp': datetime.now().isoformat()
                    })
                else:
                    return jsonify({
                        'status': 'error',
                        'message': 'Failed to update regime accuracy',
                        'timestamp': datetime.now().isoformat()
                    }), 500
                
            except Exception as e:
                self.logger.error(f"Error updating regime accuracy: {e}")
                return jsonify({
                    'error': 'Internal server error',
                    'message': str(e)
                }), 500
        
        @self.app.route('/metrics', methods=['GET'])
        def get_metrics():
            """
            Prometheus metrics endpoint.
            
            Returns metrics in Prometheus format for scraping.
            """
            try:
                return self.metrics_endpoint.get_metrics_response()
            except Exception as e:
                self.logger.error(f"Error getting metrics: {e}")
                return jsonify({
                    'error': 'Internal server error',
                    'message': str(e)
                }), 500
        
        @self.app.route('/metrics/status', methods=['GET'])
        def get_metrics_status():
            """
            Get metrics collection status.
            
            Returns information about metrics collection status and performance.
            """
            try:
                status = self.metrics_endpoint.get_collection_status()
                return jsonify({
                    'metrics_status': status,
                    'timestamp': datetime.now().isoformat()
                })
            except Exception as e:
                self.logger.error(f"Error getting metrics status: {e}")
                return jsonify({
                    'error': 'Internal server error',
                    'message': str(e)
                }), 500
    
    def _filter_by_date_range(self, data: Dict[str, Any], start_date: Optional[str], end_date: Optional[str]) -> Dict[str, Any]:
        """Filter data by date range."""
        # This is a simplified implementation
        # In practice, you'd filter the database query results
        return data
    
    def run(self, host='0.0.0.0', port=5000, debug=False):
        """Run the Flask application."""
        self.logger.info(f"Starting GRODT web application on {host}:{port}")
        self.app.run(host=host, port=port, debug=debug)


def create_app(db_path: str) -> Flask:
    """Create and configure the Flask application."""
    web_app = GRODTWebApp(db_path)
    return web_app.app


if __name__ == "__main__":
    # Default database path
    db_path = "data/grodt.db"
    
    # Create and run the application
    app = create_app(db_path)
    web_app = GRODTWebApp(db_path)
    web_app.run(debug=True)
