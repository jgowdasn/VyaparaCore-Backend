"""Inventory management routes for VyaparaCore"""
from flask import Blueprint, g, request
from datetime import datetime
from config.database import db
from app.models import (
    Warehouse, StockLocation, Stock, BatchLot, StockTransaction, StockAdjustment,
    Product, ProductVariant
)
from app.utils.security import (
    jwt_required_with_user, permission_required, sanitize_string, create_audit_log
)
from app.utils.helpers import (
    success_response, error_response, get_request_json,
    paginate, get_filters, apply_filters, model_to_dict
)

inventory_bp = Blueprint('inventory', __name__)


# Warehouses
@inventory_bp.route('/warehouses', methods=['GET'])
@jwt_required_with_user()
@permission_required('warehouse.view')
def list_warehouses():
    """List all warehouses"""
    query = Warehouse.query.filter_by(organization_id=g.organization_id)
    filters = get_filters()
    query = apply_filters(query, Warehouse, filters)
    return success_response(paginate(query, model_to_dict))


@inventory_bp.route('/warehouses', methods=['POST'])
@jwt_required_with_user()
@permission_required('warehouse.create')
def create_warehouse():
    """Create warehouse"""
    data = get_request_json()
    
    if not data.get('name'):
        return error_response('Warehouse name required')
    
    code = sanitize_string(data.get('code', '')).upper()
    if not code:
        code = ''.join(e for e in data['name'][:4] if e.isalnum()).upper()
    
    existing = Warehouse.query.filter_by(organization_id=g.organization_id, code=code).first()
    if existing:
        return error_response('Warehouse code already exists')
    
    warehouse = Warehouse(
        organization_id=g.organization_id,
        branch_id=data.get('branch_id'),
        name=sanitize_string(data['name']),
        code=code,
        warehouse_type=data.get('warehouse_type', 'warehouse'),
        address_line1=sanitize_string(data.get('address_line1', '')),
        address_line2=sanitize_string(data.get('address_line2', '')),
        city=sanitize_string(data.get('city', '')),
        state=sanitize_string(data.get('state', '')),
        state_code=data.get('state_code'),
        country=data.get('country', 'India'),
        pincode=sanitize_string(data.get('pincode', '')),
        contact_person=sanitize_string(data.get('contact_person', '')),
        phone=sanitize_string(data.get('phone', '') or data.get('contact_phone', '')),
        email=sanitize_string(data.get('email', '') or data.get('contact_email', '')),
        is_primary=data.get('is_primary', False) or data.get('is_default', False),
        is_active=True
    )

    if warehouse.is_primary:
        Warehouse.query.filter_by(organization_id=g.organization_id).update({'is_primary': False})
    
    db.session.add(warehouse)
    db.session.commit()
    
    return success_response(model_to_dict(warehouse), 'Warehouse created', 201)


@inventory_bp.route('/warehouses/<int:id>', methods=['GET'])
@jwt_required_with_user()
@permission_required('warehouse.view')
def get_warehouse(id):
    """Get warehouse details"""
    warehouse = Warehouse.query.filter_by(id=id, organization_id=g.organization_id).first()
    if not warehouse:
        return error_response('Warehouse not found', status_code=404)
    
    data = model_to_dict(warehouse)
    data['locations'] = [model_to_dict(l) for l in warehouse.locations]
    
    return success_response(data)


@inventory_bp.route('/warehouses/<int:id>', methods=['PUT'])
@jwt_required_with_user()
@permission_required('warehouse.edit')
def update_warehouse(id):
    """Update warehouse"""
    warehouse = Warehouse.query.filter_by(id=id, organization_id=g.organization_id).first()
    if not warehouse:
        return error_response('Warehouse not found', status_code=404)
    
    data = get_request_json()

    updateable = ['name', 'warehouse_type', 'address_line1', 'address_line2', 'city',
                  'state', 'state_code', 'country', 'pincode', 'contact_person',
                  'phone', 'email', 'is_primary', 'is_active']

    # Handle field name mappings from frontend
    field_mappings = {
        'contact_phone': 'phone',
        'contact_email': 'email',
        'is_default': 'is_primary',
    }

    for field in updateable:
        if field in data:
            value = data[field]
            if isinstance(value, str):
                value = sanitize_string(value)
            setattr(warehouse, field, value)

    # Handle mapped fields
    for frontend_field, model_field in field_mappings.items():
        if frontend_field in data:
            value = data[frontend_field]
            if isinstance(value, str):
                value = sanitize_string(value)
            setattr(warehouse, model_field, value)

    if warehouse.is_primary:
        Warehouse.query.filter(
            Warehouse.organization_id == g.organization_id,
            Warehouse.id != id
        ).update({'is_primary': False})
    
    warehouse.updated_at = datetime.utcnow()
    db.session.commit()
    
    return success_response(model_to_dict(warehouse), 'Warehouse updated')


@inventory_bp.route('/warehouses/<int:id>', methods=['DELETE'])
@jwt_required_with_user()
@permission_required('warehouse.delete')
def delete_warehouse(id):
    """Delete warehouse"""
    warehouse = Warehouse.query.filter_by(id=id, organization_id=g.organization_id).first()
    if not warehouse:
        return error_response('Warehouse not found', status_code=404)
    
    # Check for stock
    if Stock.query.filter_by(warehouse_id=id).filter(Stock.quantity > 0).first():
        return error_response('Cannot delete warehouse with stock')
    
    warehouse.is_active = False
    warehouse.updated_at = datetime.utcnow()
    db.session.commit()
    
    return success_response(message='Warehouse deleted')


# Stock Locations
@inventory_bp.route('/warehouses/<int:wh_id>/locations', methods=['GET'])
@jwt_required_with_user()
@permission_required('warehouse.view')
def list_locations(wh_id):
    """List locations in warehouse"""
    locations = StockLocation.query.filter_by(warehouse_id=wh_id, is_active=True).all()
    return success_response([model_to_dict(l) for l in locations])


@inventory_bp.route('/warehouses/<int:wh_id>/locations', methods=['POST'])
@jwt_required_with_user()
@permission_required('warehouse.edit')
def create_location(wh_id):
    """Create stock location"""
    warehouse = Warehouse.query.filter_by(id=wh_id, organization_id=g.organization_id).first()
    if not warehouse:
        return error_response('Warehouse not found', status_code=404)
    
    data = get_request_json()
    
    location = StockLocation(
        warehouse_id=wh_id,
        name=sanitize_string(data.get('name', '')),
        code=sanitize_string(data.get('code', '')).upper(),
        location_type=data.get('location_type', 'shelf'),
        parent_id=data.get('parent_id'),
        zone=sanitize_string(data.get('zone', '')),
        aisle=sanitize_string(data.get('aisle', '')),
        rack=sanitize_string(data.get('rack', '')),
        shelf=sanitize_string(data.get('shelf', '')),
        bin=sanitize_string(data.get('bin', '')),
        is_active=True
    )
    
    db.session.add(location)
    db.session.commit()
    
    return success_response(model_to_dict(location), 'Location created', 201)


# Stock
@inventory_bp.route('/stock', methods=['GET'])
@jwt_required_with_user()
@permission_required('inventory.view')
def list_stock():
    """List stock levels"""
    query = Stock.query.join(Product).filter(Product.organization_id == g.organization_id)
    
    if request.args.get('warehouse_id'):
        query = query.filter(Stock.warehouse_id == request.args.get('warehouse_id', type=int))
    
    if request.args.get('product_id'):
        query = query.filter(Stock.product_id == request.args.get('product_id', type=int))
    
    if request.args.get('low_stock'):
        query = query.filter(Stock.quantity <= Stock.reorder_level)
    
    def serialize(s):
        data = model_to_dict(s)
        data['product_name'] = s.product.name if s.product else None
        data['product_sku'] = s.product.sku if s.product else None
        data['warehouse_name'] = s.warehouse.name if s.warehouse else None
        return data
    
    return success_response(paginate(query, serialize))


@inventory_bp.route('/stock/product/<int:product_id>', methods=['GET'])
@jwt_required_with_user()
@permission_required('inventory.view')
def get_product_stock(product_id):
    """Get stock for a product across all warehouses"""
    product = Product.query.filter_by(id=product_id, organization_id=g.organization_id).first()
    if not product:
        return error_response('Product not found', status_code=404)
    
    stocks = Stock.query.filter_by(product_id=product_id).all()
    
    total_qty = sum(s.quantity or 0 for s in stocks)
    total_reserved = sum(s.reserved_quantity or 0 for s in stocks)
    
    return success_response({
        'product': {'id': product.id, 'name': product.name, 'sku': product.sku},
        'total_quantity': float(total_qty),
        'total_reserved': float(total_reserved),
        'total_available': float(total_qty - total_reserved),
        'by_warehouse': [
            {
                'warehouse_id': s.warehouse_id,
                'warehouse_name': s.warehouse.name if s.warehouse else None,
                'quantity': float(s.quantity or 0),
                'reserved': float(s.reserved_quantity or 0),
                'available': float((s.quantity or 0) - (s.reserved_quantity or 0))
            } for s in stocks
        ]
    })


# Batches
@inventory_bp.route('/batches', methods=['GET'])
@jwt_required_with_user()
@permission_required('inventory.view')
def list_batches():
    """List batch/lot records"""
    query = BatchLot.query.join(Product).filter(Product.organization_id == g.organization_id)
    
    if request.args.get('product_id'):
        query = query.filter(BatchLot.product_id == request.args.get('product_id', type=int))
    
    if request.args.get('expiring_soon'):
        days = request.args.get('days', 30, type=int)
        from datetime import timedelta
        expiry_date = datetime.utcnow().date() + timedelta(days=days)
        query = query.filter(BatchLot.expiry_date <= expiry_date, BatchLot.expiry_date >= datetime.utcnow().date())
    
    if request.args.get('expired'):
        query = query.filter(BatchLot.expiry_date < datetime.utcnow().date())
    
    def serialize(b):
        data = model_to_dict(b)
        data['product_name'] = b.product.name if b.product else None
        return data
    
    return success_response(paginate(query, serialize))


@inventory_bp.route('/batches', methods=['POST'])
@jwt_required_with_user()
@permission_required('inventory.adjust')
def create_batch():
    """Create batch/lot"""
    data = get_request_json()
    
    if not data.get('product_id') or not data.get('batch_number'):
        return error_response('Product ID and batch number required')
    
    product = Product.query.filter_by(id=data['product_id'], organization_id=g.organization_id).first()
    if not product:
        return error_response('Product not found', status_code=404)
    
    batch = BatchLot(
        product_id=data['product_id'],
        variant_id=data.get('variant_id'),
        warehouse_id=data.get('warehouse_id'),
        batch_number=sanitize_string(data['batch_number']),
        lot_number=sanitize_string(data.get('lot_number', '')),
        manufacturing_date=data.get('manufacturing_date'),
        expiry_date=data.get('expiry_date'),
        initial_quantity=data.get('initial_quantity', 0),
        current_quantity=data.get('initial_quantity', 0),
        cost_price=data.get('cost_price', 0),
        supplier_id=data.get('supplier_id'),
        purchase_order_id=data.get('purchase_order_id'),
        notes=sanitize_string(data.get('notes', '')),
        is_active=True
    )
    
    db.session.add(batch)
    db.session.commit()
    
    return success_response(model_to_dict(batch), 'Batch created', 201)


# Stock Transactions
@inventory_bp.route('/transactions', methods=['GET'])
@jwt_required_with_user()
@permission_required('inventory.view')
def list_transactions():
    """List stock transactions"""
    from sqlalchemy.orm import joinedload

    query = StockTransaction.query.options(
        joinedload(StockTransaction.product),
        joinedload(StockTransaction.warehouse),
        joinedload(StockTransaction.to_warehouse)
    ).filter_by(organization_id=g.organization_id)

    if request.args.get('product_id'):
        query = query.filter(StockTransaction.product_id == request.args.get('product_id', type=int))

    if request.args.get('warehouse_id'):
        query = query.filter(StockTransaction.warehouse_id == request.args.get('warehouse_id', type=int))

    if request.args.get('transaction_type'):
        query = query.filter(StockTransaction.transaction_type == request.args.get('transaction_type'))

    filters = get_filters()
    query = apply_filters(query, StockTransaction, filters)

    # Order by most recent first
    query = query.order_by(StockTransaction.created_at.desc())

    def serialize(t):
        data = model_to_dict(t)
        data['product_name'] = t.product.name if t.product else None
        data['warehouse_name'] = t.warehouse.name if t.warehouse else None
        # Get to_warehouse name for transfers
        if t.to_warehouse_id:
            to_wh = Warehouse.query.get(t.to_warehouse_id)
            data['to_warehouse_name'] = to_wh.name if to_wh else None
        else:
            data['to_warehouse_name'] = None
        return data

    return success_response(paginate(query, serialize))


# Stock Adjustment
@inventory_bp.route('/adjustments', methods=['GET'])
@jwt_required_with_user()
@permission_required('inventory.view')
def list_adjustments():
    """List stock adjustments"""
    query = StockAdjustment.query.filter_by(organization_id=g.organization_id)

    # Filter by adjustment type
    adjustment_type = request.args.get('adjustment_type')
    if adjustment_type and adjustment_type != 'all':
        query = query.filter(StockAdjustment.adjustment_type == adjustment_type)

    # Order by most recent first
    query = query.order_by(StockAdjustment.created_at.desc())

    return success_response(paginate(query, model_to_dict))


@inventory_bp.route('/adjustments', methods=['POST'])
@jwt_required_with_user()
@permission_required('inventory.adjust')
def create_adjustment():
    """Create stock adjustment"""
    data = get_request_json()
    
    if not data.get('warehouse_id') or not data.get('items'):
        return error_response('Warehouse and items required')
    
    # Generate adjustment number
    count = StockAdjustment.query.filter_by(organization_id=g.organization_id).count() + 1
    adj_number = f"ADJ{datetime.utcnow().strftime('%y%m')}{count:04d}"
    
    adjustment = StockAdjustment(
        organization_id=g.organization_id,
        adjustment_number=adj_number,
        warehouse_id=data['warehouse_id'],
        adjustment_date=data.get('adjustment_date', datetime.utcnow().date()),
        adjustment_type=data.get('adjustment_type', 'quantity'),
        reason=sanitize_string(data.get('reason', '')),
        description=sanitize_string(data.get('notes', '') or data.get('description', '')),
        status='draft',
        created_by=g.current_user.id
    )
    
    db.session.add(adjustment)
    db.session.flush()
    
    total_value = 0
    
    for item in data['items']:
        product = Product.query.filter_by(id=item['product_id'], organization_id=g.organization_id).first()
        if not product:
            continue
        
        # Get current stock
        stock = Stock.query.filter_by(
            product_id=item['product_id'],
            warehouse_id=data['warehouse_id']
        ).first()
        
        current_qty = float(stock.quantity) if stock else 0
        new_qty = float(item.get('new_quantity', current_qty))
        diff = new_qty - current_qty
        
        # Create transaction (positive qty for in, negative for out)
        txn_count = StockTransaction.query.filter_by(organization_id=g.organization_id).count() + 1
        txn_number = f"TXN{datetime.utcnow().strftime('%y%m')}{txn_count:05d}"

        txn = StockTransaction(
            organization_id=g.organization_id,
            transaction_number=txn_number,
            product_id=item['product_id'],
            variant_id=item.get('variant_id'),
            warehouse_id=data['warehouse_id'],
            transaction_type='adjustment',
            quantity=diff,  # positive for increase, negative for decrease
            balance_before=current_qty,
            balance_after=new_qty,
            reference_type='stock_adjustment',
            reference_id=adjustment.id,
            reason=item.get('reason', ''),
            transaction_date=datetime.utcnow(),
            created_by=g.current_user.id
        )
        db.session.add(txn)
        
        # Update stock
        if stock:
            stock.quantity = new_qty
            stock.updated_at = datetime.utcnow()
        else:
            stock = Stock(
                organization_id=g.organization_id,
                product_id=item['product_id'],
                variant_id=item.get('variant_id'),
                warehouse_id=data['warehouse_id'],
                quantity=new_qty
            )
            db.session.add(stock)
        
        # Update product current stock
        total_stock = db.session.query(db.func.sum(Stock.quantity)).filter_by(product_id=item['product_id']).scalar() or 0
        product.current_stock = total_stock
        
        total_value += abs(diff) * float(product.purchase_price or 0)
    
    adjustment.total_items = len(data['items'])
    adjustment.total_value = total_value
    adjustment.status = 'completed'
    adjustment.approved_by = g.current_user.id
    adjustment.approved_at = datetime.utcnow()
    
    db.session.commit()
    
    create_audit_log('stock_adjustments', adjustment.id, 'create', None, model_to_dict(adjustment))
    
    return success_response(model_to_dict(adjustment), 'Stock adjustment created', 201)


# Stock Transfer
@inventory_bp.route('/transfer', methods=['POST'])
@jwt_required_with_user()
@permission_required('inventory.transfer')
def transfer_stock():
    """Transfer stock between warehouses"""
    data = get_request_json()
    
    required = ['from_warehouse_id', 'to_warehouse_id', 'product_id', 'quantity']
    for field in required:
        if not data.get(field):
            return error_response(f'{field} is required')
    
    if data['from_warehouse_id'] == data['to_warehouse_id']:
        return error_response('Source and destination warehouses must be different')
    
    product = Product.query.filter_by(id=data['product_id'], organization_id=g.organization_id).first()
    if not product:
        return error_response('Product not found', status_code=404)
    
    # Check source stock
    source_stock = Stock.query.filter_by(
        product_id=data['product_id'],
        warehouse_id=data['from_warehouse_id']
    ).first()
    
    if not source_stock or float(source_stock.quantity or 0) < float(data['quantity']):
        return error_response('Insufficient stock in source warehouse')
    
    qty = float(data['quantity'])
    
    # Deduct from source
    source_balance_before = float(source_stock.quantity)
    source_stock.quantity = source_balance_before - qty
    
    # Add to destination
    dest_stock = Stock.query.filter_by(
        product_id=data['product_id'],
        warehouse_id=data['to_warehouse_id']
    ).first()
    
    if dest_stock:
        dest_balance_before = float(dest_stock.quantity or 0)
        dest_stock.quantity = dest_balance_before + qty
    else:
        dest_balance_before = 0
        dest_stock = Stock(
            organization_id=g.organization_id,
            product_id=data['product_id'],
            variant_id=data.get('variant_id'),
            warehouse_id=data['to_warehouse_id'],
            quantity=qty
        )
        db.session.add(dest_stock)
    
    # Create transactions (negative qty for out, positive for in)
    txn_count = StockTransaction.query.filter_by(organization_id=g.organization_id).count()

    txn_out = StockTransaction(
        organization_id=g.organization_id,
        transaction_number=f"TXN{datetime.utcnow().strftime('%y%m')}{txn_count + 1:05d}",
        product_id=data['product_id'],
        variant_id=data.get('variant_id'),
        warehouse_id=data['from_warehouse_id'],
        to_warehouse_id=data['to_warehouse_id'],
        transaction_type='transfer',
        quantity=-qty,  # negative for out
        balance_before=source_balance_before,
        balance_after=source_balance_before - qty,
        reference_type='transfer',
        reason=f"Transfer to warehouse {data['to_warehouse_id']}",
        transaction_date=datetime.utcnow(),
        created_by=g.current_user.id
    )

    txn_in = StockTransaction(
        organization_id=g.organization_id,
        transaction_number=f"TXN{datetime.utcnow().strftime('%y%m')}{txn_count + 2:05d}",
        product_id=data['product_id'],
        variant_id=data.get('variant_id'),
        warehouse_id=data['to_warehouse_id'],
        transaction_type='transfer',
        quantity=qty,  # positive for in
        balance_before=dest_balance_before,
        balance_after=dest_balance_before + qty,
        reference_type='transfer',
        reason=f"Transfer from warehouse {data['from_warehouse_id']}",
        transaction_date=datetime.utcnow(),
        created_by=g.current_user.id
    )

    db.session.add(txn_out)
    db.session.add(txn_in)
    db.session.commit()
    
    return success_response({
        'product_id': data['product_id'],
        'quantity': qty,
        'from_warehouse': data['from_warehouse_id'],
        'to_warehouse': data['to_warehouse_id']
    }, 'Stock transferred successfully')


# Low stock alerts
@inventory_bp.route('/alerts/low-stock', methods=['GET'])
@jwt_required_with_user()
@permission_required('inventory.view')
def low_stock_alerts():
    """Get low stock products"""
    products = Product.query.filter(
        Product.organization_id == g.organization_id,
        Product.is_active == True,
        Product.track_inventory == True,
        Product.current_stock <= Product.reorder_level
    ).all()
    
    return success_response([{
        'id': p.id,
        'name': p.name,
        'sku': p.sku,
        'current_stock': float(p.current_stock or 0),
        'reorder_level': float(p.reorder_level or 0),
        'reorder_quantity': float(p.reorder_quantity or 0)
    } for p in products])


# Expiring batches
@inventory_bp.route('/alerts/expiring', methods=['GET'])
@jwt_required_with_user()
@permission_required('inventory.view')
def expiring_batches():
    """Get expiring batches"""
    days = request.args.get('days', 30, type=int)
    from datetime import timedelta
    
    expiry_date = datetime.utcnow().date() + timedelta(days=days)
    
    batches = BatchLot.query.join(Product).filter(
        Product.organization_id == g.organization_id,
        BatchLot.is_active == True,
        BatchLot.current_quantity > 0,
        BatchLot.expiry_date <= expiry_date,
        BatchLot.expiry_date >= datetime.utcnow().date()
    ).order_by(BatchLot.expiry_date).all()
    
    return success_response([{
        'id': b.id,
        'product_id': b.product_id,
        'product_name': b.product.name if b.product else None,
        'batch_number': b.batch_number,
        'expiry_date': b.expiry_date.isoformat() if b.expiry_date else None,
        'current_quantity': float(b.current_quantity or 0),
        'days_to_expiry': (b.expiry_date - datetime.utcnow().date()).days if b.expiry_date else None
    } for b in batches])