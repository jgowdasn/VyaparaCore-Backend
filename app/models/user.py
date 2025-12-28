"""User models for VyaparaCore"""
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from config.database import db


# Association table for User-Role (simple table, no extra columns that cause issues)
user_roles = db.Table('user_roles',
    db.Column('id', db.Integer, primary_key=True),
    db.Column('user_id', db.Integer, db.ForeignKey('users.id'), nullable=False),
    db.Column('role_id', db.Integer, db.ForeignKey('roles.id'), nullable=False),
    db.Column('assigned_at', db.DateTime, default=datetime.utcnow),
    db.UniqueConstraint('user_id', 'role_id', name='uq_user_role'),
)


# Association table for Role-Permission
role_permissions = db.Table('role_permissions',
    db.Column('id', db.Integer, primary_key=True),
    db.Column('role_id', db.Integer, db.ForeignKey('roles.id'), nullable=False),
    db.Column('permission_id', db.Integer, db.ForeignKey('permissions.id'), nullable=False),
    db.Column('created_at', db.DateTime, default=datetime.utcnow),
    db.UniqueConstraint('role_id', 'permission_id', name='uq_role_permission'),
)


class User(db.Model):
    """User model with multi-tenant support"""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    branch_id = db.Column(db.Integer, db.ForeignKey('branches.id'))
    
    # Authentication
    email = db.Column(db.String(120), nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    
    # Profile
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100))
    employee_code = db.Column(db.String(20))
    phone = db.Column(db.String(20))
    mobile = db.Column(db.String(20))
    avatar_url = db.Column(db.String(500))
    
    # Address
    address = db.Column(db.Text)
    city = db.Column(db.String(100))
    state = db.Column(db.String(100))
    pincode = db.Column(db.String(10))
    
    # Employment Details
    designation = db.Column(db.String(100))
    department = db.Column(db.String(100))
    date_of_joining = db.Column(db.Date)
    
    # Status & Security
    is_active = db.Column(db.Boolean, default=True)
    is_email_verified = db.Column(db.Boolean, default=False)
    is_admin = db.Column(db.Boolean, default=False)
    
    # Session & Security
    last_login_at = db.Column(db.DateTime)
    last_login_ip = db.Column(db.String(45))
    password_changed_at = db.Column(db.DateTime)
    failed_login_attempts = db.Column(db.Integer, default=0)
    locked_until = db.Column(db.DateTime)
    
    # Password Reset
    reset_token = db.Column(db.String(256))
    reset_token_expires = db.Column(db.DateTime)
    
    # Email Verification
    verification_token = db.Column(db.String(256))
    verification_token_expires = db.Column(db.DateTime)
    
    # Preferences
    preferences = db.Column(db.JSON, default=dict)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.Integer)
    
    # Relationships
    roles = db.relationship('Role', secondary=user_roles, backref='users')
    branch = db.relationship('Branch', backref='users')
    
    __table_args__ = (
        db.UniqueConstraint('organization_id', 'email', name='uq_user_org_email'),
    )
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        self.password_changed_at = datetime.utcnow()
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def has_permission(self, permission_code):
        """Check if user has a specific permission"""
        for role in self.roles:
            for perm in role.permissions:
                if perm.code == permission_code:
                    return True
        return self.is_admin
    
    def has_role(self, role_name):
        """Check if user has a specific role"""
        return any(role.name == role_name for role in self.roles) or self.is_admin
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name or ''}".strip()
    
    def __repr__(self):
        return f'<User {self.email}>'


class Role(db.Model):
    """Role model for RBAC"""
    __tablename__ = 'roles'

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    
    name = db.Column(db.String(50), nullable=False)
    code = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(200))
    
    is_system_role = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    permissions = db.relationship('Permission', secondary=role_permissions, backref='roles')
    
    __table_args__ = (
        db.UniqueConstraint('organization_id', 'code', name='uq_role_org_code'),
    )
    
    def __repr__(self):
        return f'<Role {self.name}>'


class Permission(db.Model):
    """Permission model for granular access control"""
    __tablename__ = 'permissions'

    id = db.Column(db.Integer, primary_key=True)
    
    module = db.Column(db.String(50), nullable=False)
    code = db.Column(db.String(100), nullable=False, unique=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(200))
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Permission {self.code}>'


# Keep these as classes for seeds.py compatibility but they won't be used as models
class UserRole:
    """Helper class for seeds - actual table is user_roles above"""
    pass


class RolePermission:
    """Helper class for seeds - actual table is role_permissions above"""
    pass