"""Activity Logging Service for VyaparaCore"""
from datetime import datetime
from flask import request, g
from config.database import db
from app.models.audit import ActivityLog, AuditLog, LoginHistory


class ActivityType:
    """Activity type constants"""
    # Auth
    LOGIN = 'login'
    LOGOUT = 'logout'
    REGISTER = 'register'
    PASSWORD_CHANGE = 'password_change'
    PASSWORD_RESET = 'password_reset'

    # CRUD operations
    CREATE = 'create'
    UPDATE = 'update'
    DELETE = 'delete'
    VIEW = 'view'

    # Business actions
    APPROVE = 'approve'
    REJECT = 'reject'
    CANCEL = 'cancel'
    CONVERT = 'convert'
    SEND = 'send'
    STATUS_CHANGE = 'status_change'
    DOWNLOAD = 'download'
    PRINT = 'print'
    EXPORT = 'export'
    IMPORT = 'import'

    # Inventory
    STOCK_ADJUST = 'stock_adjust'
    STOCK_TRANSFER = 'stock_transfer'

    # Payments
    PAYMENT_RECEIVE = 'payment_receive'
    PAYMENT_MAKE = 'payment_make'
    REFUND = 'refund'


class EntityType:
    """Entity type constants"""
    USER = 'user'
    ORGANIZATION = 'organization'
    CUSTOMER = 'customer'
    SUPPLIER = 'supplier'
    PRODUCT = 'product'
    CATEGORY = 'category'
    INVENTORY = 'inventory'
    WAREHOUSE = 'warehouse'
    QUOTATION = 'quotation'
    SALES_ORDER = 'sales_order'
    INVOICE = 'invoice'
    CREDIT_NOTE = 'credit_note'
    PURCHASE_ORDER = 'purchase_order'
    PURCHASE = 'purchase'
    DEBIT_NOTE = 'debit_note'
    PAYMENT = 'payment'
    STOCK_TRANSFER = 'stock_transfer'
    STOCK_ADJUSTMENT = 'stock_adjustment'
    PRICE_LIST = 'price_list'
    TAX_RATE = 'tax_rate'
    UNIT = 'unit'


def get_client_info():
    """Extract client information from request"""
    ip_address = request.headers.get('X-Forwarded-For', request.remote_addr)
    if ip_address and ',' in ip_address:
        ip_address = ip_address.split(',')[0].strip()

    user_agent = request.headers.get('User-Agent', '')[:500]

    return ip_address, user_agent


def log_activity(
    activity_type: str,
    description: str,
    entity_type: str = None,
    entity_id: int = None,
    entity_number: str = None,
    extra_data: dict = None,
    user_id: int = None,
    organization_id: int = None
):
    """
    Log a user activity.

    Args:
        activity_type: Type of activity (use ActivityType constants)
        description: Human-readable description of the activity
        entity_type: Type of entity being acted upon (use EntityType constants)
        entity_id: ID of the entity
        entity_number: Display number of the entity (e.g., invoice number)
        extra_data: Additional context data as dict
        user_id: Override user ID (uses current user if not provided)
        organization_id: Override org ID (uses current org if not provided)
    """
    try:
        ip_address, user_agent = get_client_info()

        # Get user info from context if not provided
        if user_id is None and hasattr(g, 'current_user') and g.current_user:
            user_id = g.current_user.id
            user_name = f"{g.current_user.first_name} {g.current_user.last_name}".strip()
        else:
            user_name = None

        if organization_id is None:
            organization_id = getattr(g, 'organization_id', None)

        log = ActivityLog(
            organization_id=organization_id,
            user_id=user_id,
            user_name=user_name,
            activity_type=activity_type,
            description=description,
            entity_type=entity_type,
            entity_id=entity_id,
            entity_number=entity_number,
            extra_data=extra_data or {},
            ip_address=ip_address,
            user_agent=user_agent
        )

        db.session.add(log)
        db.session.commit()

        return log

    except Exception as e:
        db.session.rollback()
        print(f"Activity logging error: {str(e)}")
        return None


def log_audit(
    table_name: str,
    record_id: int,
    action: str,
    old_values: dict = None,
    new_values: dict = None
):
    """
    Log an audit trail entry for data changes.

    Args:
        table_name: Database table name
        record_id: ID of the record
        action: Action performed (create, update, delete)
        old_values: Previous values (for update/delete)
        new_values: New values (for create/update)
    """
    try:
        ip_address, user_agent = get_client_info()

        # Calculate changed fields
        changed_fields = []
        if old_values and new_values:
            all_keys = set(list(old_values.keys()) + list(new_values.keys()))
            for key in all_keys:
                old_val = old_values.get(key)
                new_val = new_values.get(key)
                if old_val != new_val:
                    changed_fields.append(key)

        user = getattr(g, 'current_user', None)

        log = AuditLog(
            organization_id=getattr(g, 'organization_id', None),
            user_id=user.id if user else None,
            user_email=user.email if user else None,
            user_name=f"{user.first_name} {user.last_name}".strip() if user else None,
            table_name=table_name,
            record_id=record_id,
            action=action,
            old_values=old_values,
            new_values=new_values,
            changed_fields=changed_fields if changed_fields else None,
            ip_address=ip_address,
            user_agent=user_agent
        )

        db.session.add(log)
        # Don't commit here - let the calling function handle transaction

        return log

    except Exception as e:
        print(f"Audit logging error: {str(e)}")
        return None


def log_login(
    user_id: int,
    organization_id: int,
    status: str = 'success',
    failure_reason: str = None,
    session_id: str = None
):
    """
    Log a login attempt.

    Args:
        user_id: ID of the user attempting login
        organization_id: Organization ID
        status: 'success' or 'failed'
        failure_reason: Reason for failure if applicable
        session_id: Session identifier
    """
    try:
        ip_address, user_agent = get_client_info()

        # Parse user agent for device info
        device_type = 'desktop'
        browser = 'unknown'
        os = 'unknown'

        ua_lower = user_agent.lower()
        if 'mobile' in ua_lower or 'android' in ua_lower or 'iphone' in ua_lower:
            device_type = 'mobile'
        elif 'tablet' in ua_lower or 'ipad' in ua_lower:
            device_type = 'tablet'

        if 'chrome' in ua_lower:
            browser = 'Chrome'
        elif 'firefox' in ua_lower:
            browser = 'Firefox'
        elif 'safari' in ua_lower:
            browser = 'Safari'
        elif 'edge' in ua_lower:
            browser = 'Edge'

        if 'windows' in ua_lower:
            os = 'Windows'
        elif 'mac' in ua_lower:
            os = 'macOS'
        elif 'linux' in ua_lower:
            os = 'Linux'
        elif 'android' in ua_lower:
            os = 'Android'
        elif 'ios' in ua_lower or 'iphone' in ua_lower or 'ipad' in ua_lower:
            os = 'iOS'

        log = LoginHistory(
            user_id=user_id,
            organization_id=organization_id,
            session_id=session_id,
            ip_address=ip_address,
            user_agent=user_agent,
            device_type=device_type,
            browser=browser,
            os=os,
            status=status,
            failure_reason=failure_reason
        )

        db.session.add(log)
        db.session.commit()

        return log

    except Exception as e:
        db.session.rollback()
        print(f"Login history error: {str(e)}")
        return None


def log_logout(user_id: int, session_id: str = None):
    """Log user logout by updating the login history record"""
    try:
        if session_id:
            login_record = LoginHistory.query.filter_by(
                user_id=user_id,
                session_id=session_id,
                logout_at=None
            ).first()
        else:
            login_record = LoginHistory.query.filter_by(
                user_id=user_id,
                logout_at=None
            ).order_by(LoginHistory.login_at.desc()).first()

        if login_record:
            login_record.logout_at = datetime.utcnow()
            db.session.commit()

        return login_record

    except Exception as e:
        db.session.rollback()
        print(f"Logout logging error: {str(e)}")
        return None


def model_to_dict(model, exclude_fields=None):
    """Convert SQLAlchemy model to dict for audit logging"""
    exclude = exclude_fields or ['password_hash', 'password']
    result = {}

    for column in model.__table__.columns:
        if column.name not in exclude:
            value = getattr(model, column.name)
            # Handle datetime serialization
            if isinstance(value, datetime):
                value = value.isoformat()
            result[column.name] = value

    return result
