"""Organization routes for VyaparaCore"""
from flask import Blueprint, g
from datetime import datetime
from config.database import db
from app.models import Organization, Branch, FinancialYear, OrganizationSettings, InvoiceSettings
from app.utils.security import (
    jwt_required_with_user, permission_required, sanitize_string,
    validate_gstin, validate_pan, create_audit_log
)
from app.utils.helpers import (
    success_response, error_response, get_request_json,
    paginate, get_filters, apply_filters, model_to_dict
)
from app.services.activity_logger import log_activity, log_audit, ActivityType, EntityType

organization_bp = Blueprint('organization', __name__)


@organization_bp.route('', methods=['GET'])
@jwt_required_with_user()
@permission_required('organization.view')
def get_organization():
    """Get current organization details"""
    org = Organization.query.get(g.organization_id)
    if not org:
        return error_response('Organization not found', status_code=404)
    
    return success_response(model_to_dict(org, exclude=['created_at', 'updated_at']))


@organization_bp.route('', methods=['PUT'])
@jwt_required_with_user()
@permission_required('organization.edit')
def update_organization():
    """Update organization details"""
    org = Organization.query.get(g.organization_id)
    if not org:
        return error_response('Organization not found', status_code=404)
    
    data = get_request_json()
    old_values = model_to_dict(org)
    
    # Update fields
    updateable = [
        'name', 'legal_name', 'organization_type', 'industry', 'email', 'phone',
        'website', 'gstin', 'pan', 'cin', 'tan', 'address_line1', 'address_line2',
        'city', 'state', 'state_code', 'country', 'pincode', 'logo_url', 'logo_data',
        'bank_name', 'bank_account_number', 'bank_ifsc', 'bank_branch'
    ]

    # Validate logo_data if provided
    if 'logo_data' in data and data['logo_data']:
        logo_data = data['logo_data']
        if not logo_data.startswith('data:image/'):
            return error_response('Invalid image format. Must be a data URL.')
        allowed_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
        mime_match = logo_data.split(';')[0].replace('data:', '')
        if mime_match not in allowed_types:
            return error_response('Invalid image type. Allowed: jpg, png, gif, webp')
        max_size = 700000  # ~500KB in base64
        if len(logo_data) > max_size:
            return error_response('Logo too large. Maximum size is 500KB.')

    for field in updateable:
        if field in data:
            value = data[field]
            if field in ['gstin', 'pan', 'cin', 'tan', 'bank_ifsc']:
                value = sanitize_string(value).upper() if value else None
            elif isinstance(value, str):
                value = sanitize_string(value)
            setattr(org, field, value)
    
    # Validate GSTIN and PAN
    if org.gstin and not validate_gstin(org.gstin):
        return error_response('Invalid GSTIN format')
    if org.pan and not validate_pan(org.pan):
        return error_response('Invalid PAN format')
    
    org.updated_at = datetime.utcnow()
    
    create_audit_log('organizations', org.id, 'update', old_values, model_to_dict(org))
    log_activity(
        activity_type=ActivityType.UPDATE,
        entity_type=EntityType.USER,
        entity_id=org.id,
        description=f"Updated organization settings"
    )
    db.session.commit()

    return success_response(model_to_dict(org), 'Organization updated')


@organization_bp.route('/logo', methods=['POST'])
@jwt_required_with_user()
@permission_required('organization.edit')
def upload_logo():
    """Upload organization logo as base64"""
    org = Organization.query.get(g.organization_id)
    if not org:
        return error_response('Organization not found', status_code=404)

    data = get_request_json()
    logo_data = data.get('logo_data')

    if not logo_data:
        return error_response('No logo data provided')

    # Validation
    if not logo_data.startswith('data:image/'):
        return error_response('Invalid image format. Must be a data URL.')

    allowed_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
    mime_match = logo_data.split(';')[0].replace('data:', '')
    if mime_match not in allowed_types:
        return error_response('Invalid image type. Allowed: jpg, png, gif, webp')

    max_size = 700000  # ~500KB in base64
    if len(logo_data) > max_size:
        return error_response('Logo too large. Maximum size is 500KB.')

    old_values = model_to_dict(org)
    org.logo_data = logo_data
    org.logo_url = None  # Clear external URL when using base64
    org.updated_at = datetime.utcnow()

    create_audit_log('organizations', org.id, 'update', old_values, model_to_dict(org))
    log_activity(
        activity_type=ActivityType.UPDATE,
        entity_type=EntityType.USER,
        entity_id=org.id,
        description="Updated organization logo"
    )
    db.session.commit()

    return success_response({'logo_data': logo_data}, 'Logo uploaded successfully')


@organization_bp.route('/logo', methods=['DELETE'])
@jwt_required_with_user()
@permission_required('organization.edit')
def delete_logo():
    """Remove organization logo"""
    org = Organization.query.get(g.organization_id)
    if not org:
        return error_response('Organization not found', status_code=404)

    old_values = model_to_dict(org)
    org.logo_data = None
    org.logo_url = None
    org.updated_at = datetime.utcnow()

    create_audit_log('organizations', org.id, 'update', old_values, model_to_dict(org))
    log_activity(
        activity_type=ActivityType.UPDATE,
        entity_type=EntityType.USER,
        entity_id=org.id,
        description="Removed organization logo"
    )
    db.session.commit()

    return success_response(message='Logo removed successfully')


# Branch routes
@organization_bp.route('/branches', methods=['GET'])
@jwt_required_with_user()
@permission_required('branch.view')
def list_branches():
    """List all branches"""
    query = Branch.query.filter_by(organization_id=g.organization_id)
    
    filters = get_filters()
    if filters.get('search'):
        search = f"%{filters['search']}%"
        query = query.filter(
            db.or_(Branch.name.ilike(search), Branch.code.ilike(search))
        )
    
    query = apply_filters(query, Branch, filters)
    return success_response(paginate(query))


@organization_bp.route('/branches', methods=['POST'])
@jwt_required_with_user()
@permission_required('branch.create')
def create_branch():
    """Create new branch"""
    data = get_request_json()
    
    if not data.get('name'):
        return error_response('Branch name required')
    
    code = sanitize_string(data.get('code', '')).upper()
    if not code:
        code = ''.join(e for e in data['name'][:4] if e.isalnum()).upper()
    
    # Check unique
    existing = Branch.query.filter_by(organization_id=g.organization_id, code=code).first()
    if existing:
        return error_response('Branch code already exists')
    
    branch = Branch(
        organization_id=g.organization_id,
        name=sanitize_string(data['name']),
        code=code,
        branch_type=data.get('branch_type', 'branch'),
        gstin=sanitize_string(data.get('gstin', '')).upper() or None,
        email=sanitize_string(data.get('email', '')),
        phone=sanitize_string(data.get('phone', '')),
        address_line1=sanitize_string(data.get('address_line1', '')),
        address_line2=sanitize_string(data.get('address_line2', '')),
        city=sanitize_string(data.get('city', '')),
        state=sanitize_string(data.get('state', '')),
        state_code=data.get('state_code'),
        country=data.get('country', 'India'),
        pincode=sanitize_string(data.get('pincode', '')),
        is_active=True
    )
    
    db.session.add(branch)
    db.session.commit()
    
    create_audit_log('branches', branch.id, 'create', None, model_to_dict(branch))
    log_activity(
        activity_type=ActivityType.CREATE,
        entity_type=EntityType.USER,
        entity_id=branch.id,
        description=f"Created branch: {branch.name}"
    )

    return success_response(model_to_dict(branch), 'Branch created', 201)


@organization_bp.route('/branches/<int:id>', methods=['GET'])
@jwt_required_with_user()
@permission_required('branch.view')
def get_branch(id):
    """Get branch details"""
    branch = Branch.query.filter_by(id=id, organization_id=g.organization_id).first()
    if not branch:
        return error_response('Branch not found', status_code=404)
    return success_response(model_to_dict(branch))


@organization_bp.route('/branches/<int:id>', methods=['PUT'])
@jwt_required_with_user()
@permission_required('branch.edit')
def update_branch(id):
    """Update branch"""
    branch = Branch.query.filter_by(id=id, organization_id=g.organization_id).first()
    if not branch:
        return error_response('Branch not found', status_code=404)
    
    data = get_request_json()
    old_values = model_to_dict(branch)
    
    updateable = [
        'name', 'branch_type', 'gstin', 'email', 'phone', 'address_line1',
        'address_line2', 'city', 'state', 'state_code', 'country', 'pincode', 'is_active'
    ]
    
    for field in updateable:
        if field in data:
            value = data[field]
            if field == 'gstin':
                value = sanitize_string(value).upper() if value else None
            elif isinstance(value, str):
                value = sanitize_string(value)
            setattr(branch, field, value)
    
    branch.updated_at = datetime.utcnow()
    
    create_audit_log('branches', branch.id, 'update', old_values, model_to_dict(branch))
    log_activity(
        activity_type=ActivityType.UPDATE,
        entity_type=EntityType.USER,
        entity_id=branch.id,
        description=f"Updated branch: {branch.name}"
    )
    db.session.commit()

    return success_response(model_to_dict(branch), 'Branch updated')


@organization_bp.route('/branches/<int:id>', methods=['DELETE'])
@jwt_required_with_user()
@permission_required('branch.delete')
def delete_branch(id):
    """Delete branch (soft delete)"""
    branch = Branch.query.filter_by(id=id, organization_id=g.organization_id).first()
    if not branch:
        return error_response('Branch not found', status_code=404)
    
    branch.is_active = False
    branch.updated_at = datetime.utcnow()
    
    create_audit_log('branches', branch.id, 'delete', model_to_dict(branch), None)
    log_activity(
        activity_type=ActivityType.DELETE,
        entity_type=EntityType.USER,
        entity_id=branch.id,
        description=f"Deleted branch: {branch.name}"
    )
    db.session.commit()

    return success_response(message='Branch deleted')


# Financial Year routes
@organization_bp.route('/financial-years', methods=['GET'])
@jwt_required_with_user()
@permission_required('organization.view')
def list_financial_years():
    """List financial years"""
    years = FinancialYear.query.filter_by(organization_id=g.organization_id).order_by(FinancialYear.start_date.desc()).all()
    return success_response([model_to_dict(fy) for fy in years])


@organization_bp.route('/financial-years', methods=['POST'])
@jwt_required_with_user()
@permission_required('organization.settings')
def create_financial_year():
    """Create financial year"""
    data = get_request_json()
    
    if not data.get('name') or not data.get('start_date') or not data.get('end_date'):
        return error_response('Name, start_date and end_date required')
    
    fy = FinancialYear(
        organization_id=g.organization_id,
        name=sanitize_string(data['name']),
        code=sanitize_string(data.get('code', data['name'])),
        start_date=data['start_date'],
        end_date=data['end_date'],
        is_active=data.get('is_active', True),
        is_locked=False
    )
    
    db.session.add(fy)
    db.session.commit()
    
    return success_response(model_to_dict(fy), 'Financial year created', 201)


# Settings routes
@organization_bp.route('/settings', methods=['GET'])
@jwt_required_with_user()
@permission_required('organization.settings')
def get_settings():
    """Get organization settings"""
    org_settings = OrganizationSettings.query.filter_by(organization_id=g.organization_id).first()
    inv_settings = InvoiceSettings.query.filter_by(organization_id=g.organization_id).first()
    
    return success_response({
        'organization': model_to_dict(org_settings) if org_settings else {},
        'invoice': model_to_dict(inv_settings) if inv_settings else {}
    })


@organization_bp.route('/settings/organization', methods=['PUT'])
@jwt_required_with_user()
@permission_required('organization.settings')
def update_org_settings():
    """Update organization settings"""
    settings = OrganizationSettings.query.filter_by(organization_id=g.organization_id).first()
    
    if not settings:
        settings = OrganizationSettings(organization_id=g.organization_id)
        db.session.add(settings)
    
    data = get_request_json()
    
    updateable = [
        'date_format', 'time_format', 'timezone', 'currency', 'currency_symbol',
        'decimal_places', 'thousand_separator', 'decimal_separator',
        'financial_year_start', 'enable_gst', 'gst_rounding', 'allow_negative_stock',
        'low_stock_alert', 'expiry_alert_days', 'smtp_host', 'smtp_port',
        'smtp_username', 'smtp_password', 'smtp_use_tls', 'email_from_name', 'email_from_address'
    ]
    
    for field in updateable:
        if field in data:
            setattr(settings, field, data[field])
    
    settings.updated_at = datetime.utcnow()
    db.session.commit()
    log_activity(
        activity_type=ActivityType.UPDATE,
        entity_type=EntityType.USER,
        entity_id=settings.id,
        description=f"Updated organization settings"
    )

    return success_response(model_to_dict(settings), 'Settings updated')


@organization_bp.route('/settings/invoice', methods=['PUT'])
@jwt_required_with_user()
@permission_required('organization.settings')
def update_invoice_settings():
    """Update invoice settings"""
    settings = InvoiceSettings.query.filter_by(organization_id=g.organization_id).first()
    
    if not settings:
        settings = InvoiceSettings(organization_id=g.organization_id)
        db.session.add(settings)
    
    data = get_request_json()
    
    updateable = [
        'invoice_prefix', 'invoice_suffix', 'quotation_prefix', 'quotation_suffix',
        'sales_order_prefix', 'purchase_order_prefix', 'credit_note_prefix',
        'debit_note_prefix', 'payment_prefix', 'sequence_reset', 'sequence_padding',
        'show_logo', 'show_signature', 'show_bank_details', 'show_terms',
        'show_qr_code', 'default_payment_terms', 'default_notes',
        'enable_einvoice', 'einvoice_username', 'einvoice_password',
        'enable_ewaybill', 'print_copies', 'paper_size'
    ]
    
    for field in updateable:
        if field in data:
            setattr(settings, field, data[field])
    
    settings.updated_at = datetime.utcnow()
    db.session.commit()
    log_activity(
        activity_type=ActivityType.UPDATE,
        entity_type=EntityType.USER,
        entity_id=settings.id,
        description=f"Updated invoice settings"
    )

    return success_response(model_to_dict(settings), 'Invoice settings updated')