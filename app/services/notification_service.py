"""
Notification Service - Generates on-demand notifications for business alerts
"""
from datetime import datetime, timedelta, date
from sqlalchemy import and_, or_
from config.database import db
from app.models.product import Product
from app.models.inventory import Stock
from app.models.invoice import Invoice
from app.models.order import SalesOrder
from app.models.quotation import Quotation


class NotificationType:
    LOW_STOCK = 'low_stock'
    INVOICE_OVERDUE = 'invoice_overdue'
    INVOICE_DUE_SOON = 'invoice_due_soon'
    ORDER_NOT_INVOICED = 'order_not_invoiced'
    QUOTATION_EXPIRING = 'quotation_expiring'
    QUOTATION_PENDING = 'quotation_pending'
    NEW_ORDER = 'new_order'
    PAYMENT_RECEIVED = 'payment_received'


class NotificationPriority:
    HIGH = 'high'
    NORMAL = 'normal'
    LOW = 'low'


def get_low_stock_alerts(organization_id):
    """
    Get products with stock below minimum stock level
    """
    notifications = []

    # Query products with min_stock_level set and current_stock below it
    products = Product.query.filter(
        Product.organization_id == organization_id,
        Product.is_active == True,
        Product.track_inventory == True,
        Product.min_stock_level > 0,
        Product.current_stock < Product.min_stock_level
    ).all()

    for product in products:
        notifications.append({
            'id': f'low_stock_{product.id}',
            'type': NotificationType.LOW_STOCK,
            'priority': NotificationPriority.HIGH,
            'title': 'Low Stock Alert',
            'message': f"'{product.name}' has {int(product.current_stock)} units (min: {int(product.min_stock_level)})",
            'entity_type': 'product',
            'entity_id': product.id,
            'action_url': f'/products/{product.id}',
            'created_at': datetime.utcnow().isoformat(),
            'data': {
                'product_name': product.name,
                'sku': product.sku,
                'current_stock': float(product.current_stock),
                'min_stock_level': float(product.min_stock_level),
                'reorder_level': float(product.reorder_level) if product.reorder_level else 0
            }
        })

    return notifications


def get_overdue_invoices(organization_id):
    """
    Get invoices past due date with unpaid balance
    """
    notifications = []
    today = date.today()

    invoices = Invoice.query.filter(
        Invoice.organization_id == organization_id,
        Invoice.due_date < today,
        Invoice.payment_status.in_(['unpaid', 'partial']),
        Invoice.status.notin_(['void', 'cancelled', 'paid'])
    ).order_by(Invoice.due_date.asc()).all()

    for invoice in invoices:
        days_overdue = (today - invoice.due_date).days
        notifications.append({
            'id': f'invoice_overdue_{invoice.id}',
            'type': NotificationType.INVOICE_OVERDUE,
            'priority': NotificationPriority.HIGH,
            'title': 'Invoice Overdue',
            'message': f"Invoice {invoice.invoice_number} is {days_overdue} days overdue (₹{float(invoice.balance_due):,.2f})",
            'entity_type': 'invoice',
            'entity_id': invoice.id,
            'action_url': f'/invoices/{invoice.id}',
            'created_at': datetime.utcnow().isoformat(),
            'data': {
                'invoice_number': invoice.invoice_number,
                'customer_name': invoice.customer_name,
                'due_date': invoice.due_date.isoformat(),
                'days_overdue': days_overdue,
                'balance_due': float(invoice.balance_due),
                'grand_total': float(invoice.grand_total)
            }
        })

    return notifications


def get_invoices_due_soon(organization_id, days=7):
    """
    Get invoices due within specified days
    """
    notifications = []
    today = date.today()
    due_threshold = today + timedelta(days=days)

    invoices = Invoice.query.filter(
        Invoice.organization_id == organization_id,
        Invoice.due_date >= today,
        Invoice.due_date <= due_threshold,
        Invoice.payment_status.in_(['unpaid', 'partial']),
        Invoice.status.notin_(['void', 'cancelled', 'paid'])
    ).order_by(Invoice.due_date.asc()).all()

    for invoice in invoices:
        days_until_due = (invoice.due_date - today).days
        notifications.append({
            'id': f'invoice_due_soon_{invoice.id}',
            'type': NotificationType.INVOICE_DUE_SOON,
            'priority': NotificationPriority.NORMAL,
            'title': 'Invoice Due Soon',
            'message': f"Invoice {invoice.invoice_number} is due in {days_until_due} days (₹{float(invoice.balance_due):,.2f})",
            'entity_type': 'invoice',
            'entity_id': invoice.id,
            'action_url': f'/invoices/{invoice.id}',
            'created_at': datetime.utcnow().isoformat(),
            'data': {
                'invoice_number': invoice.invoice_number,
                'customer_name': invoice.customer_name,
                'due_date': invoice.due_date.isoformat(),
                'days_until_due': days_until_due,
                'balance_due': float(invoice.balance_due),
                'grand_total': float(invoice.grand_total)
            }
        })

    return notifications


def get_confirmed_not_invoiced(organization_id):
    """
    Get confirmed sales orders that haven't been invoiced yet
    """
    notifications = []

    # Find confirmed/processing/shipped orders without an invoice
    orders = SalesOrder.query.filter(
        SalesOrder.organization_id == organization_id,
        SalesOrder.status.in_(['confirmed', 'processing', 'shipped']),
    ).all()

    for order in orders:
        # Check if invoice exists for this order
        invoice_exists = Invoice.query.filter(
            Invoice.sales_order_id == order.id,
            Invoice.status.notin_(['void', 'cancelled'])
        ).first()

        if not invoice_exists:
            days_since_confirmed = 0
            if order.confirmed_at:
                days_since_confirmed = (datetime.utcnow() - order.confirmed_at).days

            notifications.append({
                'id': f'order_not_invoiced_{order.id}',
                'type': NotificationType.ORDER_NOT_INVOICED,
                'priority': NotificationPriority.NORMAL,
                'title': 'Order Awaiting Invoice',
                'message': f"Sales order {order.order_number} ({order.customer_name}) needs invoicing",
                'entity_type': 'sales_order',
                'entity_id': order.id,
                'action_url': f'/sales-orders/{order.id}',
                'created_at': datetime.utcnow().isoformat(),
                'data': {
                    'order_number': order.order_number,
                    'customer_name': order.customer_name,
                    'order_date': order.order_date.isoformat() if order.order_date else None,
                    'status': order.status,
                    'grand_total': float(order.grand_total),
                    'days_since_confirmed': days_since_confirmed
                }
            })

    return notifications


def get_expiring_quotations(organization_id, days=7):
    """
    Get quotations expiring within specified days
    """
    notifications = []
    today = date.today()
    expiry_threshold = today + timedelta(days=days)

    quotations = Quotation.query.filter(
        Quotation.organization_id == organization_id,
        Quotation.valid_until >= today,
        Quotation.valid_until <= expiry_threshold,
        Quotation.status.in_(['draft', 'sent']),
        Quotation.converted_to_order == False
    ).order_by(Quotation.valid_until.asc()).all()

    for quotation in quotations:
        days_until_expiry = (quotation.valid_until - today).days
        notifications.append({
            'id': f'quotation_expiring_{quotation.id}',
            'type': NotificationType.QUOTATION_EXPIRING,
            'priority': NotificationPriority.NORMAL,
            'title': 'Quotation Expiring',
            'message': f"Quotation {quotation.quotation_number} for {quotation.customer_name} expires in {days_until_expiry} days",
            'entity_type': 'quotation',
            'entity_id': quotation.id,
            'action_url': f'/quotations/{quotation.id}',
            'created_at': datetime.utcnow().isoformat(),
            'data': {
                'quotation_number': quotation.quotation_number,
                'customer_name': quotation.customer_name,
                'valid_until': quotation.valid_until.isoformat(),
                'days_until_expiry': days_until_expiry,
                'grand_total': float(quotation.grand_total),
                'status': quotation.status
            }
        })

    return notifications


def get_pending_quotations(organization_id, days_threshold=7):
    """
    Get quotations sent but not responded to for more than threshold days
    """
    notifications = []
    threshold_date = datetime.utcnow() - timedelta(days=days_threshold)

    quotations = Quotation.query.filter(
        Quotation.organization_id == organization_id,
        Quotation.status == 'sent',
        Quotation.sent_at < threshold_date,
        Quotation.converted_to_order == False
    ).order_by(Quotation.sent_at.asc()).all()

    for quotation in quotations:
        days_waiting = (datetime.utcnow() - quotation.sent_at).days if quotation.sent_at else 0
        notifications.append({
            'id': f'quotation_pending_{quotation.id}',
            'type': NotificationType.QUOTATION_PENDING,
            'priority': NotificationPriority.LOW,
            'title': 'Quotation Follow-up',
            'message': f"Quotation {quotation.quotation_number} sent {days_waiting} days ago - follow up with {quotation.customer_name}",
            'entity_type': 'quotation',
            'entity_id': quotation.id,
            'action_url': f'/quotations/{quotation.id}',
            'created_at': datetime.utcnow().isoformat(),
            'data': {
                'quotation_number': quotation.quotation_number,
                'customer_name': quotation.customer_name,
                'sent_at': quotation.sent_at.isoformat() if quotation.sent_at else None,
                'days_waiting': days_waiting,
                'grand_total': float(quotation.grand_total)
            }
        })

    return notifications


def get_all_notifications(organization_id, user_id=None, include_types=None, limit=50):
    """
    Get all notifications for an organization, sorted by priority and date
    """
    all_notifications = []

    # Define which types to include
    type_functions = {
        NotificationType.LOW_STOCK: get_low_stock_alerts,
        NotificationType.INVOICE_OVERDUE: get_overdue_invoices,
        NotificationType.INVOICE_DUE_SOON: get_invoices_due_soon,
        NotificationType.ORDER_NOT_INVOICED: get_confirmed_not_invoiced,
        NotificationType.QUOTATION_EXPIRING: get_expiring_quotations,
        NotificationType.QUOTATION_PENDING: get_pending_quotations,
    }

    # Filter types if specified
    if include_types:
        type_functions = {k: v for k, v in type_functions.items() if k in include_types}

    # Collect all notifications
    for notification_type, func in type_functions.items():
        try:
            notifications = func(organization_id)
            all_notifications.extend(notifications)
        except Exception as e:
            print(f"Error getting {notification_type} notifications: {e}")

    # Sort by priority (high first) then by created_at
    priority_order = {
        NotificationPriority.HIGH: 0,
        NotificationPriority.NORMAL: 1,
        NotificationPriority.LOW: 2
    }

    all_notifications.sort(key=lambda x: (
        priority_order.get(x['priority'], 2),
        x['created_at']
    ), reverse=False)

    # Apply limit
    if limit:
        all_notifications = all_notifications[:limit]

    return all_notifications


def get_notification_counts(organization_id):
    """
    Get counts of notifications by type and priority
    """
    all_notifications = get_all_notifications(organization_id, limit=None)

    counts = {
        'total': len(all_notifications),
        'high_priority': sum(1 for n in all_notifications if n['priority'] == NotificationPriority.HIGH),
        'by_type': {}
    }

    for notification in all_notifications:
        ntype = notification['type']
        if ntype not in counts['by_type']:
            counts['by_type'][ntype] = 0
        counts['by_type'][ntype] += 1

    return counts
