"""Invoice routes for VyaparaCore"""
from flask import Blueprint, g, request
from datetime import datetime
from decimal import Decimal
from config.database import db
from app.models import (
    Invoice, InvoiceItem, CreditNote, CreditNoteItem, DebitNote, DebitNoteItem,
    Customer, Supplier, Product, Organization, SalesOrder, Stock, StockTransaction,
    SequenceNumber, InvoiceSettings
)
from app.utils.security import (
    jwt_required_with_user, permission_required, sanitize_string, create_audit_log
)
from app.utils.helpers import (
    success_response, error_response, get_request_json,
    paginate, get_filters, apply_filters, model_to_dict
)
from app.services.activity_logger import log_activity, log_audit, ActivityType, EntityType

invoice_bp = Blueprint('invoice', __name__)


def get_next_number(org_id, doc_type):
    """Generate next document number"""
    settings = InvoiceSettings.query.filter_by(organization_id=org_id).first()
    
    prefix_map = {
        'invoice': settings.invoice_prefix if settings else 'INV',
        'credit_note': settings.credit_note_prefix if settings else 'CN',
        'debit_note': settings.debit_note_prefix if settings else 'DN'
    }
    prefix = prefix_map.get(doc_type, 'DOC')
    
    seq = SequenceNumber.query.filter_by(organization_id=org_id, document_type=doc_type).first()
    
    if not seq:
        seq = SequenceNumber(
            organization_id=org_id,
            document_type=doc_type,
            prefix=prefix,
            current_number=0,
            number_length=5
        )
        db.session.add(seq)
    
    seq.current_number += 1
    return f"{prefix}{seq.current_number:05d}"


# ============ INVOICES ============

@invoice_bp.route('', methods=['GET'])
@jwt_required_with_user()
@permission_required('invoices.view')
def list_invoices():
    """List all invoices"""
    org_id = g.organization_id

    # Calculate stats from all invoices (unfiltered)
    base_query = Invoice.query.filter_by(organization_id=org_id)

    # Stats calculations
    total_invoices = base_query.count()
    total_amount = db.session.query(db.func.coalesce(db.func.sum(Invoice.grand_total), 0)).filter(
        Invoice.organization_id == org_id
    ).scalar()

    paid_amount = db.session.query(db.func.coalesce(db.func.sum(Invoice.grand_total), 0)).filter(
        Invoice.organization_id == org_id,
        Invoice.payment_status == 'paid'
    ).scalar()

    pending_amount = db.session.query(db.func.coalesce(db.func.sum(Invoice.balance_due), 0)).filter(
        Invoice.organization_id == org_id,
        Invoice.payment_status.in_(['unpaid', 'partial'])
    ).scalar()

    overdue_count = base_query.filter(
        Invoice.status == 'overdue'
    ).count()

    stats = {
        'total_invoices': total_invoices,
        'total_amount': float(total_amount or 0),
        'paid_amount': float(paid_amount or 0),
        'pending_amount': float(pending_amount or 0),
        'overdue_count': overdue_count
    }

    # Now apply filters for the list
    query = Invoice.query.filter_by(organization_id=org_id)

    filters = get_filters()
    if filters.get('search'):
        search = f"%{filters['search']}%"
        query = query.filter(
            db.or_(
                Invoice.invoice_number.ilike(search),
                Invoice.customer_name.ilike(search)
            )
        )

    if request.args.get('customer_id'):
        query = query.filter_by(customer_id=request.args.get('customer_id', type=int))

    if request.args.get('invoice_type'):
        query = query.filter_by(invoice_type=request.args.get('invoice_type'))

    if request.args.get('payment_status'):
        ps = request.args.get('payment_status')
        if ps == 'paid':
            query = query.filter(Invoice.balance_due <= 0)
        elif ps == 'unpaid':
            query = query.filter(Invoice.balance_due > 0)
        elif ps == 'partial':
            query = query.filter(Invoice.paid_amount > 0, Invoice.balance_due > 0)

    query = apply_filters(query, Invoice, filters)

    def serialize(inv):
        data = model_to_dict(inv)
        data['customer_name'] = inv.customer.name if inv.customer else inv.customer_name
        data['total'] = float(inv.grand_total or 0)
        data['total_amount'] = float(inv.grand_total or 0)
        # Recalculate balance_due correctly
        data['balance_due'] = max(0, float(
            Decimal(str(inv.grand_total or 0)) -
            Decimal(str(inv.paid_amount or 0)) -
            Decimal(str(inv.credit_note_amount or 0))
        ))
        return data

    result = paginate(query, serialize)
    result['stats'] = stats

    return success_response(result)


@invoice_bp.route('', methods=['POST'])
@jwt_required_with_user()
@permission_required('invoices.create')
def create_invoice():
    """Create new invoice"""
    data = get_request_json()
    
    if not data.get('customer_id') or not data.get('items'):
        return error_response('Customer and items required')
    
    customer = Customer.query.filter_by(id=data['customer_id'], organization_id=g.organization_id).first()
    if not customer:
        return error_response('Customer not found', status_code=404)
    
    org = Organization.query.get(g.organization_id)
    
    invoice_number = get_next_number(g.organization_id, 'invoice')
    is_interstate = (data.get('place_of_supply') or customer.billing_state_code) != org.state_code
    
    invoice = Invoice(
        organization_id=g.organization_id,
        branch_id=data.get('branch_id') or g.branch_id,
        invoice_number=invoice_number,
        invoice_type=data.get('invoice_type', 'tax_invoice'),
        sales_order_id=data.get('sales_order_id'),
        customer_id=data['customer_id'],
        customer_name=customer.name,
        customer_gstin=customer.gstin,
        customer_email=customer.email,
        customer_phone=customer.phone,
        billing_address_line1=data.get('billing_address_line1') or customer.billing_address_line1,
        billing_address_line2=data.get('billing_address_line2') or customer.billing_address_line2,
        billing_city=data.get('billing_city') or customer.billing_city,
        billing_state=data.get('billing_state') or customer.billing_state,
        billing_state_code=data.get('billing_state_code') or customer.billing_state_code,
        billing_pincode=data.get('billing_pincode') or customer.billing_pincode,
        shipping_address_line1=data.get('shipping_address_line1') or customer.shipping_address_line1,
        shipping_address_line2=data.get('shipping_address_line2') or customer.shipping_address_line2,
        shipping_city=data.get('shipping_city') or customer.shipping_city,
        shipping_state=data.get('shipping_state') or customer.shipping_state,
        shipping_state_code=data.get('shipping_state_code') or customer.shipping_state_code,
        shipping_pincode=data.get('shipping_pincode') or customer.shipping_pincode,
        invoice_date=data.get('invoice_date', datetime.utcnow().date()),
        due_date=data.get('due_date'),
        place_of_supply=data.get('place_of_supply') or customer.billing_state_code or org.state_code,
        is_reverse_charge=data.get('is_reverse_charge', False),
        currency=data.get('currency', 'INR'),
        exchange_rate=data.get('exchange_rate', 1),
        payment_terms=data.get('payment_terms', customer.payment_terms),
        notes=sanitize_string(data.get('notes', '')),
        terms_and_conditions=sanitize_string(data.get('terms_and_conditions', '')),
        status='draft',
        created_by=g.current_user.id
    )
    
    db.session.add(invoice)
    db.session.flush()
    
    subtotal = Decimal('0')
    total_cgst = Decimal('0')
    total_sgst = Decimal('0')
    total_igst = Decimal('0')
    total_cess = Decimal('0')
    total_discount = Decimal('0')
    
    warehouse_id = data.get('warehouse_id')
    
    for idx, item_data in enumerate(data['items']):
        product = Product.query.filter_by(id=item_data['product_id'], organization_id=g.organization_id).first()
        if not product:
            continue
        
        qty = Decimal(str(item_data.get('quantity', 1)))
        unit_price = Decimal(str(item_data.get('unit_price', product.selling_price or 0)))
        discount_pct = Decimal(str(item_data.get('discount_percent', 0)))
        
        item_subtotal = qty * unit_price
        item_discount = item_subtotal * discount_pct / 100
        taxable = item_subtotal - item_discount
        
        cgst = sgst = igst = cess = Decimal('0')
        if product.tax_rate:
            if is_interstate:
                igst = taxable * Decimal(str(product.tax_rate.igst_rate)) / 100
            else:
                cgst = taxable * Decimal(str(product.tax_rate.cgst_rate)) / 100
                sgst = taxable * Decimal(str(product.tax_rate.sgst_rate)) / 100
            cess = taxable * Decimal(str(product.tax_rate.cess_rate or 0)) / 100
        
        total = taxable + cgst + sgst + igst + cess
        
        item = InvoiceItem(
            invoice_id=invoice.id,
            product_id=product.id,
            variant_id=item_data.get('variant_id'),
            description=sanitize_string(item_data.get('description', product.name)),
            hsn_code=product.hsn_code,
            quantity=float(qty),
            unit_id=item_data.get('unit_id') or product.unit_id,
            unit_price=float(unit_price),
            discount_percent=float(discount_pct),
            discount_amount=float(item_discount),
            taxable_amount=float(taxable),
            tax_rate_id=product.tax_rate_id,
            cgst_rate=product.tax_rate.cgst_rate if product.tax_rate and not is_interstate else 0,
            cgst_amount=float(cgst),
            sgst_rate=product.tax_rate.sgst_rate if product.tax_rate and not is_interstate else 0,
            sgst_amount=float(sgst),
            igst_rate=product.tax_rate.igst_rate if product.tax_rate and is_interstate else 0,
            igst_amount=float(igst),
            cess_rate=product.tax_rate.cess_rate if product.tax_rate else 0,
            cess_amount=float(cess),
            total_amount=float(total),
            batch_id=item_data.get('batch_id'),
            serial_numbers=item_data.get('serial_numbers', [])
        )
        db.session.add(item)
        
        subtotal += taxable
        total_discount += item_discount
        total_cgst += cgst
        total_sgst += sgst
        total_igst += igst
        total_cess += cess
        
        # Deduct stock if warehouse provided
        if warehouse_id and product.track_inventory:
            stock = Stock.query.filter_by(
                product_id=product.id,
                variant_id=item_data.get('variant_id'),
                warehouse_id=warehouse_id
            ).first()

            if stock:
                balance_before = float(stock.quantity or 0)
                deduct_qty = float(qty)

                # If invoice is from a Sales Order, also release reserved stock
                if invoice.sales_order_id:
                    reserved_before = float(stock.reserved_quantity or 0)
                    release_qty = min(deduct_qty, reserved_before)
                    stock.reserved_quantity = max(0, reserved_before - release_qty)

                # Deduct from actual stock
                stock.quantity = max(0, balance_before - deduct_qty)
                stock.available_quantity = float(stock.quantity) - float(stock.reserved_quantity or 0)

                # Generate transaction number
                txn_count = StockTransaction.query.filter_by(
                    organization_id=g.organization_id
                ).count()

                txn = StockTransaction(
                    organization_id=g.organization_id,
                    transaction_number=f"SALE{datetime.utcnow().strftime('%y%m')}{txn_count + 1:05d}",
                    product_id=product.id,
                    variant_id=item_data.get('variant_id'),
                    warehouse_id=warehouse_id,
                    transaction_type='sale',
                    quantity=deduct_qty,
                    direction='out',
                    balance_before=balance_before,
                    balance_after=float(stock.quantity),
                    unit_cost=float(unit_price),
                    reference_type='invoice',
                    reference_id=invoice.id,
                    reference_number=invoice.invoice_number,
                    transaction_date=invoice.invoice_date,
                    created_by=g.current_user.id
                )
                db.session.add(txn)

                # Update product stock
                total_stock = db.session.query(db.func.sum(Stock.quantity)).filter_by(product_id=product.id).scalar() or 0
                product.current_stock = float(total_stock)
    
    shipping = Decimal(str(data.get('shipping_charges', 0)))
    packaging = Decimal(str(data.get('packaging_charges', 0)))
    other = Decimal(str(data.get('other_charges', 0)))
    
    total_tax = total_cgst + total_sgst + total_igst + total_cess
    total_amount = subtotal + total_tax + shipping + packaging + other
    round_off = round(total_amount) - total_amount
    final_total = round(total_amount)
    
    invoice.subtotal = float(subtotal)
    invoice.total_discount = float(total_discount)
    invoice.cgst_amount = float(total_cgst)
    invoice.sgst_amount = float(total_sgst)
    invoice.igst_amount = float(total_igst)
    invoice.cess_amount = float(total_cess)
    invoice.tax_amount = float(total_tax)
    invoice.shipping_charges = float(shipping)
    invoice.packaging_charges = float(packaging)
    invoice.other_charges = float(other)
    invoice.round_off = float(round_off)
    invoice.total_amount = float(final_total)
    invoice.balance_due = float(final_total)
    
    # Update customer outstanding
    customer.outstanding_amount = float(customer.outstanding_amount or 0) + float(final_total)
    
    db.session.commit()

    log_audit('invoices', invoice.id, 'create', None, model_to_dict(invoice))
    log_activity(
        activity_type=ActivityType.CREATE,
        description=f"Created invoice {invoice.invoice_number} for {customer.name}",
        entity_type=EntityType.INVOICE,
        entity_id=invoice.id,
        entity_number=invoice.invoice_number,
        extra_data={'customer_id': customer.id, 'total': float(invoice.total_amount)}
    )

    return success_response(model_to_dict(invoice), 'Invoice created', 201)


@invoice_bp.route('/<int:id>', methods=['GET'])
@jwt_required_with_user()
@permission_required('invoices.view')
def get_invoice(id):
    """Get invoice details"""
    invoice = Invoice.query.filter_by(id=id, organization_id=g.organization_id).first()
    if not invoice:
        return error_response('Invoice not found', status_code=404)
    
    data = model_to_dict(invoice)

    # Recalculate balance_due to ensure accuracy
    from decimal import Decimal
    calculated_balance = float(
        Decimal(str(invoice.grand_total or 0)) -
        Decimal(str(invoice.paid_amount or 0)) -
        Decimal(str(invoice.credit_note_amount or 0))
    )
    data['balance_due'] = max(0, calculated_balance)

    # Update status if needed
    if calculated_balance <= 0 and invoice.status not in ['void', 'cancelled', 'paid']:
        invoice.status = 'paid'
        invoice.payment_status = 'paid'
        data['status'] = 'paid'
        data['payment_status'] = 'paid'
        db.session.commit()
    elif calculated_balance <= 0 and invoice.payment_status != 'paid':
        invoice.payment_status = 'paid'
        data['payment_status'] = 'paid'
        db.session.commit()

    data['customer'] = model_to_dict(invoice.customer) if invoice.customer else None
    data['items'] = []

    for item in invoice.items:
        item_data = model_to_dict(item)
        item_data['product'] = {
            'id': item.product.id,
            'name': item.product.name,
            'sku': item.product.sku
        } if item.product else None
        data['items'].append(item_data)

    # Get credit notes created from this invoice (original invoice)
    related_credit_notes = []
    for cn in invoice.credit_notes:
        related_credit_notes.append({
            'id': cn.id,
            'credit_note_number': cn.credit_note_number,
            'credit_note_date': cn.credit_note_date.isoformat() if cn.credit_note_date else None,
            'grand_total': float(cn.grand_total or 0),
            'adjusted_amount': float(cn.adjusted_amount or 0),
            'balance_amount': float(cn.balance_amount or 0),
            'reason': cn.reason,
            'status': cn.status
        })
    data['related_credit_notes'] = related_credit_notes

    return success_response(data)


@invoice_bp.route('/<int:id>', methods=['PUT'])
@jwt_required_with_user()
@permission_required('invoices.edit')
def update_invoice(id):
    """Update invoice"""
    invoice = Invoice.query.filter_by(id=id, organization_id=g.organization_id).first()
    if not invoice:
        return error_response('Invoice not found', status_code=404)
    
    if invoice.status not in ['draft']:
        return error_response('Can only edit draft invoices')
    
    data = get_request_json()
    
    updateable = ['due_date', 'notes', 'terms_and_conditions', 'payment_terms',
                  'shipping_address_line1', 'shipping_address_line2', 'shipping_city',
                  'shipping_state', 'shipping_state_code', 'shipping_pincode']
    
    for field in updateable:
        if field in data:
            setattr(invoice, field, data[field])
    
    invoice.updated_at = datetime.utcnow()
    invoice.updated_by = g.current_user.id
    db.session.commit()
    
    return success_response(model_to_dict(invoice), 'Invoice updated')


@invoice_bp.route('/<int:id>/send', methods=['POST'])
@jwt_required_with_user()
@permission_required('invoices.email')
def send_invoice(id):
    """Send invoice via email"""
    invoice = Invoice.query.filter_by(id=id, organization_id=g.organization_id).first()
    if not invoice:
        return error_response('Invoice not found', status_code=404)

    org = Organization.query.get(g.organization_id)
    customer = Customer.query.get(invoice.customer_id) if invoice.customer_id else None

    # Email sending logic (commented out - enable when SMTP is configured)
    # ------------------------------------------------------------------
    # from flask_mail import Message
    # from app import mail
    #
    # if customer and customer.email:
    #     try:
    #         msg = Message(
    #             subject=f"Invoice {invoice.invoice_number} from {org.name}",
    #             sender=org.email or 'noreply@example.com',
    #             recipients=[customer.email]
    #         )
    #         msg.html = f"""
    #         <h2>Invoice {invoice.invoice_number}</h2>
    #         <p>Dear {customer.name},</p>
    #         <p>Please find attached your invoice for ₹{invoice.total_amount:,.2f}</p>
    #         <p>Due Date: {invoice.due_date}</p>
    #         <br>
    #         <p>Thank you for your business!</p>
    #         <p>{org.name}</p>
    #         """
    #         # Attach PDF invoice here
    #         # msg.attach(f"Invoice_{invoice.invoice_number}.pdf", "application/pdf", pdf_data)
    #         mail.send(msg)
    #     except Exception as e:
    #         print(f"Email sending failed: {str(e)}")
    # ------------------------------------------------------------------

    # Update status
    invoice.status = 'sent'
    invoice.sent_at = datetime.utcnow()
    invoice.updated_at = datetime.utcnow()
    db.session.commit()

    log_activity(
        activity_type=ActivityType.SEND,
        description=f"Sent invoice {invoice.invoice_number} via email",
        entity_type=EntityType.INVOICE,
        entity_id=invoice.id,
        entity_number=invoice.invoice_number
    )

    return success_response(model_to_dict(invoice), 'Invoice marked as sent')


@invoice_bp.route('/<int:id>/whatsapp', methods=['GET'])
@jwt_required_with_user()
@permission_required('invoices.view')
def get_whatsapp_link(id):
    """Generate WhatsApp share link for invoice"""
    invoice = Invoice.query.filter_by(id=id, organization_id=g.organization_id).first()
    if not invoice:
        return error_response('Invoice not found', status_code=404)

    org = Organization.query.get(g.organization_id)
    customer = Customer.query.get(invoice.customer_id) if invoice.customer_id else None

    # Build WhatsApp message
    message = f"""*Invoice {invoice.invoice_number}*
From: {org.name if org else 'Our Company'}

Customer: {invoice.customer_name}
Date: {invoice.invoice_date}
Due Date: {invoice.due_date or 'N/A'}

*Amount: ₹{float(invoice.grand_total or 0):,.2f}*

Thank you for your business!"""

    # URL encode the message
    import urllib.parse
    encoded_message = urllib.parse.quote(message)

    # Get customer phone (remove +91 or other prefixes for WhatsApp)
    phone = ''
    if customer and customer.phone:
        phone = customer.phone.replace('+', '').replace(' ', '').replace('-', '')
        if not phone.startswith('91') and len(phone) == 10:
            phone = '91' + phone

    whatsapp_url = f"https://wa.me/{phone}?text={encoded_message}"

    return success_response({
        'whatsapp_url': whatsapp_url,
        'phone': phone,
        'message': message
    })


@invoice_bp.route('/<int:id>/void', methods=['POST'])
@jwt_required_with_user()
@permission_required('invoices.void')
def void_invoice(id):
    """Void invoice"""
    invoice = Invoice.query.filter_by(id=id, organization_id=g.organization_id).first()
    if not invoice:
        return error_response('Invoice not found', status_code=404)
    
    if invoice.paid_amount and float(invoice.paid_amount) > 0:
        return error_response('Cannot void invoice with payments')
    
    data = get_request_json()
    
    # Update customer outstanding
    customer = invoice.customer
    if customer:
        customer.outstanding_amount = float(customer.outstanding_amount or 0) - float(invoice.total_amount or 0)
    
    invoice.status = 'void'
    invoice.void_reason = sanitize_string(data.get('reason', ''))
    invoice.voided_at = datetime.utcnow()
    invoice.voided_by = g.current_user.id
    invoice.updated_at = datetime.utcnow()
    db.session.commit()

    log_activity(
        activity_type=ActivityType.CANCEL,
        description=f"Voided invoice {invoice.invoice_number}",
        entity_type=EntityType.INVOICE,
        entity_id=invoice.id,
        entity_number=invoice.invoice_number,
        extra_data={'reason': invoice.void_reason}
    )

    return success_response(model_to_dict(invoice), 'Invoice voided')


# ============ CREDIT NOTES ============

@invoice_bp.route('/credit-notes', methods=['GET'])
@jwt_required_with_user()
@permission_required('credit_notes.view')
def list_credit_notes():
    """List credit notes"""
    org_id = g.organization_id

    # Calculate stats
    base_query = CreditNote.query.filter_by(organization_id=org_id)

    total_credit_notes = base_query.count()
    total_amount = db.session.query(db.func.coalesce(db.func.sum(CreditNote.grand_total), 0)).filter(
        CreditNote.organization_id == org_id
    ).scalar()

    applied_amount = db.session.query(db.func.coalesce(db.func.sum(CreditNote.adjusted_amount), 0)).filter(
        CreditNote.organization_id == org_id
    ).scalar()

    pending_count = base_query.filter(CreditNote.status.in_(['draft', 'approved'])).count()

    stats = {
        'total_credit_notes': total_credit_notes,
        'total_amount': float(total_amount or 0),
        'applied_amount': float(applied_amount or 0),
        'pending_count': pending_count
    }

    # Apply filters for listing
    query = CreditNote.query.filter_by(organization_id=org_id)
    filters = get_filters()

    if filters.get('search'):
        search = f"%{filters['search']}%"
        query = query.filter(
            db.or_(
                CreditNote.credit_note_number.ilike(search),
                CreditNote.customer_name.ilike(search)
            )
        )

    if request.args.get('customer_id'):
        query = query.filter_by(customer_id=request.args.get('customer_id', type=int))

    if request.args.get('status'):
        query = query.filter_by(status=request.args.get('status'))

    query = apply_filters(query, CreditNote, filters)

    def serialize(cn):
        data = model_to_dict(cn)
        data['customer_name'] = cn.customer.name if cn.customer else cn.customer_name
        # Get invoice number - try relationship first, then stored field
        if cn.invoice_id and cn.original_invoice:
            data['invoice_number'] = cn.original_invoice.invoice_number
        else:
            data['invoice_number'] = cn.invoice_number or ''
        return data

    result = paginate(query, serialize)
    result['stats'] = stats

    return success_response(result)


@invoice_bp.route('/credit-notes', methods=['POST'])
@jwt_required_with_user()
@permission_required('credit_notes.create')
def create_credit_note():
    """Create credit note"""
    data = get_request_json()

    if not data.get('customer_id') or not data.get('items'):
        return error_response('Customer and items required')

    customer = Customer.query.filter_by(id=data['customer_id'], organization_id=g.organization_id).first()
    if not customer:
        return error_response('Customer not found', status_code=404)

    org = Organization.query.get(g.organization_id)
    cn_number = get_next_number(g.organization_id, 'credit_note')
    place_of_supply = data.get('place_of_supply') or customer.billing_state_code or org.state_code
    is_interstate = place_of_supply != org.state_code

    # Convert empty string to None for integer fields
    invoice_id = data.get('invoice_id')
    if invoice_id == '' or invoice_id is None:
        invoice_id = None
    else:
        invoice_id = int(invoice_id)

    # Get original invoice if provided
    original_invoice = None
    if invoice_id:
        original_invoice = Invoice.query.filter_by(
            id=invoice_id,
            organization_id=g.organization_id
        ).first()

    credit_note = CreditNote(
        organization_id=g.organization_id,
        branch_id=data.get('branch_id') or g.branch_id,
        credit_note_number=cn_number,
        credit_note_date=datetime.strptime(data['credit_note_date'], '%Y-%m-%d').date() if data.get('credit_note_date') else datetime.utcnow().date(),
        invoice_id=invoice_id,
        invoice_number=original_invoice.invoice_number if original_invoice else data.get('invoice_number'),
        invoice_date=original_invoice.invoice_date if original_invoice else None,
        customer_id=data['customer_id'],
        customer_name=customer.name,
        customer_gstin=customer.gstin,
        billing_address_line1=customer.billing_address_line1,
        billing_address_line2=customer.billing_address_line2,
        billing_city=customer.billing_city,
        billing_state=customer.billing_state,
        billing_state_code=customer.billing_state_code,
        billing_pincode=customer.billing_pincode,
        billing_country=customer.billing_country or 'India',
        reason=data.get('reason_type') or data.get('reason', 'return'),
        reason_description=sanitize_string(data.get('reason_description') or data.get('reason', '')),
        place_of_supply=place_of_supply,
        is_igst=is_interstate,
        notes=sanitize_string(data.get('notes', '')),
        status='draft',
        created_by=g.current_user.id
    )

    db.session.add(credit_note)
    db.session.flush()

    subtotal = Decimal('0')
    total_cgst = Decimal('0')
    total_sgst = Decimal('0')
    total_igst = Decimal('0')
    total_cess = Decimal('0')

    for idx, item_data in enumerate(data['items']):
        # Handle empty strings for integer fields
        product_id = item_data.get('product_id')
        if product_id == '' or product_id is None:
            product_id = None
        else:
            product_id = int(product_id)

        variant_id = item_data.get('variant_id')
        if variant_id == '' or variant_id is None:
            variant_id = None
        else:
            variant_id = int(variant_id)

        product = None
        if product_id:
            product = Product.query.filter_by(id=product_id, organization_id=g.organization_id).first()

        qty = Decimal(str(item_data.get('quantity', 1)))
        rate = Decimal(str(item_data.get('rate', item_data.get('unit_price', product.selling_price if product else 0))))
        taxable = qty * rate

        # Get tax rates
        tax_rate = Decimal(str(item_data.get('tax_rate', 0)))
        cgst_rate = sgst_rate = igst_rate = cess_rate = Decimal('0')

        if product and product.tax_rate:
            if is_interstate:
                igst_rate = Decimal(str(product.tax_rate.igst_rate or 0))
            else:
                cgst_rate = Decimal(str(product.tax_rate.cgst_rate or 0))
                sgst_rate = Decimal(str(product.tax_rate.sgst_rate or 0))
            cess_rate = Decimal(str(product.tax_rate.cess_rate or 0))
        elif tax_rate > 0:
            if is_interstate:
                igst_rate = tax_rate
            else:
                cgst_rate = tax_rate / 2
                sgst_rate = tax_rate / 2

        cgst = taxable * cgst_rate / 100
        sgst = taxable * sgst_rate / 100
        igst = taxable * igst_rate / 100
        cess = taxable * cess_rate / 100
        item_tax = cgst + sgst + igst + cess
        amount = taxable + item_tax

        item = CreditNoteItem(
            credit_note_id=credit_note.id,
            line_number=idx + 1,
            product_id=product_id,
            variant_id=variant_id,
            invoice_item_id=item_data.get('invoice_item_id'),
            sku=product.sku if product else item_data.get('sku'),
            hsn_code=product.hsn_code if product else item_data.get('hsn_code'),
            name=item_data.get('name', product.name if product else ''),
            description=sanitize_string(item_data.get('description', '')),
            quantity=float(qty),
            unit_name=item_data.get('unit_name', product.unit.symbol if product and product.unit else ''),
            rate=float(rate),
            tax_rate=float(cgst_rate + sgst_rate + igst_rate),
            cgst_rate=float(cgst_rate),
            sgst_rate=float(sgst_rate),
            igst_rate=float(igst_rate),
            cess_rate=float(cess_rate),
            taxable_amount=float(taxable),
            cgst_amount=float(cgst),
            sgst_amount=float(sgst),
            igst_amount=float(igst),
            cess_amount=float(cess),
            total_tax=float(item_tax),
            amount=float(amount)
        )
        db.session.add(item)

        subtotal += taxable
        total_cgst += cgst
        total_sgst += sgst
        total_igst += igst
        total_cess += cess

    total_tax = total_cgst + total_sgst + total_igst + total_cess
    grand_total = subtotal + total_tax

    # Apply rounding
    round_off = Decimal(str(round(grand_total))) - grand_total

    credit_note.subtotal = float(subtotal)
    credit_note.taxable_amount = float(subtotal)
    credit_note.cgst_amount = float(total_cgst)
    credit_note.sgst_amount = float(total_sgst)
    credit_note.igst_amount = float(total_igst)
    credit_note.cess_amount = float(total_cess)
    credit_note.total_tax = float(total_tax)
    credit_note.round_off = float(round_off)
    credit_note.grand_total = float(round(grand_total))
    credit_note.balance_amount = float(round(grand_total))

    db.session.commit()

    log_activity(
        activity_type=ActivityType.CREATE,
        description=f"Created credit note {credit_note.credit_note_number} for {customer.name}",
        entity_type=EntityType.CREDIT_NOTE,
        entity_id=credit_note.id,
        entity_number=credit_note.credit_note_number,
        extra_data={'customer_id': customer.id, 'total': float(credit_note.grand_total)}
    )

    return success_response(model_to_dict(credit_note), 'Credit note created', 201)


@invoice_bp.route('/credit-notes/<int:id>', methods=['GET'])
@jwt_required_with_user()
@permission_required('credit_notes.view')
def get_credit_note(id):
    """Get credit note details"""
    cn = CreditNote.query.filter_by(id=id, organization_id=g.organization_id).first()
    if not cn:
        return error_response('Credit note not found', status_code=404)

    data = model_to_dict(cn)
    data['customer'] = model_to_dict(cn.customer) if cn.customer else None
    data['original_invoice'] = model_to_dict(cn.original_invoice) if cn.original_invoice else None

    # Ensure invoice_number is set from relationship if not stored
    if not data.get('invoice_number') and cn.original_invoice:
        data['invoice_number'] = cn.original_invoice.invoice_number

    # Map reason fields for frontend compatibility
    data['reason_type'] = cn.reason
    data['reason_description'] = cn.reason_description

    data['items'] = []

    for item in cn.items:
        item_data = model_to_dict(item)
        item_data['product'] = {
            'id': item.product.id,
            'name': item.product.name,
            'sku': item.product.sku
        } if item.product else None
        data['items'].append(item_data)

    return success_response(data)


@invoice_bp.route('/credit-notes/<int:id>', methods=['PUT'])
@jwt_required_with_user()
@permission_required('credit_notes.edit')
def update_credit_note(id):
    """Update credit note"""
    cn = CreditNote.query.filter_by(id=id, organization_id=g.organization_id).first()
    if not cn:
        return error_response('Credit note not found', status_code=404)

    if cn.status not in ['draft']:
        return error_response('Only draft credit notes can be edited')

    data = get_request_json()

    # Update basic fields
    if data.get('credit_note_date'):
        cn.credit_note_date = datetime.strptime(data['credit_note_date'], '%Y-%m-%d').date()
    if data.get('reason'):
        cn.reason = data['reason']
    if data.get('reason_description'):
        cn.reason_description = sanitize_string(data['reason_description'])
    if data.get('notes'):
        cn.notes = sanitize_string(data['notes'])

    # Update items if provided
    if data.get('items'):
        # Delete existing items
        CreditNoteItem.query.filter_by(credit_note_id=cn.id).delete()

        org = Organization.query.get(g.organization_id)
        is_interstate = cn.is_igst

        subtotal = Decimal('0')
        total_cgst = Decimal('0')
        total_sgst = Decimal('0')
        total_igst = Decimal('0')
        total_cess = Decimal('0')

        for idx, item_data in enumerate(data['items']):
            # Handle empty strings for integer fields
            product_id = item_data.get('product_id')
            if product_id == '' or product_id is None:
                product_id = None
            else:
                product_id = int(product_id)

            variant_id = item_data.get('variant_id')
            if variant_id == '' or variant_id is None:
                variant_id = None
            else:
                variant_id = int(variant_id)

            product = None
            if product_id:
                product = Product.query.filter_by(id=product_id, organization_id=g.organization_id).first()

            qty = Decimal(str(item_data.get('quantity', 1)))
            rate = Decimal(str(item_data.get('rate', product.selling_price if product else 0)))
            taxable = qty * rate

            tax_rate = Decimal(str(item_data.get('tax_rate', 0)))
            cgst_rate = sgst_rate = igst_rate = cess_rate = Decimal('0')

            if product and product.tax_rate:
                if is_interstate:
                    igst_rate = Decimal(str(product.tax_rate.igst_rate or 0))
                else:
                    cgst_rate = Decimal(str(product.tax_rate.cgst_rate or 0))
                    sgst_rate = Decimal(str(product.tax_rate.sgst_rate or 0))
                cess_rate = Decimal(str(product.tax_rate.cess_rate or 0))
            elif tax_rate > 0:
                if is_interstate:
                    igst_rate = tax_rate
                else:
                    cgst_rate = tax_rate / 2
                    sgst_rate = tax_rate / 2

            cgst = taxable * cgst_rate / 100
            sgst = taxable * sgst_rate / 100
            igst = taxable * igst_rate / 100
            cess = taxable * cess_rate / 100
            item_tax = cgst + sgst + igst + cess
            amount = taxable + item_tax

            item = CreditNoteItem(
                credit_note_id=cn.id,
                line_number=idx + 1,
                product_id=product_id,
                variant_id=variant_id,
                sku=product.sku if product else item_data.get('sku'),
                hsn_code=product.hsn_code if product else item_data.get('hsn_code'),
                name=item_data.get('name', product.name if product else ''),
                description=sanitize_string(item_data.get('description', '')),
                quantity=float(qty),
                unit_name=item_data.get('unit_name', ''),
                rate=float(rate),
                tax_rate=float(cgst_rate + sgst_rate + igst_rate),
                cgst_rate=float(cgst_rate),
                sgst_rate=float(sgst_rate),
                igst_rate=float(igst_rate),
                cess_rate=float(cess_rate),
                taxable_amount=float(taxable),
                cgst_amount=float(cgst),
                sgst_amount=float(sgst),
                igst_amount=float(igst),
                cess_amount=float(cess),
                total_tax=float(item_tax),
                amount=float(amount)
            )
            db.session.add(item)

            subtotal += taxable
            total_cgst += cgst
            total_sgst += sgst
            total_igst += igst
            total_cess += cess

        total_tax = total_cgst + total_sgst + total_igst + total_cess
        grand_total = subtotal + total_tax
        round_off = Decimal(str(round(grand_total))) - grand_total

        cn.subtotal = float(subtotal)
        cn.taxable_amount = float(subtotal)
        cn.cgst_amount = float(total_cgst)
        cn.sgst_amount = float(total_sgst)
        cn.igst_amount = float(total_igst)
        cn.cess_amount = float(total_cess)
        cn.total_tax = float(total_tax)
        cn.round_off = float(round_off)
        cn.grand_total = float(round(grand_total))
        cn.balance_amount = float(round(grand_total))

    cn.updated_at = datetime.utcnow()
    db.session.commit()

    return success_response(model_to_dict(cn), 'Credit note updated')


@invoice_bp.route('/credit-notes/<int:id>', methods=['DELETE'])
@jwt_required_with_user()
@permission_required('credit_notes.delete')
def delete_credit_note(id):
    """Delete credit note"""
    cn = CreditNote.query.filter_by(id=id, organization_id=g.organization_id).first()
    if not cn:
        return error_response('Credit note not found', status_code=404)

    if cn.status not in ['draft']:
        return error_response('Only draft credit notes can be deleted')

    db.session.delete(cn)
    db.session.commit()

    return success_response(None, 'Credit note deleted')


@invoice_bp.route('/credit-notes/<int:id>/approve', methods=['POST'])
@jwt_required_with_user()
@permission_required('credit_notes.edit')
def approve_credit_note(id):
    """Approve credit note"""
    cn = CreditNote.query.filter_by(id=id, organization_id=g.organization_id).first()
    if not cn:
        return error_response('Credit note not found', status_code=404)

    if cn.status != 'draft':
        return error_response('Only draft credit notes can be approved')

    cn.status = 'approved'
    cn.updated_at = datetime.utcnow()
    db.session.commit()

    return success_response(model_to_dict(cn), 'Credit note approved')


@invoice_bp.route('/credit-notes/<int:id>/apply', methods=['POST'])
@jwt_required_with_user()
@permission_required('credit_notes.edit')
def apply_credit_note(id):
    """Apply credit note to invoice"""
    cn = CreditNote.query.filter_by(id=id, organization_id=g.organization_id).first()
    if not cn:
        return error_response('Credit note not found', status_code=404)

    if cn.status == 'draft':
        return error_response('Credit note must be approved before applying')

    data = get_request_json()
    invoice_id = data.get('invoice_id')
    amount = Decimal(str(data.get('amount', cn.grand_total)))

    if not invoice_id:
        return error_response('Invoice ID required')

    invoice = Invoice.query.filter_by(id=invoice_id, organization_id=g.organization_id).first()
    if not invoice:
        return error_response('Invoice not found', status_code=404)

    available = Decimal(str(cn.grand_total or 0)) - Decimal(str(cn.adjusted_amount or 0))
    if amount > available:
        return error_response('Amount exceeds available credit')

    if amount > Decimal(str(invoice.balance_due or 0)):
        amount = Decimal(str(invoice.balance_due))

    # Update credit note
    cn.adjusted_amount = float(Decimal(str(cn.adjusted_amount or 0)) + amount)
    cn.balance_amount = float(Decimal(str(cn.grand_total or 0)) - Decimal(str(cn.adjusted_amount or 0)))
    cn.status = 'adjusted' if cn.balance_amount <= 0 else 'partial'

    # Update invoice
    invoice.credit_note_amount = float(Decimal(str(invoice.credit_note_amount or 0)) + amount)
    invoice.balance_due = float(Decimal(str(invoice.grand_total or 0)) - Decimal(str(invoice.paid_amount or 0)) - Decimal(str(invoice.credit_note_amount or 0)))

    if invoice.balance_due <= 0:
        invoice.payment_status = 'paid'
        invoice.status = 'paid'
    else:
        invoice.payment_status = 'partial'

    # Update customer outstanding
    customer = cn.customer
    if customer:
        customer.outstanding_amount = float(Decimal(str(customer.outstanding_amount or 0)) - amount)

    db.session.commit()

    return success_response({
        'credit_note_id': cn.id,
        'invoice_id': invoice.id,
        'amount_applied': float(amount),
        'remaining_balance': float(cn.balance_amount)
    }, 'Credit note applied')


# ============ DEBIT NOTES ============

@invoice_bp.route('/debit-notes', methods=['GET'])
@jwt_required_with_user()
@permission_required('debit_notes.view')
def list_debit_notes():
    """List debit notes"""
    query = DebitNote.query.filter_by(organization_id=g.organization_id)
    filters = get_filters()
    
    if request.args.get('supplier_id'):
        query = query.filter_by(supplier_id=request.args.get('supplier_id', type=int))
    
    query = apply_filters(query, DebitNote, filters)
    
    def serialize(dn):
        data = model_to_dict(dn)
        data['supplier_name'] = dn.supplier.name if dn.supplier else None
        # Ensure balance fields are included
        data['grand_total'] = float(dn.grand_total or 0)
        data['adjusted_amount'] = float(dn.adjusted_amount or 0)
        data['balance_amount'] = float(dn.balance_amount or 0)
        # If balance_amount is 0 and nothing adjusted, set it to grand_total
        if data['balance_amount'] == 0 and data['adjusted_amount'] == 0:
            data['balance_amount'] = data['grand_total']
        return data

    return success_response(paginate(query, serialize))


@invoice_bp.route('/debit-notes', methods=['POST'])
@jwt_required_with_user()
@permission_required('debit_notes.create')
def create_debit_note():
    """Create debit note"""
    data = get_request_json()
    
    if not data.get('supplier_id') or not data.get('items'):
        return error_response('Supplier and items required')
    
    supplier = Supplier.query.filter_by(id=data['supplier_id'], organization_id=g.organization_id).first()
    if not supplier:
        return error_response('Supplier not found', status_code=404)
    
    org = Organization.query.get(g.organization_id)
    dn_number = get_next_number(g.organization_id, 'debit_note')
    is_interstate = (supplier.state_code or '') != org.state_code
    
    # Handle empty date strings
    supplier_invoice_date = data.get('supplier_invoice_date')
    if supplier_invoice_date == '':
        supplier_invoice_date = None

    debit_note = DebitNote(
        organization_id=g.organization_id,
        branch_id=data.get('branch_id') or g.branch_id,
        debit_note_number=dn_number,
        purchase_order_id=data.get('purchase_order_id') or None,
        supplier_invoice_number=data.get('supplier_invoice_number') or None,
        supplier_invoice_date=supplier_invoice_date,
        supplier_id=data['supplier_id'],
        supplier_name=supplier.name,
        supplier_gstin=supplier.gstin,
        address_line1=supplier.address_line1,
        address_line2=supplier.address_line2,
        city=supplier.city,
        state=supplier.state,
        state_code=supplier.state_code,
        pincode=supplier.pincode,
        debit_note_date=data.get('debit_note_date', datetime.utcnow().date()),
        reason=data.get('reason_type', data.get('reason', 'return')),
        reason_description=sanitize_string(data.get('reason', '')),
        place_of_supply=data.get('place_of_supply') or org.state_code,
        is_igst=is_interstate,
        notes=sanitize_string(data.get('notes', '')),
        status='draft',
        created_by=g.current_user.id
    )
    
    db.session.add(debit_note)
    db.session.flush()
    
    subtotal = Decimal('0')
    total_cgst = Decimal('0')
    total_sgst = Decimal('0')
    total_igst = Decimal('0')
    total_cess = Decimal('0')
    
    for idx, item_data in enumerate(data['items']):
        product = Product.query.filter_by(id=item_data['product_id'], organization_id=g.organization_id).first()
        if not product:
            continue

        qty = Decimal(str(item_data.get('quantity', 1)))
        unit_price = Decimal(str(item_data.get('rate', item_data.get('unit_price', product.purchase_price or 0))))
        
        taxable = qty * unit_price
        
        cgst = sgst = igst = cess = Decimal('0')
        if product.tax_rate:
            if is_interstate:
                igst = taxable * Decimal(str(product.tax_rate.igst_rate)) / 100
            else:
                cgst = taxable * Decimal(str(product.tax_rate.cgst_rate)) / 100
                sgst = taxable * Decimal(str(product.tax_rate.sgst_rate)) / 100
            cess = taxable * Decimal(str(product.tax_rate.cess_rate or 0)) / 100
        
        total = taxable + cgst + sgst + igst + cess
        
        item = DebitNoteItem(
            debit_note_id=debit_note.id,
            line_number=idx + 1,
            product_id=product.id,
            variant_id=item_data.get('variant_id'),
            sku=product.sku,
            hsn_code=product.hsn_code,
            name=product.name,
            description=sanitize_string(item_data.get('description', '')),
            quantity=float(qty),
            unit_name=product.unit.symbol if product.unit else item_data.get('unit', ''),
            rate=float(unit_price),
            tax_rate=float(product.tax_rate.rate) if product.tax_rate else 0,
            taxable_amount=float(taxable),
            cgst_rate=product.tax_rate.cgst_rate if product.tax_rate and not is_interstate else 0,
            cgst_amount=float(cgst),
            sgst_rate=product.tax_rate.sgst_rate if product.tax_rate and not is_interstate else 0,
            sgst_amount=float(sgst),
            igst_rate=product.tax_rate.igst_rate if product.tax_rate and is_interstate else 0,
            igst_amount=float(igst),
            cess_rate=product.tax_rate.cess_rate if product.tax_rate else 0,
            cess_amount=float(cess),
            total_tax=float(cgst + sgst + igst + cess),
            amount=float(total)
        )
        db.session.add(item)
        
        subtotal += taxable
        total_cgst += cgst
        total_sgst += sgst
        total_igst += igst
        total_cess += cess
    
    total_tax = total_cgst + total_sgst + total_igst + total_cess
    total_amount = subtotal + total_tax
    
    debit_note.subtotal = float(subtotal)
    debit_note.taxable_amount = float(subtotal)
    debit_note.cgst_amount = float(total_cgst)
    debit_note.sgst_amount = float(total_sgst)
    debit_note.igst_amount = float(total_igst)
    debit_note.cess_amount = float(total_cess)
    debit_note.total_tax = float(total_tax)
    debit_note.grand_total = float(round(total_amount))
    debit_note.balance_amount = float(round(total_amount))

    db.session.commit()

    return success_response(model_to_dict(debit_note), 'Debit note created', 201)


@invoice_bp.route('/debit-notes/<int:id>', methods=['GET'])
@jwt_required_with_user()
@permission_required('debit_notes.view')
def get_debit_note(id):
    """Get debit note details"""
    dn = DebitNote.query.filter_by(id=id, organization_id=g.organization_id).first()
    if not dn:
        return error_response('Debit note not found', status_code=404)

    data = model_to_dict(dn)
    data['supplier'] = model_to_dict(dn.supplier) if dn.supplier else None
    data['items'] = [model_to_dict(i) for i in dn.items]

    return success_response(data)


@invoice_bp.route('/debit-notes/<int:id>', methods=['PUT'])
@jwt_required_with_user()
@permission_required('debit_notes.edit')
def update_debit_note(id):
    """Update debit note"""
    dn = DebitNote.query.filter_by(id=id, organization_id=g.organization_id).first()
    if not dn:
        return error_response('Debit note not found', status_code=404)

    if dn.status not in ['draft']:
        return error_response('Can only edit draft debit notes')

    data = get_request_json()

    # Handle reason_type mapping
    if 'reason_type' in data:
        dn.reason = data['reason_type']
    if 'reason' in data and 'reason_type' not in data:
        dn.reason = data['reason']
    if 'reason' in data and 'reason_type' in data:
        dn.reason_description = sanitize_string(data.get('reason', ''))

    # Handle empty date strings
    if 'supplier_invoice_date' in data:
        data['supplier_invoice_date'] = data['supplier_invoice_date'] or None
    if 'debit_note_date' in data and data['debit_note_date'] == '':
        del data['debit_note_date']  # Don't update with empty string

    # Update basic fields
    updateable = ['debit_note_date', 'reason_description', 'notes',
                  'supplier_invoice_number', 'supplier_invoice_date', 'place_of_supply', 'status']

    for field in updateable:
        if field in data:
            value = data[field]
            # Convert empty strings to None for optional fields
            if value == '' and field in ['supplier_invoice_number', 'supplier_invoice_date']:
                value = None
            setattr(dn, field, value)

    # If items are provided, update them
    if 'items' in data:
        # Delete existing items
        DebitNoteItem.query.filter_by(debit_note_id=dn.id).delete()

        org = Organization.query.get(g.organization_id)
        supplier = Supplier.query.get(dn.supplier_id)
        is_interstate = (supplier.state_code or '') != org.state_code if supplier else False

        subtotal = Decimal('0')
        total_cgst = Decimal('0')
        total_sgst = Decimal('0')
        total_igst = Decimal('0')
        total_cess = Decimal('0')

        for idx, item_data in enumerate(data['items']):
            product = Product.query.filter_by(id=item_data['product_id'], organization_id=g.organization_id).first()
            if not product:
                continue

            qty = Decimal(str(item_data.get('quantity', 1)))
            unit_price = Decimal(str(item_data.get('rate', item_data.get('unit_price', product.purchase_price or 0))))

            taxable = qty * unit_price

            cgst = sgst = igst = cess = Decimal('0')
            if product.tax_rate:
                if is_interstate:
                    igst = taxable * Decimal(str(product.tax_rate.igst_rate)) / 100
                else:
                    cgst = taxable * Decimal(str(product.tax_rate.cgst_rate)) / 100
                    sgst = taxable * Decimal(str(product.tax_rate.sgst_rate)) / 100
                cess = taxable * Decimal(str(product.tax_rate.cess_rate or 0)) / 100

            total = taxable + cgst + sgst + igst + cess

            item = DebitNoteItem(
                debit_note_id=dn.id,
                line_number=idx + 1,
                product_id=product.id,
                variant_id=item_data.get('variant_id'),
                sku=product.sku,
                hsn_code=item_data.get('hsn_code', product.hsn_code),
                name=sanitize_string(item_data.get('product_name', product.name)),
                description=sanitize_string(item_data.get('description', '')),
                quantity=float(qty),
                unit_name=item_data.get('unit', product.unit.symbol if product.unit else ''),
                rate=float(unit_price),
                tax_rate=float(product.tax_rate.rate) if product.tax_rate else 0,
                taxable_amount=float(taxable),
                cgst_rate=product.tax_rate.cgst_rate if product.tax_rate and not is_interstate else 0,
                cgst_amount=float(cgst),
                sgst_rate=product.tax_rate.sgst_rate if product.tax_rate and not is_interstate else 0,
                sgst_amount=float(sgst),
                igst_rate=product.tax_rate.igst_rate if product.tax_rate and is_interstate else 0,
                igst_amount=float(igst),
                cess_rate=product.tax_rate.cess_rate if product.tax_rate else 0,
                cess_amount=float(cess),
                total_tax=float(cgst + sgst + igst + cess),
                amount=float(total)
            )
            db.session.add(item)

            subtotal += taxable
            total_cgst += cgst
            total_sgst += sgst
            total_igst += igst
            total_cess += cess

        total_tax = total_cgst + total_sgst + total_igst + total_cess
        total_amount = subtotal + total_tax

        dn.subtotal = float(subtotal)
        dn.taxable_amount = float(subtotal)
        dn.cgst_amount = float(total_cgst)
        dn.sgst_amount = float(total_sgst)
        dn.igst_amount = float(total_igst)
        dn.cess_amount = float(total_cess)
        dn.total_tax = float(total_tax)
        dn.grand_total = float(round(total_amount))
        dn.balance_amount = float(round(total_amount))

    dn.updated_at = datetime.utcnow()
    db.session.commit()

    return success_response(model_to_dict(dn), 'Debit note updated')


@invoice_bp.route('/debit-notes/<int:id>', methods=['DELETE'])
@jwt_required_with_user()
@permission_required('debit_notes.delete')
def delete_debit_note(id):
    """Delete debit note"""
    dn = DebitNote.query.filter_by(id=id, organization_id=g.organization_id).first()
    if not dn:
        return error_response('Debit note not found', status_code=404)

    if dn.status not in ['draft']:
        return error_response('Can only delete draft debit notes')

    # Delete items first
    DebitNoteItem.query.filter_by(debit_note_id=dn.id).delete()

    db.session.delete(dn)
    db.session.commit()

    return success_response(None, 'Debit note deleted')


@invoice_bp.route('/debit-notes/<int:id>/approve', methods=['POST'])
@jwt_required_with_user()
@permission_required('debit_notes.edit')
def approve_debit_note(id):
    """Approve debit note"""
    dn = DebitNote.query.filter_by(id=id, organization_id=g.organization_id).first()
    if not dn:
        return error_response('Debit note not found', status_code=404)

    if dn.status != 'draft':
        return error_response('Only draft debit notes can be approved')

    dn.status = 'approved'
    dn.updated_at = datetime.utcnow()
    db.session.commit()

    return success_response(model_to_dict(dn), 'Debit note approved')


@invoice_bp.route('/debit-notes/<int:id>/apply', methods=['POST'])
@jwt_required_with_user()
@permission_required('debit_notes.edit')
def apply_debit_note(id):
    """Apply debit note to reduce supplier payable"""
    from app.models import PurchaseOrder

    dn = DebitNote.query.filter_by(id=id, organization_id=g.organization_id).first()
    if not dn:
        return error_response('Debit note not found', status_code=404)

    if dn.status == 'applied':
        return error_response('Debit note already fully applied')

    if dn.status not in ['approved', 'issued', 'partially_applied']:
        return error_response('Debit note must be approved before applying')

    data = get_request_json()

    # Get total amount from debit note
    total = Decimal(str(dn.grand_total or 0))
    if total <= 0:
        return error_response('Debit note has no amount to apply')

    # Calculate available amount
    already_adjusted = Decimal(str(dn.adjusted_amount or 0))
    available = total - already_adjusted

    # Get amount to apply (default to full available amount)
    amount = Decimal(str(data.get('amount', float(available))))

    if amount <= 0:
        return error_response('Amount must be greater than 0')
    if amount > available:
        return error_response(f'Amount exceeds available balance of {float(available):.2f}')

    # Update debit note
    dn.adjusted_amount = float(already_adjusted + amount)
    dn.balance_amount = float(available - amount)

    if dn.balance_amount <= 0:
        dn.status = 'applied'
    else:
        dn.status = 'partially_applied'

    # Update supplier balance if applicable (debit note reduces what we owe)
    supplier = dn.supplier
    if supplier:
        supplier.current_balance = float(Decimal(str(supplier.current_balance or 0)) - amount)

    # Update related purchase order if exists
    if dn.purchase_order_id:
        po = PurchaseOrder.query.get(dn.purchase_order_id)
        if po:
            # Add note about debit note applied
            existing_notes = po.notes or ''
            debit_note_info = f"\nDebit Note {dn.debit_note_number} applied: ₹{float(amount):.2f}"
            if debit_note_info not in existing_notes:
                po.notes = existing_notes + debit_note_info

    db.session.commit()

    return success_response({
        'debit_note_id': dn.id,
        'debit_note_number': dn.debit_note_number,
        'total_amount': float(total),
        'amount_applied': float(amount),
        'total_adjusted': float(dn.adjusted_amount),
        'balance_remaining': float(dn.balance_amount or 0),
        'status': dn.status
    }, 'Debit note applied successfully')