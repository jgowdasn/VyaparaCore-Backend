"""User management routes for VyaparaCore"""
from flask import Blueprint, request, g
from sqlalchemy import func
from config.database import db
from app.models import User, Role, Permission, user_roles, role_permissions
from app.utils.security import (
    jwt_required_with_user, permission_required, hash_password,
    validate_password_strength, sanitize_html, create_audit_log
)
from app.utils.helpers import success_response, error_response, paginate

user_bp = Blueprint('user', __name__)


# ==================== USER MANAGEMENT ====================

@user_bp.route('', methods=['GET'])
@jwt_required_with_user()
@permission_required('users.view')
def list_users():
    """List all users in organization"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    search = request.args.get('search', '')
    role_id = request.args.get('role_id', type=int)
    is_active = request.args.get('is_active')
    
    query = User.query.filter_by(organization_id=g.organization_id)
    
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            db.or_(
                User.first_name.ilike(search_term),
                User.last_name.ilike(search_term),
                User.email.ilike(search_term),
                User.employee_code.ilike(search_term)
            )
        )
    
    if role_id:
        query = query.join(user_roles).filter(user_roles.c.role_id == role_id)
    
    if is_active is not None:
        query = query.filter(User.is_active == (is_active.lower() == 'true'))
    
    query = query.order_by(User.first_name)
    
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    
    users = []
    for user in pagination.items:
        users.append({
            'id': user.id,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'full_name': user.full_name,
            'employee_code': user.employee_code,
            'phone': user.phone,
            'designation': user.designation,
            'department': user.department,
            'is_active': user.is_active,
            'is_admin': user.is_admin,
            'last_login_at': user.last_login_at.isoformat() if user.last_login_at else None,
            'roles': [{'id': r.id, 'name': r.name, 'code': r.code} for r in user.roles],
            'created_at': user.created_at.isoformat() if user.created_at else None
        })
    
    return success_response({
        'users': users,
        'pagination': {
            'page': pagination.page,
            'per_page': pagination.per_page,
            'total': pagination.total,
            'pages': pagination.pages
        }
    })


@user_bp.route('', methods=['POST'])
@jwt_required_with_user()
@permission_required('users.create')
def create_user():
    """Create a new user"""
    data = request.get_json()
    
    # Validate required fields
    required = ['email', 'password', 'first_name']
    for field in required:
        if not data.get(field):
            return error_response(f'{field} is required', 400)
    
    email = sanitize_input(data['email']).lower()
    
    # Check if email exists
    existing = User.query.filter_by(
        organization_id=g.organization_id,
        email=email
    ).first()
    
    if existing:
        return error_response('Email already exists', 400)
    
    # Validate password
    password = data['password']
    is_valid, message = validate_password_strength(password)
    if not is_valid:
        return error_response(message, 400)
    
    # Create user
    user = User(
        organization_id=g.organization_id,
        branch_id=data.get('branch_id') or g.branch_id,
        email=email,
        password_hash=hash_password(password),
        first_name=sanitize_input(data['first_name']),
        last_name=sanitize_input(data.get('last_name', '')),
        employee_code=data.get('employee_code'),
        phone=data.get('phone'),
        mobile=data.get('mobile'),
        designation=data.get('designation'),
        department=data.get('department'),
        is_active=data.get('is_active', True),
        is_admin=data.get('is_admin', False),
        created_by=g.user_id
    )
    
    db.session.add(user)
    db.session.flush()
    
    # Assign roles
    role_ids = data.get('role_ids', [])
    for role_id in role_ids:
        role = Role.query.filter_by(
            id=role_id,
            organization_id=g.organization_id
        ).first()
        if role:
            db.session.execute(user_roles.insert().values(
                user_id=user.id,
                role_id=role.id
            ))
    
    db.session.commit()
    
    create_audit_log('users', user.id, 'create', None, data)
    
    return success_response({
        'id': user.id,
        'email': user.email,
        'full_name': user.full_name,
        'message': 'User created successfully'
    }, 201)


@user_bp.route('/<int:user_id>', methods=['GET'])
@jwt_required_with_user()
@permission_required('users.view')
def get_user(user_id):
    """Get user details"""
    user = User.query.filter_by(
        id=user_id,
        organization_id=g.organization_id
    ).first()
    
    if not user:
        return error_response('User not found', 404)
    
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
        'address': user.address,
        'city': user.city,
        'state': user.state,
        'pincode': user.pincode,
        'designation': user.designation,
        'department': user.department,
        'date_of_joining': user.date_of_joining.isoformat() if user.date_of_joining else None,
        'is_active': user.is_active,
        'is_admin': user.is_admin,
        'is_email_verified': user.is_email_verified,
        'last_login_at': user.last_login_at.isoformat() if user.last_login_at else None,
        'roles': [{'id': r.id, 'name': r.name, 'code': r.code} for r in user.roles],
        'branch_id': user.branch_id,
        'created_at': user.created_at.isoformat() if user.created_at else None
    })


@user_bp.route('/<int:user_id>', methods=['PUT'])
@jwt_required_with_user()
@permission_required('users.edit')
def update_user(user_id):
    """Update user details"""
    user = User.query.filter_by(
        id=user_id,
        organization_id=g.organization_id
    ).first()
    
    if not user:
        return error_response('User not found', 404)
    
    data = request.get_json()
    old_data = {
        'email': user.email,
        'first_name': user.first_name,
        'last_name': user.last_name
    }
    
    # Update fields
    if 'email' in data:
        new_email = sanitize_input(data['email']).lower()
        if new_email != user.email:
            existing = User.query.filter_by(
                organization_id=g.organization_id,
                email=new_email
            ).first()
            if existing:
                return error_response('Email already exists', 400)
            user.email = new_email
    
    if 'first_name' in data:
        user.first_name = sanitize_input(data['first_name'])
    if 'last_name' in data:
        user.last_name = sanitize_input(data.get('last_name', ''))
    if 'employee_code' in data:
        user.employee_code = data['employee_code']
    if 'phone' in data:
        user.phone = data['phone']
    if 'mobile' in data:
        user.mobile = data['mobile']
    if 'designation' in data:
        user.designation = data['designation']
    if 'department' in data:
        user.department = data['department']
    if 'address' in data:
        user.address = data['address']
    if 'city' in data:
        user.city = data['city']
    if 'state' in data:
        user.state = data['state']
    if 'pincode' in data:
        user.pincode = data['pincode']
    if 'branch_id' in data:
        user.branch_id = data['branch_id']
    if 'is_active' in data:
        user.is_active = data['is_active']
    if 'is_admin' in data and g.current_user.is_admin:
        user.is_admin = data['is_admin']
    
    # Update password if provided
    if data.get('password'):
        is_valid, message = validate_password_strength(data['password'])
        if not is_valid:
            return error_response(message, 400)
        user.password_hash = hash_password(data['password'])
    
    db.session.commit()
    
    create_audit_log('users', user.id, 'update', old_data, data)
    
    return success_response({
        'id': user.id,
        'message': 'User updated successfully'
    })


@user_bp.route('/<int:user_id>', methods=['DELETE'])
@jwt_required_with_user()
@permission_required('users.delete')
def delete_user(user_id):
    """Delete (deactivate) a user"""
    if user_id == g.user_id:
        return error_response('Cannot delete yourself', 400)
    
    user = User.query.filter_by(
        id=user_id,
        organization_id=g.organization_id
    ).first()
    
    if not user:
        return error_response('User not found', 404)
    
    # Soft delete
    user.is_active = False
    db.session.commit()
    
    create_audit_log('users', user.id, 'delete', {'is_active': True}, {'is_active': False})
    
    return success_response({'message': 'User deleted successfully'})


@user_bp.route('/<int:user_id>/roles', methods=['PUT'])
@jwt_required_with_user()
@permission_required('users.edit')
def update_user_roles(user_id):
    """Update user roles"""
    user = User.query.filter_by(
        id=user_id,
        organization_id=g.organization_id
    ).first()
    
    if not user:
        return error_response('User not found', 404)
    
    data = request.get_json()
    role_ids = data.get('role_ids', [])
    
    # Remove existing roles
    db.session.execute(user_roles.delete().where(user_roles.c.user_id == user.id))
    
    # Add new roles
    for role_id in role_ids:
        role = Role.query.filter_by(
            id=role_id,
            organization_id=g.organization_id
        ).first()
        if role:
            db.session.execute(user_roles.insert().values(
                user_id=user.id,
                role_id=role.id
            ))
    
    db.session.commit()
    
    return success_response({'message': 'User roles updated successfully'})


# ==================== ROLE MANAGEMENT ====================

@user_bp.route('/roles', methods=['GET'])
@jwt_required_with_user()
@permission_required('roles.view')
def list_roles():
    """List all roles"""
    roles = Role.query.filter_by(
        organization_id=g.organization_id,
        is_active=True
    ).order_by(Role.name).all()
    
    result = []
    for role in roles:
        # Count users with this role
        user_count = db.session.query(func.count(user_roles.c.user_id)).filter(
            user_roles.c.role_id == role.id
        ).scalar()
        
        result.append({
            'id': role.id,
            'name': role.name,
            'code': role.code,
            'description': role.description,
            'is_system_role': role.is_system_role,
            'user_count': user_count,
            'permission_count': len(role.permissions)
        })
    
    return success_response(result)


@user_bp.route('/roles', methods=['POST'])
@jwt_required_with_user()
@permission_required('roles.create')
def create_role():
    """Create a new role"""
    data = request.get_json()
    
    if not data.get('name'):
        return error_response('Role name is required', 400)
    
    code = data.get('code') or data['name'].lower().replace(' ', '_')
    
    existing = Role.query.filter_by(
        organization_id=g.organization_id,
        code=code
    ).first()
    
    if existing:
        return error_response('Role with this code already exists', 400)
    
    role = Role(
        organization_id=g.organization_id,
        name=sanitize_input(data['name']),
        code=code,
        description=data.get('description'),
        is_system_role=False,
        is_active=True
    )
    
    db.session.add(role)
    db.session.flush()
    
    # Assign permissions
    permission_ids = data.get('permission_ids', [])
    for perm_id in permission_ids:
        perm = Permission.query.get(perm_id)
        if perm:
            db.session.execute(role_permissions.insert().values(
                role_id=role.id,
                permission_id=perm.id
            ))
    
    db.session.commit()
    
    return success_response({
        'id': role.id,
        'name': role.name,
        'message': 'Role created successfully'
    }, 201)


@user_bp.route('/roles/<int:role_id>', methods=['GET'])
@jwt_required_with_user()
@permission_required('roles.view')
def get_role(role_id):
    """Get role details with permissions"""
    role = Role.query.filter_by(
        id=role_id,
        organization_id=g.organization_id
    ).first()
    
    if not role:
        return error_response('Role not found', 404)
    
    return success_response({
        'id': role.id,
        'name': role.name,
        'code': role.code,
        'description': role.description,
        'is_system_role': role.is_system_role,
        'permissions': [{'id': p.id, 'code': p.code, 'name': p.name, 'module': p.module} for p in role.permissions]
    })


@user_bp.route('/roles/<int:role_id>', methods=['PUT'])
@jwt_required_with_user()
@permission_required('roles.edit')
def update_role(role_id):
    """Update role"""
    role = Role.query.filter_by(
        id=role_id,
        organization_id=g.organization_id
    ).first()
    
    if not role:
        return error_response('Role not found', 404)
    
    if role.is_system_role:
        return error_response('Cannot modify system role', 400)
    
    data = request.get_json()
    
    if 'name' in data:
        role.name = sanitize_input(data['name'])
    if 'description' in data:
        role.description = data['description']
    
    # Update permissions if provided
    if 'permission_ids' in data:
        # Remove existing permissions
        db.session.execute(role_permissions.delete().where(role_permissions.c.role_id == role.id))
        
        # Add new permissions
        for perm_id in data['permission_ids']:
            perm = Permission.query.get(perm_id)
            if perm:
                db.session.execute(role_permissions.insert().values(
                    role_id=role.id,
                    permission_id=perm.id
                ))
    
    db.session.commit()
    
    return success_response({'message': 'Role updated successfully'})


@user_bp.route('/roles/<int:role_id>', methods=['DELETE'])
@jwt_required_with_user()
@permission_required('roles.delete')
def delete_role(role_id):
    """Delete a role"""
    role = Role.query.filter_by(
        id=role_id,
        organization_id=g.organization_id
    ).first()
    
    if not role:
        return error_response('Role not found', 404)
    
    if role.is_system_role:
        return error_response('Cannot delete system role', 400)
    
    # Check if role is in use
    user_count = db.session.query(func.count(user_roles.c.user_id)).filter(
        user_roles.c.role_id == role.id
    ).scalar()
    
    if user_count > 0:
        return error_response(f'Cannot delete role. {user_count} users have this role.', 400)
    
    # Delete role permissions first
    db.session.execute(role_permissions.delete().where(role_permissions.c.role_id == role.id))
    
    # Delete role
    db.session.delete(role)
    db.session.commit()
    
    return success_response({'message': 'Role deleted successfully'})


# ==================== PERMISSIONS ====================

@user_bp.route('/permissions', methods=['GET'])
@jwt_required_with_user()
@permission_required('roles.view')
def list_permissions():
    """List all permissions grouped by module"""
    permissions = Permission.query.order_by(Permission.module, Permission.code).all()
    
    # Group by module
    grouped = {}
    for perm in permissions:
        if perm.module not in grouped:
            grouped[perm.module] = []
        grouped[perm.module].append({
            'id': perm.id,
            'code': perm.code,
            'name': perm.name,
            'description': perm.description
        })
    
    return success_response(grouped)