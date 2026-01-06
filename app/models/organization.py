from datetime import datetime
from config.database import db


class Organization(db.Model):
    """Multi-tenant organization/company model"""
    __tablename__ = 'organizations'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    legal_name = db.Column(db.String(200))
    organization_type = db.Column(db.String(50))  # company, shop, firm, etc.
    industry_type = db.Column(db.String(100))  # medical, agriculture, retail, etc.
    
    # Registration Details
    gstin = db.Column(db.String(15), unique=True)
    pan = db.Column(db.String(10))
    cin = db.Column(db.String(21))  # Company Identification Number
    tan = db.Column(db.String(10))  # Tax Deduction Account Number
    registration_number = db.Column(db.String(50))
    
    # Contact Information
    email = db.Column(db.String(120))
    phone = db.Column(db.String(20))
    mobile = db.Column(db.String(20))
    website = db.Column(db.String(200))
    
    # Address
    address_line1 = db.Column(db.String(200))
    address_line2 = db.Column(db.String(200))
    city = db.Column(db.String(100))
    state = db.Column(db.String(100))
    state_code = db.Column(db.String(2))  # For GST state code
    country = db.Column(db.String(100), default='India')
    pincode = db.Column(db.String(10))
    
    # Branding
    logo_url = db.Column(db.String(500))
    logo_data = db.Column(db.Text)  # Base64 encoded logo image
    signature_url = db.Column(db.String(500))
    
    # Currency & Locale
    currency = db.Column(db.String(3), default='INR')
    currency_symbol = db.Column(db.String(5), default='₹')
    date_format = db.Column(db.String(20), default='DD/MM/YYYY')
    timezone = db.Column(db.String(50), default='Asia/Kolkata')
    
    # Bank Details
    bank_name = db.Column(db.String(100))
    bank_account_number = db.Column(db.String(30))
    bank_ifsc = db.Column(db.String(11))
    bank_branch = db.Column(db.String(100))
    
    # Subscription/Plan (for SaaS model)
    plan_type = db.Column(db.String(20), default='free')  # free, basic, premium, enterprise
    plan_expires_at = db.Column(db.DateTime)
    max_users = db.Column(db.Integer, default=5)
    max_branches = db.Column(db.Integer, default=1)
    
    # Status
    is_active = db.Column(db.Boolean, default=True)
    is_verified = db.Column(db.Boolean, default=False)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    branches = db.relationship('Branch', backref='organization', lazy='dynamic')
    users = db.relationship('User', backref='organization', lazy='dynamic')
    financial_years = db.relationship('FinancialYear', backref='organization', lazy='dynamic')
    
    def __repr__(self):
        return f'<Organization {self.name}>'


class Branch(db.Model):
    """Branch/Location for multi-branch organizations"""
    __tablename__ = 'branches'

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    
    name = db.Column(db.String(200), nullable=False)
    code = db.Column(db.String(20))
    branch_type = db.Column(db.String(50))  # head_office, branch, warehouse, retail
    
    # Contact
    email = db.Column(db.String(120))
    phone = db.Column(db.String(20))
    mobile = db.Column(db.String(20))
    
    # Address
    address_line1 = db.Column(db.String(200))
    address_line2 = db.Column(db.String(200))
    city = db.Column(db.String(100))
    state = db.Column(db.String(100))
    state_code = db.Column(db.String(2))
    country = db.Column(db.String(100), default='India')
    pincode = db.Column(db.String(10))
    
    # GST (different branches might have different GSTIN)
    gstin = db.Column(db.String(15))
    
    is_head_office = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    warehouses = db.relationship('Warehouse', backref='branch', lazy='dynamic')
    
    def __repr__(self):
        return f'<Branch {self.name}>'


class FinancialYear(db.Model):
    """Financial year management"""
    __tablename__ = 'financial_years'

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    
    name = db.Column(db.String(20), nullable=False)  # e.g., "2024-25"
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    
    is_current = db.Column(db.Boolean, default=False)
    is_locked = db.Column(db.Boolean, default=False)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<FinancialYear {self.name}>'