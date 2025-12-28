"""Customer models for VyaparaCore"""
from datetime import datetime
from config.database import db


class Customer(db.Model):
    """Customer/Client model"""
    __tablename__ = 'customers'

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    
    # Basic Info
    name = db.Column(db.String(200), nullable=False)
    code = db.Column(db.String(50))
    customer_type = db.Column(db.String(20), default='business')  # business, individual
    
    # GST Details
    gst_treatment = db.Column(db.String(50), default='regular')
    gstin = db.Column(db.String(15))
    pan = db.Column(db.String(10))
    
    # Contact Info
    email = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    mobile = db.Column(db.String(20))
    website = db.Column(db.String(200))
    
    # Billing Address
    billing_address_line1 = db.Column(db.String(200))
    billing_address_line2 = db.Column(db.String(200))
    billing_city = db.Column(db.String(100))
    billing_state = db.Column(db.String(100))
    billing_state_code = db.Column(db.String(2))
    billing_country = db.Column(db.String(100), default='India')
    billing_pincode = db.Column(db.String(10))
    
    # Shipping Address
    shipping_address_line1 = db.Column(db.String(200))
    shipping_address_line2 = db.Column(db.String(200))
    shipping_city = db.Column(db.String(100))
    shipping_state = db.Column(db.String(100))
    shipping_state_code = db.Column(db.String(2))
    shipping_country = db.Column(db.String(100), default='India')
    shipping_pincode = db.Column(db.String(10))
    
    # Financial
    credit_limit = db.Column(db.Numeric(15, 2), default=0)
    payment_terms = db.Column(db.Integer, default=30)
    opening_balance = db.Column(db.Numeric(15, 2), default=0)
    outstanding_amount = db.Column(db.Numeric(15, 2), default=0)
    
    # Pricing
    price_list_id = db.Column(db.Integer, db.ForeignKey('price_lists.id'))
    discount_percent = db.Column(db.Numeric(5, 2), default=0)
    
    # Additional
    notes = db.Column(db.Text)
    tags = db.Column(db.JSON, default=list)
    custom_fields = db.Column(db.JSON, default=dict)
    
    # Status
    is_active = db.Column(db.Boolean, default=True)
    
    # Audit
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    # Relationships
    addresses = db.relationship('CustomerAddress', backref='customer', lazy='dynamic', cascade='all, delete-orphan')
    contacts = db.relationship('CustomerContact', backref='customer', lazy='dynamic', cascade='all, delete-orphan')
    
    __table_args__ = (
        db.Index('ix_customers_org_code', 'organization_id', 'code'),
        db.Index('ix_customers_org_name', 'organization_id', 'name'),
        db.UniqueConstraint('organization_id', 'code', name='uq_customers_org_code'),
    )

    def __repr__(self):
        return f'<Customer {self.name}>'


class CustomerAddress(db.Model):
    """Customer additional addresses"""
    __tablename__ = 'customer_addresses'

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)
    
    address_type = db.Column(db.String(20), default='shipping')
    label = db.Column(db.String(50))
    
    address_line1 = db.Column(db.String(200))
    address_line2 = db.Column(db.String(200))
    city = db.Column(db.String(100))
    state = db.Column(db.String(100))
    state_code = db.Column(db.String(2))
    country = db.Column(db.String(100), default='India')
    pincode = db.Column(db.String(10))
    
    contact_person = db.Column(db.String(100))
    contact_phone = db.Column(db.String(20))
    
    is_default = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<CustomerAddress {self.label}>'


class CustomerContact(db.Model):
    """Customer contact persons"""
    __tablename__ = 'customer_contacts'

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)
    
    name = db.Column(db.String(100), nullable=False)
    designation = db.Column(db.String(100))
    department = db.Column(db.String(100))
    
    email = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    mobile = db.Column(db.String(20))
    
    is_primary = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    
    notes = db.Column(db.Text)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<CustomerContact {self.name}>'