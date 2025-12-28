"""Dashboard routes for VyaparaCore"""
from flask import Blueprint, g
from datetime import datetime, timedelta
from sqlalchemy import func
from config.database import db
from app.models import (
    Invoice, Payment, Customer, Supplier, Product, SalesOrder, PurchaseOrder,
    Stock, Quotation
)
from app.utils.security import jwt_required_with_user, permission_required
from app.utils.helpers import success_response

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/summary', methods=['GET'])
@jwt_required_with_user()
@permission_required('dashboard.view')
def get_summary():
    """Get dashboard summary"""
    today = datetime.utcnow().date()
    month_start = today.replace(day=1)

    # Sales this month
    monthly_sales = db.session.query(func.sum(Invoice.grand_total)).filter(
        Invoice.organization_id == g.organization_id,
        Invoice.invoice_date >= month_start,
        Invoice.status != 'void'
    ).scalar() or 0

    # Total invoices count
    total_invoices = Invoice.query.filter(
        Invoice.organization_id == g.organization_id,
        Invoice.status != 'void'
    ).count()

    # Receivables (pending payments)
    total_receivables = db.session.query(func.sum(Invoice.balance_due)).filter(
        Invoice.organization_id == g.organization_id,
        Invoice.status.in_(['sent', 'partial', 'overdue']),
        Invoice.balance_due > 0
    ).scalar() or 0

    # Overdue invoices count
    overdue_count = Invoice.query.filter(
        Invoice.organization_id == g.organization_id,
        Invoice.due_date < today,
        Invoice.balance_due > 0,
        Invoice.status.in_(['sent', 'partial', 'overdue'])
    ).count()

    # Payments received this month
    monthly_receipts = db.session.query(func.sum(Payment.amount)).filter(
        Payment.organization_id == g.organization_id,
        Payment.payment_date >= month_start,
        Payment.payment_type == 'receipt',
        Payment.status == 'completed'
    ).scalar() or 0

    # Counts
    customer_count = Customer.query.filter_by(
        organization_id=g.organization_id, is_active=True
    ).count()

    product_count = Product.query.filter_by(
        organization_id=g.organization_id, is_active=True
    ).count()

    supplier_count = Supplier.query.filter_by(
        organization_id=g.organization_id, is_active=True
    ).count()

    # Low stock products
    low_stock_count = Product.query.filter(
        Product.organization_id == g.organization_id,
        Product.is_active == True,
        Product.track_inventory == True,
        Product.current_stock <= Product.reorder_level
    ).count()

    # Pending orders
    pending_orders = SalesOrder.query.filter(
        SalesOrder.organization_id == g.organization_id,
        SalesOrder.status.in_(['confirmed', 'processing'])
    ).count()

    # Pending quotations
    pending_quotations = Quotation.query.filter(
        Quotation.organization_id == g.organization_id,
        Quotation.status.in_(['draft', 'sent'])
    ).count()

    return success_response({
        'total_sales': float(monthly_sales),
        'total_invoices': total_invoices,
        'total_customers': customer_count,
        'total_products': product_count,
        'total_suppliers': supplier_count,
        'pending_payments': float(total_receivables),
        'overdue_invoices': overdue_count,
        'monthly_receipts': float(monthly_receipts),
        'low_stock_count': low_stock_count,
        'pending_orders': pending_orders,
        'pending_quotations': pending_quotations
    })


@dashboard_bp.route('/sales-chart', methods=['GET'])
@jwt_required_with_user()
@permission_required('dashboard.view')
def get_sales_chart():
    """Get sales data for chart (last 12 months)"""
    today = datetime.utcnow().date()

    data = []
    for i in range(11, -1, -1):
        month_start = (today.replace(day=1) - timedelta(days=i*30)).replace(day=1)
        if month_start.month == 12:
            month_end = month_start.replace(year=month_start.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            month_end = month_start.replace(month=month_start.month + 1, day=1) - timedelta(days=1)

        sales = db.session.query(func.sum(Invoice.grand_total)).filter(
            Invoice.organization_id == g.organization_id,
            Invoice.invoice_date >= month_start,
            Invoice.invoice_date <= month_end,
            Invoice.status != 'void'
        ).scalar() or 0

        data.append({
            'month': month_start.strftime('%b %Y'),
            'sales': float(sales)
        })

    return success_response(data)


@dashboard_bp.route('/recent-invoices', methods=['GET'])
@jwt_required_with_user()
@permission_required('dashboard.view')
def get_recent_invoices():
    """Get recent invoices"""
    invoices = Invoice.query.filter_by(
        organization_id=g.organization_id
    ).order_by(Invoice.created_at.desc()).limit(10).all()
    
    return success_response([{
        'id': inv.id,
        'invoice_number': inv.invoice_number,
        'customer_name': inv.customer_name,
        'invoice_date': inv.invoice_date.isoformat() if inv.invoice_date else None,
        'total_amount': float(inv.grand_total or 0),
        'balance_due': float(inv.balance_due or 0),
        'status': inv.status
    } for inv in invoices])


@dashboard_bp.route('/recent-payments', methods=['GET'])
@jwt_required_with_user()
@permission_required('dashboard.view')
def get_recent_payments():
    """Get recent payments"""
    payments = Payment.query.filter_by(
        organization_id=g.organization_id,
        status='completed'
    ).order_by(Payment.created_at.desc()).limit(10).all()
    
    return success_response([{
        'id': p.id,
        'payment_number': p.payment_number,
        'party_name': p.party_name,
        'payment_date': p.payment_date.isoformat() if p.payment_date else None,
        'amount': float(p.amount or 0),
        'payment_type': p.payment_type
    } for p in payments])


@dashboard_bp.route('/top-customers', methods=['GET'])
@jwt_required_with_user()
@permission_required('dashboard.view')
def get_top_customers():
    """Get top customers by sales"""
    today = datetime.utcnow().date()
    month_start = today.replace(day=1)
    
    results = db.session.query(
        Invoice.customer_id,
        Invoice.customer_name,
        func.sum(Invoice.grand_total).label('total_sales')
    ).filter(
        Invoice.organization_id == g.organization_id,
        Invoice.invoice_date >= month_start,
        Invoice.status != 'void'
    ).group_by(Invoice.customer_id, Invoice.customer_name).order_by(
        func.sum(Invoice.grand_total).desc()
    ).limit(5).all()
    
    return success_response([{
        'customer_id': r.customer_id,
        'customer_name': r.customer_name,
        'total_sales': float(r.total_sales or 0)
    } for r in results])


@dashboard_bp.route('/top-products', methods=['GET'])
@jwt_required_with_user()
@permission_required('dashboard.view')
def get_top_products():
    """Get top selling products"""
    from app.models import InvoiceItem
    
    today = datetime.utcnow().date()
    month_start = today.replace(day=1)
    
    results = db.session.query(
        InvoiceItem.product_id,
        Product.name,
        func.sum(InvoiceItem.quantity).label('quantity_sold'),
        func.sum(InvoiceItem.amount).label('total_sales')
    ).join(Product).join(Invoice).filter(
        Invoice.organization_id == g.organization_id,
        Invoice.invoice_date >= month_start,
        Invoice.status != 'void'
    ).group_by(InvoiceItem.product_id, Product.name).order_by(
        func.sum(InvoiceItem.amount).desc()
    ).limit(5).all()
    
    return success_response([{
        'product_id': r.product_id,
        'product_name': r.name,
        'quantity_sold': float(r.quantity_sold or 0),
        'total_sales': float(r.total_sales or 0)
    } for r in results])


@dashboard_bp.route('/overdue-invoices', methods=['GET'])
@jwt_required_with_user()
@permission_required('dashboard.view')
def get_overdue_invoices():
    """Get overdue invoices"""
    today = datetime.utcnow().date()
    
    invoices = Invoice.query.filter(
        Invoice.organization_id == g.organization_id,
        Invoice.due_date < today,
        Invoice.balance_due > 0,
        Invoice.status.in_(['sent', 'partial', 'overdue'])
    ).order_by(Invoice.due_date).limit(10).all()
    
    return success_response([{
        'id': inv.id,
        'invoice_number': inv.invoice_number,
        'customer_name': inv.customer_name,
        'due_date': inv.due_date.isoformat() if inv.due_date else None,
        'balance_due': float(inv.balance_due or 0),
        'days_overdue': (today - inv.due_date).days if inv.due_date else 0
    } for inv in invoices])


@dashboard_bp.route('/low-stock', methods=['GET'])
@jwt_required_with_user()
@permission_required('dashboard.view')
def get_low_stock_products():
    """Get low stock products"""
    products = Product.query.filter(
        Product.organization_id == g.organization_id,
        Product.is_active == True,
        Product.track_inventory == True,
        Product.current_stock <= Product.reorder_level
    ).order_by(Product.current_stock).limit(10).all()
    
    return success_response([{
        'id': p.id,
        'name': p.name,
        'sku': p.sku,
        'current_stock': float(p.current_stock or 0),
        'reorder_level': float(p.reorder_level or 0)
    } for p in products])