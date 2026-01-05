"""Order routes for VyaparaCore - Sales Orders and Purchase Orders"""
from flask import Blueprint, g, request
from datetime import datetime
from decimal import Decimal
from config.database import db
from app.models import (
    SalesOrder, SalesOrderItem, PurchaseOrder, PurchaseOrderItem,
    Customer, Supplier, Product, Organization, Stock, StockTransaction
)
from app.utils.security import (
    jwt_required_with_user, permission_required, sanitize_string, create_audit_log
)
from app.utils.helpers import (
    success_response, error_response, get_request_json,
    paginate, get_filters, apply_filters, model_to_dict
)
from app.services.activity_logger import log_activity, log_audit, ActivityType, EntityType

order_bp = Blueprint('order', __name__)


# ============ SALES ORDERS ============

@order_bp.route('/sales', methods=['GET'])
@jwt_required_with_user()
@permission_required('sales_orders.view')
def list_sales_orders():
    """List all sales orders"""
    query = SalesOrder.query.filter_by(organization_id=g.organization_id)
    
    filters = get_filters()
    if filters.get('search'):
        search = f"%{filters['search']}%"
        query = query.filter(
            db.or_(
                SalesOrder.order_number.ilike(search),
                SalesOrder.customer_name.ilike(search)
            )
        )
    
    if request.args.get('customer_id'):
        query = query.filter_by(customer_id=request.args.get('customer_id', type=int))
    
    query = apply_filters(query, SalesOrder, filters)
    
    def serialize(o):
        data = model_to_dict(o)
        data['customer_name'] = o.customer.name if o.customer else o.customer_name
        data['total_amount'] = float(o.grand_total or 0)
        data['items_count'] = o.items.count() if o.items else 0
        # Include invoice info if exists
        invoice = o.invoices.first()
        if invoice:
            data['invoice'] = {
                'id': invoice.id,
                'invoice_number': invoice.invoice_number,
                'status': invoice.status
            }
        else:
            data['invoice'] = None
        return data
    
    return success_response(paginate(query, serialize))


@order_bp.route('/sales', methods=['POST'])
@jwt_required_with_user()
@permission_required('sales_orders.create')
def create_sales_order():
    """Create sales order"""
    data = get_request_json()
    
    if not data.get('customer_id') or not data.get('items'):
        return error_response('Customer and items required')
    
    customer = Customer.query.filter_by(id=data['customer_id'], organization_id=g.organization_id).first()
    if not customer:
        return error_response('Customer not found', status_code=404)
    
    org = Organization.query.get(g.organization_id)
    
    # Generate order number
    count = SalesOrder.query.filter_by(organization_id=g.organization_id).count() + 1
    order_number = f"SO{datetime.utcnow().strftime('%y%m')}{count:05d}"
    
    is_interstate = (data.get('place_of_supply') or customer.billing_state_code) != org.state_code
    
    order = SalesOrder(
        organization_id=g.organization_id,
        branch_id=data.get('branch_id') or g.branch_id,
        order_number=order_number,
        customer_id=data['customer_id'],
        customer_name=customer.name,
        customer_gstin=customer.gstin,
        billing_address_line1=data.get('billing_address_line1') or customer.billing_address_line1,
        billing_address_line2=data.get('billing_address_line2') or customer.billing_address_line2,
        billing_city=data.get('billing_city') or customer.billing_city,
        billing_state=data.get('billing_state') or customer.billing_state,
        billing_state_code=data.get('billing_state_code') or customer.billing_state_code,
        billing_pincode=data.get('billing_pincode') or customer.billing_pincode,
        shipping_address_line1=data.get('shipping_address_line1') or customer.shipping_address_line1,
        shipping_address_line2=data.get('shipping_address_line2') or customer.shipping_address_line2,
        shipping_city=data.get('shipping_city') or customer.shipping_city,
        shipping_state=data.get('shipping_state') or customer.shipping_state,
        shipping_state_code=data.get('shipping_state_code') or customer.shipping_state_code,
        shipping_pincode=data.get('shipping_pincode') or customer.shipping_pincode,
        order_date=data.get('order_date', datetime.utcnow().date()),
        expected_delivery_date=data.get('expected_delivery_date'),
        place_of_supply=data.get('place_of_supply') or customer.billing_state_code or org.state_code,
        currency=data.get('currency', 'INR'),
        payment_terms=data.get('payment_terms', customer.payment_terms),
        advance_amount=data.get('advance_amount', 0),
        delivery_method=data.get('shipping_method') or data.get('delivery_method'),
        notes=sanitize_string(data.get('notes', '')),
        status='draft',
        created_by=g.current_user.id
    )
    
    db.session.add(order)
    db.session.flush()
    
    # Calculate totals
    subtotal = Decimal('0')
    total_cgst = Decimal('0')
    total_sgst = Decimal('0')
    total_igst = Decimal('0')
    total_cess = Decimal('0')
    total_discount = Decimal('0')
    
    for idx, item_data in enumerate(data['items']):
        product = Product.query.filter_by(id=item_data['product_id'], organization_id=g.organization_id).first()
        if not product:
            continue
        
        qty = Decimal(str(item_data.get('quantity', 1)))
        unit_price = Decimal(str(item_data.get('unit_price', product.selling_price or 0)))
        discount_pct = Decimal(str(item_data.get('discount_percent', 0)))
        
        item_subtotal = qty * unit_price
        item_discount = item_subtotal * discount_pct / 100
        taxable = item_subtotal - item_discount
        
        cgst = sgst = igst = cess = Decimal('0')
        if product.tax_rate:
            if is_interstate:
                igst = taxable * Decimal(str(product.tax_rate.igst_rate)) / 100
            else:
                cgst = taxable * Decimal(str(product.tax_rate.cgst_rate)) / 100
                sgst = taxable * Decimal(str(product.tax_rate.sgst_rate)) / 100
            cess = taxable * Decimal(str(product.tax_rate.cess_rate or 0)) / 100
        
        total = taxable + cgst + sgst + igst + cess
        
        item = SalesOrderItem(
            order_id=order.id,
            product_id=product.id,
            variant_id=item_data.get('variant_id'),
            name=product.name,
            description=sanitize_string(item_data.get('description', '')),
            hsn_code=product.hsn_code,
            quantity=float(qty),
            unit_id=item_data.get('unit_id') or product.unit_id,
            rate=float(unit_price),
            discount_type='percentage',
            discount_value=float(discount_pct),
            discount_amount=float(item_discount),
            taxable_amount=float(taxable),
            tax_rate_id=product.tax_rate_id,
            tax_rate=product.tax_rate.rate if product.tax_rate else 0,
            cgst_rate=product.tax_rate.cgst_rate if product.tax_rate and not is_interstate else 0,
            cgst_amount=float(cgst),
            sgst_rate=product.tax_rate.sgst_rate if product.tax_rate and not is_interstate else 0,
            sgst_amount=float(sgst),
            igst_rate=product.tax_rate.igst_rate if product.tax_rate and is_interstate else 0,
            igst_amount=float(igst),
            cess_rate=product.tax_rate.cess_rate if product.tax_rate else 0,
            cess_amount=float(cess),
            total_tax=float(cgst + sgst + igst + cess),
            amount=float(total)
        )
        db.session.add(item)
        
        subtotal += taxable
        total_discount += item_discount
        total_cgst += cgst
        total_sgst += sgst
        total_igst += igst
        total_cess += cess
    
    shipping = Decimal(str(data.get('shipping_charges', 0)))
    packaging = Decimal(str(data.get('packaging_charges', 0)))
    other = Decimal(str(data.get('other_charges', 0)))
    
    total_tax = total_cgst + total_sgst + total_igst + total_cess
    total_amount = subtotal + total_tax + shipping + packaging + other
    round_off = round(total_amount) - total_amount
    
    order.subtotal = float(subtotal)
    order.discount_amount = float(total_discount)
    order.taxable_amount = float(subtotal - total_discount)
    order.cgst_amount = float(total_cgst)
    order.sgst_amount = float(total_sgst)
    order.igst_amount = float(total_igst)
    order.cess_amount = float(total_cess)
    order.total_tax = float(total_tax)
    order.shipping_charges = float(shipping)
    order.packaging_charges = float(packaging)
    order.other_charges = float(other)
    order.round_off = float(round_off)
    order.grand_total = float(round(total_amount))
    
    db.session.commit()
    
    create_audit_log('sales_orders', order.id, 'create', None, model_to_dict(order))
    log_activity(
        activity_type=ActivityType.CREATE,
        entity_type=EntityType.SALES_ORDER,
        entity_id=order.id,
        description=f"Created sales order {order.order_number} for {customer.name}"
    )

    return success_response(model_to_dict(order), 'Sales order created', 201)


@order_bp.route('/sales/<int:id>', methods=['GET'])
@jwt_required_with_user()
@permission_required('sales_orders.view')
def get_sales_order(id):
    """Get sales order details"""
    order = SalesOrder.query.filter_by(id=id, organization_id=g.organization_id).first()
    if not order:
        return error_response('Sales order not found', status_code=404)
    
    data = model_to_dict(order)
    data['customer'] = model_to_dict(order.customer) if order.customer else None
    data['items'] = []

    for item in order.items:
        item_data = model_to_dict(item)
        item_data['product'] = {
            'id': item.product.id,
            'name': item.product.name,
            'sku': item.product.sku
        } if item.product else None
        data['items'].append(item_data)

    # Include invoice information if exists
    invoice = order.invoices.first()
    if invoice:
        data['invoice'] = {
            'id': invoice.id,
            'invoice_number': invoice.invoice_number,
            'status': invoice.status,
            'payment_status': invoice.payment_status,
            'total_amount': float(invoice.total_amount or 0)
        }
    else:
        data['invoice'] = None

    return success_response(data)


@order_bp.route('/sales/<int:id>', methods=['PUT'])
@jwt_required_with_user()
@permission_required('sales_orders.edit')
def update_sales_order(id):
    """Update sales order"""
    order = SalesOrder.query.filter_by(id=id, organization_id=g.organization_id).first()
    if not order:
        return error_response('Sales order not found', status_code=404)
    
    if order.status not in ['draft', 'confirmed']:
        return error_response('Cannot edit order in current status')
    
    data = get_request_json()

    updateable = ['expected_delivery_date', 'payment_terms', 'advance_amount', 'notes',
                  'delivery_method', 'shipping_address_line1', 'shipping_address_line2',
                  'shipping_city', 'shipping_state', 'shipping_state_code', 'shipping_pincode']

    # Handle shipping_method from frontend mapping to delivery_method
    if 'shipping_method' in data:
        order.delivery_method = data['shipping_method']

    for field in updateable:
        if field in data:
            setattr(order, field, data[field])
    
    order.updated_at = datetime.utcnow()
    order.updated_by = g.current_user.id
    db.session.commit()
    log_activity(
        activity_type=ActivityType.UPDATE,
        entity_type=EntityType.SALES_ORDER,
        entity_id=order.id,
        description=f"Updated sales order {order.order_number}"
    )

    return success_response(model_to_dict(order), 'Sales order updated')


@order_bp.route('/sales/<int:id>/confirm', methods=['POST'])
@jwt_required_with_user()
@permission_required('sales_orders.approve')
def confirm_sales_order(id):
    """Confirm sales order and reserve stock"""
    order = SalesOrder.query.filter_by(id=id, organization_id=g.organization_id).first()
    if not order:
        return error_response('Sales order not found', status_code=404)

    if order.status != 'draft':
        return error_response('Only draft orders can be confirmed')

    # Check and reserve stock if warehouse is specified
    if order.warehouse_id:
        insufficient_items = []
        items_to_reserve = []

        for item in order.items:
            if not item.product_id:
                continue

            product = Product.query.get(item.product_id)
            if not product or not product.track_inventory:
                continue

            # Find stock record
            stock = Stock.query.filter_by(
                product_id=item.product_id,
                variant_id=item.variant_id,
                warehouse_id=order.warehouse_id
            ).first()

            qty_needed = float(item.quantity or 0)
            available = 0

            if stock:
                available = float(stock.quantity or 0) - float(stock.reserved_quantity or 0)

            if available < qty_needed:
                insufficient_items.append({
                    'product': item.name,
                    'required': qty_needed,
                    'available': available
                })
            else:
                items_to_reserve.append({
                    'item': item,
                    'product': product,
                    'stock': stock,
                    'quantity': qty_needed
                })

        # If any items have insufficient stock, return error
        if insufficient_items:
            return error_response(
                'Insufficient stock for some items',
                errors={'insufficient_items': insufficient_items},
                status_code=400
            )

        # Reserve stock for all items
        txn_count = StockTransaction.query.filter_by(
            organization_id=g.organization_id
        ).count()

        for idx, reserve_item in enumerate(items_to_reserve):
            stock = reserve_item['stock']
            qty = reserve_item['quantity']
            item = reserve_item['item']

            # Update reserved quantity
            balance_before = float(stock.reserved_quantity or 0)
            stock.reserved_quantity = balance_before + qty
            stock.available_quantity = float(stock.quantity or 0) - stock.reserved_quantity

            # Create reservation transaction
            txn = StockTransaction(
                organization_id=g.organization_id,
                transaction_number=f"RES{datetime.utcnow().strftime('%y%m')}{txn_count + idx + 1:05d}",
                product_id=item.product_id,
                variant_id=item.variant_id,
                warehouse_id=order.warehouse_id,
                transaction_type='reservation',
                quantity=qty,
                direction='reserve',
                balance_before=balance_before,
                balance_after=stock.reserved_quantity,
                reference_type='sales_order',
                reference_id=order.id,
                reference_number=order.order_number,
                transaction_date=datetime.utcnow(),
                created_by=g.current_user.id,
                notes=f"Reserved for Sales Order {order.order_number}"
            )
            db.session.add(txn)

    order.status = 'confirmed'
    order.confirmed_at = datetime.utcnow()
    order.updated_at = datetime.utcnow()
    db.session.commit()

    log_activity(
        activity_type=ActivityType.STATUS_CHANGE,
        entity_type=EntityType.SALES_ORDER,
        entity_id=order.id,
        description=f"Confirmed sales order {order.order_number}"
    )

    return success_response(model_to_dict(order), 'Sales order confirmed and stock reserved')


@order_bp.route('/sales/<int:id>/cancel', methods=['POST'])
@jwt_required_with_user()
@permission_required('sales_orders.cancel')
def cancel_sales_order(id):
    """Cancel sales order and release reserved stock"""
    order = SalesOrder.query.filter_by(id=id, organization_id=g.organization_id).first()
    if not order:
        return error_response('Sales order not found', status_code=404)

    if order.status in ['delivered', 'cancelled']:
        return error_response('Cannot cancel order in current status')

    data = get_request_json()

    # Release reserved stock if order was confirmed and has warehouse
    if order.status == 'confirmed' and order.warehouse_id:
        txn_count = StockTransaction.query.filter_by(
            organization_id=g.organization_id
        ).count()

        for idx, item in enumerate(order.items):
            if not item.product_id:
                continue

            product = Product.query.get(item.product_id)
            if not product or not product.track_inventory:
                continue

            stock = Stock.query.filter_by(
                product_id=item.product_id,
                variant_id=item.variant_id,
                warehouse_id=order.warehouse_id
            ).first()

            if stock and float(stock.reserved_quantity or 0) > 0:
                qty_to_release = min(float(item.quantity or 0), float(stock.reserved_quantity or 0))
                balance_before = float(stock.reserved_quantity or 0)

                stock.reserved_quantity = max(0, balance_before - qty_to_release)
                stock.available_quantity = float(stock.quantity or 0) - float(stock.reserved_quantity or 0)

                # Create release transaction
                txn = StockTransaction(
                    organization_id=g.organization_id,
                    transaction_number=f"REL{datetime.utcnow().strftime('%y%m')}{txn_count + idx + 1:05d}",
                    product_id=item.product_id,
                    variant_id=item.variant_id,
                    warehouse_id=order.warehouse_id,
                    transaction_type='reservation_release',
                    quantity=qty_to_release,
                    direction='release',
                    balance_before=balance_before,
                    balance_after=stock.reserved_quantity,
                    reference_type='sales_order',
                    reference_id=order.id,
                    reference_number=order.order_number,
                    transaction_date=datetime.utcnow(),
                    created_by=g.current_user.id,
                    notes=f"Released reservation for cancelled Sales Order {order.order_number}"
                )
                db.session.add(txn)

    order.status = 'cancelled'
    order.cancellation_reason = sanitize_string(data.get('reason', ''))
    order.cancelled_at = datetime.utcnow()
    order.updated_at = datetime.utcnow()
    db.session.commit()

    log_activity(
        activity_type=ActivityType.STATUS_CHANGE,
        entity_type=EntityType.SALES_ORDER,
        entity_id=order.id,
        description=f"Cancelled sales order {order.order_number}"
    )

    return success_response(model_to_dict(order), 'Sales order cancelled and stock released')


@order_bp.route('/sales/<int:id>/ship', methods=['POST'])
@jwt_required_with_user()
@permission_required('sales_orders.edit')
def ship_sales_order(id):
    """Mark sales order as shipped"""
    order = SalesOrder.query.filter_by(id=id, organization_id=g.organization_id).first()
    if not order:
        return error_response('Sales order not found', status_code=404)

    if order.status not in ['confirmed', 'processing']:
        return error_response('Only confirmed or processing orders can be marked as shipped')

    order.status = 'shipped'
    order.shipped_at = datetime.utcnow()
    order.updated_at = datetime.utcnow()
    db.session.commit()

    log_activity(
        activity_type=ActivityType.STATUS_CHANGE,
        entity_type=EntityType.SALES_ORDER,
        entity_id=order.id,
        description=f"Marked sales order {order.order_number} as shipped"
    )

    return success_response(model_to_dict(order), 'Sales order marked as shipped')


@order_bp.route('/sales/<int:id>/invoice', methods=['POST'])
@jwt_required_with_user()
@permission_required('invoices.create')
def convert_sales_order_to_invoice(id):
    """Convert sales order to invoice"""
    from app.models import Invoice, InvoiceItem

    order = SalesOrder.query.filter_by(id=id, organization_id=g.organization_id).first()
    if not order:
        return error_response('Sales order not found', status_code=404)

    if order.status not in ['confirmed', 'processing', 'shipped']:
        return error_response('Only confirmed, processing or shipped orders can be converted to invoice')

    # Check if already converted
    existing_invoice = Invoice.query.filter_by(sales_order_id=order.id).first()
    if existing_invoice:
        return error_response('Sales order already converted to invoice', status_code=400)

    # Generate invoice number
    count = Invoice.query.filter_by(organization_id=g.organization_id).count() + 1
    invoice_number = f"INV{datetime.utcnow().strftime('%y%m')}{count:05d}"

    # Calculate due date based on payment terms
    from datetime import timedelta
    due_date = None
    if order.payment_terms:
        due_date = datetime.utcnow().date() + timedelta(days=int(order.payment_terms))

    # Create invoice
    invoice = Invoice(
        organization_id=g.organization_id,
        branch_id=order.branch_id,
        invoice_number=invoice_number,
        invoice_date=datetime.utcnow().date(),
        due_date=due_date,
        reference_number=order.order_number,
        invoice_type='tax_invoice',
        source_type='sales_order',
        sales_order_id=order.id,
        customer_id=order.customer_id,
        customer_name=order.customer_name,
        customer_gstin=order.customer_gstin,
        billing_address_line1=order.billing_address_line1,
        billing_address_line2=order.billing_address_line2,
        billing_city=order.billing_city,
        billing_state=order.billing_state,
        billing_state_code=order.billing_state_code,
        billing_pincode=order.billing_pincode,
        shipping_address_line1=order.shipping_address_line1,
        shipping_address_line2=order.shipping_address_line2,
        shipping_city=order.shipping_city,
        shipping_state=order.shipping_state,
        shipping_state_code=order.shipping_state_code,
        shipping_pincode=order.shipping_pincode,
        place_of_supply=order.place_of_supply,
        is_igst=order.is_igst if hasattr(order, 'is_igst') else False,
        subtotal=order.subtotal,
        discount_amount=order.discount_amount,
        taxable_amount=order.taxable_amount,
        cgst_amount=order.cgst_amount,
        sgst_amount=order.sgst_amount,
        igst_amount=order.igst_amount,
        cess_amount=order.cess_amount,
        total_tax=order.total_tax,
        shipping_charges=order.shipping_charges,
        packaging_charges=order.packaging_charges,
        other_charges=order.other_charges if hasattr(order, 'other_charges') else 0,
        round_off=order.round_off,
        grand_total=order.grand_total,
        balance_due=order.grand_total,
        currency=order.currency,
        status='draft',
        payment_status='unpaid',
        notes=order.notes,
        created_by=g.current_user.id
    )

    db.session.add(invoice)
    db.session.flush()

    # Copy items
    for order_item in order.items:
        invoice_item = InvoiceItem(
            invoice_id=invoice.id,
            line_number=order_item.line_number if hasattr(order_item, 'line_number') else 1,
            product_id=order_item.product_id,
            variant_id=order_item.variant_id,
            item_type=order_item.item_type if hasattr(order_item, 'item_type') else 'product',
            sku=order_item.sku if hasattr(order_item, 'sku') else None,
            hsn_code=order_item.hsn_code,
            name=order_item.name,
            description=order_item.description,
            quantity=order_item.quantity,
            unit_id=order_item.unit_id,
            unit_name=order_item.unit_name if hasattr(order_item, 'unit_name') else None,
            rate=order_item.rate,
            mrp=order_item.mrp if hasattr(order_item, 'mrp') else None,
            discount_type=order_item.discount_type,
            discount_value=order_item.discount_value,
            discount_amount=order_item.discount_amount,
            tax_rate_id=order_item.tax_rate_id,
            tax_rate=order_item.tax_rate,
            cgst_rate=order_item.cgst_rate,
            sgst_rate=order_item.sgst_rate,
            igst_rate=order_item.igst_rate,
            cess_rate=order_item.cess_rate,
            taxable_amount=order_item.taxable_amount,
            cgst_amount=order_item.cgst_amount,
            sgst_amount=order_item.sgst_amount,
            igst_amount=order_item.igst_amount,
            cess_amount=order_item.cess_amount,
            total_tax=order_item.total_tax,
            amount=order_item.amount,
            sales_order_item_id=order_item.id
        )
        db.session.add(invoice_item)

    # Deduct stock from reserved quantity (reserved when SO was confirmed)
    if order.warehouse_id:
        txn_count = StockTransaction.query.filter_by(
            organization_id=g.organization_id
        ).count()

        for idx, order_item in enumerate(order.items):
            if not order_item.product_id:
                continue

            product = Product.query.get(order_item.product_id)
            if not product or not product.track_inventory:
                continue

            stock = Stock.query.filter_by(
                product_id=order_item.product_id,
                variant_id=order_item.variant_id,
                warehouse_id=order.warehouse_id
            ).first()

            if stock:
                qty = float(order_item.quantity or 0)

                # Release from reserved and deduct from actual stock
                reserved_before = float(stock.reserved_quantity or 0)
                qty_before = float(stock.quantity or 0)

                # Release reservation
                release_qty = min(qty, reserved_before)
                stock.reserved_quantity = max(0, reserved_before - release_qty)

                # Deduct from actual stock
                stock.quantity = max(0, qty_before - qty)
                stock.available_quantity = float(stock.quantity) - float(stock.reserved_quantity)

                # Create sale transaction
                txn = StockTransaction(
                    organization_id=g.organization_id,
                    transaction_number=f"SALE{datetime.utcnow().strftime('%y%m')}{txn_count + idx + 1:05d}",
                    product_id=order_item.product_id,
                    variant_id=order_item.variant_id,
                    warehouse_id=order.warehouse_id,
                    transaction_type='sale',
                    quantity=qty,
                    direction='out',
                    balance_before=qty_before,
                    balance_after=float(stock.quantity),
                    unit_cost=float(order_item.rate or 0),
                    reference_type='invoice',
                    reference_id=invoice.id,
                    reference_number=invoice.invoice_number,
                    transaction_date=datetime.utcnow(),
                    created_by=g.current_user.id,
                    notes=f"Sale via Invoice {invoice.invoice_number} from SO {order.order_number}"
                )
                db.session.add(txn)

                # Update product denormalized stock
                total_stock = db.session.query(db.func.sum(Stock.quantity)).filter_by(
                    product_id=order_item.product_id
                ).scalar() or 0
                product.current_stock = float(total_stock)

    # Update sales order status
    order.status = 'processing'
    order.updated_at = datetime.utcnow()

    db.session.commit()

    create_audit_log('invoices', invoice.id, 'create', None, {'source': 'sales_order', 'sales_order_id': order.id})
    log_activity(
        activity_type=ActivityType.CREATE,
        entity_type=EntityType.INVOICE,
        entity_id=invoice.id,
        description=f"Created invoice {invoice.invoice_number} from sales order {order.order_number}"
    )

    return success_response({'invoice_id': invoice.id, 'invoice_number': invoice.invoice_number}, 'Invoice created from sales order', 201)


# ============ PURCHASE ORDERS ============

@order_bp.route('/purchase', methods=['GET'])
@jwt_required_with_user()
@permission_required('purchase_orders.view')
def list_purchase_orders():
    """List all purchase orders"""
    org_id = g.organization_id
    base_query = PurchaseOrder.query.filter_by(organization_id=org_id)

    # Calculate stats
    total_orders = base_query.count()
    total_amount = db.session.query(db.func.coalesce(db.func.sum(PurchaseOrder.grand_total), 0)).filter(
        PurchaseOrder.organization_id == org_id
    ).scalar()
    pending_count = base_query.filter(PurchaseOrder.status.in_(['draft', 'approved'])).count()
    received_count = base_query.filter(PurchaseOrder.status == 'received').count()
    partial_count = base_query.filter(PurchaseOrder.status == 'partial').count()

    stats = {
        'total_orders': total_orders,
        'total_amount': float(total_amount or 0),
        'pending_count': pending_count,
        'received_count': received_count,
        'partial_count': partial_count
    }

    query = PurchaseOrder.query.filter_by(organization_id=org_id)

    filters = get_filters()
    if filters.get('search'):
        search = f"%{filters['search']}%"
        query = query.filter(
            db.or_(
                PurchaseOrder.order_number.ilike(search),
                PurchaseOrder.supplier_name.ilike(search)
            )
        )

    if request.args.get('supplier_id'):
        query = query.filter_by(supplier_id=request.args.get('supplier_id', type=int))

    query = apply_filters(query, PurchaseOrder, filters)

    def serialize(o):
        from app.models import DebitNote
        data = model_to_dict(o)
        data['supplier_name'] = o.supplier.name if o.supplier else o.supplier_name
        data['total_amount'] = float(o.grand_total or 0)
        data['items_count'] = o.items.count() if o.items else 0
        data['po_number'] = o.order_number
        data['po_date'] = o.order_date.isoformat() if o.order_date else None
        data['expected_date'] = o.expected_delivery_date.isoformat() if o.expected_delivery_date else None

        # Calculate debit notes applied
        debit_notes = DebitNote.query.filter_by(
            purchase_order_id=o.id,
            organization_id=o.organization_id
        ).all()
        total_debit_applied = sum(float(dn.adjusted_amount or 0) for dn in debit_notes)
        data['debit_applied'] = total_debit_applied
        data['net_payable'] = float(o.grand_total or 0) - total_debit_applied
        data['has_debit_notes'] = len(debit_notes) > 0

        return data

    result = paginate(query, serialize)
    result['stats'] = stats

    return success_response(result)


@order_bp.route('/purchase', methods=['POST'])
@jwt_required_with_user()
@permission_required('purchase_orders.create')
def create_purchase_order():
    """Create purchase order"""
    data = get_request_json()
    
    if not data.get('supplier_id') or not data.get('items'):
        return error_response('Supplier and items required')
    
    supplier = Supplier.query.filter_by(id=data['supplier_id'], organization_id=g.organization_id).first()
    if not supplier:
        return error_response('Supplier not found', status_code=404)
    
    org = Organization.query.get(g.organization_id)
    
    # Generate order number
    count = PurchaseOrder.query.filter_by(organization_id=g.organization_id).count() + 1
    order_number = f"PO{datetime.utcnow().strftime('%y%m')}{count:05d}"
    
    is_interstate = (supplier.state_code or '') != org.state_code
    
    order = PurchaseOrder(
        organization_id=g.organization_id,
        branch_id=data.get('branch_id') or g.branch_id,
        order_number=order_number,
        supplier_id=data['supplier_id'],
        supplier_name=supplier.name,
        supplier_gstin=supplier.gstin,
        supplier_address_line1=data.get('supplier_address_line1') or supplier.address_line1,
        supplier_address_line2=data.get('supplier_address_line2') or supplier.address_line2,
        supplier_city=data.get('supplier_city') or supplier.city,
        supplier_state=data.get('supplier_state') or supplier.state,
        supplier_state_code=data.get('supplier_state_code') or supplier.state_code,
        supplier_pincode=data.get('supplier_pincode') or supplier.pincode,
        delivery_address_line1=data.get('delivery_address_line1') or org.address_line1,
        delivery_address_line2=data.get('delivery_address_line2'),
        delivery_city=data.get('delivery_city') or org.city,
        delivery_state=data.get('delivery_state') or org.state,
        delivery_pincode=data.get('delivery_pincode') or org.pincode,
        order_date=data.get('order_date', datetime.utcnow().date()),
        expected_delivery_date=data.get('expected_delivery_date'),
        place_of_supply=data.get('place_of_supply') or org.state_code,
        currency=data.get('currency', 'INR'),
        payment_terms=data.get('payment_terms', supplier.payment_terms),
        notes=sanitize_string(data.get('notes', '')),
        status='draft',
        created_by=g.current_user.id
    )
    
    db.session.add(order)
    db.session.flush()
    
    # Calculate totals
    subtotal = Decimal('0')
    total_cgst = Decimal('0')
    total_sgst = Decimal('0')
    total_igst = Decimal('0')
    total_cess = Decimal('0')
    total_discount = Decimal('0')
    
    for idx, item_data in enumerate(data['items']):
        product = Product.query.filter_by(id=item_data['product_id'], organization_id=g.organization_id).first()
        if not product:
            continue
        
        qty = Decimal(str(item_data.get('quantity', 1)))
        unit_price = Decimal(str(item_data.get('unit_price', product.purchase_price or 0)))
        discount_pct = Decimal(str(item_data.get('discount_percent', 0)))
        
        item_subtotal = qty * unit_price
        item_discount = item_subtotal * discount_pct / 100
        taxable = item_subtotal - item_discount
        
        cgst = sgst = igst = cess = Decimal('0')
        if product.tax_rate:
            if is_interstate:
                igst = taxable * Decimal(str(product.tax_rate.igst_rate)) / 100
            else:
                cgst = taxable * Decimal(str(product.tax_rate.cgst_rate)) / 100
                sgst = taxable * Decimal(str(product.tax_rate.sgst_rate)) / 100
            cess = taxable * Decimal(str(product.tax_rate.cess_rate or 0)) / 100
        
        total = taxable + cgst + sgst + igst + cess
        
        item = PurchaseOrderItem(
            order_id=order.id,
            product_id=product.id,
            variant_id=item_data.get('variant_id'),
            name=product.name,
            description=sanitize_string(item_data.get('description', '')),
            hsn_code=product.hsn_code,
            quantity=float(qty),
            unit_id=item_data.get('unit_id') or product.unit_id,
            rate=float(unit_price),
            discount_type='percentage',
            discount_value=float(discount_pct),
            discount_amount=float(item_discount),
            taxable_amount=float(taxable),
            tax_rate_id=product.tax_rate_id,
            tax_rate=product.tax_rate.rate if product.tax_rate else 0,
            cgst_rate=product.tax_rate.cgst_rate if product.tax_rate and not is_interstate else 0,
            cgst_amount=float(cgst),
            sgst_rate=product.tax_rate.sgst_rate if product.tax_rate and not is_interstate else 0,
            sgst_amount=float(sgst),
            igst_rate=product.tax_rate.igst_rate if product.tax_rate and is_interstate else 0,
            igst_amount=float(igst),
            cess_rate=product.tax_rate.cess_rate if product.tax_rate else 0,
            cess_amount=float(cess),
            total_tax=float(cgst + sgst + igst + cess),
            amount=float(total)
        )
        db.session.add(item)
        
        subtotal += taxable
        total_discount += item_discount
        total_cgst += cgst
        total_sgst += sgst
        total_igst += igst
        total_cess += cess
    
    shipping = Decimal(str(data.get('shipping_charges', 0)))
    other = Decimal(str(data.get('other_charges', 0)))
    
    total_tax = total_cgst + total_sgst + total_igst + total_cess
    total_amount = subtotal + total_tax + shipping + other
    round_off = round(total_amount) - total_amount
    
    order.subtotal = float(subtotal)
    order.discount_amount = float(total_discount)
    order.taxable_amount = float(subtotal - total_discount)
    order.cgst_amount = float(total_cgst)
    order.sgst_amount = float(total_sgst)
    order.igst_amount = float(total_igst)
    order.cess_amount = float(total_cess)
    order.total_tax = float(total_tax)
    order.shipping_charges = float(shipping)
    order.other_charges = float(other)
    order.round_off = float(round_off)
    order.grand_total = float(round(total_amount))

    db.session.commit()

    create_audit_log('purchase_orders', order.id, 'create', None, model_to_dict(order))
    log_activity(
        activity_type=ActivityType.CREATE,
        entity_type=EntityType.PURCHASE_ORDER,
        entity_id=order.id,
        description=f"Created purchase order {order.order_number} for {supplier.name}"
    )

    return success_response(model_to_dict(order), 'Purchase order created', 201)


@order_bp.route('/purchase/<int:id>', methods=['GET'])
@jwt_required_with_user()
@permission_required('purchase_orders.view')
def get_purchase_order(id):
    """Get purchase order details"""
    order = PurchaseOrder.query.filter_by(id=id, organization_id=g.organization_id).first()
    if not order:
        return error_response('Purchase order not found', status_code=404)

    data = model_to_dict(order)
    data['supplier'] = model_to_dict(order.supplier) if order.supplier else None
    data['items'] = []

    for item in order.items:
        item_data = model_to_dict(item)
        item_data['product'] = {
            'id': item.product.id,
            'name': item.product.name,
            'sku': item.product.sku,
            'hsn_code': item.product.hsn_code
        } if item.product else None
        data['items'].append(item_data)

    # Get related debit notes
    from app.models import DebitNote
    debit_notes = DebitNote.query.filter_by(
        purchase_order_id=order.id,
        organization_id=g.organization_id
    ).all()
    data['debit_notes'] = [{
        'id': dn.id,
        'debit_note_number': dn.debit_note_number,
        'debit_note_date': dn.debit_note_date.isoformat() if dn.debit_note_date else None,
        'reason': dn.reason,
        'grand_total': float(dn.grand_total or 0),
        'adjusted_amount': float(dn.adjusted_amount or 0),
        'balance_amount': float(dn.balance_amount or 0),
        'status': dn.status
    } for dn in debit_notes]

    # Calculate total debit applied
    total_debit_applied = sum(float(dn.adjusted_amount or 0) for dn in debit_notes)
    data['total_debit_applied'] = total_debit_applied
    data['net_payable'] = float(order.grand_total or 0) - total_debit_applied

    return success_response(data)


@order_bp.route('/purchase/<int:id>', methods=['PUT'])
@jwt_required_with_user()
@permission_required('purchase_orders.edit')
def update_purchase_order(id):
    """Update purchase order"""
    order = PurchaseOrder.query.filter_by(id=id, organization_id=g.organization_id).first()
    if not order:
        return error_response('Purchase order not found', status_code=404)

    if order.status not in ['draft']:
        return error_response('Only draft orders can be edited')

    data = get_request_json()
    org = Organization.query.get(g.organization_id)

    # Update supplier if changed
    if data.get('supplier_id') and data['supplier_id'] != order.supplier_id:
        supplier = Supplier.query.filter_by(id=data['supplier_id'], organization_id=g.organization_id).first()
        if supplier:
            order.supplier_id = supplier.id
            order.supplier_name = supplier.name
            order.supplier_gstin = supplier.gstin
            order.supplier_address_line1 = supplier.address_line1
            order.supplier_address_line2 = supplier.address_line2
            order.supplier_city = supplier.city
            order.supplier_state = supplier.state
            order.supplier_state_code = supplier.state_code
            order.supplier_pincode = supplier.pincode

    # Update basic fields
    updateable = ['expected_delivery_date', 'payment_terms', 'notes', 'reference_number',
                  'delivery_address_line1', 'delivery_address_line2', 'delivery_city',
                  'delivery_state', 'delivery_pincode']

    for field in updateable:
        if field in data:
            setattr(order, field, data[field])

    # Update items if provided
    if data.get('items'):
        supplier = order.supplier
        is_interstate = (supplier.state_code or '') != org.state_code if supplier else False

        # Delete existing items
        PurchaseOrderItem.query.filter_by(order_id=order.id).delete()

        subtotal = Decimal('0')
        total_cgst = Decimal('0')
        total_sgst = Decimal('0')
        total_igst = Decimal('0')
        total_cess = Decimal('0')
        total_discount = Decimal('0')

        for item_data in data['items']:
            product_id = item_data.get('product_id')
            if product_id == '' or product_id is None:
                continue

            product = Product.query.filter_by(id=int(product_id), organization_id=g.organization_id).first()
            if not product:
                continue

            qty = Decimal(str(item_data.get('quantity', 1)))
            unit_price = Decimal(str(item_data.get('unit_price') or item_data.get('rate') or product.purchase_price or 0))
            discount_pct = Decimal(str(item_data.get('discount_percent') or item_data.get('discount_value') or 0))

            item_subtotal = qty * unit_price
            item_discount = item_subtotal * discount_pct / 100
            taxable = item_subtotal - item_discount

            cgst = sgst = igst = cess = Decimal('0')
            if product.tax_rate:
                if is_interstate:
                    igst = taxable * Decimal(str(product.tax_rate.igst_rate)) / 100
                else:
                    cgst = taxable * Decimal(str(product.tax_rate.cgst_rate)) / 100
                    sgst = taxable * Decimal(str(product.tax_rate.sgst_rate)) / 100
                cess = taxable * Decimal(str(product.tax_rate.cess_rate or 0)) / 100

            total = taxable + cgst + sgst + igst + cess

            item = PurchaseOrderItem(
                order_id=order.id,
                product_id=product.id,
                variant_id=item_data.get('variant_id'),
                name=product.name,
                description=sanitize_string(item_data.get('description', '')),
                hsn_code=product.hsn_code,
                quantity=float(qty),
                unit_id=item_data.get('unit_id') or product.unit_id,
                rate=float(unit_price),
                discount_type='percentage',
                discount_value=float(discount_pct),
                discount_amount=float(item_discount),
                taxable_amount=float(taxable),
                tax_rate_id=product.tax_rate_id,
                tax_rate=product.tax_rate.rate if product.tax_rate else 0,
                cgst_rate=product.tax_rate.cgst_rate if product.tax_rate and not is_interstate else 0,
                cgst_amount=float(cgst),
                sgst_rate=product.tax_rate.sgst_rate if product.tax_rate and not is_interstate else 0,
                sgst_amount=float(sgst),
                igst_rate=product.tax_rate.igst_rate if product.tax_rate and is_interstate else 0,
                igst_amount=float(igst),
                cess_rate=product.tax_rate.cess_rate if product.tax_rate else 0,
                cess_amount=float(cess),
                total_tax=float(cgst + sgst + igst + cess),
                amount=float(total)
            )
            db.session.add(item)

            subtotal += taxable
            total_discount += item_discount
            total_cgst += cgst
            total_sgst += sgst
            total_igst += igst
            total_cess += cess

        shipping = Decimal(str(data.get('shipping_charges', order.shipping_charges or 0)))
        other = Decimal(str(data.get('other_charges', order.other_charges or 0)))

        total_tax = total_cgst + total_sgst + total_igst + total_cess
        total_amount = subtotal + total_tax + shipping + other
        round_off = round(total_amount) - total_amount

        order.subtotal = float(subtotal)
        order.discount_amount = float(total_discount)
        order.taxable_amount = float(subtotal - total_discount)
        order.cgst_amount = float(total_cgst)
        order.sgst_amount = float(total_sgst)
        order.igst_amount = float(total_igst)
        order.cess_amount = float(total_cess)
        order.total_tax = float(total_tax)
        order.shipping_charges = float(shipping)
        order.other_charges = float(other)
        order.round_off = float(round_off)
        order.grand_total = float(round(total_amount))

    order.updated_at = datetime.utcnow()
    order.updated_by = g.current_user.id
    db.session.commit()
    log_activity(
        activity_type=ActivityType.UPDATE,
        entity_type=EntityType.PURCHASE_ORDER,
        entity_id=order.id,
        description=f"Updated purchase order {order.order_number}"
    )

    return success_response(model_to_dict(order), 'Purchase order updated')


@order_bp.route('/purchase/<int:id>', methods=['DELETE'])
@jwt_required_with_user()
@permission_required('purchase_orders.delete')
def delete_purchase_order(id):
    """Delete purchase order"""
    order = PurchaseOrder.query.filter_by(id=id, organization_id=g.organization_id).first()
    if not order:
        return error_response('Purchase order not found', status_code=404)

    if order.status not in ['draft']:
        return error_response('Only draft orders can be deleted')

    # Delete items first
    PurchaseOrderItem.query.filter_by(order_id=order.id).delete()

    order_number = order.order_number
    order_id = order.id
    db.session.delete(order)
    db.session.commit()
    log_activity(
        activity_type=ActivityType.DELETE,
        entity_type=EntityType.PURCHASE_ORDER,
        entity_id=order_id,
        description=f"Deleted purchase order {order_number}"
    )

    return success_response(None, 'Purchase order deleted')


@order_bp.route('/purchase/<int:id>/approve', methods=['POST'])
@jwt_required_with_user()
@permission_required('purchase_orders.approve')
def approve_purchase_order(id):
    """Approve purchase order"""
    order = PurchaseOrder.query.filter_by(id=id, organization_id=g.organization_id).first()
    if not order:
        return error_response('Purchase order not found', status_code=404)
    
    if order.status != 'draft':
        return error_response('Only draft orders can be approved')
    
    order.status = 'approved'
    order.approved_by = g.current_user.id
    order.approved_at = datetime.utcnow()
    order.updated_at = datetime.utcnow()
    db.session.commit()
    log_activity(
        activity_type=ActivityType.STATUS_CHANGE,
        entity_type=EntityType.PURCHASE_ORDER,
        entity_id=order.id,
        description=f"Approved purchase order {order.order_number}"
    )

    return success_response(model_to_dict(order), 'Purchase order approved')


@order_bp.route('/purchase/<int:id>/receive', methods=['POST'])
@jwt_required_with_user()
@permission_required('purchase_orders.receive')
def receive_purchase_order(id):
    """Receive goods against purchase order"""
    order = PurchaseOrder.query.filter_by(id=id, organization_id=g.organization_id).first()
    if not order:
        return error_response('Purchase order not found', status_code=404)
    
    if order.status not in ['approved', 'partial']:
        return error_response('Order must be approved to receive goods')
    
    data = get_request_json()
    warehouse_id = data.get('warehouse_id')
    
    if not warehouse_id:
        return error_response('Warehouse required')
    
    items_received = data.get('items', [])
    all_received = True
    
    for recv in items_received:
        item = PurchaseOrderItem.query.filter_by(
            id=recv['item_id'],
            order_id=order.id
        ).first()
        
        if not item:
            continue
        
        qty_to_receive = float(recv.get('quantity', 0))
        pending = float(item.quantity or 0) - float(item.received_quantity or 0)
        
        if qty_to_receive > pending:
            qty_to_receive = pending
        
        if qty_to_receive <= 0:
            continue
        
        # Update item
        item.received_quantity = float(item.received_quantity or 0) + qty_to_receive
        
        if item.received_quantity < item.quantity:
            all_received = False
        
        # Update stock
        stock = Stock.query.filter_by(
            product_id=item.product_id,
            variant_id=item.variant_id,
            warehouse_id=warehouse_id
        ).first()
        
        if stock:
            balance_before = float(stock.quantity or 0)
            stock.quantity = balance_before + qty_to_receive
        else:
            balance_before = 0
            stock = Stock(
                product_id=item.product_id,
                variant_id=item.variant_id,
                warehouse_id=warehouse_id,
                quantity=qty_to_receive
            )
            db.session.add(stock)
        
        # Create transaction
        # Generate transaction number
        txn_count = StockTransaction.query.filter_by(organization_id=g.organization_id).count() + 1
        txn_number = f"STK{datetime.utcnow().strftime('%y%m')}{txn_count:05d}"

        txn = StockTransaction(
            organization_id=g.organization_id,
            transaction_number=txn_number,
            product_id=item.product_id,
            variant_id=item.variant_id,
            warehouse_id=warehouse_id,
            transaction_type='purchase',
            quantity=qty_to_receive,
            balance_before=balance_before,
            balance_after=balance_before + qty_to_receive,
            unit_cost=float(item.rate or 0),
            total_cost=float(item.rate or 0) * qty_to_receive,
            reference_type='purchase_order',
            reference_id=order.id,
            reference_number=order.order_number,
            transaction_date=datetime.utcnow(),
            created_by=g.current_user.id
        )
        db.session.add(txn)
        
        # Update product stock
        product = item.product
        if product:
            total_stock = db.session.query(db.func.sum(Stock.quantity)).filter_by(product_id=product.id).scalar() or 0
            product.current_stock = total_stock
    
    order.status = 'received' if all_received else 'partial'
    order.received_at = datetime.utcnow() if all_received else order.received_at
    order.updated_at = datetime.utcnow()

    db.session.commit()
    log_activity(
        activity_type=ActivityType.STATUS_CHANGE,
        entity_type=EntityType.PURCHASE_ORDER,
        entity_id=order.id,
        description=f"Received goods for purchase order {order.order_number}"
    )

    return success_response(model_to_dict(order), 'Goods received')


@order_bp.route('/purchase/<int:id>/cancel', methods=['POST'])
@jwt_required_with_user()
@permission_required('purchase_orders.approve')
def cancel_purchase_order(id):
    """Cancel purchase order"""
    order = PurchaseOrder.query.filter_by(id=id, organization_id=g.organization_id).first()
    if not order:
        return error_response('Purchase order not found', status_code=404)
    
    if order.status in ['received', 'cancelled']:
        return error_response('Cannot cancel order in current status')
    
    data = get_request_json()
    
    order.status = 'cancelled'
    order.cancellation_reason = sanitize_string(data.get('reason', ''))
    order.cancelled_at = datetime.utcnow()
    order.updated_at = datetime.utcnow()
    db.session.commit()
    log_activity(
        activity_type=ActivityType.STATUS_CHANGE,
        entity_type=EntityType.PURCHASE_ORDER,
        entity_id=order.id,
        description=f"Cancelled purchase order {order.order_number}"
    )

    return success_response(model_to_dict(order), 'Purchase order cancelled')