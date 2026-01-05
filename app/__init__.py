"""VyaparaCore Flask Application Factory"""
from flask import Flask, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager

from config.database import db, migrate
from config.config import Config


jwt = JWTManager()


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    
    # CORS with security settings
    CORS(app, resources={
        r"/api/*": {
            "origins": app.config.get('CORS_ORIGINS', ['http://localhost:3000']),
            "methods": ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization", "X-CSRF-Token"],
            "supports_credentials": True
        }
    })

    # Security headers
    @app.after_request
    def add_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        return response

    # JWT error handlers
    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        return jsonify({'error': 'Token has expired'}), 401

    @jwt.invalid_token_loader
    def invalid_token_callback(error):
        return jsonify({'error': 'Invalid token'}), 401

    @jwt.unauthorized_loader
    def missing_token_callback(error):
        return jsonify({'error': 'Authorization token required'}), 401

    @jwt.revoked_token_loader
    def revoked_token_callback(jwt_header, jwt_payload):
        return jsonify({'error': 'Token has been revoked'}), 401

    # Import models for migrations
    with app.app_context():
        from app import models

    # Register blueprints
    from app.routes.auth import auth_bp
    from app.routes.organization import organization_bp
    from app.routes.user import user_bp
    from app.routes.customer import customer_bp
    from app.routes.supplier import supplier_bp
    from app.routes.products import product_bp
    from app.routes.inventory import inventory_bp
    from app.routes.quotation import quotation_bp
    from app.routes.order import order_bp
    from app.routes.invoice import invoice_bp
    from app.routes.payment import payment_bp
    from app.routes.report import report_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.activity import activity_bp
    from app.routes.notification import notification_bp

    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(organization_bp, url_prefix='/api/organizations')
    app.register_blueprint(user_bp, url_prefix='/api/users')
    app.register_blueprint(customer_bp, url_prefix='/api/customers')
    app.register_blueprint(supplier_bp, url_prefix='/api/suppliers')
    app.register_blueprint(product_bp, url_prefix='/api/products')
    app.register_blueprint(inventory_bp, url_prefix='/api/inventory')
    app.register_blueprint(quotation_bp, url_prefix='/api/quotations')
    app.register_blueprint(order_bp, url_prefix='/api/orders')
    app.register_blueprint(invoice_bp, url_prefix='/api/invoices')
    app.register_blueprint(payment_bp, url_prefix='/api/payments')
    app.register_blueprint(report_bp, url_prefix='/api/reports')
    app.register_blueprint(dashboard_bp, url_prefix='/api/dashboard')
    app.register_blueprint(activity_bp, url_prefix='/api/activities')
    app.register_blueprint(notification_bp, url_prefix='/api/notifications')

    # Health check endpoint
    @app.route('/api/health')
    def health_check():
        return jsonify({'status': 'healthy', 'app': 'VyaparaCore'})

    # One-time seed endpoint (delete after use)
    @app.route('/api/seed')
    def run_seed():
        from flask import request
        secret = request.args.get('key', '')
        # Simple fixed seed key - DELETE THIS ENDPOINT AFTER SEEDING
        if secret != 'vyapara2024seed':
            return jsonify({'error': 'Invalid secret'}), 403
        try:
            from seeds import run_all_seeds
            run_all_seeds()
            return jsonify({'status': 'success', 'message': 'Database seeded!'})
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)}), 500

    return app