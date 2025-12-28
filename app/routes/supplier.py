"""Supplier management routes for VyaparaCore"""
from flask import Blueprint, g
from datetime import datetime
from config.database import db
from app.models import Supplier, SupplierAddress, SupplierContact
from app.utils.security import (
    jwt_required_with_user, permission_required, sanitize_string,
    validate_gstin, validate_pan, create_audit_log
)
from app.utils.helpers import (
    success_response, error_response, get_request_json,
    paginate, get_filters, apply_filters, model_to_dict
)

supplier_bp = Blueprint('supplier', __name__)


@supplier_bp.route('', methods=['GET'])
@jwt_required_with_user()
@permission_required('suppliers.view')
def list_suppliers():
    """List all suppliers"""
    query = Supplier.query.filter_by(organization_id=g.organization_id)
    
    filters = get_filters()
    if filters.get('search'):
        search = f"%{filters['search']}%"
        query = query.filter(
            db.or_(
                Supplier.name.ilike(search),
                Supplier.code.ilike(search),
                Supplier.email.ilike(search),
                Supplier.gstin.ilike(search)
            )
        )
    
    if filters.get('supplier_type'):
        query = query.filter(Supplier.supplier_type == filters['supplier_type'])
    
    query = apply_filters(query, Supplier, filters)
    
    def serialize(s):
        data = model_to_dict(s)
        data['outstanding_amount'] = float(s.current_balance or 0)
        return data
    
    return success_response(paginate(query, serialize))


@supplier_bp.route('', methods=['POST'])
@jwt_required_with_user()
@permission_required('suppliers.create')
def create_supplier():
    """Create new supplier"""
    data = get_request_json()
    
    if not data.get('name'):
        return error_response('Supplier name required')

    supplier_code = sanitize_string(data.get('supplier_code', '')).upper()
    if not supplier_code:
        count = Supplier.query.filter_by(organization_id=g.organization_id).count() + 1
        supplier_code = f"SUPP{count:05d}"

    existing = Supplier.query.filter_by(organization_id=g.organization_id, supplier_code=supplier_code).first()
    if existing:
        return error_response('Supplier code already exists')
    
    gstin = sanitize_string(data.get('gstin', '')).upper() or None
    pan = sanitize_string(data.get('pan', '')).upper() or None
    
    if gstin and not validate_gstin(gstin):
        return error_response('Invalid GSTIN format')
    if pan and not validate_pan(pan):
        return error_response('Invalid PAN format')
    
    supplier = Supplier(
        organization_id=g.organization_id,
        name=sanitize_string(data['name']),
        supplier_code=supplier_code,
        display_name=sanitize_string(data.get('display_name', data['name'])),
        supplier_type=data.get('supplier_type', 'business'),
        gst_treatment=data.get('gst_treatment', 'regular'),
        gstin=gstin,
        pan=pan,
        email=sanitize_string(data.get('email', '')).lower() or None,
        phone=sanitize_string(data.get('phone', '')),
        mobile=sanitize_string(data.get('mobile', '')),
        website=sanitize_string(data.get('website', '')),
        address_line1=sanitize_string(data.get('address_line1', '')),
        address_line2=sanitize_string(data.get('address_line2', '')),
        city=sanitize_string(data.get('city', '')),
        state=sanitize_string(data.get('state', '')),
        state_code=data.get('state_code'),
        country=data.get('country', 'India'),
        pincode=sanitize_string(data.get('pincode', '')),
        payment_terms=data.get('payment_terms', 30),
        tds_applicable=data.get('tds_applicable', False),
        tds_section=data.get('tds_section'),
        bank_name=sanitize_string(data.get('bank_name', '')),
        bank_account_number=sanitize_string(data.get('bank_account_number', '')),
        bank_ifsc=sanitize_string(data.get('bank_ifsc', '')).upper() or None,
        bank_branch=sanitize_string(data.get('bank_branch', '')),
        notes=sanitize_string(data.get('notes', '')),
        is_active=True,
        created_by=g.current_user.id
    )
    
    db.session.add(supplier)
    db.session.flush()
    
    # Add addresses
    if data.get('addresses'):
        for addr in data['addresses']:
            address = SupplierAddress(
                supplier_id=supplier.id,
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
            contact = SupplierContact(
                supplier_id=supplier.id,
                name=sanitize_string(cont.get('name', '')),
                designation=sanitize_string(cont.get('designation', '')),
                email=sanitize_string(cont.get('email', '')).lower() or None,
                phone=sanitize_string(cont.get('phone', '')),
                mobile=sanitize_string(cont.get('mobile', '')),
                is_primary=cont.get('is_primary', False)
            )
            db.session.add(contact)
    
    db.session.commit()
    
    create_audit_log('suppliers', supplier.id, 'create', None, model_to_dict(supplier))
    
    return success_response(model_to_dict(supplier), 'Supplier created', 201)


@supplier_bp.route('/<int:id>', methods=['GET'])
@jwt_required_with_user()
@permission_required('suppliers.view')
def get_supplier(id):
    """Get supplier details"""
    supplier = Supplier.query.filter_by(id=id, organization_id=g.organization_id).first()
    if not supplier:
        return error_response('Supplier not found', status_code=404)
    
    data = model_to_dict(supplier)
    data['addresses'] = [model_to_dict(a) for a in supplier.addresses]
    data['contacts'] = [model_to_dict(c) for c in supplier.contacts]
    data['outstanding_amount'] = float(supplier.current_balance or 0)  # For frontend compatibility

    return success_response(data)


@supplier_bp.route('/<int:id>', methods=['PUT'])
@jwt_required_with_user()
@permission_required('suppliers.edit')
def update_supplier(id):
    """Update supplier"""
    supplier = Supplier.query.filter_by(id=id, organization_id=g.organization_id).first()
    if not supplier:
        return error_response('Supplier not found', status_code=404)
    
    data = get_request_json()
    old_values = model_to_dict(supplier)
    
    updateable = [
        'name', 'supplier_type', 'gst_treatment', 'gstin', 'pan', 'email', 'phone',
        'website', 'address_line1', 'address_line2', 'city', 'state', 'state_code',
        'country', 'pincode', 'payment_terms', 'tds_applicable', 'tds_section',
        'tds_rate', 'bank_name', 'bank_account_number', 'bank_ifsc', 'bank_branch',
        'notes', 'tags', 'custom_fields', 'is_active'
    ]
    
    for field in updateable:
        if field in data:
            value = data[field]
            if field in ['gstin', 'pan', 'bank_ifsc']:
                value = sanitize_string(value).upper() if value else None
            elif field == 'email':
                value = sanitize_string(value).lower() if value else None
            elif isinstance(value, str):
                value = sanitize_string(value)
            setattr(supplier, field, value)
    
    if supplier.gstin and not validate_gstin(supplier.gstin):
        return error_response('Invalid GSTIN format')
    if supplier.pan and not validate_pan(supplier.pan):
        return error_response('Invalid PAN format')
    
    supplier.updated_at = datetime.utcnow()
    supplier.updated_by = g.current_user.id
    
    create_audit_log('suppliers', supplier.id, 'update', old_values, model_to_dict(supplier))
    db.session.commit()
    
    return success_response(model_to_dict(supplier), 'Supplier updated')


@supplier_bp.route('/<int:id>', methods=['DELETE'])
@jwt_required_with_user()
@permission_required('suppliers.delete')
def delete_supplier(id):
    """Delete supplier (soft delete)"""
    supplier = Supplier.query.filter_by(id=id, organization_id=g.organization_id).first()
    if not supplier:
        return error_response('Supplier not found', status_code=404)
    
    if supplier.current_balance and float(supplier.current_balance) > 0:
        return error_response('Cannot delete supplier with outstanding balance')
    
    supplier.is_active = False
    supplier.updated_at = datetime.utcnow()
    
    create_audit_log('suppliers', supplier.id, 'delete', model_to_dict(supplier), None)
    db.session.commit()
    
    return success_response(message='Supplier deleted')


# Supplier Addresses
@supplier_bp.route('/<int:id>/addresses', methods=['POST'])
@jwt_required_with_user()
@permission_required('suppliers.edit')
def add_address(id):
    """Add supplier address"""
    supplier = Supplier.query.filter_by(id=id, organization_id=g.organization_id).first()
    if not supplier:
        return error_response('Supplier not found', status_code=404)
    
    data = get_request_json()
    
    address = SupplierAddress(
        supplier_id=supplier.id,
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
        SupplierAddress.query.filter_by(
            supplier_id=supplier.id, address_type=address.address_type
        ).update({'is_default': False})
    
    db.session.add(address)
    db.session.commit()
    
    return success_response(model_to_dict(address), 'Address added', 201)


@supplier_bp.route('/<int:id>/addresses/<int:addr_id>', methods=['DELETE'])
@jwt_required_with_user()
@permission_required('suppliers.edit')
def delete_address(id, addr_id):
    """Delete supplier address"""
    address = SupplierAddress.query.filter_by(id=addr_id, supplier_id=id).first()
    if not address:
        return error_response('Address not found', status_code=404)
    
    db.session.delete(address)
    db.session.commit()
    
    return success_response(message='Address deleted')


# Supplier Contacts
@supplier_bp.route('/<int:id>/contacts', methods=['POST'])
@jwt_required_with_user()
@permission_required('suppliers.edit')
def add_contact(id):
    """Add supplier contact"""
    supplier = Supplier.query.filter_by(id=id, organization_id=g.organization_id).first()
    if not supplier:
        return error_response('Supplier not found', status_code=404)
    
    data = get_request_json()
    
    contact = SupplierContact(
        supplier_id=supplier.id,
        name=sanitize_string(data.get('name', '')),
        designation=sanitize_string(data.get('designation', '')),
        email=sanitize_string(data.get('email', '')).lower() or None,
        phone=sanitize_string(data.get('phone', '')),
        mobile=sanitize_string(data.get('mobile', '')),
        is_primary=data.get('is_primary', False)
    )
    
    if contact.is_primary:
        SupplierContact.query.filter_by(supplier_id=supplier.id).update({'is_primary': False})
    
    db.session.add(contact)
    db.session.commit()
    
    return success_response(model_to_dict(contact), 'Contact added', 201)


@supplier_bp.route('/<int:id>/contacts/<int:cont_id>', methods=['DELETE'])
@jwt_required_with_user()
@permission_required('suppliers.edit')
def delete_contact(id, cont_id):
    """Delete supplier contact"""
    contact = SupplierContact.query.filter_by(id=cont_id, supplier_id=id).first()
    if not contact:
        return error_response('Contact not found', status_code=404)
    
    db.session.delete(contact)
    db.session.commit()
    
    return success_response(message='Contact deleted')


# Supplier Ledger
@supplier_bp.route('/<int:id>/ledger', methods=['GET'])
@jwt_required_with_user()
@permission_required('suppliers.view')
def get_ledger(id):
    """Get supplier ledger"""
    supplier = Supplier.query.filter_by(id=id, organization_id=g.organization_id).first()
    if not supplier:
        return error_response('Supplier not found', status_code=404)
    
    from app.models import PurchaseOrder, Payment, DebitNote
    
    # This is a simplified ledger - in production you'd have purchase invoices
    transactions = []
    
    # Get payments to supplier
    payments = Payment.query.filter_by(
        organization_id=g.organization_id,
        party_id=id,
        party_type='supplier'
    ).filter(Payment.status == 'completed').order_by(Payment.payment_date.desc()).all()
    
    for pmt in payments:
        transactions.append({
            'date': pmt.payment_date.isoformat() if pmt.payment_date else None,
            'type': 'payment',
            'number': pmt.payment_number,
            'description': f'Payment #{pmt.payment_number}',
            'debit': float(pmt.amount or 0),
            'credit': 0,
            'id': pmt.id
        })
    
    # Get debit notes
    debit_notes = DebitNote.query.filter_by(
        organization_id=g.organization_id,
        supplier_id=id
    ).filter(DebitNote.status != 'draft').order_by(DebitNote.debit_note_date.desc()).all()
    
    for dn in debit_notes:
        transactions.append({
            'date': dn.debit_note_date.isoformat() if dn.debit_note_date else None,
            'type': 'debit_note',
            'number': dn.debit_note_number,
            'description': f'Debit Note #{dn.debit_note_number}',
            'debit': float(dn.total_amount or 0),
            'credit': 0,
            'id': dn.id
        })
    
    transactions.sort(key=lambda x: x['date'] or '', reverse=True)
    
    return success_response({
        'supplier': {'id': supplier.id, 'name': supplier.name, 'code': supplier.code},
        'outstanding_amount': float(supplier.current_balance or 0),
        'transactions': transactions
    })