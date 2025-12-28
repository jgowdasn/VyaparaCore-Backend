from datetime import datetime
from config.database import db


class PaymentMode(db.Model):
    """Payment modes (Cash, Bank Transfer, UPI, etc.)"""
    __tablename__ = 'payment_modes'

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    
    name = db.Column(db.String(50), nullable=False)  # Cash, Bank Transfer, UPI, Cheque
    code = db.Column(db.String(20))
    payment_type = db.Column(db.String(20))  # cash, bank, card, online, cheque
    
    # Associated bank account for this mode
    bank_account_id = db.Column(db.Integer, db.ForeignKey('bank_accounts.id'))
    
    is_active = db.Column(db.Boolean, default=True)
    is_default = db.Column(db.Boolean, default=False)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        db.UniqueConstraint('organization_id', 'code', name='uq_payment_mode_code'),
    )
    
    def __repr__(self):
        return f'<PaymentMode {self.name}>'


class BankAccount(db.Model):
    """Bank accounts for the organization"""
    __tablename__ = 'bank_accounts'

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    branch_id = db.Column(db.Integer, db.ForeignKey('branches.id'))
    
    account_name = db.Column(db.String(200), nullable=False)
    account_number = db.Column(db.String(30), nullable=False)
    bank_name = db.Column(db.String(100), nullable=False)
    ifsc_code = db.Column(db.String(11))
    branch_name = db.Column(db.String(100))
    
    account_type = db.Column(db.String(20))  # current, savings, cash
    
    # For UPI
    upi_id = db.Column(db.String(100))
    
    opening_balance = db.Column(db.Numeric(15, 2), default=0)
    current_balance = db.Column(db.Numeric(15, 2), default=0)
    
    is_primary = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    
    # For display on invoices
    show_on_invoice = db.Column(db.Boolean, default=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<BankAccount {self.account_name}>'


class Payment(db.Model):
    """Payment transactions (both receipts and payouts)"""
    __tablename__ = 'payments'

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    branch_id = db.Column(db.Integer, db.ForeignKey('branches.id'))
    financial_year_id = db.Column(db.Integer, db.ForeignKey('financial_years.id'))
    
    # Payment Reference
    payment_number = db.Column(db.String(30), nullable=False)
    payment_date = db.Column(db.Date, nullable=False)
    
    # Payment Type
    payment_type = db.Column(db.String(20), nullable=False)
    # receipt (from customer), payout (to supplier), refund_out, refund_in
    
    # Party
    party_type = db.Column(db.String(20))  # customer, supplier
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'))
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'))
    party_name = db.Column(db.String(200))
    
    # Invoice/Bill Reference
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id'))
    purchase_order_id = db.Column(db.Integer, db.ForeignKey('purchase_orders.id'))
    reference_number = db.Column(db.String(50))
    
    # Amount
    amount = db.Column(db.Numeric(15, 2), nullable=False)
    currency = db.Column(db.String(3), default='INR')
    exchange_rate = db.Column(db.Numeric(10, 4), default=1)
    amount_in_base_currency = db.Column(db.Numeric(15, 2))
    
    # Payment Mode
    payment_mode_id = db.Column(db.Integer, db.ForeignKey('payment_modes.id'))
    payment_mode_name = db.Column(db.String(50))
    
    # Bank Account
    bank_account_id = db.Column(db.Integer, db.ForeignKey('bank_accounts.id'))
    
    # Cheque Details (if payment by cheque)
    cheque_number = db.Column(db.String(20))
    cheque_date = db.Column(db.Date)
    bank_name = db.Column(db.String(100))
    
    # Transaction Reference (for online/UPI)
    transaction_id = db.Column(db.String(100))
    transaction_reference = db.Column(db.String(200))
    
    # Card Details (masked)
    card_type = db.Column(db.String(20))  # visa, mastercard, rupay
    card_last_four = db.Column(db.String(4))
    
    # TDS (Tax Deducted at Source)
    tds_applicable = db.Column(db.Boolean, default=False)
    tds_section = db.Column(db.String(20))
    tds_rate = db.Column(db.Numeric(5, 2), default=0)
    tds_amount = db.Column(db.Numeric(15, 2), default=0)
    
    # Write-off
    is_write_off = db.Column(db.Boolean, default=False)
    write_off_reason = db.Column(db.String(200))
    
    # Status
    status = db.Column(db.String(20), default='completed')
    # pending, completed, failed, cancelled, bounced (for cheques)
    
    # Notes
    notes = db.Column(db.Text)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    # Reconciliation
    is_reconciled = db.Column(db.Boolean, default=False)
    reconciled_at = db.Column(db.DateTime)
    reconciled_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    # Relationships
    customer = db.relationship('Customer', foreign_keys=[customer_id])
    supplier = db.relationship('Supplier', foreign_keys=[supplier_id])
    payment_mode = db.relationship('PaymentMode')
    bank_account = db.relationship('BankAccount')
    
    __table_args__ = (
        db.UniqueConstraint('organization_id', 'payment_number', 'financial_year_id',
                           name='uq_payment_number'),
        db.Index('idx_payment_customer', 'organization_id', 'customer_id'),
        db.Index('idx_payment_supplier', 'organization_id', 'supplier_id'),
        db.Index('idx_payment_date', 'organization_id', 'payment_date'),
        db.Index('idx_payment_type', 'organization_id', 'payment_type'),
    )
    
    def __repr__(self):
        return f'<Payment {self.payment_number}>'


class PaymentAllocation(db.Model):
    """Allocation of payment across multiple invoices"""
    __tablename__ = 'payment_allocations'

    id = db.Column(db.Integer, primary_key=True)
    payment_id = db.Column(db.Integer, db.ForeignKey('payments.id'), nullable=False)
    
    # Invoice/Document being paid
    document_type = db.Column(db.String(20), nullable=False)  # invoice, credit_note, debit_note
    document_id = db.Column(db.Integer, nullable=False)
    document_number = db.Column(db.String(30))
    
    # Allocation
    allocated_amount = db.Column(db.Numeric(15, 2), nullable=False)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship
    payment = db.relationship('Payment', backref='allocations')
    
    __table_args__ = (
        db.Index('idx_payment_allocation', 'payment_id', 'document_type', 'document_id'),
    )