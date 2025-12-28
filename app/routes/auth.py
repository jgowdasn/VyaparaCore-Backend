"""Authentication routes for VyaparaCore"""
from flask import Blueprint, request, g
from datetime import datetime, timedelta
from flask_jwt_extended import (
    create_access_token, create_refresh_token, 
    jwt_required, get_jwt_identity, get_jwt
)
from config.database import db
from app.models import User, Organization, LoginHistory, Role, user_roles
from app.utils.security import (
    hash_password, verify_password, generate_token,
    validate_email, validate_password_strength, sanitize_html, sanitize_input,
    rate_limit, create_audit_log
)
from app.utils.helpers import success_response, error_response

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/register', methods=['POST'])
@rate_limit(max_requests=10, window_seconds=3600)  # 10 registrations per hour
def register():
    """Register a new organization and admin user"""
    data = request.get_json()
    
    # Validate required fields
    required = ['organization_name', 'email', 'password', 'first_name']
    for field in required:
        if not data.get(field):
            return error_response(f'{field} is required', 400)
    
    email = sanitize_input(data['email']).lower()
    
    # Validate email format
    if not validate_email(email):
        return error_response('Invalid email format', 400)
    
    # Validate password strength
    is_valid, message = validate_password_strength(data['password'])
    if not is_valid:
        return error_response(message, 400)
    
    # Check if organization or email already exists
    existing_org = Organization.query.filter_by(name=data['organization_name']).first()
    if existing_org:
        return error_response('Organization name already exists', 400)
    
    existing_user = User.query.filter_by(email=email).first()
    if existing_user:
        return error_response('Email already registered', 400)
    
    try:
        # Create organization
        org = Organization(
            name=sanitize_input(data['organization_name']),
            legal_name=data.get('legal_name'),
            email=email,
            phone=data.get('phone'),
            gstin=data.get('gstin'),
            pan=data.get('pan'),
            is_active=True
        )
        db.session.add(org)
        db.session.flush()
        
        # Create admin user
        user = User(
            organization_id=org.id,
            email=email,
            password_hash=hash_password(data['password']),
            first_name=sanitize_input(data['first_name']),
            last_name=sanitize_input(data.get('last_name', '')),
            is_active=True,
            is_admin=True,
            is_email_verified=False
        )
        db.session.add(user)
        db.session.flush()
        
        # Assign admin role if exists
        admin_role = Role.query.filter_by(
            organization_id=org.id,
            code='admin'
        ).first()
        
        if admin_role:
            db.session.execute(user_roles.insert().values(
                user_id=user.id,
                role_id=admin_role.id
            ))
        
        # Run seeds for new organization
        from app.seeds import (
            seed_roles_for_organization, seed_units_for_organization,
            seed_tax_rates_for_organization, seed_organization_settings
        )
        
        seed_roles_for_organization(org.id)
        seed_units_for_organization(org.id)
        seed_tax_rates_for_organization(org.id)
        seed_organization_settings(org.id)
        
        # Generate verification token
        user.verification_token = generate_token()
        user.verification_token_expires = datetime.utcnow() + timedelta(hours=24)
        
        db.session.commit()
        
        # TODO: Send verification email
        
        # Create tokens
        access_token = create_access_token(
            identity=str(user.id),
            additional_claims={
                'organization_id': org.id,
                'email': user.email,
                'is_admin': user.is_admin
            }
        )
        refresh_token = create_refresh_token(identity=str(user.id))
        
        return success_response({
            'message': 'Registration successful',
            'user': {
                'id': user.id,
                'email': user.email,
                'full_name': user.full_name
            },
            'organization': {
                'id': org.id,
                'name': org.name
            },
            'access_token': access_token,
            'refresh_token': refresh_token
        }, 201)
        
    except Exception as e:
        db.session.rollback()
        return error_response(f'Registration failed: {str(e)}', 500)


@auth_bp.route('/login', methods=['POST'])
@rate_limit(max_requests=10, window_seconds=3600)  # 20 attempts per 5 minutes
def login():
    """User login"""
    data = request.get_json()
    
    if not data.get('email') or not data.get('password'):
        return error_response('Email and password are required', 400)
    
    email = sanitize_input(data['email']).lower()
    
    user = User.query.filter_by(email=email).first()
    
    if not user:
        return error_response('Invalid email or password', 401)
    
    # Check if account is locked
    if user.locked_until and user.locked_until > datetime.utcnow():
        remaining = (user.locked_until - datetime.utcnow()).seconds // 60
        return error_response(f'Account locked. Try again in {remaining} minutes.', 423)
    
    # Verify password
    if not verify_password(data['password'], user.password_hash):
        user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
        
        # Lock account after 5 failed attempts
        if user.failed_login_attempts >= 5:
            user.locked_until = datetime.utcnow() + timedelta(minutes=30)
            db.session.commit()
            return error_response('Account locked due to too many failed attempts', 423)
        
        db.session.commit()
        
        # Log failed attempt
        login_history = LoginHistory(
            user_id=user.id,
            organization_id=user.organization_id,
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string[:500] if request.user_agent else None,
            status='failed',
            failure_reason='Invalid password'
        )
        db.session.add(login_history)
        db.session.commit()
        
        return error_response('Invalid email or password', 401)
    
    # Check if user is active
    if not user.is_active:
        return error_response('Account is deactivated', 403)
    
    # Check if organization is active
    org = Organization.query.get(user.organization_id)
    if not org or not org.is_active:
        return error_response('Organization is deactivated', 403)
    
    # Reset failed attempts
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login_at = datetime.utcnow()
    user.last_login_ip = request.remote_addr
    
    # Log successful login
    login_history = LoginHistory(
        user_id=user.id,
        organization_id=user.organization_id,
        ip_address=request.remote_addr,
        user_agent=request.user_agent.string[:500] if request.user_agent else None,
        status='success'
    )
    db.session.add(login_history)
    db.session.commit()
    
    # Create tokens
    access_token = create_access_token(
        identity=str(user.id),
        additional_claims={
            'organization_id': user.organization_id,
            'branch_id': user.branch_id,
            'email': user.email,
            'is_admin': user.is_admin
        }
    )
    refresh_token = create_refresh_token(identity=str(user.id))
    
    # Get user permissions
    permissions = set()
    for role in user.roles:
        for perm in role.permissions:
            permissions.add(perm.code)
    if user.is_admin:
        permissions.add('*')
    
    return success_response({
        'user': {
            'id': user.id,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'full_name': user.full_name,
            'is_admin': user.is_admin,
            'organization_id': user.organization_id,
            'branch_id': user.branch_id
        },
        'organization': {
            'id': org.id,
            'name': org.name
        },
        'roles': [{'id': r.id, 'name': r.name, 'code': r.code} for r in user.roles],
        'permissions': list(permissions),
        'access_token': access_token,
        'refresh_token': refresh_token
    })


@auth_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    """Refresh access token"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    if not user or not user.is_active:
        return error_response('User not found or inactive', 401)
    
    access_token = create_access_token(
        identity=str(user.id),
        additional_claims={
            'organization_id': user.organization_id,
            'branch_id': user.branch_id,
            'email': user.email,
            'is_admin': user.is_admin
        }
    )

    return success_response({'access_token': access_token})


@auth_bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    """User logout"""
    # In a production app, you'd blacklist the token here
    return success_response({'message': 'Logged out successfully'})


@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def get_current_user():
    """Get current user profile"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    if not user:
        return error_response('User not found', 404)
    
    # Get permissions
    permissions = set()
    for role in user.roles:
        for perm in role.permissions:
            permissions.add(perm.code)
    if user.is_admin:
        permissions.add('*')
    
    org = Organization.query.get(user.organization_id)
    
    return success_response({
        'id': user.id,
        'email': user.email,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'full_name': user.full_name,
        'employee_code': user.employee_code,
        'phone': user.phone,
        'mobile': user.mobile,
        'avatar_url': user.avatar_url,
        'designation': user.designation,
        'department': user.department,
        'is_admin': user.is_admin,
        'is_email_verified': user.is_email_verified,
        'organization': {
            'id': org.id,
            'name': org.name
        } if org else None,
        'branch_id': user.branch_id,
        'roles': [{'id': r.id, 'name': r.name, 'code': r.code} for r in user.roles],
        'permissions': list(permissions)
    })


@auth_bp.route('/me', methods=['PUT'])
@jwt_required()
def update_current_user():
    """Update current user profile"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    if not user:
        return error_response('User not found', 404)
    
    data = request.get_json()
    
    if 'first_name' in data:
        user.first_name = sanitize_input(data['first_name'])
    if 'last_name' in data:
        user.last_name = sanitize_input(data.get('last_name', ''))
    if 'phone' in data:
        user.phone = data['phone']
    if 'mobile' in data:
        user.mobile = data['mobile']
    if 'avatar_url' in data:
        user.avatar_url = data['avatar_url']
    if 'preferences' in data:
        user.preferences = data['preferences']
    
    db.session.commit()
    
    return success_response({'message': 'Profile updated successfully'})


@auth_bp.route('/change-password', methods=['POST'])
@jwt_required()
def change_password():
    """Change password"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    if not user:
        return error_response('User not found', 404)
    
    data = request.get_json()
    
    if not data.get('current_password') or not data.get('new_password'):
        return error_response('Current and new password are required', 400)
    
    # Verify current password
    if not verify_password(data['current_password'], user.password_hash):
        return error_response('Current password is incorrect', 400)
    
    # Validate new password
    is_valid, message = validate_password_strength(data['new_password'])
    if not is_valid:
        return error_response(message, 400)
    
    user.password_hash = hash_password(data['new_password'])
    user.password_changed_at = datetime.utcnow()
    db.session.commit()
    
    return success_response({'message': 'Password changed successfully'})


@auth_bp.route('/forgot-password', methods=['POST'])
@rate_limit(max_requests=10, window_seconds=3600)  # 5 requests per hour
def forgot_password():
    """Request password reset"""
    data = request.get_json()
    
    if not data.get('email'):
        return error_response('Email is required', 400)
    
    email = sanitize_input(data['email']).lower()
    user = User.query.filter_by(email=email).first()
    
    # Always return success to prevent email enumeration
    if user:
        user.reset_token = generate_token()
        user.reset_token_expires = datetime.utcnow() + timedelta(hours=1)
        db.session.commit()
        
        # TODO: Send password reset email
    
    return success_response({
        'message': 'If the email exists, a password reset link has been sent'
    })


@auth_bp.route('/reset-password', methods=['POST'])
def reset_password():
    """Reset password with token"""
    data = request.get_json()
    
    if not data.get('token') or not data.get('password'):
        return error_response('Token and password are required', 400)
    
    user = User.query.filter_by(reset_token=data['token']).first()
    
    if not user:
        return error_response('Invalid or expired token', 400)
    
    if user.reset_token_expires and user.reset_token_expires < datetime.utcnow():
        return error_response('Token has expired', 400)
    
    # Validate new password
    is_valid, message = validate_password_strength(data['password'])
    if not is_valid:
        return error_response(message, 400)
    
    user.password_hash = hash_password(data['password'])
    user.password_changed_at = datetime.utcnow()
    user.reset_token = None
    user.reset_token_expires = None
    user.failed_login_attempts = 0
    user.locked_until = None
    
    db.session.commit()
    
    return success_response({'message': 'Password reset successfully'})


@auth_bp.route('/verify-email', methods=['POST'])
def verify_email():
    """Verify email with token"""
    data = request.get_json()
    
    if not data.get('token'):
        return error_response('Token is required', 400)
    
    user = User.query.filter_by(verification_token=data['token']).first()
    
    if not user:
        return error_response('Invalid token', 400)
    
    if user.verification_token_expires and user.verification_token_expires < datetime.utcnow():
        return error_response('Token has expired', 400)
    
    user.is_email_verified = True
    user.verification_token = None
    user.verification_token_expires = None
    
    db.session.commit()
    
    return success_response({'message': 'Email verified successfully'})