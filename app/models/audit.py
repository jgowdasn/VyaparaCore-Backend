"""Audit models for VyaparaCore"""
from datetime import datetime
from config.database import db


class AuditLog(db.Model):
    """Audit log for tracking all data changes"""
    __tablename__ = 'audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    user_email = db.Column(db.String(120))
    user_name = db.Column(db.String(200))
    
    table_name = db.Column(db.String(100), nullable=False)
    record_id = db.Column(db.Integer, nullable=False)
    action = db.Column(db.String(20), nullable=False)
    
    old_values = db.Column(db.JSON)
    new_values = db.Column(db.JSON)
    changed_fields = db.Column(db.JSON)
    
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(500))
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    __table_args__ = (
        db.Index('idx_audit_table_record', 'organization_id', 'table_name', 'record_id'),
        db.Index('idx_audit_user', 'organization_id', 'user_id'),
    )
    
    def __repr__(self):
        return f'<AuditLog {self.action} on {self.table_name}:{self.record_id}>'


class ActivityLog(db.Model):
    """Activity log for tracking user actions"""
    __tablename__ = 'activity_logs'

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    user_name = db.Column(db.String(200))
    
    activity_type = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(500), nullable=False)
    
    entity_type = db.Column(db.String(50))
    entity_id = db.Column(db.Integer)
    entity_number = db.Column(db.String(50))
    
    extra_data = db.Column(db.JSON, default=dict)  # Changed from 'metadata'
    
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(500))
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    __table_args__ = (
        db.Index('idx_activity_type', 'organization_id', 'activity_type'),
        db.Index('idx_activity_user', 'organization_id', 'user_id'),
    )
    
    def __repr__(self):
        return f'<ActivityLog {self.activity_type}>'


class LoginHistory(db.Model):
    """Login history for security tracking"""
    __tablename__ = 'login_history'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    
    login_at = db.Column(db.DateTime, default=datetime.utcnow)
    logout_at = db.Column(db.DateTime)
    
    session_id = db.Column(db.String(100))
    
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(500))
    device_type = db.Column(db.String(20))
    browser = db.Column(db.String(50))
    os = db.Column(db.String(50))
    
    city = db.Column(db.String(100))
    country = db.Column(db.String(100))
    
    status = db.Column(db.String(20), default='success')
    failure_reason = db.Column(db.String(200))
    
    __table_args__ = (
        db.Index('idx_login_user', 'user_id'),
        db.Index('idx_login_time', 'organization_id', 'login_at'),
    )

    def __repr__(self):
        return f'<LoginHistory {self.user_id}>'


class Notification(db.Model):
    """User notifications"""
    __tablename__ = 'notifications'

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    
    notification_type = db.Column(db.String(30), nullable=False)
    priority = db.Column(db.String(10), default='normal')
    
    entity_type = db.Column(db.String(50))
    entity_id = db.Column(db.Integer)
    
    action_url = db.Column(db.String(500))
    
    is_read = db.Column(db.Boolean, default=False)
    read_at = db.Column(db.DateTime)
    
    email_sent = db.Column(db.Boolean, default=False)
    email_sent_at = db.Column(db.DateTime)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime)
    
    __table_args__ = (
        db.Index('idx_notification_user', 'user_id', 'is_read'),
    )
    
    def __repr__(self):
        return f'<Notification {self.title}>'