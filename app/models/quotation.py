from datetime import datetime
from config.database import db


class Quotation(db.Model):
    """Quotation/Estimate model"""
    __tablename__ = 'quotations'

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    branch_id = db.Column(db.Integer, db.ForeignKey('branches.id'))
    
    # Quotation Details
    quotation_number = db.Column(db.String(30), nullable=False)
    quotation_date = db.Column(db.Date, nullable=False)
    reference_number = db.Column(db.String(50))  # Customer's reference
    
    # Validity
    valid_until = db.Column(db.Date)
    
    # Customer
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)
    customer_name = db.Column(db.String(200))  # Denormalized for quick access
    
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
    is_igst = db.Column(db.Boolean, default=False)  # IGST or CGST+SGST
    
    # Amounts
    subtotal = db.Column(db.Numeric(15, 2), default=0)
    discount_type = db.Column(db.String(10))  # percentage, fixed
    discount_value = db.Column(db.Numeric(10, 2), default=0)
    discount_amount = db.Column(db.Numeric(15, 2), default=0)
    
    # Tax Amounts
    taxable_amount = db.Column(db.Numeric(15, 2), default=0)
    cgst_amount = db.Column(db.Numeric(15, 2), default=0)
    sgst_amount = db.Column(db.Numeric(15, 2), default=0)
    igst_amount = db.Column(db.Numeric(15, 2), default=0)
    cess_amount = db.Column(db.Numeric(15, 2), default=0)
    total_tax = db.Column(db.Numeric(15, 2), default=0)
    
    # Other Charges
    shipping_charges = db.Column(db.Numeric(15, 2), default=0)
    packaging_charges = db.Column(db.Numeric(15, 2), default=0)
    other_charges = db.Column(db.Numeric(15, 2), default=0)
    round_off = db.Column(db.Numeric(10, 2), default=0)
    
    # Total
    grand_total = db.Column(db.Numeric(15, 2), default=0)
    amount_in_words = db.Column(db.String(500))
    
    # Currency
    currency = db.Column(db.String(3), default='INR')
    exchange_rate = db.Column(db.Numeric(10, 4), default=1)
    
    # Status
    status = db.Column(db.String(20), default='draft')  # draft, sent, accepted, rejected, expired, converted
    
    # Conversion Tracking
    converted_to_order = db.Column(db.Boolean, default=False)
    sales_order_id = db.Column(db.Integer, db.ForeignKey('sales_orders.id', use_alter=True, name='fk_quotation_sales_order'))
    
    # Notes
    subject = db.Column(db.String(500))
    notes = db.Column(db.Text)  # Internal notes
    customer_notes = db.Column(db.Text)  # Visible to customer
    
    # Attachments
    attachments = db.Column(db.JSON, default=list)
    
    # Sales Info
    salesperson_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    sent_at = db.Column(db.DateTime)
    accepted_at = db.Column(db.DateTime)
    rejected_at = db.Column(db.DateTime)
    rejection_reason = db.Column(db.String(500))
    converted_at = db.Column(db.DateTime)

    # Relationships
    items = db.relationship('QuotationItem', backref='quotation', lazy='dynamic', cascade='all, delete-orphan')
    terms = db.relationship('QuotationTerms', backref='quotation', lazy='dynamic', cascade='all, delete-orphan')
    
    __table_args__ = (
        db.UniqueConstraint('organization_id', 'quotation_number', name='uq_quotation_number'),
        db.Index('idx_quotation_customer', 'organization_id', 'customer_id'),
        db.Index('idx_quotation_date', 'organization_id', 'quotation_date'),
        db.Index('idx_quotation_status', 'organization_id', 'status'),
    )
    
    def __repr__(self):
        return f'<Quotation {self.quotation_number}>'


class QuotationItem(db.Model):
    """Quotation line items"""
    __tablename__ = 'quotation_items'

    id = db.Column(db.Integer, primary_key=True)
    quotation_id = db.Column(db.Integer, db.ForeignKey('quotations.id'), nullable=False)
    
    # Line Number
    line_number = db.Column(db.Integer, default=1)
    
    # Product
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'))
    variant_id = db.Column(db.Integer, db.ForeignKey('product_variants.id'))
    
    # Item Details (can be custom item without product_id)
    item_type = db.Column(db.String(20), default='product')  # product, service, custom
    sku = db.Column(db.String(50))
    hsn_code = db.Column(db.String(10))
    sac_code = db.Column(db.String(10))
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    
    # Quantity & Unit
    quantity = db.Column(db.Numeric(15, 3), nullable=False)
    unit_id = db.Column(db.Integer, db.ForeignKey('units.id'))
    unit_name = db.Column(db.String(20))
    
    # Pricing
    rate = db.Column(db.Numeric(15, 2), nullable=False)  # Unit price
    mrp = db.Column(db.Numeric(15, 2))
    
    # Discount
    discount_type = db.Column(db.String(10))  # percentage, fixed
    discount_value = db.Column(db.Numeric(10, 2), default=0)
    discount_amount = db.Column(db.Numeric(15, 2), default=0)
    
    # Tax
    tax_rate_id = db.Column(db.Integer, db.ForeignKey('tax_rates.id'))
    tax_rate = db.Column(db.Numeric(5, 2), default=0)
    cgst_rate = db.Column(db.Numeric(5, 2), default=0)
    sgst_rate = db.Column(db.Numeric(5, 2), default=0)
    igst_rate = db.Column(db.Numeric(5, 2), default=0)
    cess_rate = db.Column(db.Numeric(5, 2), default=0)
    
    # Calculated Amounts
    taxable_amount = db.Column(db.Numeric(15, 2), default=0)
    cgst_amount = db.Column(db.Numeric(15, 2), default=0)
    sgst_amount = db.Column(db.Numeric(15, 2), default=0)
    igst_amount = db.Column(db.Numeric(15, 2), default=0)
    cess_amount = db.Column(db.Numeric(15, 2), default=0)
    total_tax = db.Column(db.Numeric(15, 2), default=0)
    
    # Total
    amount = db.Column(db.Numeric(15, 2), default=0)  # Final amount including tax
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<QuotationItem {self.name}>'


class QuotationTerms(db.Model):
    """Terms and conditions for quotation"""
    __tablename__ = 'quotation_terms'

    id = db.Column(db.Integer, primary_key=True)
    quotation_id = db.Column(db.Integer, db.ForeignKey('quotations.id'), nullable=False)
    
    term_type = db.Column(db.String(50))  # payment, delivery, warranty, etc.
    title = db.Column(db.String(200))
    description = db.Column(db.Text, nullable=False)
    display_order = db.Column(db.Integer, default=0)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)