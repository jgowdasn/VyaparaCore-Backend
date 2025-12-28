"""Response and helper utilities for VyaparaCore"""
from flask import jsonify, request
from functools import wraps
from decimal import Decimal


def success_response(data=None, message=None, status_code=200):
    response = {'success': True}
    if message:
        response['message'] = message
    if data is not None:
        response['data'] = data
    return jsonify(response), status_code


def error_response(message, errors=None, status_code=400):
    response = {'success': False, 'error': message}
    if errors:
        response['errors'] = errors
    return jsonify(response), status_code


def paginate(query, schema=None):
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)
    
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    
    items = pagination.items
    if schema:
        items = schema.dump(items, many=True) if hasattr(schema, 'dump') else [schema(i) for i in items]
    
    return {
        'items': items,
        'pagination': {
            'page': pagination.page,
            'per_page': pagination.per_page,
            'total_pages': pagination.pages,
            'total_items': pagination.total,
            'has_next': pagination.has_next,
            'has_prev': pagination.has_prev
        }
    }


def get_request_json():
    """Safely get JSON from request"""
    try:
        return request.get_json() or {}
    except Exception:
        return {}


def get_filters():
    """Extract common filter parameters"""
    return {
        'search': request.args.get('search', ''),
        'sort_by': request.args.get('sort_by', 'created_at'),
        'sort_order': request.args.get('sort_order', 'desc'),
        'status': request.args.get('status'),
        'from_date': request.args.get('from_date'),
        'to_date': request.args.get('to_date'),
        'is_active': request.args.get('is_active', type=lambda x: x.lower() == 'true' if x else None)
    }


def apply_filters(query, model, filters):
    """Apply common filters to query"""
    from sqlalchemy import desc, asc
    
    if filters.get('is_active') is not None and hasattr(model, 'is_active'):
        query = query.filter(model.is_active == filters['is_active'])
    
    if filters.get('status') and hasattr(model, 'status'):
        query = query.filter(model.status == filters['status'])
    
    if filters.get('from_date') and hasattr(model, 'created_at'):
        query = query.filter(model.created_at >= filters['from_date'])
    
    if filters.get('to_date') and hasattr(model, 'created_at'):
        query = query.filter(model.created_at <= filters['to_date'])
    
    # Sorting
    sort_by = filters.get('sort_by', 'created_at')
    if hasattr(model, sort_by):
        sort_column = getattr(model, sort_by)
        if filters.get('sort_order', 'desc') == 'desc':
            query = query.order_by(desc(sort_column))
        else:
            query = query.order_by(asc(sort_column))
    
    return query


def model_to_dict(model, exclude=None, include=None):
    """Convert SQLAlchemy model to dictionary"""
    exclude = exclude or []
    result = {}

    for column in model.__table__.columns:
        if column.name in exclude:
            continue
        if include and column.name not in include:
            continue

        value = getattr(model, column.name)
        if hasattr(value, 'isoformat'):
            value = value.isoformat()
        elif isinstance(value, Decimal):
            value = float(value)
        result[column.name] = value

    return result


def validate_required_fields(data, required_fields):
    """Validate required fields in request data"""
    missing = [f for f in required_fields if not data.get(f)]
    if missing:
        return False, f"Missing required fields: {', '.join(missing)}"
    return True, None


def validate_unique(model, field, value, org_id, exclude_id=None):
    """Check if a value is unique within organization"""
    query = model.query.filter(
        model.organization_id == org_id,
        getattr(model, field) == value
    )
    if exclude_id:
        query = query.filter(model.id != exclude_id)
    return query.first() is None