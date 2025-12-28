"""Report routes for VyaparaCore"""
from flask import Blueprint, g, request
from datetime import datetime, timedelta
from sqlalchemy import func
from config.database import db
from app.models import (
    Invoice, InvoiceItem, Payment, Customer, Supplier, Product,
    SalesOrder, PurchaseOrder, Stock, StockTransaction
)
from app.utils.security import jwt_required_with_user, permission_required
from app.utils.helpers import success_response, error_response

report_bp = Blueprint('report', __name__)


def parse_date_range():
    """Parse date range from request args"""
    from_date = request.args.get('from_date')
    to_date = request.args.get('to_date')
    period = request.args.get('period', 'month')
    
    if not from_date or not to_date:
        today = datetime.utcnow().date()
        if period == 'day':
            from_date = to_date = today
        elif period == 'week':
            from_date = today - timedelta(days=today.weekday())
            to_date = today
        elif period == 'month':
            from_date = today.replace(day=1)
            to_date = today
        elif period == 'quarter':
            quarter = (today.month - 1) // 3
            from_date = today.replace(month=quarter * 3 + 1, day=1)
            to_date = today
        elif period == 'year':
            from_date = today.replace(month=1, day=1)
            to_date = today
        else:
            from_date = today.replace(day=1)
            to_date = today
    
    return from_date, to_date


@report_bp.route('/sales/summary', methods=['GET'])
@jwt_required_with_user()
@permission_required('reports.sales')
def sales_summary():
    """Get sales summary report"""
    from_date, to_date = parse_date_range()
    
    invoices = Invoice.query.filter(
        Invoice.organization_id == g.organization_id,
        Invoice.invoice_date >= from_date,
        Invoice.invoice_date <= to_date,
        Invoice.status != 'void'
    ).all()
    
    total_sales = sum(float(inv.grand_total or 0) for inv in invoices)
    total_tax = sum(float(inv.total_tax or 0) for inv in invoices)
    total_discount = sum(float(inv.discount_amount or 0) for inv in invoices)
    
    payments = Payment.query.filter(
        Payment.organization_id == g.organization_id,
        Payment.payment_date >= from_date,
        Payment.payment_date <= to_date,
        Payment.payment_type == 'receipt',
        Payment.status == 'completed'
    ).all()
    
    total_received = sum(float(p.amount or 0) for p in payments)
    
    outstanding = Invoice.query.filter(
        Invoice.organization_id == g.organization_id,
        Invoice.status.in_(['sent', 'partial', 'overdue']),
        Invoice.balance_due > 0
    ).with_entities(func.sum(Invoice.balance_due)).scalar() or 0
    
    return success_response({
        'period': {'from': str(from_date), 'to': str(to_date)},
        'total_sales': float(total_sales),
        'total_tax': float(total_tax),
        'total_discount': float(total_discount),
        'invoice_count': len(invoices),
        'total_received': float(total_received),
        'total_outstanding': float(outstanding),
        'average_invoice_value': float(total_sales / len(invoices)) if invoices else 0
    })


@report_bp.route('/sales/by-customer', methods=['GET'])
@jwt_required_with_user()
@permission_required('reports.sales')
def sales_by_customer():
    """Get sales by customer"""
    from_date, to_date = parse_date_range()
    
    results = db.session.query(
        Invoice.customer_id,
        Invoice.customer_name,
        func.count(Invoice.id).label('invoice_count'),
        func.sum(Invoice.grand_total).label('total_sales'),
        func.sum(Invoice.balance_due).label('outstanding')
    ).filter(
        Invoice.organization_id == g.organization_id,
        Invoice.invoice_date >= from_date,
        Invoice.invoice_date <= to_date,
        Invoice.status != 'void'
    ).group_by(Invoice.customer_id, Invoice.customer_name).order_by(
        func.sum(Invoice.grand_total).desc()
    ).limit(50).all()
    
    return success_response({
        'period': {'from': str(from_date), 'to': str(to_date)},
        'data': [{
            'customer_id': r.customer_id,
            'customer_name': r.customer_name,
            'invoice_count': r.invoice_count,
            'total_sales': float(r.total_sales or 0),
            'outstanding': float(r.outstanding or 0)
        } for r in results]
    })


@report_bp.route('/sales/by-product', methods=['GET'])
@jwt_required_with_user()
@permission_required('reports.sales')
def sales_by_product():
    """Get sales by product"""
    from_date, to_date = parse_date_range()
    
    results = db.session.query(
        InvoiceItem.product_id,
        Product.name.label('product_name'),
        Product.sku,
        func.sum(InvoiceItem.quantity).label('quantity_sold'),
        func.sum(InvoiceItem.amount).label('total_sales')
    ).join(Product).join(Invoice).filter(
        Invoice.organization_id == g.organization_id,
        Invoice.invoice_date >= from_date,
        Invoice.invoice_date <= to_date,
        Invoice.status != 'void'
    ).group_by(InvoiceItem.product_id, Product.name, Product.sku).order_by(
        func.sum(InvoiceItem.amount).desc()
    ).limit(50).all()
    
    return success_response({
        'period': {'from': str(from_date), 'to': str(to_date)},
        'data': [{
            'product_id': r.product_id,
            'product_name': r.product_name,
            'sku': r.sku,
            'quantity_sold': float(r.quantity_sold or 0),
            'total_sales': float(r.total_sales or 0)
        } for r in results]
    })


@report_bp.route('/tax/gst-summary', methods=['GET'])
@jwt_required_with_user()
@permission_required('reports.tax')
def gst_summary():
    """Get GST summary report"""
    from_date, to_date = parse_date_range()
    
    invoices = Invoice.query.filter(
        Invoice.organization_id == g.organization_id,
        Invoice.invoice_date >= from_date,
        Invoice.invoice_date <= to_date,
        Invoice.status != 'void'
    ).all()
    
    total_cgst = sum(float(inv.cgst_amount or 0) for inv in invoices)
    total_sgst = sum(float(inv.sgst_amount or 0) for inv in invoices)
    total_igst = sum(float(inv.igst_amount or 0) for inv in invoices)
    total_cess = sum(float(inv.cess_amount or 0) for inv in invoices)
    total_taxable = sum(float(inv.subtotal or 0) for inv in invoices)
    
    return success_response({
        'period': {'from': str(from_date), 'to': str(to_date)},
        'total_taxable_value': float(total_taxable),
        'cgst': float(total_cgst),
        'sgst': float(total_sgst),
        'igst': float(total_igst),
        'cess': float(total_cess),
        'total_tax': float(total_cgst + total_sgst + total_igst + total_cess),
        'invoice_count': len(invoices)
    })


@report_bp.route('/inventory/stock-summary', methods=['GET'])
@jwt_required_with_user()
@permission_required('reports.inventory')
def stock_summary():
    """Get stock summary"""
    products = Product.query.filter(
        Product.organization_id == g.organization_id,
        Product.is_active == True,
        Product.track_inventory == True
    ).all()
    
    total_value = 0
    low_stock = 0
    out_of_stock = 0
    
    for p in products:
        stock_value = float(p.current_stock or 0) * float(p.purchase_price or 0)
        total_value += stock_value
        
        if (p.current_stock or 0) <= 0:
            out_of_stock += 1
        elif (p.current_stock or 0) <= (p.reorder_level or 0):
            low_stock += 1
    
    return success_response({
        'total_products': len(products),
        'total_stock_value': float(total_value),
        'low_stock_count': low_stock,
        'out_of_stock_count': out_of_stock
    })


@report_bp.route('/inventory/stock-value', methods=['GET'])
@jwt_required_with_user()
@permission_required('reports.inventory')
def stock_value():
    """Get stock value report"""
    products = Product.query.filter(
        Product.organization_id == g.organization_id,
        Product.is_active == True,
        Product.track_inventory == True
    ).all()
    
    data = []
    for p in products:
        qty = float(p.current_stock or 0)
        cost = float(p.purchase_price or 0)
        value = qty * cost
        
        data.append({
            'product_id': p.id,
            'product_name': p.name,
            'sku': p.sku,
            'category': p.category.name if p.category else None,
            'quantity': qty,
            'cost_price': cost,
            'stock_value': value
        })
    
    total_value = sum(d['stock_value'] for d in data)

    return success_response({
        'total_value': float(total_value),
        'product_count': len(data),
        'data': sorted(data, key=lambda x: x['stock_value'], reverse=True)[:100]
    })


@report_bp.route('/inventory/movement', methods=['GET'])
@jwt_required_with_user()
@permission_required('reports.inventory')
def stock_movement():
    """Get stock movement report"""
    from_date, to_date = parse_date_range()

    transactions = StockTransaction.query.filter(
        StockTransaction.organization_id == g.organization_id,
        StockTransaction.transaction_date >= from_date,
        StockTransaction.transaction_date <= to_date
    ).order_by(StockTransaction.transaction_date.desc()).limit(500).all()

    inward = sum(float(t.quantity or 0) for t in transactions if t.transaction_type in ['purchase', 'adjustment_in', 'transfer_in', 'opening'])
    outward = sum(float(t.quantity or 0) for t in transactions if t.transaction_type in ['sale', 'adjustment_out', 'transfer_out'])

    by_type = {}
    for t in transactions:
        tt = t.transaction_type
        if tt not in by_type:
            by_type[tt] = {'count': 0, 'quantity': 0}
        by_type[tt]['count'] += 1
        by_type[tt]['quantity'] += float(t.quantity or 0)

    return success_response({
        'period': {'from': str(from_date), 'to': str(to_date)},
        'total_inward': float(inward),
        'total_outward': float(outward),
        'transaction_count': len(transactions),
        'by_type': by_type,
        'transactions': [{
            'id': t.id,
            'date': t.transaction_date.isoformat() if t.transaction_date else None,
            'product_id': t.product_id,
            'product_name': t.product.name if t.product else None,
            'type': t.transaction_type,
            'quantity': float(t.quantity or 0),
            'reference': t.reference_number,
            'notes': t.notes
        } for t in transactions[:100]]
    })


@report_bp.route('/inventory/low-stock', methods=['GET'])
@jwt_required_with_user()
@permission_required('reports.inventory')
def low_stock_report():
    """Get low stock and out of stock products"""
    products = Product.query.filter(
        Product.organization_id == g.organization_id,
        Product.is_active == True,
        Product.track_inventory == True
    ).all()

    low_stock = []
    out_of_stock = []

    for p in products:
        qty = float(p.current_stock or 0)
        reorder = float(p.reorder_level or 0)

        item = {
            'product_id': p.id,
            'product_name': p.name,
            'sku': p.sku,
            'category': p.category.name if p.category else None,
            'current_stock': qty,
            'reorder_level': reorder,
            'unit': p.unit
        }

        if qty <= 0:
            out_of_stock.append(item)
        elif qty <= reorder:
            low_stock.append(item)

    return success_response({
        'low_stock': low_stock,
        'out_of_stock': out_of_stock,
        'low_stock_count': len(low_stock),
        'out_of_stock_count': len(out_of_stock)
    })


# Purchase Reports
@report_bp.route('/purchase/summary', methods=['GET'])
@jwt_required_with_user()
@permission_required('reports.purchase')
def purchase_summary():
    """Get purchase summary report"""
    from_date, to_date = parse_date_range()

    purchase_orders = PurchaseOrder.query.filter(
        PurchaseOrder.organization_id == g.organization_id,
        PurchaseOrder.order_date >= from_date,
        PurchaseOrder.order_date <= to_date,
        PurchaseOrder.status != 'cancelled'
    ).all()

    total_purchases = sum(float(po.grand_total or 0) for po in purchase_orders)
    total_tax = sum(float(po.total_tax or 0) for po in purchase_orders)

    payments = Payment.query.filter(
        Payment.organization_id == g.organization_id,
        Payment.payment_date >= from_date,
        Payment.payment_date <= to_date,
        Payment.payment_type == 'payout',
        Payment.status == 'completed'
    ).all()

    total_paid = sum(float(p.amount or 0) for p in payments)

    outstanding = PurchaseOrder.query.filter(
        PurchaseOrder.organization_id == g.organization_id,
        PurchaseOrder.status.in_(['sent', 'confirmed', 'partially_received', 'received']),
        PurchaseOrder.payment_status.in_(['unpaid', 'partial'])
    ).all()

    total_outstanding = sum(float(po.grand_total or 0) - float(po.advance_amount or 0) for po in outstanding)

    return success_response({
        'period': {'from': str(from_date), 'to': str(to_date)},
        'total_purchases': float(total_purchases),
        'total_tax': float(total_tax),
        'order_count': len(purchase_orders),
        'total_paid': float(total_paid),
        'total_outstanding': float(total_outstanding),
        'average_order_value': float(total_purchases / len(purchase_orders)) if purchase_orders else 0
    })


@report_bp.route('/purchase/by-supplier', methods=['GET'])
@jwt_required_with_user()
@permission_required('reports.purchase')
def purchase_by_supplier():
    """Get purchases by supplier"""
    from_date, to_date = parse_date_range()

    results = db.session.query(
        PurchaseOrder.supplier_id,
        PurchaseOrder.supplier_name,
        func.count(PurchaseOrder.id).label('order_count'),
        func.sum(PurchaseOrder.grand_total).label('total_purchases')
    ).filter(
        PurchaseOrder.organization_id == g.organization_id,
        PurchaseOrder.order_date >= from_date,
        PurchaseOrder.order_date <= to_date,
        PurchaseOrder.status != 'cancelled'
    ).group_by(PurchaseOrder.supplier_id, PurchaseOrder.supplier_name).order_by(
        func.sum(PurchaseOrder.grand_total).desc()
    ).limit(50).all()

    return success_response({
        'period': {'from': str(from_date), 'to': str(to_date)},
        'data': [{
            'supplier_id': r.supplier_id,
            'supplier_name': r.supplier_name,
            'order_count': r.order_count,
            'total_purchases': float(r.total_purchases or 0)
        } for r in results]
    })


@report_bp.route('/purchase/by-product', methods=['GET'])
@jwt_required_with_user()
@permission_required('reports.purchase')
def purchase_by_product():
    """Get purchases by product"""
    from_date, to_date = parse_date_range()
    from app.models import PurchaseOrderItem

    results = db.session.query(
        PurchaseOrderItem.product_id,
        Product.name.label('product_name'),
        Product.sku,
        func.sum(PurchaseOrderItem.quantity).label('quantity_purchased'),
        func.sum(PurchaseOrderItem.amount).label('total_cost')
    ).join(Product).join(PurchaseOrder).filter(
        PurchaseOrder.organization_id == g.organization_id,
        PurchaseOrder.order_date >= from_date,
        PurchaseOrder.order_date <= to_date,
        PurchaseOrder.status != 'cancelled'
    ).group_by(PurchaseOrderItem.product_id, Product.name, Product.sku).order_by(
        func.sum(PurchaseOrderItem.amount).desc()
    ).limit(50).all()

    return success_response({
        'period': {'from': str(from_date), 'to': str(to_date)},
        'data': [{
            'product_id': r.product_id,
            'product_name': r.product_name,
            'sku': r.sku,
            'quantity_purchased': float(r.quantity_purchased or 0),
            'total_cost': float(r.total_cost or 0)
        } for r in results]
    })


# GST Reports
@report_bp.route('/gst/gstr1', methods=['GET'])
@jwt_required_with_user()
@permission_required('reports.tax')
def gstr1_report():
    """Get GSTR-1 report (Outward supplies)"""
    from_date, to_date = parse_date_range()

    invoices = Invoice.query.filter(
        Invoice.organization_id == g.organization_id,
        Invoice.invoice_date >= from_date,
        Invoice.invoice_date <= to_date,
        Invoice.status != 'void'
    ).order_by(Invoice.invoice_date).all()

    # B2B - Invoices to registered businesses
    b2b = []
    # B2C Large - B2C invoices > 2.5 lakh for inter-state
    b2c_large = []
    # B2C Small - Other B2C invoices
    b2c_small = []

    for inv in invoices:
        inv_data = {
            'invoice_number': inv.invoice_number,
            'invoice_date': inv.invoice_date.isoformat() if inv.invoice_date else None,
            'customer_name': inv.customer_name,
            'customer_gstin': inv.customer_gstin,
            'place_of_supply': inv.place_of_supply or inv.billing_state,
            'taxable_value': float(inv.subtotal or 0),
            'cgst': float(inv.cgst_amount or 0),
            'sgst': float(inv.sgst_amount or 0),
            'igst': float(inv.igst_amount or 0),
            'cess': float(inv.cess_amount or 0),
            'total_tax': float(inv.total_tax or 0),
            'invoice_value': float(inv.grand_total or 0),
            'is_reverse_charge': inv.reverse_charge or False
        }

        if inv.customer_gstin:
            b2b.append(inv_data)
        elif float(inv.grand_total or 0) > 250000 and inv.igst_amount:
            b2c_large.append(inv_data)
        else:
            b2c_small.append(inv_data)

    # Summary by tax rate
    tax_summary = {}
    for inv in invoices:
        # Simplified - group by tax rate
        rate = '18%'  # Default
        if inv.igst_amount and float(inv.subtotal or 0) > 0:
            rate = f"{round(float(inv.igst_amount) / float(inv.subtotal) * 100)}%"
        elif inv.cgst_amount and float(inv.subtotal or 0) > 0:
            rate = f"{round(float(inv.cgst_amount) / float(inv.subtotal) * 200)}%"

        if rate not in tax_summary:
            tax_summary[rate] = {'taxable': 0, 'cgst': 0, 'sgst': 0, 'igst': 0, 'cess': 0}
        tax_summary[rate]['taxable'] += float(inv.subtotal or 0)
        tax_summary[rate]['cgst'] += float(inv.cgst_amount or 0)
        tax_summary[rate]['sgst'] += float(inv.sgst_amount or 0)
        tax_summary[rate]['igst'] += float(inv.igst_amount or 0)
        tax_summary[rate]['cess'] += float(inv.cess_amount or 0)

    return success_response({
        'period': {'from': str(from_date), 'to': str(to_date)},
        'summary': {
            'total_invoices': len(invoices),
            'total_taxable': sum(float(inv.subtotal or 0) for inv in invoices),
            'total_cgst': sum(float(inv.cgst_amount or 0) for inv in invoices),
            'total_sgst': sum(float(inv.sgst_amount or 0) for inv in invoices),
            'total_igst': sum(float(inv.igst_amount or 0) for inv in invoices),
            'total_cess': sum(float(inv.cess_amount or 0) for inv in invoices),
            'total_tax': sum(float(inv.total_tax or 0) for inv in invoices),
            'total_value': sum(float(inv.grand_total or 0) for inv in invoices)
        },
        'tax_summary': tax_summary,
        'b2b': b2b,
        'b2c_large': b2c_large,
        'b2c_small_count': len(b2c_small),
        'b2c_small_value': sum(d['invoice_value'] for d in b2c_small)
    })


@report_bp.route('/gst/gstr3b', methods=['GET'])
@jwt_required_with_user()
@permission_required('reports.tax')
def gstr3b_report():
    """Get GSTR-3B report (Summary return)"""
    from_date, to_date = parse_date_range()

    # Outward supplies (Sales)
    invoices = Invoice.query.filter(
        Invoice.organization_id == g.organization_id,
        Invoice.invoice_date >= from_date,
        Invoice.invoice_date <= to_date,
        Invoice.status != 'void'
    ).all()

    outward_taxable = sum(float(inv.subtotal or 0) for inv in invoices)
    outward_cgst = sum(float(inv.cgst_amount or 0) for inv in invoices)
    outward_sgst = sum(float(inv.sgst_amount or 0) for inv in invoices)
    outward_igst = sum(float(inv.igst_amount or 0) for inv in invoices)
    outward_cess = sum(float(inv.cess_amount or 0) for inv in invoices)

    # Inward supplies (Purchases) - for ITC calculation
    purchase_orders = PurchaseOrder.query.filter(
        PurchaseOrder.organization_id == g.organization_id,
        PurchaseOrder.order_date >= from_date,
        PurchaseOrder.order_date <= to_date,
        PurchaseOrder.status.in_(['confirmed', 'partially_received', 'received'])
    ).all()

    inward_taxable = sum(float(po.subtotal or 0) for po in purchase_orders)
    inward_cgst = sum(float(po.cgst_amount or 0) for po in purchase_orders)
    inward_sgst = sum(float(po.sgst_amount or 0) for po in purchase_orders)
    inward_igst = sum(float(po.igst_amount or 0) for po in purchase_orders)
    inward_cess = sum(float(po.cess_amount or 0) for po in purchase_orders)

    # Net tax payable
    net_cgst = outward_cgst - inward_cgst
    net_sgst = outward_sgst - inward_sgst
    net_igst = outward_igst - inward_igst
    net_cess = outward_cess - inward_cess

    return success_response({
        'period': {'from': str(from_date), 'to': str(to_date)},
        'outward_supplies': {
            'taxable_value': float(outward_taxable),
            'cgst': float(outward_cgst),
            'sgst': float(outward_sgst),
            'igst': float(outward_igst),
            'cess': float(outward_cess),
            'total_tax': float(outward_cgst + outward_sgst + outward_igst + outward_cess)
        },
        'inward_supplies_itc': {
            'taxable_value': float(inward_taxable),
            'cgst': float(inward_cgst),
            'sgst': float(inward_sgst),
            'igst': float(inward_igst),
            'cess': float(inward_cess),
            'total_itc': float(inward_cgst + inward_sgst + inward_igst + inward_cess)
        },
        'net_tax_payable': {
            'cgst': float(max(0, net_cgst)),
            'sgst': float(max(0, net_sgst)),
            'igst': float(max(0, net_igst)),
            'cess': float(max(0, net_cess)),
            'total': float(max(0, net_cgst) + max(0, net_sgst) + max(0, net_igst) + max(0, net_cess))
        },
        'itc_available': {
            'cgst': float(max(0, -net_cgst)),
            'sgst': float(max(0, -net_sgst)),
            'igst': float(max(0, -net_igst)),
            'cess': float(max(0, -net_cess))
        }
    })


@report_bp.route('/sales/trend', methods=['GET'])
@jwt_required_with_user()
@permission_required('reports.sales')
def sales_trend():
    """Get daily/monthly sales trend"""
    from_date, to_date = parse_date_range()
    group_by = request.args.get('group_by', 'day')  # day, week, month

    invoices = Invoice.query.filter(
        Invoice.organization_id == g.organization_id,
        Invoice.invoice_date >= from_date,
        Invoice.invoice_date <= to_date,
        Invoice.status != 'void'
    ).all()

    trend = {}
    for inv in invoices:
        if not inv.invoice_date:
            continue

        if group_by == 'month':
            key = inv.invoice_date.strftime('%Y-%m')
        elif group_by == 'week':
            key = inv.invoice_date.strftime('%Y-W%W')
        else:
            key = inv.invoice_date.strftime('%Y-%m-%d')

        if key not in trend:
            trend[key] = {'date': key, 'sales': 0, 'count': 0, 'tax': 0}
        trend[key]['sales'] += float(inv.grand_total or 0)
        trend[key]['count'] += 1
        trend[key]['tax'] += float(inv.total_tax or 0)

    data = sorted(trend.values(), key=lambda x: x['date'])

    return success_response({
        'period': {'from': str(from_date), 'to': str(to_date)},
        'group_by': group_by,
        'data': data
    })


@report_bp.route('/purchase/trend', methods=['GET'])
@jwt_required_with_user()
@permission_required('reports.purchase')
def purchase_trend():
    """Get daily/monthly purchase trend"""
    from_date, to_date = parse_date_range()
    group_by = request.args.get('group_by', 'day')

    orders = PurchaseOrder.query.filter(
        PurchaseOrder.organization_id == g.organization_id,
        PurchaseOrder.order_date >= from_date,
        PurchaseOrder.order_date <= to_date,
        PurchaseOrder.status != 'cancelled'
    ).all()

    trend = {}
    for po in orders:
        if not po.order_date:
            continue

        if group_by == 'month':
            key = po.order_date.strftime('%Y-%m')
        elif group_by == 'week':
            key = po.order_date.strftime('%Y-W%W')
        else:
            key = po.order_date.strftime('%Y-%m-%d')

        if key not in trend:
            trend[key] = {'date': key, 'purchases': 0, 'count': 0, 'tax': 0}
        trend[key]['purchases'] += float(po.grand_total or 0)
        trend[key]['count'] += 1
        trend[key]['tax'] += float(po.total_tax or 0)

    data = sorted(trend.values(), key=lambda x: x['date'])

    return success_response({
        'period': {'from': str(from_date), 'to': str(to_date)},
        'group_by': group_by,
        'data': data
    })