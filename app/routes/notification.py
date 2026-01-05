"""Notification routes for VyaparaCore"""
from flask import Blueprint, g, request
from app.utils.security import jwt_required_with_user
from app.utils.helpers import success_response, error_response
from app.services.notification_service import (
    get_all_notifications,
    get_notification_counts,
    NotificationType
)

notification_bp = Blueprint('notification', __name__)


@notification_bp.route('', methods=['GET'])
@jwt_required_with_user()
def get_notifications():
    """
    Get all notifications for the current organization

    Query params:
    - type: Filter by notification type (comma-separated)
    - limit: Maximum number of notifications (default: 50)
    """
    # Parse query parameters
    notification_types = request.args.get('type')
    limit = request.args.get('limit', 50, type=int)

    include_types = None
    if notification_types:
        include_types = [t.strip() for t in notification_types.split(',')]

    # Get notifications
    notifications = get_all_notifications(
        organization_id=g.organization_id,
        user_id=g.current_user.id,
        include_types=include_types,
        limit=limit
    )

    return success_response({
        'notifications': notifications,
        'total': len(notifications)
    })


@notification_bp.route('/count', methods=['GET'])
@jwt_required_with_user()
def get_notification_count():
    """
    Get notification counts by type and priority
    Used for badge display in header
    """
    counts = get_notification_counts(g.organization_id)

    return success_response({
        'total': counts['total'],
        'high_priority': counts['high_priority'],
        'by_type': counts['by_type']
    })


@notification_bp.route('/types', methods=['GET'])
@jwt_required_with_user()
def get_notification_types():
    """
    Get available notification types
    """
    types = [
        {
            'value': NotificationType.LOW_STOCK,
            'label': 'Low Stock Alerts',
            'icon': 'cube',
            'color': 'orange'
        },
        {
            'value': NotificationType.INVOICE_OVERDUE,
            'label': 'Overdue Invoices',
            'icon': 'document-text',
            'color': 'red'
        },
        {
            'value': NotificationType.INVOICE_DUE_SOON,
            'label': 'Invoices Due Soon',
            'icon': 'document-text',
            'color': 'yellow'
        },
        {
            'value': NotificationType.ORDER_NOT_INVOICED,
            'label': 'Orders Awaiting Invoice',
            'icon': 'clipboard-document-list',
            'color': 'blue'
        },
        {
            'value': NotificationType.QUOTATION_EXPIRING,
            'label': 'Expiring Quotations',
            'icon': 'clipboard-document',
            'color': 'yellow'
        },
        {
            'value': NotificationType.QUOTATION_PENDING,
            'label': 'Quotation Follow-ups',
            'icon': 'clipboard-document',
            'color': 'gray'
        }
    ]

    return success_response({'types': types})


# Note: Since notifications are generated on-demand (not stored in DB),
# "mark as read" and "dismiss" require a different approach.
# For now, we can track dismissed/read notification IDs in user preferences
# or localStorage on the frontend.

@notification_bp.route('/<notification_id>/dismiss', methods=['POST'])
@jwt_required_with_user()
def dismiss_notification(notification_id):
    """
    Dismiss a notification

    Since notifications are generated on-demand, we would need to store
    dismissed notification IDs. For MVP, this can be handled client-side
    with localStorage.

    Returns success for frontend compatibility.
    """
    # For future: Store dismissed notification IDs in user preferences
    # dismissed_ids = g.current_user.preferences.get('dismissed_notifications', [])
    # dismissed_ids.append(notification_id)
    # g.current_user.preferences['dismissed_notifications'] = dismissed_ids
    # db.session.commit()

    return success_response({
        'message': 'Notification dismissed',
        'notification_id': notification_id
    })


@notification_bp.route('/dismiss-all', methods=['POST'])
@jwt_required_with_user()
def dismiss_all_notifications():
    """
    Dismiss all notifications

    For MVP, handled client-side. Returns current notification IDs.
    """
    notifications = get_all_notifications(
        organization_id=g.organization_id,
        limit=None
    )

    notification_ids = [n['id'] for n in notifications]

    return success_response({
        'message': 'All notifications dismissed',
        'dismissed_ids': notification_ids
    })
