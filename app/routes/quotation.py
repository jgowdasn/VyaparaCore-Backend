"""Quotation routes for VyaparaCore"""
from flask import Blueprint, g, request
from datetime import datetime, timedelta
from decimal import Decimal
from config.database import db
from app.models import (
    Quotation, QuotationItem, QuotationTerms, Customer, Product,
    Organization, SequenceNumber
)
from app.utils.security import (
    jwt_required_with_user, permission_required, sanitize_string, create_audit_log
)
from app.utils.helpers import (
    success_response, error_response, get_request_json,
    paginate, get_filters, apply_filters, model_to_dict
)

quotation_bp = Blueprint('quotation', __name__)


def get_next_quotation_number(org_id):
    """Generate next quotation number"""
    from app.models import InvoiceSettings
    settings = InvoiceSettings.query.filter_by(organization_id=org_id).first()
    prefix = settings.quotation_prefix if settings else 'QTN'
    
    seq = SequenceNumber.query.filter_by(
        organization_id=org_id,
        document_type='quotation'
    ).first()
    
    if not seq:
        seq = SequenceNumber(
            organization_id=org_id,
            document_type='quotation',
            prefix=prefix,
            current_number=0,
            number_length=5
        )
        db.session.add(seq)
    
    seq.current_number += 1
    number = f"{prefix}{seq.current_number:05d}"
    
    return number


def calculate_tax(item_data, product, org):
    """Calculate tax amounts based on GST rules"""
    quantity = Decimal(str(item_data.get('quantity', 1)))
    unit_price = Decimal(str(item_data.get('unit_price', product.selling_price or 0)))
    discount_percent = Decimal(str(item_data.get('discount_percent', 0)))
    
    subtotal = quantity * unit_price
    discount_amount = subtotal * discount_percent / 100
    taxable_amount = subtotal - discount_amount
    
    # Get tax rate
    tax_rate = product.tax_rate
    cgst = sgst = igst = cess = Decimal('0')
    
    if tax_rate:
        # Determine if IGST or CGST+SGST based on place of supply
        # For simplicity, using CGST+SGST (same state)
        is_interstate = item_data.get('is_interstate', False)
        
        if is_interstate:
            igst = taxable_amount * Decimal(str(tax_rate.igst_rate)) / 100
        else:
            cgst = taxable_amount * Decimal(str(tax_rate.cgst_rate)) / 100
            sgst = taxable_amount * Decimal(str(tax_rate.sgst_rate)) / 100
        
        cess = taxable_amount * Decimal(str(tax_rate.cess_rate or 0)) / 100
    
    total_tax = cgst + sgst + igst + cess
    total = taxable_amount + total_tax
    
    return {
        'subtotal': float(subtotal),
        'discount_amount': float(discount_amount),
        'taxable_amount': float(taxable_amount),
        'cgst_amount': float(cgst),
        'sgst_amount': float(sgst),
        'igst_amount': float(igst),
        'cess_amount': float(cess),
        'tax_amount': float(total_tax),
        'total': float(total)
    }


@quotation_bp.route('', methods=['GET'])
@jwt_required_with_user()
@permission_required('quotations.view')
def list_quotations():
    """List all quotations"""
    query = Quotation.query.filter_by(organization_id=g.organization_id)
    
    filters = get_filters()
    if filters.get('search'):
        search = f"%{filters['search']}%"
        query = query.filter(
            db.or_(
                Quotation.quotation_number.ilike(search),
                Quotation.reference_number.ilike(search)
            )
        )
    
    if request.args.get('customer_id'):
        query = query.filter_by(customer_id=request.args.get('customer_id', type=int))
    
    if filters.get('status'):
        query = query.filter_by(status=filters['status'])
    
    query = apply_filters(query, Quotation, filters)
    
    def serialize(q):
        data = model_to_dict(q)
        # customer_name is already stored in the model
        data['total_amount'] = float(q.grand_total or 0)
        return data
    
    return success_response(paginate(query, serialize))


@quotation_bp.route('', methods=['POST'])
@jwt_required_with_user()
@permission_required('quotations.create')
def create_quotation():
    """Create new quotation"""
    data = get_request_json()
    
    if not data.get('customer_id') or not data.get('items'):
        return error_response('Customer and items required')
    
    customer = Customer.query.filter_by(id=data['customer_id'], organization_id=g.organization_id).first()
    if not customer:
        return error_response('Customer not found', status_code=404)
    
    org = Organization.query.get(g.organization_id)
    
    # Generate quotation number
    quotation_number = get_next_quotation_number(g.organization_id)
    
    quotation = Quotation(
        organization_id=g.organization_id,
        branch_id=data.get('branch_id') or g.branch_id,
        quotation_number=quotation_number,
        reference_number=sanitize_string(data.get('reference_number', '')),
        customer_id=data['customer_id'],
        customer_name=customer.name,
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
        quotation_date=data.get('quotation_date', datetime.utcnow().date()),
        valid_until=data.get('valid_until', (datetime.utcnow() + timedelta(days=30)).date()),
        place_of_supply=data.get('place_of_supply') or customer.billing_state_code or org.state_code,
        currency=data.get('currency', 'INR'),
        exchange_rate=data.get('exchange_rate', 1),
        status=data.get('status', 'draft'),
        subject=sanitize_string(data.get('subject', '')),
        notes=sanitize_string(data.get('notes', '')),
        customer_notes=sanitize_string(data.get('customer_notes', '')),
        created_by=g.current_user.id
    )
    
    # Determine if interstate
    is_interstate = quotation.place_of_supply != org.state_code
    
    db.session.add(quotation)
    db.session.flush()
    
    # Add items
    subtotal = Decimal('0')
    total_discount = Decimal('0')
    total_cgst = Decimal('0')
    total_sgst = Decimal('0')
    total_igst = Decimal('0')
    total_cess = Decimal('0')
    
    for idx, item_data in enumerate(data['items']):
        product = Product.query.filter_by(id=item_data['product_id'], organization_id=g.organization_id).first()
        if not product:
            continue
        
        item_data['is_interstate'] = is_interstate
        tax_calc = calculate_tax(item_data, product, org)
        
        item = QuotationItem(
            quotation_id=quotation.id,
            product_id=product.id,
            variant_id=item_data.get('variant_id'),
            line_number=idx + 1,
            name=product.name,
            description=sanitize_string(item_data.get('description', '')),
            sku=product.sku,
            hsn_code=product.hsn_code or item_data.get('hsn_code', ''),
            quantity=item_data.get('quantity', 1),
            unit_id=item_data.get('unit_id') or product.unit_id,
            unit_name=product.unit.symbol if product.unit else None,
            rate=item_data.get('unit_price', product.selling_price),
            discount_type='percentage',
            discount_value=item_data.get('discount_percent', 0),
            discount_amount=tax_calc['discount_amount'],
            taxable_amount=tax_calc['taxable_amount'],
            tax_rate_id=product.tax_rate_id,
            tax_rate=product.tax_rate.rate if product.tax_rate else 0,
            cgst_rate=product.tax_rate.cgst_rate if product.tax_rate and not is_interstate else 0,
            cgst_amount=tax_calc['cgst_amount'],
            sgst_rate=product.tax_rate.sgst_rate if product.tax_rate and not is_interstate else 0,
            sgst_amount=tax_calc['sgst_amount'],
            igst_rate=product.tax_rate.igst_rate if product.tax_rate and is_interstate else 0,
            igst_amount=tax_calc['igst_amount'],
            cess_rate=product.tax_rate.cess_rate if product.tax_rate else 0,
            cess_amount=tax_calc['cess_amount'],
            total_tax=tax_calc['cgst_amount'] + tax_calc['sgst_amount'] + tax_calc['igst_amount'] + tax_calc['cess_amount'],
            amount=tax_calc['total']
        )
        db.session.add(item)
        
        subtotal += Decimal(str(tax_calc['taxable_amount']))
        total_discount += Decimal(str(tax_calc['discount_amount']))
        total_cgst += Decimal(str(tax_calc['cgst_amount']))
        total_sgst += Decimal(str(tax_calc['sgst_amount']))
        total_igst += Decimal(str(tax_calc['igst_amount']))
        total_cess += Decimal(str(tax_calc['cess_amount']))
    
    # Additional charges
    shipping_charges = Decimal(str(data.get('shipping_charges', 0)))
    packaging_charges = Decimal(str(data.get('packaging_charges', 0)))
    other_charges = Decimal(str(data.get('other_charges', 0)))
    additional_discount = Decimal(str(data.get('additional_discount', 0)))
    
    total_tax = total_cgst + total_sgst + total_igst + total_cess
    total_amount = subtotal + total_tax + shipping_charges + packaging_charges + other_charges - additional_discount
    
    # Round off
    round_off = round(total_amount) - total_amount
    total_amount = round(total_amount)
    
    quotation.subtotal = float(subtotal)
    quotation.discount_amount = float(total_discount + additional_discount)
    quotation.taxable_amount = float(subtotal - total_discount - additional_discount)
    quotation.cgst_amount = float(total_cgst)
    quotation.sgst_amount = float(total_sgst)
    quotation.igst_amount = float(total_igst)
    quotation.cess_amount = float(total_cess)
    quotation.total_tax = float(total_tax)
    quotation.shipping_charges = float(shipping_charges)
    quotation.packaging_charges = float(packaging_charges)
    quotation.other_charges = float(other_charges)
    quotation.round_off = float(round_off)
    quotation.grand_total = float(total_amount)
    
    # Add terms - handle both string and array format
    terms_data = data.get('terms')
    if terms_data:
        if isinstance(terms_data, str):
            # If terms is a string, store it in customer_notes
            if terms_data.strip():
                quotation.customer_notes = terms_data
        elif isinstance(terms_data, list):
            # If terms is an array of objects
            for term_data in terms_data:
                if isinstance(term_data, dict):
                    term = QuotationTerms(
                        quotation_id=quotation.id,
                        term_type=term_data.get('term_type', 'general'),
                        title=sanitize_string(term_data.get('title', '')),
                        description=sanitize_string(term_data.get('description', '')),
                        display_order=term_data.get('display_order', 0)
                    )
                    db.session.add(term)
    
    db.session.commit()
    
    create_audit_log('quotations', quotation.id, 'create', None, model_to_dict(quotation))
    
    return success_response(model_to_dict(quotation), 'Quotation created', 201)


@quotation_bp.route('/<int:id>', methods=['GET'])
@jwt_required_with_user()
@permission_required('quotations.view')
def get_quotation(id):
    """Get quotation details"""
    quotation = Quotation.query.filter_by(id=id, organization_id=g.organization_id).first()
    if not quotation:
        return error_response('Quotation not found', status_code=404)

    data = model_to_dict(quotation)

    # Fetch customer separately
    if quotation.customer_id:
        customer = Customer.query.get(quotation.customer_id)
        data['customer'] = model_to_dict(customer) if customer else None
    else:
        data['customer'] = None

    data['items'] = []
    for item in quotation.items:
        item_data = model_to_dict(item)
        # Fetch product separately
        if item.product_id:
            product = Product.query.get(item.product_id)
            item_data['product'] = {
                'id': product.id,
                'name': product.name,
                'sku': product.sku
            } if product else None
        else:
            item_data['product'] = None
        data['items'].append(item_data)

    data['terms'] = [model_to_dict(t) for t in quotation.terms]

    return success_response(data)


@quotation_bp.route('/<int:id>', methods=['PUT'])
@jwt_required_with_user()
@permission_required('quotations.edit')
def update_quotation(id):
    """Update quotation"""
    quotation = Quotation.query.filter_by(id=id, organization_id=g.organization_id).first()
    if not quotation:
        return error_response('Quotation not found', status_code=404)
    
    if quotation.status not in ['draft', 'sent']:
        return error_response('Cannot edit quotation in current status')
    
    data = get_request_json()
    old_values = model_to_dict(quotation)
    
    # Update basic fields
    updateable = ['reference_number', 'valid_until', 'notes', 'internal_notes',
                  'billing_address_line1', 'billing_address_line2', 'billing_city',
                  'billing_state', 'billing_state_code', 'billing_pincode',
                  'shipping_address_line1', 'shipping_address_line2', 'shipping_city',
                  'shipping_state', 'shipping_state_code', 'shipping_pincode']
    
    for field in updateable:
        if field in data:
            setattr(quotation, field, sanitize_string(data[field]) if isinstance(data[field], str) else data[field])
    
    # Update items if provided
    if 'items' in data:
        # Delete existing items
        QuotationItem.query.filter_by(quotation_id=quotation.id).delete()
        
        org = Organization.query.get(g.organization_id)
        is_interstate = quotation.place_of_supply != org.state_code
        
        subtotal = Decimal('0')
        total_discount = Decimal('0')
        total_cgst = Decimal('0')
        total_sgst = Decimal('0')
        total_igst = Decimal('0')
        total_cess = Decimal('0')
        
        for idx, item_data in enumerate(data['items']):
            product = Product.query.filter_by(id=item_data['product_id'], organization_id=g.organization_id).first()
            if not product:
                continue
            
            item_data['is_interstate'] = is_interstate
            tax_calc = calculate_tax(item_data, product, org)
            
            item = QuotationItem(
                quotation_id=quotation.id,
                product_id=product.id,
                variant_id=item_data.get('variant_id'),
                line_number=idx + 1,
                name=product.name,
                description=sanitize_string(item_data.get('description', '')),
                sku=product.sku,
                hsn_code=product.hsn_code or item_data.get('hsn_code', ''),
                quantity=item_data.get('quantity', 1),
                unit_id=item_data.get('unit_id') or product.unit_id,
                unit_name=product.unit.symbol if product.unit else None,
                rate=item_data.get('unit_price', product.selling_price),
                discount_type='percentage',
                discount_value=item_data.get('discount_percent', 0),
                discount_amount=tax_calc['discount_amount'],
                taxable_amount=tax_calc['taxable_amount'],
                tax_rate_id=product.tax_rate_id,
                tax_rate=product.tax_rate.rate if product.tax_rate else 0,
                cgst_rate=product.tax_rate.cgst_rate if product.tax_rate and not is_interstate else 0,
                cgst_amount=tax_calc['cgst_amount'],
                sgst_rate=product.tax_rate.sgst_rate if product.tax_rate and not is_interstate else 0,
                sgst_amount=tax_calc['sgst_amount'],
                igst_rate=product.tax_rate.igst_rate if product.tax_rate and is_interstate else 0,
                igst_amount=tax_calc['igst_amount'],
                cess_rate=product.tax_rate.cess_rate if product.tax_rate else 0,
                cess_amount=tax_calc['cess_amount'],
                total_tax=tax_calc['cgst_amount'] + tax_calc['sgst_amount'] + tax_calc['igst_amount'] + tax_calc['cess_amount'],
                amount=tax_calc['total']
            )
            db.session.add(item)
            
            subtotal += Decimal(str(tax_calc['taxable_amount']))
            total_discount += Decimal(str(tax_calc['discount_amount']))
            total_cgst += Decimal(str(tax_calc['cgst_amount']))
            total_sgst += Decimal(str(tax_calc['sgst_amount']))
            total_igst += Decimal(str(tax_calc['igst_amount']))
            total_cess += Decimal(str(tax_calc['cess_amount']))
        
        shipping_charges = Decimal(str(data.get('shipping_charges', quotation.shipping_charges or 0)))
        packaging_charges = Decimal(str(data.get('packaging_charges', quotation.packaging_charges or 0)))
        other_charges = Decimal(str(data.get('other_charges', quotation.other_charges or 0)))
        additional_discount = Decimal(str(data.get('additional_discount', 0)))
        
        total_tax = total_cgst + total_sgst + total_igst + total_cess
        total_amount = subtotal + total_tax + shipping_charges + packaging_charges + other_charges - additional_discount
        
        round_off = round(total_amount) - total_amount
        total_amount = round(total_amount)
        
        quotation.subtotal = float(subtotal)
        quotation.discount_amount = float(total_discount + additional_discount)
        quotation.taxable_amount = float(subtotal - total_discount - additional_discount)
        quotation.cgst_amount = float(total_cgst)
        quotation.sgst_amount = float(total_sgst)
        quotation.igst_amount = float(total_igst)
        quotation.cess_amount = float(total_cess)
        quotation.total_tax = float(total_tax)
        quotation.shipping_charges = float(shipping_charges)
        quotation.packaging_charges = float(packaging_charges)
        quotation.other_charges = float(other_charges)
        quotation.round_off = float(round_off)
        quotation.grand_total = float(total_amount)
    
    quotation.updated_at = datetime.utcnow()
    quotation.updated_by = g.current_user.id
    
    create_audit_log('quotations', quotation.id, 'update', old_values, model_to_dict(quotation))
    db.session.commit()
    
    return success_response(model_to_dict(quotation), 'Quotation updated')


@quotation_bp.route('/<int:id>', methods=['DELETE'])
@jwt_required_with_user()
@permission_required('quotations.delete')
def delete_quotation(id):
    """Delete quotation"""
    quotation = Quotation.query.filter_by(id=id, organization_id=g.organization_id).first()
    if not quotation:
        return error_response('Quotation not found', status_code=404)
    
    if quotation.status not in ['draft']:
        return error_response('Can only delete draft quotations')
    
    QuotationTerms.query.filter_by(quotation_id=quotation.id).delete()
    QuotationItem.query.filter_by(quotation_id=quotation.id).delete()
    db.session.delete(quotation)
    db.session.commit()
    
    return success_response(message='Quotation deleted')


@quotation_bp.route('/<int:id>/send', methods=['POST'])
@jwt_required_with_user()
@permission_required('quotations.edit')
def send_quotation(id):
    """Mark quotation as sent"""
    quotation = Quotation.query.filter_by(id=id, organization_id=g.organization_id).first()
    if not quotation:
        return error_response('Quotation not found', status_code=404)
    
    quotation.status = 'sent'
    quotation.sent_at = datetime.utcnow()
    quotation.updated_at = datetime.utcnow()
    db.session.commit()
    
    # TODO: Send email to customer
    
    return success_response(model_to_dict(quotation), 'Quotation sent')


@quotation_bp.route('/<int:id>/accept', methods=['POST'])
@jwt_required_with_user()
@permission_required('quotations.approve')
def accept_quotation(id):
    """Accept quotation"""
    quotation = Quotation.query.filter_by(id=id, organization_id=g.organization_id).first()
    if not quotation:
        return error_response('Quotation not found', status_code=404)
    
    if quotation.status not in ['draft', 'sent']:
        return error_response('Cannot accept quotation in current status')
    
    quotation.status = 'accepted'
    quotation.accepted_at = datetime.utcnow()
    quotation.updated_at = datetime.utcnow()
    db.session.commit()
    
    return success_response(model_to_dict(quotation), 'Quotation accepted')


@quotation_bp.route('/<int:id>/reject', methods=['POST'])
@jwt_required_with_user()
@permission_required('quotations.approve')
def reject_quotation(id):
    """Reject quotation"""
    quotation = Quotation.query.filter_by(id=id, organization_id=g.organization_id).first()
    if not quotation:
        return error_response('Quotation not found', status_code=404)
    
    data = get_request_json()
    
    quotation.status = 'rejected'
    quotation.rejection_reason = sanitize_string(data.get('reason', ''))
    quotation.rejected_at = datetime.utcnow()
    quotation.updated_at = datetime.utcnow()
    db.session.commit()
    
    return success_response(model_to_dict(quotation), 'Quotation rejected')


@quotation_bp.route('/<int:id>/convert', methods=['POST'])
@jwt_required_with_user()
@permission_required('quotations.convert')
def convert_to_order(id):
    """Convert quotation to sales order"""
    quotation = Quotation.query.filter_by(id=id, organization_id=g.organization_id).first()
    if not quotation:
        return error_response('Quotation not found', status_code=404)
    
    if quotation.status not in ['sent', 'accepted']:
        return error_response('Quotation must be sent or accepted to convert')
    
    if quotation.converted_to_order:
        return error_response('Quotation already converted')
    
    from app.models import SalesOrder, SalesOrderItem
    
    # Generate order number
    count = SalesOrder.query.filter_by(organization_id=g.organization_id).count() + 1
    order_number = f"SO{datetime.utcnow().strftime('%y%m')}{count:05d}"
    
    # Create sales order
    order = SalesOrder(
        organization_id=g.organization_id,
        branch_id=quotation.branch_id,
        order_number=order_number,
        customer_id=quotation.customer_id,
        quotation_id=quotation.id,
        customer_name=quotation.customer_name,
        billing_address_line1=quotation.billing_address_line1,
        billing_address_line2=quotation.billing_address_line2,
        billing_city=quotation.billing_city,
        billing_state=quotation.billing_state,
        billing_state_code=quotation.billing_state_code,
        billing_pincode=quotation.billing_pincode,
        shipping_address_line1=quotation.shipping_address_line1,
        shipping_address_line2=quotation.shipping_address_line2,
        shipping_city=quotation.shipping_city,
        shipping_state=quotation.shipping_state,
        shipping_state_code=quotation.shipping_state_code,
        shipping_pincode=quotation.shipping_pincode,
        order_date=datetime.utcnow().date(),
        place_of_supply=quotation.place_of_supply,
        currency=quotation.currency,
        subtotal=quotation.subtotal,
        discount_amount=quotation.discount_amount,
        taxable_amount=quotation.taxable_amount,
        cgst_amount=quotation.cgst_amount,
        sgst_amount=quotation.sgst_amount,
        igst_amount=quotation.igst_amount,
        cess_amount=quotation.cess_amount,
        total_tax=quotation.total_tax,
        shipping_charges=quotation.shipping_charges,
        packaging_charges=quotation.packaging_charges,
        other_charges=quotation.other_charges,
        round_off=quotation.round_off,
        grand_total=quotation.grand_total,
        notes=quotation.notes,
        status='confirmed',
        created_by=g.current_user.id
    )
    
    db.session.add(order)
    db.session.flush()
    
    # Copy items
    for q_item in quotation.items:
        o_item = SalesOrderItem(
            order_id=order.id,
            product_id=q_item.product_id,
            variant_id=q_item.variant_id,
            name=q_item.name,
            description=q_item.description,
            sku=q_item.sku,
            hsn_code=q_item.hsn_code,
            quantity=q_item.quantity,
            unit_id=q_item.unit_id,
            unit_name=q_item.unit_name,
            rate=q_item.rate,
            discount_type=q_item.discount_type,
            discount_value=q_item.discount_value,
            discount_amount=q_item.discount_amount,
            taxable_amount=q_item.taxable_amount,
            tax_rate_id=q_item.tax_rate_id,
            tax_rate=q_item.tax_rate,
            cgst_rate=q_item.cgst_rate,
            cgst_amount=q_item.cgst_amount,
            sgst_rate=q_item.sgst_rate,
            sgst_amount=q_item.sgst_amount,
            igst_rate=q_item.igst_rate,
            igst_amount=q_item.igst_amount,
            cess_rate=q_item.cess_rate,
            cess_amount=q_item.cess_amount,
            total_tax=q_item.total_tax,
            amount=q_item.amount
        )
        db.session.add(o_item)
    
    # Update quotation
    quotation.status = 'converted'
    quotation.converted_to_order = True
    quotation.sales_order_id = order.id
    quotation.converted_at = datetime.utcnow()
    quotation.updated_at = datetime.utcnow()
    
    db.session.commit()
    
    return success_response({
        'quotation_id': quotation.id,
        'sales_order_id': order.id,
        'order_number': order.order_number
    }, 'Quotation converted to sales order')