"""Security utilities for VyaparaCore"""
import re
import secrets
import hashlib
import hmac
from datetime import datetime, timedelta
from functools import wraps
from flask import request, g, jsonify, current_app
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity, get_jwt
import bleach
from werkzeug.security import generate_password_hash, check_password_hash


# Password hashing
def hash_password(password: str) -> str:
    return generate_password_hash(password, method='pbkdf2:sha256:600000')


def verify_password(password: str, password_hash: str) -> bool:
    return check_password_hash(password_hash, password)


# Token generation
def generate_token(length: int = 32) -> str:
    return secrets.token_urlsafe(length)


def generate_otp(length: int = 6) -> str:
    return ''.join([str(secrets.randbelow(10)) for _ in range(length)])


# Input sanitization
ALLOWED_TAGS = ['b', 'i', 'u', 'em', 'strong', 'p', 'br', 'ul', 'ol', 'li']
ALLOWED_ATTRIBUTES = {}


def sanitize_html(text: str) -> str:
    if not text:
        return text
    return bleach.clean(text, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES, strip=True)


def sanitize_string(text: str) -> str:
    if not text:
        return text
    return bleach.clean(text, tags=[], strip=True).strip()


def sanitize_input(text: str) -> str:
    """Alias for sanitize_string - removes all HTML and strips whitespace"""
    return sanitize_string(text)


# Input validation
def validate_email(email: str) -> bool:
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def validate_phone(phone: str) -> bool:
    pattern = r'^[+]?[\d\s-]{10,15}$'
    return bool(re.match(pattern, phone.replace(' ', '')))


def validate_gstin(gstin: str) -> bool:
    pattern = r'^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$'
    return bool(re.match(pattern, gstin.upper()))


def validate_pan(pan: str) -> bool:
    pattern = r'^[A-Z]{5}[0-9]{4}[A-Z]{1}$'
    return bool(re.match(pattern, pan.upper()))


def validate_ifsc(ifsc: str) -> bool:
    pattern = r'^[A-Z]{4}0[A-Z0-9]{6}$'
    return bool(re.match(pattern, ifsc.upper()))


def validate_pincode(pincode: str) -> bool:
    pattern = r'^[1-9][0-9]{5}$'
    return bool(re.match(pattern, pincode))


# Password strength validation
def validate_password_strength(password: str) -> tuple[bool, str]:
    if len(password) < 8:
        return False, "Password must be at least 8 characters"
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain uppercase letter"
    if not re.search(r'[a-z]', password):
        return False, "Password must contain lowercase letter"
    if not re.search(r'\d', password):
        return False, "Password must contain digit"
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return False, "Password must contain special character"
    return True, "Password is strong"


# Rate limiting (simple in-memory implementation)
_rate_limit_store = {}


def rate_limit(max_requests: int = 100, window_seconds: int = 60):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
            key = f"{client_ip}:{f.__name__}"
            now = datetime.utcnow()
            
            if key not in _rate_limit_store:
                _rate_limit_store[key] = {'count': 0, 'reset': now + timedelta(seconds=window_seconds)}
            
            if now > _rate_limit_store[key]['reset']:
                _rate_limit_store[key] = {'count': 0, 'reset': now + timedelta(seconds=window_seconds)}
            
            _rate_limit_store[key]['count'] += 1
            
            if _rate_limit_store[key]['count'] > max_requests:
                return jsonify({'error': 'Rate limit exceeded'}), 429
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


# JWT authentication decorator
def jwt_required_with_user():
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            from flask_jwt_extended.exceptions import NoAuthorizationError, InvalidHeaderError
            from jwt.exceptions import ExpiredSignatureError, InvalidTokenError

            try:
                verify_jwt_in_request()
                user_id = get_jwt_identity()
                claims = get_jwt()

                from app.models import User
                user = User.query.filter_by(id=user_id, is_active=True).first()

                if not user:
                    return jsonify({'error': 'User not found or inactive'}), 401

                g.current_user = user
                g.organization_id = claims.get('organization_id')
                g.branch_id = claims.get('branch_id')

                return f(*args, **kwargs)
            except NoAuthorizationError:
                return jsonify({'error': 'Authorization header missing'}), 401
            except InvalidHeaderError as e:
                return jsonify({'error': f'Invalid authorization header: {str(e)}'}), 401
            except ExpiredSignatureError:
                return jsonify({'error': 'Token has expired'}), 401
            except InvalidTokenError as e:
                return jsonify({'error': f'Invalid token: {str(e)}'}), 401
            except Exception as e:
                import traceback
                print(f"Auth error: {str(e)}")
                print(traceback.format_exc())
                return jsonify({'error': f'Authentication required: {str(e)}'}), 401
        return decorated_function
    return decorator


# Permission decorator
def permission_required(*permissions):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not hasattr(g, 'current_user') or not g.current_user:
                return jsonify({'error': 'Authentication required'}), 401
            
            user = g.current_user
            
            # Check if user has any of the required permissions
            has_permission = any(user.has_permission(p) for p in permissions)
            
            if not has_permission:
                return jsonify({'error': 'Permission denied'}), 403
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


# Role decorator
def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not hasattr(g, 'current_user') or not g.current_user:
                return jsonify({'error': 'Authentication required'}), 401
            
            user = g.current_user
            has_role = any(user.has_role(r) for r in roles)
            
            if not has_role:
                return jsonify({'error': 'Insufficient role privileges'}), 403
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


# Organization scope decorator
def org_scope_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not hasattr(g, 'organization_id') or not g.organization_id:
            return jsonify({'error': 'Organization context required'}), 400
        return f(*args, **kwargs)
    return decorated_function


# CSRF protection for non-GET requests
def csrf_protect(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if request.method in ['POST', 'PUT', 'PATCH', 'DELETE']:
            csrf_token = request.headers.get('X-CSRF-Token')
            if not csrf_token:
                return jsonify({'error': 'CSRF token missing'}), 403
        return f(*args, **kwargs)
    return decorated_function


# Request logging
def log_request(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        from app.models import ActivityLog
        from config.database import db
        
        result = f(*args, **kwargs)
        
        try:
            if hasattr(g, 'current_user') and g.current_user:
                log = ActivityLog(
                    organization_id=g.organization_id,
                    user_id=g.current_user.id,
                    activity_type='api_request',
                    description=f"{request.method} {request.path}",
                    ip_address=request.headers.get('X-Forwarded-For', request.remote_addr),
                    user_agent=request.headers.get('User-Agent', '')[:500]
                )
                db.session.add(log)
                db.session.commit()
        except Exception:
            pass
        
        return result
    return decorated_function


# Audit trail helper
def create_audit_log(table_name: str, record_id: int, action: str, old_values: dict = None, new_values: dict = None):
    from app.models import AuditLog
    from config.database import db
    
    try:
        changed_fields = []
        if old_values and new_values:
            for key in set(list(old_values.keys()) + list(new_values.keys())):
                if old_values.get(key) != new_values.get(key):
                    changed_fields.append(key)
        
        log = AuditLog(
            organization_id=getattr(g, 'organization_id', None),
            user_id=getattr(g, 'current_user', None) and g.current_user.id,
            table_name=table_name,
            record_id=record_id,
            action=action,
            old_values=old_values,
            new_values=new_values,
            changed_fields=changed_fields,
            ip_address=request.headers.get('X-Forwarded-For', request.remote_addr) if request else None,
            user_agent=request.headers.get('User-Agent', '')[:500] if request else None
        )
        db.session.add(log)
    except Exception:
        pass


# XSS protection header middleware
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    response.headers['Content-Security-Policy'] = "default-src 'self'"
    return response


# SQL injection prevention helper
def safe_like_query(value: str) -> str:
    """Escape special characters for LIKE queries"""
    return value.replace('%', r'\%').replace('_', r'\_')