from datetime import datetime
from config.database import db


class SalesOrder(db.Model):
    """Sales Order model"""
    __tablename__ = 'sales_orders'

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    branch_id = db.Column(db.Integer, db.ForeignKey('branches.id'))
    
    # Order Details
    order_number = db.Column(db.String(30), nullable=False)
    order_date = db.Column(db.Date, nullable=False)
    reference_number = db.Column(db.String(50))
    
    # Source
    source_type = db.Column(db.String(20))  # quotation, direct, online
    quotation_id = db.Column(db.Integer, db.ForeignKey('quotations.id'))
    
    # Customer
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)
    customer_name = db.Column(db.String(200))
    customer_gstin = db.Column(db.String(15))
    
    # Billing Address
    billing_address_line1 = db.Column(db.String(200))
    billing_address_line2 = db.Column(db.String(200))
    billing_city = db.Column(db.String(100))
    billing_state = db.Column(db.String(100))
    billing_state_code = db.Column(db.String(2))
    billing_country = db.Column(db.String(100))
    billing_pincode = db.Column(db.String(10))
    
    # Shipping Address
    shipping_address_line1 = db.Column(db.String(200))
    shipping_address_line2 = db.Column(db.String(200))
    shipping_city = db.Column(db.String(100))
    shipping_state = db.Column(db.String(100))
    shipping_state_code = db.Column(db.String(2))
    shipping_country = db.Column(db.String(100))
    shipping_pincode = db.Column(db.String(10))
    
    # GST
    place_of_supply = db.Column(db.String(100))
    is_igst = db.Column(db.Boolean, default=False)
    
    # Delivery
    expected_delivery_date = db.Column(db.Date)
    delivery_method = db.Column(db.String(50))
    
    # Amounts
    subtotal = db.Column(db.Numeric(15, 2), default=0)
    discount_type = db.Column(db.String(10))
    discount_value = db.Column(db.Numeric(10, 2), default=0)
    discount_amount = db.Column(db.Numeric(15, 2), default=0)
    
    taxable_amount = db.Column(db.Numeric(15, 2), default=0)
    cgst_amount = db.Column(db.Numeric(15, 2), default=0)
    sgst_amount = db.Column(db.Numeric(15, 2), default=0)
    igst_amount = db.Column(db.Numeric(15, 2), default=0)
    cess_amount = db.Column(db.Numeric(15, 2), default=0)
    total_tax = db.Column(db.Numeric(15, 2), default=0)
    
    shipping_charges = db.Column(db.Numeric(15, 2), default=0)
    packaging_charges = db.Column(db.Numeric(15, 2), default=0)
    other_charges = db.Column(db.Numeric(15, 2), default=0)
    round_off = db.Column(db.Numeric(10, 2), default=0)
    
    grand_total = db.Column(db.Numeric(15, 2), default=0)
    amount_in_words = db.Column(db.String(500))
    
    currency = db.Column(db.String(3), default='INR')
    exchange_rate = db.Column(db.Numeric(10, 4), default=1)
    
    # Payment
    payment_terms = db.Column(db.Integer, default=0)
    payment_due_date = db.Column(db.Date)
    advance_amount = db.Column(db.Numeric(15, 2), default=0)
    
    # Status
    status = db.Column(db.String(20), default='draft')
    # draft, confirmed, processing, partially_shipped, shipped, delivered, cancelled, on_hold
    
    payment_status = db.Column(db.String(20), default='unpaid')  # unpaid, partial, paid
    delivery_status = db.Column(db.String(20), default='pending')  # pending, partial, delivered
    
    # Fulfillment Tracking
    total_items = db.Column(db.Integer, default=0)
    shipped_items = db.Column(db.Integer, default=0)
    invoiced_items = db.Column(db.Integer, default=0)
    
    # Notes
    notes = db.Column(db.Text)
    customer_notes = db.Column(db.Text)
    
    # Sales Info
    salesperson_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    # Warehouse
    warehouse_id = db.Column(db.Integer, db.ForeignKey('warehouses.id'))
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    confirmed_at = db.Column(db.DateTime)
    shipped_at = db.Column(db.DateTime)
    delivered_at = db.Column(db.DateTime)
    cancelled_at = db.Column(db.DateTime)
    
    # Relationships
    customer = db.relationship('Customer', foreign_keys=[customer_id])
    items = db.relationship('SalesOrderItem', backref='order', lazy='dynamic', cascade='all, delete-orphan')
    invoices = db.relationship('Invoice', backref='sales_order', lazy='dynamic')

    __table_args__ = (
        db.UniqueConstraint('organization_id', 'order_number', name='uq_sales_order_number'),
        db.Index('idx_so_customer', 'organization_id', 'customer_id'),
        db.Index('idx_so_date', 'organization_id', 'order_date'),
        db.Index('idx_so_status', 'organization_id', 'status'),
    )

    def __repr__(self):
        return f'<SalesOrder {self.order_number}>'


class SalesOrderItem(db.Model):
    """Sales order line items"""
    __tablename__ = 'sales_order_items'

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('sales_orders.id'), nullable=False)
    
    line_number = db.Column(db.Integer, default=1)
    
    # Product
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'))
    variant_id = db.Column(db.Integer, db.ForeignKey('product_variants.id'))
    
    item_type = db.Column(db.String(20), default='product')
    sku = db.Column(db.String(50))
    hsn_code = db.Column(db.String(10))
    sac_code = db.Column(db.String(10))
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    
    # Quantity
    quantity = db.Column(db.Numeric(15, 3), nullable=False)
    unit_id = db.Column(db.Integer, db.ForeignKey('units.id'))
    unit_name = db.Column(db.String(20))
    
    # Fulfillment
    shipped_quantity = db.Column(db.Numeric(15, 3), default=0)
    invoiced_quantity = db.Column(db.Numeric(15, 3), default=0)
    delivered_quantity = db.Column(db.Numeric(15, 3), default=0)
    returned_quantity = db.Column(db.Numeric(15, 3), default=0)
    
    # Pricing
    rate = db.Column(db.Numeric(15, 2), nullable=False)
    mrp = db.Column(db.Numeric(15, 2))
    
    discount_type = db.Column(db.String(10))
    discount_value = db.Column(db.Numeric(10, 2), default=0)
    discount_amount = db.Column(db.Numeric(15, 2), default=0)
    
    # Tax
    tax_rate_id = db.Column(db.Integer, db.ForeignKey('tax_rates.id'))
    tax_rate = db.Column(db.Numeric(5, 2), default=0)
    cgst_rate = db.Column(db.Numeric(5, 2), default=0)
    sgst_rate = db.Column(db.Numeric(5, 2), default=0)
    igst_rate = db.Column(db.Numeric(5, 2), default=0)
    cess_rate = db.Column(db.Numeric(5, 2), default=0)
    
    taxable_amount = db.Column(db.Numeric(15, 2), default=0)
    cgst_amount = db.Column(db.Numeric(15, 2), default=0)
    sgst_amount = db.Column(db.Numeric(15, 2), default=0)
    igst_amount = db.Column(db.Numeric(15, 2), default=0)
    cess_amount = db.Column(db.Numeric(15, 2), default=0)
    total_tax = db.Column(db.Numeric(15, 2), default=0)
    
    amount = db.Column(db.Numeric(15, 2), default=0)

    # Batch (for inventory with batch tracking)
    batch_id = db.Column(db.Integer, db.ForeignKey('batch_lots.id'))

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    product = db.relationship('Product', foreign_keys=[product_id])


class PurchaseOrder(db.Model):
    """Purchase Order model"""
    __tablename__ = 'purchase_orders'

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    branch_id = db.Column(db.Integer, db.ForeignKey('branches.id'))

    # PO Details
    order_number = db.Column(db.String(30), nullable=False)
    order_date = db.Column(db.Date, nullable=False)
    reference_number = db.Column(db.String(50))

    # Supplier
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'), nullable=False)
    supplier_name = db.Column(db.String(200))
    supplier_gstin = db.Column(db.String(15))

    # Supplier Address
    supplier_address_line1 = db.Column(db.String(200))
    supplier_address_line2 = db.Column(db.String(200))
    supplier_city = db.Column(db.String(100))
    supplier_state = db.Column(db.String(100))
    supplier_state_code = db.Column(db.String(2))
    supplier_country = db.Column(db.String(100))
    supplier_pincode = db.Column(db.String(10))
    
    # Delivery
    delivery_address_line1 = db.Column(db.String(200))
    delivery_address_line2 = db.Column(db.String(200))
    delivery_city = db.Column(db.String(100))
    delivery_state = db.Column(db.String(100))
    delivery_state_code = db.Column(db.String(2))
    delivery_country = db.Column(db.String(100))
    delivery_pincode = db.Column(db.String(10))
    
    expected_delivery_date = db.Column(db.Date)
    
    # GST
    place_of_supply = db.Column(db.String(100))
    is_igst = db.Column(db.Boolean, default=False)
    
    # Amounts
    subtotal = db.Column(db.Numeric(15, 2), default=0)
    discount_type = db.Column(db.String(10))
    discount_value = db.Column(db.Numeric(10, 2), default=0)
    discount_amount = db.Column(db.Numeric(15, 2), default=0)
    
    taxable_amount = db.Column(db.Numeric(15, 2), default=0)
    cgst_amount = db.Column(db.Numeric(15, 2), default=0)
    sgst_amount = db.Column(db.Numeric(15, 2), default=0)
    igst_amount = db.Column(db.Numeric(15, 2), default=0)
    cess_amount = db.Column(db.Numeric(15, 2), default=0)
    total_tax = db.Column(db.Numeric(15, 2), default=0)
    
    shipping_charges = db.Column(db.Numeric(15, 2), default=0)
    other_charges = db.Column(db.Numeric(15, 2), default=0)
    round_off = db.Column(db.Numeric(10, 2), default=0)
    
    grand_total = db.Column(db.Numeric(15, 2), default=0)
    amount_in_words = db.Column(db.String(500))
    
    currency = db.Column(db.String(3), default='INR')
    exchange_rate = db.Column(db.Numeric(10, 4), default=1)
    
    # Payment
    payment_terms = db.Column(db.Integer, default=0)
    payment_due_date = db.Column(db.Date)
    advance_amount = db.Column(db.Numeric(15, 2), default=0)
    
    # Status
    status = db.Column(db.String(20), default='draft')
    # draft, sent, confirmed, partially_received, received, cancelled
    
    payment_status = db.Column(db.String(20), default='unpaid')
    receipt_status = db.Column(db.String(20), default='pending')
    
    # Fulfillment
    total_items = db.Column(db.Integer, default=0)
    received_items = db.Column(db.Integer, default=0)
    
    # Warehouse
    warehouse_id = db.Column(db.Integer, db.ForeignKey('warehouses.id'))
    
    # Notes
    notes = db.Column(db.Text)
    supplier_notes = db.Column(db.Text)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    sent_at = db.Column(db.DateTime)
    confirmed_at = db.Column(db.DateTime)
    received_at = db.Column(db.DateTime)
    cancelled_at = db.Column(db.DateTime)
    
    # Relationships
    items = db.relationship('PurchaseOrderItem', backref='order', lazy='dynamic', cascade='all, delete-orphan')
    batches = db.relationship('BatchLot', backref='purchase_order', lazy='dynamic')

    __table_args__ = (
        db.UniqueConstraint('organization_id', 'order_number', name='uq_purchase_order_number'),
        db.Index('idx_po_supplier', 'organization_id', 'supplier_id'),
        db.Index('idx_po_date', 'organization_id', 'order_date'),
        db.Index('idx_po_status', 'organization_id', 'status'),
    )

    def __repr__(self):
        return f'<PurchaseOrder {self.order_number}>'


class PurchaseOrderItem(db.Model):
    """Purchase order line items"""
    __tablename__ = 'purchase_order_items'

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('purchase_orders.id'), nullable=False)
    
    line_number = db.Column(db.Integer, default=1)
    
    # Product
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'))
    variant_id = db.Column(db.Integer, db.ForeignKey('product_variants.id'))
    
    item_type = db.Column(db.String(20), default='product')
    sku = db.Column(db.String(50))
    hsn_code = db.Column(db.String(10))
    sac_code = db.Column(db.String(10))
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    
    # Quantity
    quantity = db.Column(db.Numeric(15, 3), nullable=False)
    unit_id = db.Column(db.Integer, db.ForeignKey('units.id'))
    unit_name = db.Column(db.String(20))
    
    # Receiving
    received_quantity = db.Column(db.Numeric(15, 3), default=0)
    rejected_quantity = db.Column(db.Numeric(15, 3), default=0)
    pending_quantity = db.Column(db.Numeric(15, 3), default=0)
    
    # Pricing
    rate = db.Column(db.Numeric(15, 2), nullable=False)
    
    discount_type = db.Column(db.String(10))
    discount_value = db.Column(db.Numeric(10, 2), default=0)
    discount_amount = db.Column(db.Numeric(15, 2), default=0)
    
    # Tax
    tax_rate_id = db.Column(db.Integer, db.ForeignKey('tax_rates.id'))
    tax_rate = db.Column(db.Numeric(5, 2), default=0)
    cgst_rate = db.Column(db.Numeric(5, 2), default=0)
    sgst_rate = db.Column(db.Numeric(5, 2), default=0)
    igst_rate = db.Column(db.Numeric(5, 2), default=0)
    cess_rate = db.Column(db.Numeric(5, 2), default=0)
    
    taxable_amount = db.Column(db.Numeric(15, 2), default=0)
    cgst_amount = db.Column(db.Numeric(15, 2), default=0)
    sgst_amount = db.Column(db.Numeric(15, 2), default=0)
    igst_amount = db.Column(db.Numeric(15, 2), default=0)
    cess_amount = db.Column(db.Numeric(15, 2), default=0)
    total_tax = db.Column(db.Numeric(15, 2), default=0)
    
    amount = db.Column(db.Numeric(15, 2), default=0)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    product = db.relationship('Product', foreign_keys=[product_id])