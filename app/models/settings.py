from datetime import datetime
from config.database import db


class OrganizationSettings(db.Model):
    """Organization-wide settings"""
    __tablename__ = 'organization_settings'

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False, unique=True)
    
    # General Settings
    date_format = db.Column(db.String(20), default='DD/MM/YYYY')
    time_format = db.Column(db.String(10), default='12h')  # 12h, 24h
    timezone = db.Column(db.String(50), default='Asia/Kolkata')
    
    # Number Formats
    decimal_separator = db.Column(db.String(1), default='.')
    thousand_separator = db.Column(db.String(1), default=',')
    decimal_places = db.Column(db.Integer, default=2)
    
    # Currency
    base_currency = db.Column(db.String(3), default='INR')
    currency_symbol = db.Column(db.String(5), default='₹')
    currency_position = db.Column(db.String(10), default='before')  # before, after
    
    # GST Settings
    gst_enabled = db.Column(db.Boolean, default=True)
    default_tax_type = db.Column(db.String(10), default='exclusive')  # inclusive, exclusive
    round_off_enabled = db.Column(db.Boolean, default=True)
    round_off_to = db.Column(db.Numeric(5, 2), default=1)  # Round to nearest 1
    
    # Inventory Settings
    negative_stock_allowed = db.Column(db.Boolean, default=False)
    low_stock_alert_enabled = db.Column(db.Boolean, default=True)
    expiry_alert_days = db.Column(db.Integer, default=30)  # Alert before expiry
    default_warehouse_id = db.Column(db.Integer, db.ForeignKey('warehouses.id'))
    
    # Sales Settings
    default_payment_terms = db.Column(db.Integer, default=0)  # Days
    quotation_validity_days = db.Column(db.Integer, default=30)
    auto_generate_sales_order = db.Column(db.Boolean, default=False)
    
    # Purchase Settings
    default_purchase_payment_terms = db.Column(db.Integer, default=0)
    
    # Email Settings
    email_enabled = db.Column(db.Boolean, default=False)
    smtp_host = db.Column(db.String(200))
    smtp_port = db.Column(db.Integer)
    smtp_username = db.Column(db.String(200))
    smtp_password = db.Column(db.String(500))  # Encrypted
    smtp_encryption = db.Column(db.String(10))  # tls, ssl
    email_from_name = db.Column(db.String(200))
    email_from_address = db.Column(db.String(200))
    
    # Notification Settings
    email_on_quotation_accept = db.Column(db.Boolean, default=True)
    email_on_payment_received = db.Column(db.Boolean, default=True)
    low_stock_email_alert = db.Column(db.Boolean, default=True)
    
    # Custom Fields Configuration
    custom_fields_config = db.Column(db.JSON, default=dict)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class InvoiceSettings(db.Model):
    """Invoice/Document-specific settings"""
    __tablename__ = 'invoice_settings'

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False, unique=True)
    
    # Invoice Format
    invoice_prefix = db.Column(db.String(10), default='INV-')
    invoice_suffix = db.Column(db.String(10))
    invoice_number_length = db.Column(db.Integer, default=5)  # Padded with zeros
    reset_sequence = db.Column(db.String(20), default='yearly')  # never, yearly, monthly
    
    # Invoice Display
    show_logo = db.Column(db.Boolean, default=True)
    show_signature = db.Column(db.Boolean, default=True)
    show_bank_details = db.Column(db.Boolean, default=True)
    show_qr_code = db.Column(db.Boolean, default=False)
    
    # Default Terms
    default_terms = db.Column(db.Text)
    default_notes = db.Column(db.Text)
    default_footer = db.Column(db.Text)
    
    # Other Documents
    quotation_prefix = db.Column(db.String(10), default='QTN-')
    sales_order_prefix = db.Column(db.String(10), default='SO-')
    purchase_order_prefix = db.Column(db.String(10), default='PO-')
    credit_note_prefix = db.Column(db.String(10), default='CN-')
    debit_note_prefix = db.Column(db.String(10), default='DN-')
    payment_prefix = db.Column(db.String(10), default='REC-')
    
    # E-Invoice Settings (India)
    einvoice_enabled = db.Column(db.Boolean, default=False)
    einvoice_username = db.Column(db.String(100))
    einvoice_password = db.Column(db.String(500))  # Encrypted
    einvoice_environment = db.Column(db.String(20), default='sandbox')  # sandbox, production
    
    # E-Way Bill Settings
    eway_bill_enabled = db.Column(db.Boolean, default=False)
    auto_generate_eway_bill = db.Column(db.Boolean, default=False)
    eway_bill_threshold = db.Column(db.Numeric(15, 2), default=50000)
    
    # Print Settings
    print_copies = db.Column(db.Integer, default=1)
    paper_size = db.Column(db.String(10), default='A4')  # A4, A5, Letter
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SequenceNumber(db.Model):
    """Sequence numbers for documents"""
    __tablename__ = 'sequence_numbers'

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    branch_id = db.Column(db.Integer, db.ForeignKey('branches.id'))
    financial_year_id = db.Column(db.Integer, db.ForeignKey('financial_years.id'))
    
    document_type = db.Column(db.String(30), nullable=False)
    # invoice, quotation, sales_order, purchase_order, credit_note, debit_note, payment, stock_txn
    
    prefix = db.Column(db.String(20))
    suffix = db.Column(db.String(20))
    current_number = db.Column(db.Integer, default=0)
    number_length = db.Column(db.Integer, default=5)
    
    last_generated_at = db.Column(db.DateTime)
    
    __table_args__ = (
        db.UniqueConstraint('organization_id', 'branch_id', 'financial_year_id', 'document_type',
                           name='uq_sequence_number'),
    )
    
    def get_next_number(self):
        """Generate next number in sequence"""
        self.current_number += 1
        self.last_generated_at = datetime.utcnow()
        
        number_str = str(self.current_number).zfill(self.number_length)
        
        result = ''
        if self.prefix:
            result += self.prefix
        result += number_str
        if self.suffix:
            result += self.suffix
        
        return result


class EmailTemplate(db.Model):
    """Email templates for various notifications"""
    __tablename__ = 'email_templates'

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    
    name = db.Column(db.String(100), nullable=False)
    code = db.Column(db.String(50), nullable=False)
    # invoice_created, quotation_sent, payment_received, order_confirmed, etc.
    
    subject = db.Column(db.String(500), nullable=False)
    body_html = db.Column(db.Text, nullable=False)
    body_text = db.Column(db.Text)  # Plain text version
    
    # Available variables/placeholders for this template
    available_variables = db.Column(db.JSON, default=list)
    
    is_active = db.Column(db.Boolean, default=True)
    is_default = db.Column(db.Boolean, default=False)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        db.UniqueConstraint('organization_id', 'code', name='uq_email_template_code'),
    )


class PrintTemplate(db.Model):
    """Print templates for documents (Invoice, Quotation, etc.)"""
    __tablename__ = 'print_templates'

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    
    name = db.Column(db.String(100), nullable=False)
    document_type = db.Column(db.String(30), nullable=False)
    # invoice, quotation, sales_order, purchase_order, delivery_challan
    
    # Template Content (HTML with placeholders)
    template_html = db.Column(db.Text, nullable=False)
    
    # Template Styling
    custom_css = db.Column(db.Text)
    
    # Paper Settings
    paper_size = db.Column(db.String(10), default='A4')
    orientation = db.Column(db.String(10), default='portrait')  # portrait, landscape
    margin_top = db.Column(db.Integer, default=20)  # mm
    margin_bottom = db.Column(db.Integer, default=20)
    margin_left = db.Column(db.Integer, default=15)
    margin_right = db.Column(db.Integer, default=15)
    
    # Layout Options
    header_height = db.Column(db.Integer, default=100)  # pixels
    footer_height = db.Column(db.Integer, default=50)
    
    is_active = db.Column(db.Boolean, default=True)
    is_default = db.Column(db.Boolean, default=False)
    
    # Preview Image
    preview_image_url = db.Column(db.String(500))
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    __table_args__ = (
        db.Index('idx_print_template', 'organization_id', 'document_type'),
    )