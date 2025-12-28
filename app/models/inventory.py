from datetime import datetime
from config.database import db


class Warehouse(db.Model):
    """Warehouse/Storage location"""
    __tablename__ = 'warehouses'

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    branch_id = db.Column(db.Integer, db.ForeignKey('branches.id'))
    
    name = db.Column(db.String(100), nullable=False)
    code = db.Column(db.String(20))
    warehouse_type = db.Column(db.String(30), default='warehouse')  # warehouse, store, godown
    
    # Contact
    contact_person = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    email = db.Column(db.String(120))
    
    # Address
    address_line1 = db.Column(db.String(200))
    address_line2 = db.Column(db.String(200))
    city = db.Column(db.String(100))
    state = db.Column(db.String(100))
    state_code = db.Column(db.String(2))
    country = db.Column(db.String(100), default='India')
    pincode = db.Column(db.String(10))
    
    is_primary = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    locations = db.relationship('StockLocation', backref='warehouse', lazy='dynamic')
    stocks = db.relationship('Stock', backref='warehouse', lazy='dynamic')
    
    __table_args__ = (
        db.UniqueConstraint('organization_id', 'code', name='uq_warehouse_org_code'),
    )
    
    def __repr__(self):
        return f'<Warehouse {self.name}>'


class StockLocation(db.Model):
    """Stock locations within warehouse (racks, bins, shelves)"""
    __tablename__ = 'stock_locations'

    id = db.Column(db.Integer, primary_key=True)
    warehouse_id = db.Column(db.Integer, db.ForeignKey('warehouses.id'), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('stock_locations.id'))
    
    name = db.Column(db.String(50), nullable=False)  # "Rack A", "Shelf 1"
    code = db.Column(db.String(20))
    location_type = db.Column(db.String(20))  # rack, shelf, bin, zone
    
    # Path for hierarchy (e.g., "Zone A > Rack 1 > Shelf 2")
    path = db.Column(db.String(200))
    
    is_active = db.Column(db.Boolean, default=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    children = db.relationship('StockLocation', backref=db.backref('parent', remote_side=[id]))
    
    def __repr__(self):
        return f'<StockLocation {self.name}>'


class Stock(db.Model):
    """Current stock levels"""
    __tablename__ = 'stocks'

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    variant_id = db.Column(db.Integer, db.ForeignKey('product_variants.id'))
    warehouse_id = db.Column(db.Integer, db.ForeignKey('warehouses.id'), nullable=False)
    location_id = db.Column(db.Integer, db.ForeignKey('stock_locations.id'))
    batch_id = db.Column(db.Integer, db.ForeignKey('batch_lots.id'))
    
    # Stock Quantities
    quantity = db.Column(db.Numeric(15, 3), default=0)  # Current available
    reserved_quantity = db.Column(db.Numeric(15, 3), default=0)  # Reserved for orders
    incoming_quantity = db.Column(db.Numeric(15, 3), default=0)  # Expected from PO
    
    # Calculated
    available_quantity = db.Column(db.Numeric(15, 3), default=0)  # quantity - reserved
    
    # Valuation
    avg_cost = db.Column(db.Numeric(15, 2), default=0)  # Weighted average cost
    last_purchase_price = db.Column(db.Numeric(15, 2), default=0)
    
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        db.UniqueConstraint('product_id', 'variant_id', 'warehouse_id', 'location_id', 'batch_id',
                           name='uq_stock_product_warehouse'),
        db.Index('idx_stock_product', 'organization_id', 'product_id'),
        db.Index('idx_stock_warehouse', 'warehouse_id'),
    )
    
    def __repr__(self):
        return f'<Stock {self.product_id} @ {self.warehouse_id}>'


class BatchLot(db.Model):
    """Batch/Lot tracking for products (pharma, food, medical)"""
    __tablename__ = 'batch_lots'

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    variant_id = db.Column(db.Integer, db.ForeignKey('product_variants.id'))
    
    batch_number = db.Column(db.String(50), nullable=False)
    lot_number = db.Column(db.String(50))
    
    # Dates
    manufacturing_date = db.Column(db.Date)
    expiry_date = db.Column(db.Date)
    received_date = db.Column(db.Date)
    
    # Quantities
    initial_quantity = db.Column(db.Numeric(15, 3), default=0)
    current_quantity = db.Column(db.Numeric(15, 3), default=0)
    
    # Cost
    cost_price = db.Column(db.Numeric(15, 2))
    
    # Status
    status = db.Column(db.String(20), default='active')  # active, expired, consumed, returned
    
    # Source
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'))
    purchase_order_id = db.Column(db.Integer, db.ForeignKey('purchase_orders.id'))
    
    notes = db.Column(db.Text)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        db.UniqueConstraint('organization_id', 'product_id', 'batch_number', name='uq_batch_product'),
        db.Index('idx_batch_expiry', 'organization_id', 'expiry_date'),
    )
    
    def __repr__(self):
        return f'<BatchLot {self.batch_number}>'


class StockTransaction(db.Model):
    """All stock movements (in/out/transfer/adjustment/return)"""
    __tablename__ = 'stock_transactions'

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    
    # Transaction Reference
    transaction_number = db.Column(db.String(30), nullable=False)
    transaction_date = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Transaction Type
    transaction_type = db.Column(db.String(30), nullable=False)
    # Types: stock_in, stock_out, purchase, sale, return_in, return_out, 
    #        transfer, adjustment, damage, expiry, opening_stock
    
    # Product
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    variant_id = db.Column(db.Integer, db.ForeignKey('product_variants.id'))
    batch_id = db.Column(db.Integer, db.ForeignKey('batch_lots.id'))
    
    # Warehouse/Location
    warehouse_id = db.Column(db.Integer, db.ForeignKey('warehouses.id'), nullable=False)
    location_id = db.Column(db.Integer, db.ForeignKey('stock_locations.id'))
    
    # For transfers
    to_warehouse_id = db.Column(db.Integer, db.ForeignKey('warehouses.id'))
    to_location_id = db.Column(db.Integer, db.ForeignKey('stock_locations.id'))
    
    # Quantity
    quantity = db.Column(db.Numeric(15, 3), nullable=False)  # Positive for in, negative for out
    unit_id = db.Column(db.Integer, db.ForeignKey('units.id'))
    
    # Cost
    unit_cost = db.Column(db.Numeric(15, 2), default=0)
    total_cost = db.Column(db.Numeric(15, 2), default=0)
    
    # Stock Balance (after transaction)
    balance_before = db.Column(db.Numeric(15, 3), default=0)
    balance_after = db.Column(db.Numeric(15, 3), default=0)
    
    # Reference Document
    reference_type = db.Column(db.String(30))  # invoice, purchase_order, adjustment, etc.
    reference_id = db.Column(db.Integer)
    reference_number = db.Column(db.String(50))
    
    # Reason (for adjustments, returns, etc.)
    reason = db.Column(db.String(200))
    notes = db.Column(db.Text)
    
    # Status
    status = db.Column(db.String(20), default='completed')  # pending, completed, cancelled
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    # Relationships
    product = db.relationship('Product', foreign_keys=[product_id])
    warehouse = db.relationship('Warehouse', foreign_keys=[warehouse_id])
    to_warehouse = db.relationship('Warehouse', foreign_keys=[to_warehouse_id])
    batch = db.relationship('BatchLot')
    
    __table_args__ = (
        db.UniqueConstraint('organization_id', 'transaction_number', name='uq_stock_txn_number'),
        db.Index('idx_stock_txn_product', 'organization_id', 'product_id'),
        db.Index('idx_stock_txn_date', 'organization_id', 'transaction_date'),
        db.Index('idx_stock_txn_type', 'organization_id', 'transaction_type'),
    )
    
    def __repr__(self):
        return f'<StockTransaction {self.transaction_number}>'


class StockAdjustment(db.Model):
    """Stock adjustment document (for multiple items)"""
    __tablename__ = 'stock_adjustments'

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    
    adjustment_number = db.Column(db.String(30), nullable=False)
    adjustment_date = db.Column(db.DateTime, default=datetime.utcnow)
    
    adjustment_type = db.Column(db.String(30), nullable=False)  # increase, decrease, damage, expiry
    warehouse_id = db.Column(db.Integer, db.ForeignKey('warehouses.id'), nullable=False)
    
    reason = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    
    total_items = db.Column(db.Integer, default=0)
    total_value = db.Column(db.Numeric(15, 2), default=0)
    
    status = db.Column(db.String(20), default='draft')  # draft, approved, completed, cancelled
    
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    approved_at = db.Column(db.DateTime)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    __table_args__ = (
        db.UniqueConstraint('organization_id', 'adjustment_number', name='uq_stock_adj_number'),
    )
    
    def __repr__(self):
        return f'<StockAdjustment {self.adjustment_number}>'