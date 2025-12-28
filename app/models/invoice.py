from datetime import datetime
from config.database import db


class Invoice(db.Model):
    """Sales Invoice / Bill model"""
    __tablename__ = 'invoices'

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    branch_id = db.Column(db.Integer, db.ForeignKey('branches.id'))
    financial_year_id = db.Column(db.Integer, db.ForeignKey('financial_years.id'))
    
    # Invoice Details
    invoice_number = db.Column(db.String(30), nullable=False)
    invoice_date = db.Column(db.Date, nullable=False)
    due_date = db.Column(db.Date)
    reference_number = db.Column(db.String(50))
    
    # Invoice Type
    invoice_type = db.Column(db.String(20), default='tax_invoice')
    # tax_invoice, retail_invoice, proforma, bill_of_supply, export
    
    # Source
    source_type = db.Column(db.String(20))  # sales_order, direct
    sales_order_id = db.Column(db.Integer, db.ForeignKey('sales_orders.id'))
    
    # Customer
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)
    customer_name = db.Column(db.String(200))
    customer_gstin = db.Column(db.String(15))
    customer_pan = db.Column(db.String(10))
    
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
    
    # GST Details
    place_of_supply = db.Column(db.String(100))
    is_igst = db.Column(db.Boolean, default=False)
    reverse_charge = db.Column(db.Boolean, default=False)
    
    # E-Invoice (India)
    is_einvoice = db.Column(db.Boolean, default=False)
    irn = db.Column(db.String(100))  # Invoice Reference Number
    irn_date = db.Column(db.DateTime)
    qr_code = db.Column(db.Text)  # Base64 QR code
    ack_number = db.Column(db.String(50))
    ack_date = db.Column(db.DateTime)
    
    # E-Way Bill
    eway_bill_number = db.Column(db.String(20))
    eway_bill_date = db.Column(db.DateTime)
    eway_bill_valid_until = db.Column(db.DateTime)
    
    # Transport Details
    transport_mode = db.Column(db.String(20))  # road, rail, air, ship
    vehicle_number = db.Column(db.String(20))
    transporter_name = db.Column(db.String(200))
    transporter_gstin = db.Column(db.String(15))
    lr_number = db.Column(db.String(50))  # Lorry Receipt
    lr_date = db.Column(db.Date)
    
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
    
    # TCS/TDS (for specific industries)
    tcs_rate = db.Column(db.Numeric(5, 2), default=0)
    tcs_amount = db.Column(db.Numeric(15, 2), default=0)
    tds_rate = db.Column(db.Numeric(5, 2), default=0)
    tds_amount = db.Column(db.Numeric(15, 2), default=0)
    
    shipping_charges = db.Column(db.Numeric(15, 2), default=0)
    packaging_charges = db.Column(db.Numeric(15, 2), default=0)
    other_charges = db.Column(db.Numeric(15, 2), default=0)
    round_off = db.Column(db.Numeric(10, 2), default=0)
    
    grand_total = db.Column(db.Numeric(15, 2), default=0)
    amount_in_words = db.Column(db.String(500))
    
    currency = db.Column(db.String(3), default='INR')
    exchange_rate = db.Column(db.Numeric(10, 4), default=1)
    
    # Payment Tracking
    paid_amount = db.Column(db.Numeric(15, 2), default=0)
    balance_due = db.Column(db.Numeric(15, 2), default=0)
    write_off_amount = db.Column(db.Numeric(15, 2), default=0)
    
    # Credit Note Adjustments
    credit_note_amount = db.Column(db.Numeric(15, 2), default=0)
    
    # Status
    status = db.Column(db.String(20), default='draft')
    # draft, sent, viewed, partial, paid, overdue, void, cancelled
    
    payment_status = db.Column(db.String(20), default='unpaid')
    # unpaid, partial, paid, overdue, written_off
    
    # Notes
    notes = db.Column(db.Text)
    customer_notes = db.Column(db.Text)
    terms_and_conditions = db.Column(db.Text)
    
    # Attachments
    attachments = db.Column(db.JSON, default=list)
    
    # Sales Info
    salesperson_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    # Warehouse
    warehouse_id = db.Column(db.Integer, db.ForeignKey('warehouses.id'))
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    sent_at = db.Column(db.DateTime)
    viewed_at = db.Column(db.DateTime)
    paid_at = db.Column(db.DateTime)
    cancelled_at = db.Column(db.DateTime)
    
    # Relationships
    customer = db.relationship('Customer', foreign_keys=[customer_id])
    items = db.relationship('InvoiceItem', backref='invoice', lazy='dynamic', cascade='all, delete-orphan')
    payments = db.relationship('Payment', backref='invoice', lazy='dynamic')
    credit_notes = db.relationship('CreditNote', backref='invoice', lazy='dynamic')
    
    __table_args__ = (
        db.UniqueConstraint('organization_id', 'invoice_number', 'financial_year_id', 
                           name='uq_invoice_number'),
        db.Index('idx_invoice_customer', 'organization_id', 'customer_id'),
        db.Index('idx_invoice_date', 'organization_id', 'invoice_date'),
        db.Index('idx_invoice_status', 'organization_id', 'status'),
        db.Index('idx_invoice_payment_status', 'organization_id', 'payment_status'),
    )
    
    def __repr__(self):
        return f'<Invoice {self.invoice_number}>'


class InvoiceItem(db.Model):
    """Invoice line items"""
    __tablename__ = 'invoice_items'

    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id'), nullable=False)
    
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
    
    # Returned quantity (for tracking returns)
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
    
    # Batch
    batch_id = db.Column(db.Integer, db.ForeignKey('batch_lots.id'))
    batch_number = db.Column(db.String(50))
    expiry_date = db.Column(db.Date)
    
    # Serial Numbers (for serialized items)
    serial_numbers = db.Column(db.JSON, default=list)
    
    # From Sales Order
    sales_order_item_id = db.Column(db.Integer, db.ForeignKey('sales_order_items.id'))

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    product = db.relationship('Product', foreign_keys=[product_id])


class CreditNote(db.Model):
    """Credit Note for sales returns"""
    __tablename__ = 'credit_notes'

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    branch_id = db.Column(db.Integer, db.ForeignKey('branches.id'))
    financial_year_id = db.Column(db.Integer, db.ForeignKey('financial_years.id'))
    
    # Credit Note Details
    credit_note_number = db.Column(db.String(30), nullable=False)
    credit_note_date = db.Column(db.Date, nullable=False)
    
    # Original Invoice
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id'))
    invoice_number = db.Column(db.String(30))
    invoice_date = db.Column(db.Date)
    
    # Reason
    reason = db.Column(db.String(50), nullable=False)
    # return, discount, price_correction, defective, other
    reason_description = db.Column(db.Text)
    
    # Customer
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)
    customer_name = db.Column(db.String(200))
    customer_gstin = db.Column(db.String(15))
    
    # Address
    billing_address_line1 = db.Column(db.String(200))
    billing_address_line2 = db.Column(db.String(200))
    billing_city = db.Column(db.String(100))
    billing_state = db.Column(db.String(100))
    billing_state_code = db.Column(db.String(2))
    billing_country = db.Column(db.String(100))
    billing_pincode = db.Column(db.String(10))
    
    # GST
    place_of_supply = db.Column(db.String(100))
    is_igst = db.Column(db.Boolean, default=False)
    
    # Amounts
    subtotal = db.Column(db.Numeric(15, 2), default=0)
    taxable_amount = db.Column(db.Numeric(15, 2), default=0)
    cgst_amount = db.Column(db.Numeric(15, 2), default=0)
    sgst_amount = db.Column(db.Numeric(15, 2), default=0)
    igst_amount = db.Column(db.Numeric(15, 2), default=0)
    cess_amount = db.Column(db.Numeric(15, 2), default=0)
    total_tax = db.Column(db.Numeric(15, 2), default=0)
    round_off = db.Column(db.Numeric(10, 2), default=0)
    grand_total = db.Column(db.Numeric(15, 2), default=0)
    
    # Adjustment
    adjusted_amount = db.Column(db.Numeric(15, 2), default=0)  # Applied to invoices
    refunded_amount = db.Column(db.Numeric(15, 2), default=0)  # Refunded to customer
    balance_amount = db.Column(db.Numeric(15, 2), default=0)
    
    # Status
    status = db.Column(db.String(20), default='draft')
    # draft, approved, adjusted, refunded, cancelled
    
    notes = db.Column(db.Text)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    # Relationships
    customer = db.relationship('Customer', foreign_keys=[customer_id])
    original_invoice = db.relationship('Invoice', foreign_keys=[invoice_id])
    items = db.relationship('CreditNoteItem', backref='credit_note', lazy='dynamic',
                           cascade='all, delete-orphan')

    __table_args__ = (
        db.UniqueConstraint('organization_id', 'credit_note_number', 'financial_year_id',
                           name='uq_credit_note_number'),
    )


class CreditNoteItem(db.Model):
    """Credit Note line items"""
    __tablename__ = 'credit_note_items'

    id = db.Column(db.Integer, primary_key=True)
    credit_note_id = db.Column(db.Integer, db.ForeignKey('credit_notes.id'), nullable=False)
    
    line_number = db.Column(db.Integer, default=1)
    
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'))
    variant_id = db.Column(db.Integer, db.ForeignKey('product_variants.id'))
    invoice_item_id = db.Column(db.Integer, db.ForeignKey('invoice_items.id'))
    
    sku = db.Column(db.String(50))
    hsn_code = db.Column(db.String(10))
    sac_code = db.Column(db.String(10))
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    
    quantity = db.Column(db.Numeric(15, 3), nullable=False)
    unit_name = db.Column(db.String(20))
    
    rate = db.Column(db.Numeric(15, 2), nullable=False)
    
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

    batch_id = db.Column(db.Integer, db.ForeignKey('batch_lots.id'))

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    product = db.relationship('Product', foreign_keys=[product_id])


class DebitNote(db.Model):
    """Debit Note for purchase returns"""
    __tablename__ = 'debit_notes'

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    branch_id = db.Column(db.Integer, db.ForeignKey('branches.id'))
    financial_year_id = db.Column(db.Integer, db.ForeignKey('financial_years.id'))
    
    debit_note_number = db.Column(db.String(30), nullable=False)
    debit_note_date = db.Column(db.Date, nullable=False)
    
    # Original Purchase
    purchase_order_id = db.Column(db.Integer, db.ForeignKey('purchase_orders.id'))
    supplier_invoice_number = db.Column(db.String(50))
    supplier_invoice_date = db.Column(db.Date)
    
    reason = db.Column(db.String(50), nullable=False)
    reason_description = db.Column(db.Text)
    
    # Supplier
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'), nullable=False)
    supplier_name = db.Column(db.String(200))
    supplier_gstin = db.Column(db.String(15))
    
    # Address
    address_line1 = db.Column(db.String(200))
    address_line2 = db.Column(db.String(200))
    city = db.Column(db.String(100))
    state = db.Column(db.String(100))
    state_code = db.Column(db.String(2))
    country = db.Column(db.String(100))
    pincode = db.Column(db.String(10))
    
    # GST
    place_of_supply = db.Column(db.String(100))
    is_igst = db.Column(db.Boolean, default=False)
    
    # Amounts
    subtotal = db.Column(db.Numeric(15, 2), default=0)
    taxable_amount = db.Column(db.Numeric(15, 2), default=0)
    cgst_amount = db.Column(db.Numeric(15, 2), default=0)
    sgst_amount = db.Column(db.Numeric(15, 2), default=0)
    igst_amount = db.Column(db.Numeric(15, 2), default=0)
    cess_amount = db.Column(db.Numeric(15, 2), default=0)
    total_tax = db.Column(db.Numeric(15, 2), default=0)
    round_off = db.Column(db.Numeric(10, 2), default=0)
    grand_total = db.Column(db.Numeric(15, 2), default=0)
    
    # Adjustment
    adjusted_amount = db.Column(db.Numeric(15, 2), default=0)
    refunded_amount = db.Column(db.Numeric(15, 2), default=0)
    balance_amount = db.Column(db.Numeric(15, 2), default=0)
    
    status = db.Column(db.String(20), default='draft')
    
    notes = db.Column(db.Text)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    items = db.relationship('DebitNoteItem', backref='debit_note', lazy='dynamic',
                           cascade='all, delete-orphan')
    supplier = db.relationship('Supplier', foreign_keys=[supplier_id])

    __table_args__ = (
        db.UniqueConstraint('organization_id', 'debit_note_number', 'financial_year_id',
                           name='uq_debit_note_number'),
    )


class DebitNoteItem(db.Model):
    """Debit Note line items"""
    __tablename__ = 'debit_note_items'

    id = db.Column(db.Integer, primary_key=True)
    debit_note_id = db.Column(db.Integer, db.ForeignKey('debit_notes.id'), nullable=False)
    
    line_number = db.Column(db.Integer, default=1)
    
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'))
    variant_id = db.Column(db.Integer, db.ForeignKey('product_variants.id'))
    
    sku = db.Column(db.String(50))
    hsn_code = db.Column(db.String(10))
    sac_code = db.Column(db.String(10))
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    
    quantity = db.Column(db.Numeric(15, 3), nullable=False)
    unit_name = db.Column(db.String(20))
    
    rate = db.Column(db.Numeric(15, 2), nullable=False)
    
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
    
    batch_id = db.Column(db.Integer, db.ForeignKey('batch_lots.id'))
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)