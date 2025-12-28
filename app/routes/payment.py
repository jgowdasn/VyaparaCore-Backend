"""Payment routes for VyaparaCore"""
from flask import Blueprint, g, request
from datetime import datetime
from decimal import Decimal
from config.database import db
from app.models import (
    Payment, PaymentAllocation, PaymentMode, BankAccount,
    Invoice, Customer, Supplier, SequenceNumber, InvoiceSettings,
    PurchaseOrder, DebitNote
)
from app.utils.security import (
    jwt_required_with_user, permission_required, sanitize_string, create_audit_log
)
from app.utils.helpers import (
    success_response, error_response, get_request_json,
    paginate, get_filters, apply_filters, model_to_dict
)

payment_bp = Blueprint('payment', __name__)


def get_next_payment_number(org_id):
    """Generate next payment number"""
    settings = InvoiceSettings.query.filter_by(organization_id=org_id).first()
    prefix = settings.payment_prefix if settings else 'PAY'
    
    seq = SequenceNumber.query.filter_by(organization_id=org_id, document_type='payment').first()
    
    if not seq:
        seq = SequenceNumber(
            organization_id=org_id,
            document_type='payment',
            prefix=prefix,
            current_number=0,
            number_length=5
        )
        db.session.add(seq)
    
    seq.current_number += 1
    return f"{prefix}{seq.current_number:05d}"


# ============ PAYMENT MODES ============

@payment_bp.route('/modes', methods=['GET'])
@jwt_required_with_user()
def list_payment_modes():
    """List payment modes"""
    modes = PaymentMode.query.filter_by(organization_id=g.organization_id, is_active=True).all()
    return success_response([model_to_dict(m) for m in modes])


@payment_bp.route('/modes', methods=['POST'])
@jwt_required_with_user()
@permission_required('payments.create')
def create_payment_mode():
    """Create payment mode"""
    data = get_request_json()
    
    if not data.get('name'):
        return error_response('Payment mode name required')
    
    mode = PaymentMode(
        organization_id=g.organization_id,
        name=sanitize_string(data['name']),
        code=sanitize_string(data.get('code', '')).upper() or sanitize_string(data['name']).upper()[:10],
        payment_type=data.get('mode_type', 'other'),
        bank_account_id=data.get('bank_account_id'),
        is_active=True
    )
    
    db.session.add(mode)
    db.session.commit()
    
    return success_response(model_to_dict(mode), 'Payment mode created', 201)


# ============ BANK ACCOUNTS ============

@payment_bp.route('/bank-accounts', methods=['GET'])
@jwt_required_with_user()
def list_bank_accounts():
    """List bank accounts"""
    accounts = BankAccount.query.filter_by(organization_id=g.organization_id, is_active=True).all()
    return success_response([model_to_dict(a) for a in accounts])


@payment_bp.route('/bank-accounts', methods=['POST'])
@jwt_required_with_user()
@permission_required('payments.create')
def create_bank_account():
    """Create bank account"""
    data = get_request_json()
    
    required = ['bank_name', 'account_number', 'ifsc_code']
    for field in required:
        if not data.get(field):
            return error_response(f'{field} is required')
    
    account = BankAccount(
        organization_id=g.organization_id,
        branch_id=data.get('branch_id'),
        bank_name=sanitize_string(data['bank_name']),
        account_number=sanitize_string(data['account_number']),
        account_name=sanitize_string(data.get('account_name', '')),
        account_type=data.get('account_type', 'current'),
        ifsc_code=sanitize_string(data['ifsc_code']).upper(),
        branch_name=sanitize_string(data.get('branch_name', '')),
        upi_id=sanitize_string(data.get('upi_id', '')),
        opening_balance=data.get('opening_balance', 0),
        current_balance=data.get('opening_balance', 0),
        is_primary=data.get('is_primary', False),
        is_active=True
    )
    
    if account.is_primary:
        BankAccount.query.filter_by(organization_id=g.organization_id).update({'is_primary': False})
    
    db.session.add(account)
    db.session.commit()
    
    return success_response(model_to_dict(account), 'Bank account created', 201)


@payment_bp.route('/bank-accounts/<int:id>', methods=['PUT'])
@jwt_required_with_user()
@permission_required('payments.edit')
def update_bank_account(id):
    """Update bank account"""
    account = BankAccount.query.filter_by(id=id, organization_id=g.organization_id).first()
    if not account:
        return error_response('Bank account not found', status_code=404)
    
    data = get_request_json()
    
    updateable = ['bank_name', 'account_name', 'account_type', 'ifsc_code', 
                  'branch_name', 'upi_id', 'is_primary', 'is_active']
    
    for field in updateable:
        if field in data:
            value = data[field]
            if field == 'ifsc_code':
                value = sanitize_string(value).upper()
            elif isinstance(value, str):
                value = sanitize_string(value)
            setattr(account, field, value)
    
    if account.is_primary:
        BankAccount.query.filter(
            BankAccount.organization_id == g.organization_id,
            BankAccount.id != id
        ).update({'is_primary': False})
    
    account.updated_at = datetime.utcnow()
    db.session.commit()
    
    return success_response(model_to_dict(account), 'Bank account updated')


# ============ PAYMENTS ============

@payment_bp.route('', methods=['GET'])
@jwt_required_with_user()
@permission_required('payments.view')
def list_payments():
    """List all payments"""
    query = Payment.query.filter_by(organization_id=g.organization_id)
    
    filters = get_filters()
    if filters.get('search'):
        search = f"%{filters['search']}%"
        query = query.filter(
            db.or_(
                Payment.payment_number.ilike(search),
                Payment.party_name.ilike(search)
            )
        )
    
    if request.args.get('payment_type'):
        query = query.filter_by(payment_type=request.args.get('payment_type'))
    
    if request.args.get('party_type'):
        query = query.filter_by(party_type=request.args.get('party_type'))

    if request.args.get('party_id'):
        party_id = request.args.get('party_id', type=int)
        party_type = request.args.get('party_type', 'customer')
        if party_type == 'customer':
            query = query.filter_by(customer_id=party_id)
        else:
            query = query.filter_by(supplier_id=party_id)

    query = apply_filters(query, Payment, filters)

    def serialize(p):
        data = model_to_dict(p)
        data['amount'] = float(p.amount or 0)
        data['party_id'] = p.customer_id if p.party_type == 'customer' else p.supplier_id
        data['payment_mode'] = p.payment_mode.name if p.payment_mode else None
        return data
    
    return success_response(paginate(query, serialize))


@payment_bp.route('', methods=['POST'])
@jwt_required_with_user()
@permission_required('payments.create')
def create_payment():
    """Create payment (receipt or payout)"""
    data = get_request_json()
    
    if not data.get('party_type') or not data.get('party_id') or not data.get('amount'):
        return error_response('Party type, party ID and amount required')
    
    party_type = data['party_type']  # customer or supplier
    party_id = data['party_id']
    amount = Decimal(str(data['amount']))
    
    # Validate party
    if party_type == 'customer':
        party = Customer.query.filter_by(id=party_id, organization_id=g.organization_id).first()
        payment_type = 'receipt'
    else:
        party = Supplier.query.filter_by(id=party_id, organization_id=g.organization_id).first()
        payment_type = 'payout'
    
    if not party:
        return error_response('Party not found', status_code=404)
    
    payment_number = get_next_payment_number(g.organization_id)

    # Get payment mode name if mode ID provided
    payment_mode_name = None
    if data.get('payment_mode_id'):
        mode = PaymentMode.query.get(data.get('payment_mode_id'))
        if mode:
            payment_mode_name = mode.name

    payment = Payment(
        organization_id=g.organization_id,
        branch_id=data.get('branch_id') or g.branch_id,
        payment_number=payment_number,
        payment_type=payment_type,
        party_type=party_type,
        customer_id=party_id if party_type == 'customer' else None,
        supplier_id=party_id if party_type == 'supplier' else None,
        party_name=party.name,
        amount=float(amount),
        payment_date=data.get('payment_date', datetime.utcnow().date()),
        payment_mode_id=data.get('payment_mode_id'),
        payment_mode_name=payment_mode_name,
        bank_account_id=data.get('bank_account_id'),
        cheque_number=sanitize_string(data.get('cheque_number', '')),
        cheque_date=data.get('cheque_date'),
        transaction_id=sanitize_string(data.get('transaction_id', '')),
        reference_number=sanitize_string(data.get('reference_number', '')),
        tds_amount=data.get('tds_amount', 0),
        tds_rate=data.get('tds_rate', 0),
        notes=sanitize_string(data.get('notes', '')),
        status='completed',
        created_by=g.current_user.id
    )
    
    db.session.add(payment)
    db.session.flush()
    
    # Allocate to invoices if provided
    allocated_amount = Decimal('0')
    
    if data.get('allocations'):
        for alloc in data['allocations']:
            invoice_id = alloc.get('invoice_id')
            alloc_amount = Decimal(str(alloc.get('amount', 0)))
            
            if party_type == 'customer':
                invoice = Invoice.query.filter_by(id=invoice_id, organization_id=g.organization_id).first()
                if not invoice:
                    continue

                # Don't allocate more than balance due
                balance = Decimal(str(invoice.balance_due or 0))
                if alloc_amount > balance:
                    alloc_amount = balance

                if alloc_amount <= 0:
                    continue

                allocation = PaymentAllocation(
                    payment_id=payment.id,
                    document_type='invoice',
                    document_id=invoice.id,
                    allocated_amount=float(alloc_amount)
                )
                db.session.add(allocation)

                # Update invoice
                invoice.paid_amount = float(Decimal(str(invoice.paid_amount or 0)) + alloc_amount)
                invoice.balance_due = float(Decimal(str(invoice.grand_total or 0)) - Decimal(str(invoice.paid_amount or 0)) - Decimal(str(invoice.credit_note_amount or 0)))

                if invoice.balance_due <= 0:
                    invoice.status = 'paid'
                    invoice.payment_status = 'paid'
                    invoice.paid_at = datetime.utcnow()
                else:
                    invoice.status = 'partial'
                    invoice.payment_status = 'partial'

                allocated_amount += alloc_amount
            else:
                # For supplier payments, allocate to purchase orders
                po_id = alloc.get('purchase_order_id') or alloc.get('invoice_id')  # invoice_id may contain PO id
                if not po_id:
                    continue

                po = PurchaseOrder.query.filter_by(id=po_id, organization_id=g.organization_id).first()
                if not po:
                    continue

                allocation = PaymentAllocation(
                    payment_id=payment.id,
                    document_type='purchase_order',
                    document_id=po.id,
                    allocated_amount=float(alloc_amount)
                )
                db.session.add(allocation)

                # Link payment to PO
                payment.purchase_order_id = po.id

                # Update PO payment status
                total_paid = float(alloc_amount)
                existing_allocs = PaymentAllocation.query.join(Payment).filter(
                    PaymentAllocation.document_type == 'purchase_order',
                    PaymentAllocation.document_id == po.id,
                    Payment.status == 'completed',
                    Payment.id != payment.id
                ).all()
                total_paid += sum(float(a.allocated_amount or 0) for a in existing_allocs)

                # Get debit notes
                debit_notes = DebitNote.query.filter(
                    DebitNote.purchase_order_id == po.id,
                    DebitNote.status.in_(['approved', 'applied', 'partial'])
                ).all()
                debit_note_amount = sum(float(dn.grand_total or 0) for dn in debit_notes)

                po_balance = float(po.grand_total or 0) - float(po.advance_amount or 0) - debit_note_amount - total_paid

                if po_balance <= 0:
                    po.payment_status = 'paid'
                else:
                    po.payment_status = 'partial'

                allocated_amount += alloc_amount
    
    # Update party outstanding/balance
    if party_type == 'customer':
        party.outstanding_amount = float(Decimal(str(party.outstanding_amount or 0)) - amount)
    else:
        party.current_balance = float(Decimal(str(party.current_balance or 0)) - amount)
    
    # Update bank account balance
    if payment.bank_account_id:
        bank = BankAccount.query.get(payment.bank_account_id)
        if bank:
            if payment_type == 'receipt':
                bank.current_balance = float(Decimal(str(bank.current_balance or 0)) + amount)
            else:
                bank.current_balance = float(Decimal(str(bank.current_balance or 0)) - amount)
    
    payment.allocated_amount = float(allocated_amount)
    payment.unallocated_amount = float(amount - allocated_amount)
    
    db.session.commit()
    
    create_audit_log('payments', payment.id, 'create', None, model_to_dict(payment))
    
    return success_response(model_to_dict(payment), 'Payment recorded', 201)


@payment_bp.route('/<int:id>', methods=['GET'])
@jwt_required_with_user()
@permission_required('payments.view')
def get_payment(id):
    """Get payment details"""
    payment = Payment.query.filter_by(id=id, organization_id=g.organization_id).first()
    if not payment:
        return error_response('Payment not found', status_code=404)
    
    data = model_to_dict(payment)
    data['amount'] = float(payment.amount or 0)
    data['party_id'] = payment.customer_id if payment.party_type == 'customer' else payment.supplier_id
    data['payment_mode'] = payment.payment_mode.name if payment.payment_mode else None
    data['allocations'] = []

    for alloc in payment.allocations:
        alloc_data = model_to_dict(alloc)
        alloc_data['amount'] = float(alloc.allocated_amount or 0)  # For frontend compatibility
        if alloc.document_type == 'invoice':
            invoice = Invoice.query.get(alloc.document_id)
            if invoice:
                alloc_data['document_number'] = invoice.invoice_number
                alloc_data['document_total'] = float(invoice.grand_total or 0)
        data['allocations'].append(alloc_data)
    
    return success_response(data)


@payment_bp.route('/<int:id>/allocate', methods=['POST'])
@jwt_required_with_user()
@permission_required('payments.edit')
def allocate_payment(id):
    """Allocate unallocated payment to invoices"""
    payment = Payment.query.filter_by(id=id, organization_id=g.organization_id).first()
    if not payment:
        return error_response('Payment not found', status_code=404)
    
    available = Decimal(str(payment.unallocated_amount or 0))
    if available <= 0:
        return error_response('No unallocated amount available')
    
    data = get_request_json()
    allocations = data.get('allocations', [])
    
    total_allocated = Decimal('0')
    
    for alloc in allocations:
        invoice_id = alloc.get('invoice_id')
        alloc_amount = Decimal(str(alloc.get('amount', 0)))
        
        if alloc_amount <= 0:
            continue
        
        if total_allocated + alloc_amount > available:
            alloc_amount = available - total_allocated
        
        if alloc_amount <= 0:
            break
        
        invoice = Invoice.query.filter_by(id=invoice_id, organization_id=g.organization_id).first()
        if not invoice:
            continue
        
        balance = Decimal(str(invoice.balance_due or 0))
        if alloc_amount > balance:
            alloc_amount = balance
        
        allocation = PaymentAllocation(
            payment_id=payment.id,
            document_type='invoice',
            document_id=invoice.id,
            allocated_amount=float(alloc_amount)
        )
        db.session.add(allocation)

        invoice.paid_amount = float(Decimal(str(invoice.paid_amount or 0)) + alloc_amount)
        invoice.balance_due = float(Decimal(str(invoice.grand_total or 0)) - Decimal(str(invoice.paid_amount or 0)) - Decimal(str(invoice.credit_note_amount or 0)))

        if invoice.balance_due <= 0:
            invoice.status = 'paid'
            invoice.payment_status = 'paid'
            invoice.paid_at = datetime.utcnow()
        else:
            invoice.status = 'partial'
            invoice.payment_status = 'partial'

        total_allocated += alloc_amount
    
    payment.allocated_amount = float(Decimal(str(payment.allocated_amount or 0)) + total_allocated)
    payment.unallocated_amount = float(Decimal(str(payment.amount or 0)) - Decimal(str(payment.allocated_amount or 0)))
    
    db.session.commit()
    
    return success_response(model_to_dict(payment), 'Payment allocated')


@payment_bp.route('/<int:id>/cancel', methods=['POST'])
@jwt_required_with_user()
@permission_required('payments.delete')
def cancel_payment(id):
    """Cancel payment"""
    payment = Payment.query.filter_by(id=id, organization_id=g.organization_id).first()
    if not payment:
        return error_response('Payment not found', status_code=404)
    
    if payment.status == 'cancelled':
        return error_response('Payment already cancelled')
    
    data = get_request_json()
    
    # Reverse allocations
    for alloc in payment.allocations:
        if alloc.document_type == 'invoice':
            invoice = Invoice.query.get(alloc.document_id)
            if invoice:
                invoice.paid_amount = float(Decimal(str(invoice.paid_amount or 0)) - Decimal(str(alloc.allocated_amount or 0)))
                invoice.balance_due = float(Decimal(str(invoice.grand_total or 0)) - Decimal(str(invoice.paid_amount or 0)) - Decimal(str(invoice.credit_note_amount or 0)))

                if invoice.balance_due > 0:
                    invoice.status = 'partial' if invoice.paid_amount > 0 else 'sent'
                    invoice.payment_status = 'partial' if invoice.paid_amount > 0 else 'unpaid'

    # Reverse party outstanding
    if payment.party_type == 'customer':
        party = Customer.query.get(payment.customer_id)
    else:
        party = Supplier.query.get(payment.supplier_id)
    
    if party:
        if payment.party_type == 'customer':
            party.outstanding_amount = float(Decimal(str(party.outstanding_amount or 0)) + Decimal(str(payment.amount or 0)))
        else:
            party.current_balance = float(Decimal(str(party.current_balance or 0)) + Decimal(str(payment.amount or 0)))
    
    # Reverse bank balance
    if payment.bank_account_id:
        bank = BankAccount.query.get(payment.bank_account_id)
        if bank:
            if payment.payment_type == 'receipt':
                bank.current_balance = float(Decimal(str(bank.current_balance or 0)) - Decimal(str(payment.amount or 0)))
            else:
                bank.current_balance = float(Decimal(str(bank.current_balance or 0)) + Decimal(str(payment.amount or 0)))
    
    payment.status = 'cancelled'
    payment.cancellation_reason = sanitize_string(data.get('reason', ''))
    payment.cancelled_at = datetime.utcnow()
    payment.cancelled_by = g.current_user.id
    payment.updated_at = datetime.utcnow()
    
    db.session.commit()
    
    return success_response(model_to_dict(payment), 'Payment cancelled')


# ============ REPORTS ============

@payment_bp.route('/summary', methods=['GET'])
@jwt_required_with_user()
@permission_required('payments.view')
def payment_summary():
    """Get payment summary"""
    from_date = request.args.get('from_date')
    to_date = request.args.get('to_date')
    
    query = Payment.query.filter_by(organization_id=g.organization_id, status='completed')
    
    if from_date:
        query = query.filter(Payment.payment_date >= from_date)
    if to_date:
        query = query.filter(Payment.payment_date <= to_date)
    
    receipts = query.filter_by(payment_type='receipt').all()
    payouts = query.filter_by(payment_type='payout').all()
    
    total_receipts = sum(float(p.amount or 0) for p in receipts)
    total_payouts = sum(float(p.amount or 0) for p in payouts)
    
    return success_response({
        'total_receipts': total_receipts,
        'total_payouts': total_payouts,
        'net_cash_flow': total_receipts - total_payouts,
        'receipt_count': len(receipts),
        'payout_count': len(payouts)
    })


@payment_bp.route('/receivables', methods=['GET'])
@jwt_required_with_user()
@permission_required('payments.view')
def get_receivables():
    """Get outstanding receivables with aging analysis"""
    from datetime import timedelta
    today = datetime.utcnow().date()

    # Base query for outstanding invoices
    query = Invoice.query.filter(
        Invoice.organization_id == g.organization_id,
        Invoice.status.in_(['sent', 'partial', 'overdue'])
    )

    # Apply filters
    customer_id = request.args.get('customer_id', type=int)
    if customer_id:
        query = query.filter(Invoice.customer_id == customer_id)

    search = request.args.get('search')
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            db.or_(
                Invoice.invoice_number.ilike(search_term),
                Invoice.customer_name.ilike(search_term)
            )
        )

    invoices = query.order_by(Invoice.due_date).all()

    # Calculate aging buckets
    current = []  # Not yet due
    days_1_30 = []
    days_31_60 = []
    days_61_90 = []
    days_90_plus = []

    for inv in invoices:
        # Calculate correct balance
        balance = float(
            Decimal(str(inv.grand_total or 0)) -
            Decimal(str(inv.paid_amount or 0)) -
            Decimal(str(inv.credit_note_amount or 0))
        )
        if balance <= 0:
            continue

        inv_data = {
            'id': inv.id,
            'invoice_number': inv.invoice_number,
            'customer_id': inv.customer_id,
            'customer_name': inv.customer_name,
            'invoice_date': inv.invoice_date.isoformat() if inv.invoice_date else None,
            'due_date': inv.due_date.isoformat() if inv.due_date else None,
            'grand_total': float(inv.grand_total or 0),
            'paid_amount': float(inv.paid_amount or 0),
            'credit_note_amount': float(inv.credit_note_amount or 0),
            'balance_due': balance,
            'status': inv.status,
            'days_overdue': 0
        }

        if inv.due_date:
            days_diff = (today - inv.due_date).days
            inv_data['days_overdue'] = max(0, days_diff)

            if days_diff <= 0:
                current.append(inv_data)
            elif days_diff <= 30:
                days_1_30.append(inv_data)
            elif days_diff <= 60:
                days_31_60.append(inv_data)
            elif days_diff <= 90:
                days_61_90.append(inv_data)
            else:
                days_90_plus.append(inv_data)
        else:
            current.append(inv_data)

    # Calculate totals
    all_invoices = current + days_1_30 + days_31_60 + days_61_90 + days_90_plus
    total_receivables = sum(inv['balance_due'] for inv in all_invoices)

    # Customer-wise summary
    customer_summary = {}
    for inv in all_invoices:
        cust_id = inv['customer_id']
        if cust_id not in customer_summary:
            customer_summary[cust_id] = {
                'customer_id': cust_id,
                'customer_name': inv['customer_name'],
                'total_outstanding': 0,
                'invoice_count': 0
            }
        customer_summary[cust_id]['total_outstanding'] += inv['balance_due']
        customer_summary[cust_id]['invoice_count'] += 1

    return success_response({
        'total_receivables': total_receivables,
        'invoice_count': len(all_invoices),
        'aging': {
            'current': {'count': len(current), 'amount': sum(i['balance_due'] for i in current)},
            'days_1_30': {'count': len(days_1_30), 'amount': sum(i['balance_due'] for i in days_1_30)},
            'days_31_60': {'count': len(days_31_60), 'amount': sum(i['balance_due'] for i in days_31_60)},
            'days_61_90': {'count': len(days_61_90), 'amount': sum(i['balance_due'] for i in days_61_90)},
            'days_90_plus': {'count': len(days_90_plus), 'amount': sum(i['balance_due'] for i in days_90_plus)}
        },
        'invoices': all_invoices,
        'customer_summary': list(customer_summary.values())
    })


@payment_bp.route('/payables', methods=['GET'])
@jwt_required_with_user()
@permission_required('payments.view')
def get_payables():
    """Get outstanding payables with aging analysis"""
    today = datetime.utcnow().date()

    # Base query for purchase orders that need payment
    query = PurchaseOrder.query.filter(
        PurchaseOrder.organization_id == g.organization_id,
        PurchaseOrder.status.in_(['sent', 'confirmed', 'partially_received', 'received']),
        PurchaseOrder.payment_status.in_(['unpaid', 'partial'])
    )

    # Apply filters
    supplier_id = request.args.get('supplier_id', type=int)
    if supplier_id:
        query = query.filter(PurchaseOrder.supplier_id == supplier_id)

    search = request.args.get('search')
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            db.or_(
                PurchaseOrder.order_number.ilike(search_term),
                PurchaseOrder.supplier_name.ilike(search_term)
            )
        )

    purchase_orders = query.order_by(PurchaseOrder.payment_due_date).all()

    # Calculate aging buckets
    current = []  # Not yet due
    days_1_30 = []
    days_31_60 = []
    days_61_90 = []
    days_90_plus = []

    for po in purchase_orders:
        # Calculate debit note amount for this purchase order
        debit_notes = DebitNote.query.filter(
            DebitNote.purchase_order_id == po.id,
            DebitNote.status.in_(['approved', 'applied', 'partial'])
        ).all()
        debit_note_amount = sum(float(dn.grand_total or 0) for dn in debit_notes)

        # Calculate paid amount from payment allocations
        paid_allocations = PaymentAllocation.query.join(Payment).filter(
            PaymentAllocation.document_type == 'purchase_order',
            PaymentAllocation.document_id == po.id,
            Payment.status == 'completed'
        ).all()
        paid_amount = sum(float(a.allocated_amount or 0) for a in paid_allocations)

        # Calculate net payable: grand_total - advance - debit_notes - paid
        grand_total = float(po.grand_total or 0)
        advance = float(po.advance_amount or 0)
        balance = grand_total - advance - debit_note_amount - paid_amount

        if balance <= 0:
            # Update payment status if fully paid
            if po.payment_status != 'paid':
                po.payment_status = 'paid'
                db.session.commit()
            continue

        # Update payment status if partial
        if paid_amount > 0 and po.payment_status == 'unpaid':
            po.payment_status = 'partial'
            db.session.commit()

        po_data = {
            'id': po.id,
            'order_number': po.order_number,
            'supplier_id': po.supplier_id,
            'supplier_name': po.supplier_name,
            'order_date': po.order_date.isoformat() if po.order_date else None,
            'due_date': po.payment_due_date.isoformat() if po.payment_due_date else None,
            'grand_total': grand_total,
            'advance_amount': advance,
            'paid_amount': paid_amount,
            'debit_note_amount': debit_note_amount,
            'balance_due': balance,
            'status': po.status,
            'payment_status': po.payment_status,
            'days_overdue': 0
        }

        due_date = po.payment_due_date or po.order_date
        if due_date:
            days_diff = (today - due_date).days
            po_data['days_overdue'] = max(0, days_diff)

            if days_diff <= 0:
                current.append(po_data)
            elif days_diff <= 30:
                days_1_30.append(po_data)
            elif days_diff <= 60:
                days_31_60.append(po_data)
            elif days_diff <= 90:
                days_61_90.append(po_data)
            else:
                days_90_plus.append(po_data)
        else:
            current.append(po_data)

    # Calculate totals
    all_orders = current + days_1_30 + days_31_60 + days_61_90 + days_90_plus
    total_payables = sum(po['balance_due'] for po in all_orders)

    # Supplier-wise summary
    supplier_summary = {}
    for po in all_orders:
        supp_id = po['supplier_id']
        if supp_id not in supplier_summary:
            supplier_summary[supp_id] = {
                'supplier_id': supp_id,
                'supplier_name': po['supplier_name'],
                'total_outstanding': 0,
                'order_count': 0
            }
        supplier_summary[supp_id]['total_outstanding'] += po['balance_due']
        supplier_summary[supp_id]['order_count'] += 1

    return success_response({
        'total_payables': total_payables,
        'order_count': len(all_orders),
        'aging': {
            'current': {'count': len(current), 'amount': sum(p['balance_due'] for p in current)},
            'days_1_30': {'count': len(days_1_30), 'amount': sum(p['balance_due'] for p in days_1_30)},
            'days_31_60': {'count': len(days_31_60), 'amount': sum(p['balance_due'] for p in days_31_60)},
            'days_61_90': {'count': len(days_61_90), 'amount': sum(p['balance_due'] for p in days_61_90)},
            'days_90_plus': {'count': len(days_90_plus), 'amount': sum(p['balance_due'] for p in days_90_plus)}
        },
        'purchase_orders': all_orders,
        'supplier_summary': list(supplier_summary.values())
    })