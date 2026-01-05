"""Customer management routes for VyaparaCore"""
from flask import Blueprint, g
from datetime import datetime
from config.database import db
from app.models import Customer, CustomerAddress, CustomerContact
from app.utils.security import (
    jwt_required_with_user, permission_required, sanitize_string,
    validate_gstin, validate_pan, validate_email, validate_phone,
    create_audit_log
)
from app.utils.helpers import (
    success_response, error_response, get_request_json,
    paginate, get_filters, apply_filters, model_to_dict
)
from app.services.activity_logger import log_activity, log_audit, ActivityType, EntityType

customer_bp = Blueprint('customer', __name__)


@customer_bp.route('', methods=['GET'])
@jwt_required_with_user()
@permission_required('customers.view')
def list_customers():
    """List all customers"""
    query = Customer.query.filter_by(organization_id=g.organization_id)
    
    filters = get_filters()
    if filters.get('search'):
        search = f"%{filters['search']}%"
        query = query.filter(
            db.or_(
                Customer.name.ilike(search),
                Customer.code.ilike(search),
                Customer.email.ilike(search),
                Customer.phone.ilike(search),
                Customer.gstin.ilike(search)
            )
        )
    
    if filters.get('customer_type'):
        query = query.filter(Customer.customer_type == filters['customer_type'])
    
    if filters.get('gst_treatment'):
        query = query.filter(Customer.gst_treatment == filters['gst_treatment'])
    
    query = apply_filters(query, Customer, filters)
    
    def serialize(c):
        data = model_to_dict(c)
        data['outstanding_amount'] = float(c.outstanding_amount or 0)
        return data
    
    return success_response(paginate(query, serialize))


@customer_bp.route('', methods=['POST'])
@jwt_required_with_user()
@permission_required('customers.create')
def create_customer():
    """Create new customer"""
    data = get_request_json()
    
    if not data.get('name'):
        return error_response('Customer name required')
    
    # Generate code
    code = sanitize_string(data.get('code', '')).upper()
    if not code:
        count = Customer.query.filter_by(organization_id=g.organization_id).count() + 1
        code = f"CUST{count:05d}"
    
    existing = Customer.query.filter_by(organization_id=g.organization_id, code=code).first()
    if existing:
        return error_response('Customer code already exists')
    
    # Validate GSTIN/PAN
    gstin = sanitize_string(data.get('gstin', '')).upper() or None
    pan = sanitize_string(data.get('pan', '')).upper() or None
    
    if gstin and not validate_gstin(gstin):
        return error_response('Invalid GSTIN format')
    if pan and not validate_pan(pan):
        return error_response('Invalid PAN format')
    
    customer = Customer(
        organization_id=g.organization_id,
        name=sanitize_string(data['name']),
        code=code,
        customer_type=data.get('customer_type', 'business'),
        gst_treatment=data.get('gst_treatment', 'regular'),
        gstin=gstin,
        pan=pan,
        email=sanitize_string(data.get('email', '')).lower() or None,
        phone=sanitize_string(data.get('phone', '')),
        website=sanitize_string(data.get('website', '')),
        billing_address_line1=sanitize_string(data.get('billing_address_line1', '')),
        billing_address_line2=sanitize_string(data.get('billing_address_line2', '')),
        billing_city=sanitize_string(data.get('billing_city', '')),
        billing_state=sanitize_string(data.get('billing_state', '')),
        billing_state_code=data.get('billing_state_code'),
        billing_country=data.get('billing_country', 'India'),
        billing_pincode=sanitize_string(data.get('billing_pincode', '')),
        shipping_address_line1=sanitize_string(data.get('shipping_address_line1', '')),
        shipping_address_line2=sanitize_string(data.get('shipping_address_line2', '')),
        shipping_city=sanitize_string(data.get('shipping_city', '')),
        shipping_state=sanitize_string(data.get('shipping_state', '')),
        shipping_state_code=data.get('shipping_state_code'),
        shipping_country=data.get('shipping_country', 'India'),
        shipping_pincode=sanitize_string(data.get('shipping_pincode', '')),
        credit_limit=data.get('credit_limit', 0),
        payment_terms=data.get('payment_terms', 30),
        price_list_id=data.get('price_list_id'),
        notes=sanitize_string(data.get('notes', '')),
        tags=data.get('tags', []),
        custom_fields=data.get('custom_fields', {}),
        is_active=True,
        created_by=g.current_user.id
    )
    
    db.session.add(customer)
    db.session.flush()
    
    # Add additional addresses
    if data.get('addresses'):
        for addr in data['addresses']:
            address = CustomerAddress(
                customer_id=customer.id,
                address_type=addr.get('address_type', 'other'),
                label=sanitize_string(addr.get('label', '')),
                address_line1=sanitize_string(addr.get('address_line1', '')),
                address_line2=sanitize_string(addr.get('address_line2', '')),
                city=sanitize_string(addr.get('city', '')),
                state=sanitize_string(addr.get('state', '')),
                state_code=addr.get('state_code'),
                country=addr.get('country', 'India'),
                pincode=sanitize_string(addr.get('pincode', '')),
                is_default=addr.get('is_default', False)
            )
            db.session.add(address)
    
    # Add contacts
    if data.get('contacts'):
        for cont in data['contacts']:
            contact = CustomerContact(
                customer_id=customer.id,
                name=sanitize_string(cont.get('name', '')),
                designation=sanitize_string(cont.get('designation', '')),
                email=sanitize_string(cont.get('email', '')).lower() or None,
                phone=sanitize_string(cont.get('phone', '')),
                mobile=sanitize_string(cont.get('mobile', '')),
                is_primary=cont.get('is_primary', False)
            )
            db.session.add(contact)
    
    db.session.commit()

    log_audit('customers', customer.id, 'create', None, model_to_dict(customer))
    log_activity(
        activity_type=ActivityType.CREATE,
        description=f"Created customer '{customer.name}' ({customer.code})",
        entity_type=EntityType.CUSTOMER,
        entity_id=customer.id,
        entity_number=customer.code
    )

    return success_response(model_to_dict(customer), 'Customer created', 201)


@customer_bp.route('/<int:id>', methods=['GET'])
@jwt_required_with_user()
@permission_required('customers.view')
def get_customer(id):
    """Get customer details"""
    customer = Customer.query.filter_by(id=id, organization_id=g.organization_id).first()
    if not customer:
        return error_response('Customer not found', status_code=404)
    
    data = model_to_dict(customer)
    data['addresses'] = [model_to_dict(a) for a in customer.addresses]
    data['contacts'] = [model_to_dict(c) for c in customer.contacts]
    data['outstanding_amount'] = float(customer.outstanding_amount or 0)
    
    return success_response(data)


@customer_bp.route('/<int:id>', methods=['PUT'])
@jwt_required_with_user()
@permission_required('customers.edit')
def update_customer(id):
    """Update customer"""
    customer = Customer.query.filter_by(id=id, organization_id=g.organization_id).first()
    if not customer:
        return error_response('Customer not found', status_code=404)
    
    data = get_request_json()
    old_values = model_to_dict(customer)
    
    updateable = [
        'name', 'customer_type', 'gst_treatment', 'gstin', 'pan', 'email', 'phone',
        'website', 'billing_address_line1', 'billing_address_line2', 'billing_city',
        'billing_state', 'billing_state_code', 'billing_country', 'billing_pincode',
        'shipping_address_line1', 'shipping_address_line2', 'shipping_city',
        'shipping_state', 'shipping_state_code', 'shipping_country', 'shipping_pincode',
        'credit_limit', 'payment_terms', 'price_list_id', 'notes', 'tags',
        'custom_fields', 'is_active'
    ]
    
    for field in updateable:
        if field in data:
            value = data[field]
            if field in ['gstin', 'pan']:
                value = sanitize_string(value).upper() if value else None
            elif field == 'email':
                value = sanitize_string(value).lower() if value else None
            elif isinstance(value, str):
                value = sanitize_string(value)
            setattr(customer, field, value)
    
    # Validate
    if customer.gstin and not validate_gstin(customer.gstin):
        return error_response('Invalid GSTIN format')
    if customer.pan and not validate_pan(customer.pan):
        return error_response('Invalid PAN format')
    
    customer.updated_at = datetime.utcnow()
    customer.updated_by = g.current_user.id

    log_audit('customers', customer.id, 'update', old_values, model_to_dict(customer))
    db.session.commit()

    log_activity(
        activity_type=ActivityType.UPDATE,
        description=f"Updated customer '{customer.name}' ({customer.code})",
        entity_type=EntityType.CUSTOMER,
        entity_id=customer.id,
        entity_number=customer.code
    )

    return success_response(model_to_dict(customer), 'Customer updated')


@customer_bp.route('/<int:id>', methods=['DELETE'])
@jwt_required_with_user()
@permission_required('customers.delete')
def delete_customer(id):
    """Delete customer (soft delete)"""
    customer = Customer.query.filter_by(id=id, organization_id=g.organization_id).first()
    if not customer:
        return error_response('Customer not found', status_code=404)
    
    # Check for outstanding
    if customer.outstanding_amount and float(customer.outstanding_amount) > 0:
        return error_response('Cannot delete customer with outstanding balance')
    
    customer.is_active = False
    customer.updated_at = datetime.utcnow()

    log_audit('customers', customer.id, 'delete', model_to_dict(customer), None)
    db.session.commit()

    log_activity(
        activity_type=ActivityType.DELETE,
        description=f"Deleted customer '{customer.name}' ({customer.code})",
        entity_type=EntityType.CUSTOMER,
        entity_id=customer.id,
        entity_number=customer.code
    )

    return success_response(message='Customer deleted')


# Customer Addresses
@customer_bp.route('/<int:id>/addresses', methods=['POST'])
@jwt_required_with_user()
@permission_required('customers.edit')
def add_address(id):
    """Add customer address"""
    customer = Customer.query.filter_by(id=id, organization_id=g.organization_id).first()
    if not customer:
        return error_response('Customer not found', status_code=404)
    
    data = get_request_json()
    
    address = CustomerAddress(
        customer_id=customer.id,
        address_type=data.get('address_type', 'other'),
        label=sanitize_string(data.get('label', '')),
        address_line1=sanitize_string(data.get('address_line1', '')),
        address_line2=sanitize_string(data.get('address_line2', '')),
        city=sanitize_string(data.get('city', '')),
        state=sanitize_string(data.get('state', '')),
        state_code=data.get('state_code'),
        country=data.get('country', 'India'),
        pincode=sanitize_string(data.get('pincode', '')),
        is_default=data.get('is_default', False)
    )
    
    if address.is_default:
        CustomerAddress.query.filter_by(
            customer_id=customer.id, address_type=address.address_type
        ).update({'is_default': False})
    
    db.session.add(address)
    db.session.commit()
    
    return success_response(model_to_dict(address), 'Address added', 201)


@customer_bp.route('/<int:id>/addresses/<int:addr_id>', methods=['DELETE'])
@jwt_required_with_user()
@permission_required('customers.edit')
def delete_address(id, addr_id):
    """Delete customer address"""
    address = CustomerAddress.query.filter_by(id=addr_id, customer_id=id).first()
    if not address:
        return error_response('Address not found', status_code=404)
    
    db.session.delete(address)
    db.session.commit()
    
    return success_response(message='Address deleted')


# Customer Contacts
@customer_bp.route('/<int:id>/contacts', methods=['POST'])
@jwt_required_with_user()
@permission_required('customers.edit')
def add_contact(id):
    """Add customer contact"""
    customer = Customer.query.filter_by(id=id, organization_id=g.organization_id).first()
    if not customer:
        return error_response('Customer not found', status_code=404)
    
    data = get_request_json()
    
    contact = CustomerContact(
        customer_id=customer.id,
        name=sanitize_string(data.get('name', '')),
        designation=sanitize_string(data.get('designation', '')),
        email=sanitize_string(data.get('email', '')).lower() or None,
        phone=sanitize_string(data.get('phone', '')),
        mobile=sanitize_string(data.get('mobile', '')),
        is_primary=data.get('is_primary', False)
    )
    
    if contact.is_primary:
        CustomerContact.query.filter_by(customer_id=customer.id).update({'is_primary': False})
    
    db.session.add(contact)
    db.session.commit()
    
    return success_response(model_to_dict(contact), 'Contact added', 201)


@customer_bp.route('/<int:id>/contacts/<int:cont_id>', methods=['DELETE'])
@jwt_required_with_user()
@permission_required('customers.edit')
def delete_contact(id, cont_id):
    """Delete customer contact"""
    contact = CustomerContact.query.filter_by(id=cont_id, customer_id=id).first()
    if not contact:
        return error_response('Contact not found', status_code=404)
    
    db.session.delete(contact)
    db.session.commit()
    
    return success_response(message='Contact deleted')


# Customer Transactions/Ledger
@customer_bp.route('/<int:id>/ledger', methods=['GET'])
@jwt_required_with_user()
@permission_required('customers.view')
def get_ledger(id):
    """Get customer ledger/transaction history"""
    customer = Customer.query.filter_by(id=id, organization_id=g.organization_id).first()
    if not customer:
        return error_response('Customer not found', status_code=404)
    
    from app.models import Invoice, Payment, CreditNote
    
    # Get invoices
    invoices = Invoice.query.filter_by(
        organization_id=g.organization_id,
        customer_id=id
    ).filter(Invoice.status != 'draft').order_by(Invoice.invoice_date.desc()).all()
    
    # Get payments
    payments = Payment.query.filter_by(
        organization_id=g.organization_id,
        party_id=id,
        party_type='customer'
    ).filter(Payment.status == 'completed').order_by(Payment.payment_date.desc()).all()
    
    # Get credit notes
    credit_notes = CreditNote.query.filter_by(
        organization_id=g.organization_id,
        customer_id=id
    ).filter(CreditNote.status != 'draft').order_by(CreditNote.credit_note_date.desc()).all()
    
    transactions = []
    
    for inv in invoices:
        transactions.append({
            'date': inv.invoice_date.isoformat() if inv.invoice_date else None,
            'type': 'invoice',
            'number': inv.invoice_number,
            'description': f'Invoice #{inv.invoice_number}',
            'debit': float(inv.total_amount or 0),
            'credit': 0,
            'id': inv.id
        })
    
    for pmt in payments:
        transactions.append({
            'date': pmt.payment_date.isoformat() if pmt.payment_date else None,
            'type': 'payment',
            'number': pmt.payment_number,
            'description': f'Payment #{pmt.payment_number}',
            'debit': 0,
            'credit': float(pmt.amount or 0),
            'id': pmt.id
        })
    
    for cn in credit_notes:
        transactions.append({
            'date': cn.credit_note_date.isoformat() if cn.credit_note_date else None,
            'type': 'credit_note',
            'number': cn.credit_note_number,
            'description': f'Credit Note #{cn.credit_note_number}',
            'debit': 0,
            'credit': float(cn.total_amount or 0),
            'id': cn.id
        })
    
    # Sort by date
    transactions.sort(key=lambda x: x['date'] or '', reverse=True)
    
    # Calculate running balance
    balance = 0
    for txn in reversed(transactions):
        balance += txn['debit'] - txn['credit']
        txn['balance'] = balance
    
    return success_response({
        'customer': {'id': customer.id, 'name': customer.name, 'code': customer.code},
        'opening_balance': 0,
        'closing_balance': float(customer.outstanding_amount or 0),
        'transactions': transactions
    })