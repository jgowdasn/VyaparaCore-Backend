from datetime import datetime
from config.database import db


class Supplier(db.Model):
    """Supplier/Vendor model"""
    __tablename__ = 'suppliers'

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    
    # Basic Info
    supplier_code = db.Column(db.String(20))
    name = db.Column(db.String(200), nullable=False)
    display_name = db.Column(db.String(200))
    supplier_type = db.Column(db.String(20), default='business')  # business, individual
    
    # Contact
    email = db.Column(db.String(120))
    phone = db.Column(db.String(20))
    mobile = db.Column(db.String(20))
    website = db.Column(db.String(200))
    
    # Tax Details
    gstin = db.Column(db.String(15))
    pan = db.Column(db.String(10))
    gst_treatment = db.Column(db.String(30))
    tds_applicable = db.Column(db.Boolean, default=False)
    tds_section = db.Column(db.String(20))
    
    # Address
    address_line1 = db.Column(db.String(200))
    address_line2 = db.Column(db.String(200))
    city = db.Column(db.String(100))
    state = db.Column(db.String(100))
    state_code = db.Column(db.String(2))
    country = db.Column(db.String(100), default='India')
    pincode = db.Column(db.String(10))
    
    # Payment Terms
    payment_terms = db.Column(db.Integer, default=0)
    opening_balance = db.Column(db.Numeric(15, 2), default=0)
    current_balance = db.Column(db.Numeric(15, 2), default=0)
    
    # Bank Details
    bank_name = db.Column(db.String(100))
    bank_account_number = db.Column(db.String(30))
    bank_ifsc = db.Column(db.String(11))
    bank_branch = db.Column(db.String(100))
    
    # Additional Info
    notes = db.Column(db.Text)
    tags = db.Column(db.JSON, default=list)
    custom_fields = db.Column(db.JSON, default=dict)
    
    # Status
    is_active = db.Column(db.Boolean, default=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    # Relationships
    addresses = db.relationship('SupplierAddress', backref='supplier', lazy='dynamic', cascade='all, delete-orphan')
    contacts = db.relationship('SupplierContact', backref='supplier', lazy='dynamic', cascade='all, delete-orphan')
    purchase_orders = db.relationship('PurchaseOrder', backref='supplier', lazy='dynamic')
    
    __table_args__ = (
        db.UniqueConstraint('organization_id', 'supplier_code', name='uq_supplier_org_code'),
        db.Index('idx_supplier_name', 'organization_id', 'name'),
    )
    
    def __repr__(self):
        return f'<Supplier {self.name}>'


class SupplierAddress(db.Model):
    """Multiple addresses for suppliers"""
    __tablename__ = 'supplier_addresses'

    id = db.Column(db.Integer, primary_key=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'), nullable=False)
    
    address_type = db.Column(db.String(20), default='other')
    label = db.Column(db.String(100))
    
    address_line1 = db.Column(db.String(200))
    address_line2 = db.Column(db.String(200))
    city = db.Column(db.String(100))
    state = db.Column(db.String(100))
    state_code = db.Column(db.String(2))
    country = db.Column(db.String(100), default='India')
    pincode = db.Column(db.String(10))
    
    is_default = db.Column(db.Boolean, default=False)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SupplierContact(db.Model):
    """Multiple contact persons for suppliers"""
    __tablename__ = 'supplier_contacts'

    id = db.Column(db.Integer, primary_key=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'), nullable=False)
    
    salutation = db.Column(db.String(10))
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100))
    designation = db.Column(db.String(100))
    department = db.Column(db.String(100))
    
    email = db.Column(db.String(120))
    phone = db.Column(db.String(20))
    mobile = db.Column(db.String(20))
    
    is_primary = db.Column(db.Boolean, default=False)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name or ''}".strip()