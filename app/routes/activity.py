"""Activity log routes for VyaparaCore"""
from flask import Blueprint, g, request
from datetime import datetime, timedelta
from config.database import db
from app.models.audit import ActivityLog, AuditLog, LoginHistory
from app.utils.security import jwt_required_with_user, permission_required
from app.utils.helpers import success_response, error_response, paginate, get_filters

activity_bp = Blueprint('activity', __name__)


@activity_bp.route('', methods=['GET'])
@jwt_required_with_user()
def list_activities():
    """List activity logs with filtering"""
    query = ActivityLog.query.filter_by(organization_id=g.organization_id)

    filters = get_filters()

    # Filter by activity type
    if request.args.get('activity_type'):
        query = query.filter_by(activity_type=request.args.get('activity_type'))

    # Filter by entity type
    if request.args.get('entity_type'):
        query = query.filter_by(entity_type=request.args.get('entity_type'))

    # Filter by user
    if request.args.get('user_id'):
        query = query.filter_by(user_id=request.args.get('user_id', type=int))

    # Filter by date range
    if request.args.get('from_date'):
        from_date = datetime.strptime(request.args.get('from_date'), '%Y-%m-%d')
        query = query.filter(ActivityLog.created_at >= from_date)

    if request.args.get('to_date'):
        to_date = datetime.strptime(request.args.get('to_date'), '%Y-%m-%d')
        to_date = to_date + timedelta(days=1)  # Include the end date
        query = query.filter(ActivityLog.created_at < to_date)

    # Search in description
    if filters.get('search'):
        search = f"%{filters['search']}%"
        query = query.filter(
            db.or_(
                ActivityLog.description.ilike(search),
                ActivityLog.entity_number.ilike(search),
                ActivityLog.user_name.ilike(search)
            )
        )

    # Order by most recent
    query = query.order_by(ActivityLog.created_at.desc())

    def serialize(log):
        return {
            'id': log.id,
            'activity_type': log.activity_type,
            'description': log.description,
            'entity_type': log.entity_type,
            'entity_id': log.entity_id,
            'entity_number': log.entity_number,
            'user_id': log.user_id,
            'user_name': log.user_name,
            'ip_address': log.ip_address,
            'extra_data': log.extra_data,
            'created_at': log.created_at.isoformat() if log.created_at else None
        }

    return success_response(paginate(query, serialize))


@activity_bp.route('/recent', methods=['GET'])
@jwt_required_with_user()
def recent_activities():
    """Get recent activities (last 24 hours)"""
    since = datetime.utcnow() - timedelta(hours=24)

    activities = ActivityLog.query.filter(
        ActivityLog.organization_id == g.organization_id,
        ActivityLog.created_at >= since
    ).order_by(ActivityLog.created_at.desc()).limit(50).all()

    result = [{
        'id': log.id,
        'activity_type': log.activity_type,
        'description': log.description,
        'entity_type': log.entity_type,
        'entity_id': log.entity_id,
        'entity_number': log.entity_number,
        'user_name': log.user_name,
        'created_at': log.created_at.isoformat() if log.created_at else None
    } for log in activities]

    return success_response(result)


@activity_bp.route('/entity/<entity_type>/<int:entity_id>', methods=['GET'])
@jwt_required_with_user()
def entity_activities(entity_type, entity_id):
    """Get activity history for a specific entity"""
    activities = ActivityLog.query.filter(
        ActivityLog.organization_id == g.organization_id,
        ActivityLog.entity_type == entity_type,
        ActivityLog.entity_id == entity_id
    ).order_by(ActivityLog.created_at.desc()).all()

    result = [{
        'id': log.id,
        'activity_type': log.activity_type,
        'description': log.description,
        'user_name': log.user_name,
        'ip_address': log.ip_address,
        'extra_data': log.extra_data,
        'created_at': log.created_at.isoformat() if log.created_at else None
    } for log in activities]

    return success_response(result)


@activity_bp.route('/user/<int:user_id>', methods=['GET'])
@jwt_required_with_user()
def user_activities(user_id):
    """Get activity history for a specific user"""
    query = ActivityLog.query.filter(
        ActivityLog.organization_id == g.organization_id,
        ActivityLog.user_id == user_id
    ).order_by(ActivityLog.created_at.desc())

    # Limit to last 100 activities
    activities = query.limit(100).all()

    result = [{
        'id': log.id,
        'activity_type': log.activity_type,
        'description': log.description,
        'entity_type': log.entity_type,
        'entity_id': log.entity_id,
        'entity_number': log.entity_number,
        'ip_address': log.ip_address,
        'created_at': log.created_at.isoformat() if log.created_at else None
    } for log in activities]

    return success_response(result)


@activity_bp.route('/audit', methods=['GET'])
@jwt_required_with_user()
@permission_required('admin.audit')
def list_audit_logs():
    """List audit logs (data change history)"""
    query = AuditLog.query.filter_by(organization_id=g.organization_id)

    # Filter by table
    if request.args.get('table_name'):
        query = query.filter_by(table_name=request.args.get('table_name'))

    # Filter by action
    if request.args.get('action'):
        query = query.filter_by(action=request.args.get('action'))

    # Filter by record
    if request.args.get('record_id'):
        query = query.filter_by(record_id=request.args.get('record_id', type=int))

    # Filter by date range
    if request.args.get('from_date'):
        from_date = datetime.strptime(request.args.get('from_date'), '%Y-%m-%d')
        query = query.filter(AuditLog.created_at >= from_date)

    if request.args.get('to_date'):
        to_date = datetime.strptime(request.args.get('to_date'), '%Y-%m-%d')
        to_date = to_date + timedelta(days=1)
        query = query.filter(AuditLog.created_at < to_date)

    query = query.order_by(AuditLog.created_at.desc())

    def serialize(log):
        return {
            'id': log.id,
            'table_name': log.table_name,
            'record_id': log.record_id,
            'action': log.action,
            'user_id': log.user_id,
            'user_email': log.user_email,
            'user_name': log.user_name,
            'old_values': log.old_values,
            'new_values': log.new_values,
            'changed_fields': log.changed_fields,
            'ip_address': log.ip_address,
            'created_at': log.created_at.isoformat() if log.created_at else None
        }

    return success_response(paginate(query, serialize))


@activity_bp.route('/login-history', methods=['GET'])
@jwt_required_with_user()
@permission_required('admin.audit')
def list_login_history():
    """List login history"""
    query = LoginHistory.query.filter_by(organization_id=g.organization_id)

    # Filter by user
    if request.args.get('user_id'):
        query = query.filter_by(user_id=request.args.get('user_id', type=int))

    # Filter by status
    if request.args.get('status'):
        query = query.filter_by(status=request.args.get('status'))

    # Filter by date range
    if request.args.get('from_date'):
        from_date = datetime.strptime(request.args.get('from_date'), '%Y-%m-%d')
        query = query.filter(LoginHistory.login_at >= from_date)

    if request.args.get('to_date'):
        to_date = datetime.strptime(request.args.get('to_date'), '%Y-%m-%d')
        to_date = to_date + timedelta(days=1)
        query = query.filter(LoginHistory.login_at < to_date)

    query = query.order_by(LoginHistory.login_at.desc())

    def serialize(log):
        return {
            'id': log.id,
            'user_id': log.user_id,
            'login_at': log.login_at.isoformat() if log.login_at else None,
            'logout_at': log.logout_at.isoformat() if log.logout_at else None,
            'ip_address': log.ip_address,
            'device_type': log.device_type,
            'browser': log.browser,
            'os': log.os,
            'city': log.city,
            'country': log.country,
            'status': log.status,
            'failure_reason': log.failure_reason
        }

    return success_response(paginate(query, serialize))


@activity_bp.route('/stats', methods=['GET'])
@jwt_required_with_user()
def activity_stats():
    """Get activity statistics"""
    org_id = g.organization_id

    # Today's activity count
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_count = ActivityLog.query.filter(
        ActivityLog.organization_id == org_id,
        ActivityLog.created_at >= today
    ).count()

    # This week's activity count
    week_start = today - timedelta(days=today.weekday())
    week_count = ActivityLog.query.filter(
        ActivityLog.organization_id == org_id,
        ActivityLog.created_at >= week_start
    ).count()

    # Activity by type (last 7 days)
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    activity_by_type = db.session.query(
        ActivityLog.activity_type,
        db.func.count(ActivityLog.id)
    ).filter(
        ActivityLog.organization_id == org_id,
        ActivityLog.created_at >= seven_days_ago
    ).group_by(ActivityLog.activity_type).all()

    # Most active users (last 7 days)
    active_users = db.session.query(
        ActivityLog.user_id,
        ActivityLog.user_name,
        db.func.count(ActivityLog.id).label('activity_count')
    ).filter(
        ActivityLog.organization_id == org_id,
        ActivityLog.created_at >= seven_days_ago,
        ActivityLog.user_id.isnot(None)
    ).group_by(
        ActivityLog.user_id,
        ActivityLog.user_name
    ).order_by(db.desc('activity_count')).limit(5).all()

    return success_response({
        'today_count': today_count,
        'week_count': week_count,
        'by_type': {t: c for t, c in activity_by_type},
        'active_users': [
            {'user_id': u[0], 'user_name': u[1], 'count': u[2]}
            for u in active_users
        ]
    })
