"""Product management routes for VyaparaCore"""
from flask import Blueprint, g, request
from datetime import datetime
from config.database import db
from app.models import (
    Product, ProductVariant, ProductImage, Category, Unit, TaxRate,
    PriceList, ProductPriceList
)
from app.utils.security import (
    jwt_required_with_user, permission_required, sanitize_string, create_audit_log
)
from app.utils.helpers import (
    success_response, error_response, get_request_json,
    paginate, get_filters, apply_filters, model_to_dict
)
from app.services.activity_logger import log_activity, log_audit, ActivityType, EntityType

product_bp = Blueprint('product', __name__)


# Categories
@product_bp.route('/categories', methods=['GET'])
@jwt_required_with_user()
@permission_required('categories.view')
def list_categories():
    """List all categories"""
    query = Category.query.filter_by(organization_id=g.organization_id)
    
    if request.args.get('parent_id'):
        query = query.filter_by(parent_id=request.args.get('parent_id', type=int))
    elif request.args.get('root_only'):
        query = query.filter_by(parent_id=None)
    
    filters = get_filters()
    if filters.get('search'):
        query = query.filter(Category.name.ilike(f"%{filters['search']}%"))
    
    query = query.order_by(Category.name)
    categories = query.all()
    
    def serialize(cat):
        data = model_to_dict(cat)
        data['children_count'] = Category.query.filter_by(parent_id=cat.id).count()
        data['products_count'] = Product.query.filter_by(category_id=cat.id).count()
        return data
    
    return success_response([serialize(c) for c in categories])


@product_bp.route('/categories', methods=['POST'])
@jwt_required_with_user()
@permission_required('categories.create')
def create_category():
    """Create category"""
    data = get_request_json()
    
    if not data.get('name'):
        return error_response('Category name required')
    
    code = sanitize_string(data.get('code', '')).upper()
    if not code:
        code = ''.join(e for e in data['name'][:6] if e.isalnum()).upper()
    
    existing = Category.query.filter_by(organization_id=g.organization_id, code=code).first()
    if existing:
        code = f"{code}{datetime.utcnow().strftime('%H%M%S')}"
    
    category = Category(
        organization_id=g.organization_id,
        name=sanitize_string(data['name']),
        code=code,
        description=sanitize_string(data.get('description', '')),
        parent_id=data.get('parent_id'),
        image_url=data.get('image_url'),
        is_active=True
    )
    
    db.session.add(category)
    db.session.commit()

    log_activity(
        activity_type=ActivityType.CREATE,
        description=f"Created category '{category.name}'",
        entity_type=EntityType.CATEGORY,
        entity_id=category.id,
        entity_number=category.code
    )

    return success_response(model_to_dict(category), 'Category created', 201)


@product_bp.route('/categories/<int:id>', methods=['GET'])
@jwt_required_with_user()
@permission_required('categories.view')
def get_category(id):
    """Get single category"""
    category = Category.query.filter_by(id=id, organization_id=g.organization_id).first()
    if not category:
        return error_response('Category not found', status_code=404)

    data = model_to_dict(category)
    data['children_count'] = Category.query.filter_by(parent_id=category.id).count()
    data['products_count'] = Product.query.filter_by(category_id=category.id).count()
    return success_response(data)


@product_bp.route('/categories/<int:id>', methods=['PUT'])
@jwt_required_with_user()
@permission_required('categories.edit')
def update_category(id):
    """Update category"""
    category = Category.query.filter_by(id=id, organization_id=g.organization_id).first()
    if not category:
        return error_response('Category not found', status_code=404)
    
    data = get_request_json()
    
    if data.get('name'):
        category.name = sanitize_string(data['name'])
    if 'description' in data:
        category.description = sanitize_string(data['description'])
    if 'parent_id' in data:
        if data['parent_id'] == category.id:
            return error_response('Cannot set category as its own parent')
        category.parent_id = data['parent_id']
    if 'image_url' in data:
        category.image_url = data['image_url']
    if 'is_active' in data:
        category.is_active = data['is_active']
    
    category.updated_at = datetime.utcnow()
    db.session.commit()
    
    return success_response(model_to_dict(category), 'Category updated')


@product_bp.route('/categories/<int:id>', methods=['DELETE'])
@jwt_required_with_user()
@permission_required('categories.delete')
def delete_category(id):
    """Delete category"""
    category = Category.query.filter_by(id=id, organization_id=g.organization_id).first()
    if not category:
        return error_response('Category not found', status_code=404)
    
    # Check for children
    if Category.query.filter_by(parent_id=id).count() > 0:
        return error_response('Cannot delete category with subcategories')
    
    # Check for products
    if Product.query.filter_by(category_id=id).count() > 0:
        return error_response('Cannot delete category with products')
    
    db.session.delete(category)
    db.session.commit()
    
    return success_response(message='Category deleted')


# Units
@product_bp.route('/units', methods=['GET'])
@jwt_required_with_user()
def list_units():
    """List all units"""
    units = Unit.query.filter_by(organization_id=g.organization_id, is_active=True).order_by(Unit.name).all()
    return success_response([model_to_dict(u) for u in units])


@product_bp.route('/units', methods=['POST'])
@jwt_required_with_user()
@permission_required('products.create')
def create_unit():
    """Create unit"""
    data = get_request_json()
    
    if not data.get('name') or not data.get('code'):
        return error_response('Name and code required')
    
    code = sanitize_string(data['code']).upper()
    
    existing = Unit.query.filter_by(organization_id=g.organization_id, code=code).first()
    if existing:
        return error_response('Unit code already exists')
    
    unit = Unit(
        organization_id=g.organization_id,
        code=code,
        name=sanitize_string(data['name']),
        category=data.get('category', 'Quantity'),
        conversion_factor=data.get('conversion_factor', 1),
        is_active=True
    )
    
    db.session.add(unit)
    db.session.commit()

    return success_response(model_to_dict(unit), 'Unit created', 201)


@product_bp.route('/units/<int:id>', methods=['PUT'])
@jwt_required_with_user()
@permission_required('products.create')
def update_unit(id):
    """Update unit"""
    unit = Unit.query.filter_by(id=id, organization_id=g.organization_id).first()
    if not unit:
        return error_response('Unit not found', status_code=404)

    data = get_request_json()

    if 'name' in data:
        unit.name = sanitize_string(data['name'])
    if 'symbol' in data:
        unit.symbol = sanitize_string(data['symbol']).upper()
    if 'conversion_factor' in data:
        unit.conversion_factor = data['conversion_factor']
    if 'base_unit_id' in data:
        unit.base_unit_id = data['base_unit_id']

    db.session.commit()

    return success_response(model_to_dict(unit), 'Unit updated')


@product_bp.route('/units/<int:id>', methods=['DELETE'])
@jwt_required_with_user()
@permission_required('products.create')
def delete_unit(id):
    """Delete unit"""
    unit = Unit.query.filter_by(id=id, organization_id=g.organization_id).first()
    if not unit:
        return error_response('Unit not found', status_code=404)

    # Check if unit is in use
    product_count = Product.query.filter_by(organization_id=g.organization_id, unit_id=id).count()
    if product_count > 0:
        return error_response(f'Cannot delete unit. {product_count} products use this unit.')

    unit.is_active = False
    db.session.commit()

    return success_response(message='Unit deleted')


# Tax Rates
@product_bp.route('/tax-rates', methods=['GET'])
@jwt_required_with_user()
def list_tax_rates():
    """List all tax rates"""
    rates = TaxRate.query.filter_by(organization_id=g.organization_id, is_active=True).order_by(TaxRate.rate).all()
    return success_response([model_to_dict(r) for r in rates])


@product_bp.route('/tax-rates', methods=['POST'])
@jwt_required_with_user()
@permission_required('products.pricing')
def create_tax_rate():
    """Create tax rate"""
    data = get_request_json()
    
    if not data.get('name') or not data.get('code'):
        return error_response('Name and code required')
    
    tax = TaxRate(
        organization_id=g.organization_id,
        name=sanitize_string(data['name']),
        code=sanitize_string(data['code']).upper(),
        rate=data.get('rate', 0),
        cgst_rate=data.get('cgst_rate', 0),
        sgst_rate=data.get('sgst_rate', 0),
        igst_rate=data.get('igst_rate', 0),
        cess_rate=data.get('cess_rate', 0),
        description=sanitize_string(data.get('description', '')),
        hsn_code=sanitize_string(data.get('hsn_code', '')),
        sac_code=sanitize_string(data.get('sac_code', '')),
        is_default=data.get('is_default', False),
        is_active=True
    )
    
    db.session.add(tax)
    db.session.commit()
    
    return success_response(model_to_dict(tax), 'Tax rate created', 201)


@product_bp.route('/tax-rates/<int:id>', methods=['PUT'])
@jwt_required_with_user()
@permission_required('products.pricing')
def update_tax_rate(id):
    """Update tax rate"""
    tax = TaxRate.query.filter_by(id=id, organization_id=g.organization_id).first()
    if not tax:
        return error_response('Tax rate not found', status_code=404)

    data = get_request_json()

    if 'name' in data:
        tax.name = sanitize_string(data['name'])
    if 'rate' in data:
        tax.rate = data['rate']
    if 'cgst_rate' in data:
        tax.cgst_rate = data['cgst_rate']
    if 'sgst_rate' in data:
        tax.sgst_rate = data['sgst_rate']
    if 'igst_rate' in data:
        tax.igst_rate = data['igst_rate']
    if 'cess_rate' in data:
        tax.cess_rate = data['cess_rate']
    if 'description' in data:
        tax.description = sanitize_string(data['description'])
    if 'hsn_code' in data:
        tax.hsn_code = sanitize_string(data['hsn_code'])
    if 'sac_code' in data:
        tax.sac_code = sanitize_string(data['sac_code'])
    if 'is_default' in data:
        # If setting as default, unset other defaults
        if data['is_default']:
            TaxRate.query.filter_by(organization_id=g.organization_id, is_default=True).update({'is_default': False})
        tax.is_default = data['is_default']

    db.session.commit()

    return success_response(model_to_dict(tax), 'Tax rate updated')


@product_bp.route('/tax-rates/<int:id>', methods=['DELETE'])
@jwt_required_with_user()
@permission_required('products.pricing')
def delete_tax_rate(id):
    """Delete tax rate"""
    tax = TaxRate.query.filter_by(id=id, organization_id=g.organization_id).first()
    if not tax:
        return error_response('Tax rate not found', status_code=404)

    # Check if tax rate is in use
    product_count = Product.query.filter_by(organization_id=g.organization_id, tax_rate_id=id).count()
    if product_count > 0:
        return error_response(f'Cannot delete tax rate. {product_count} products use this tax rate.')

    tax.is_active = False
    db.session.commit()

    return success_response(message='Tax rate deleted')


# Products
@product_bp.route('', methods=['GET'])
@jwt_required_with_user()
@permission_required('products.view')
def list_products():
    """List all products"""
    query = Product.query.filter_by(organization_id=g.organization_id)
    
    filters = get_filters()
    if filters.get('search'):
        search = f"%{filters['search']}%"
        query = query.filter(
            db.or_(
                Product.name.ilike(search),
                Product.sku.ilike(search),
                Product.barcode.ilike(search),
                Product.hsn_code.ilike(search)
            )
        )
    
    if request.args.get('category_id'):
        query = query.filter_by(category_id=request.args.get('category_id', type=int))
    
    if request.args.get('product_type'):
        query = query.filter_by(product_type=request.args.get('product_type'))
    
    if request.args.get('low_stock'):
        query = query.filter(Product.current_stock <= Product.reorder_level)
    
    query = apply_filters(query, Product, filters)
    
    def serialize(p):
        data = model_to_dict(p)
        data['category_name'] = p.category.name if p.category else None
        data['unit_name'] = p.unit.name if p.unit else None
        data['tax_rate_name'] = p.tax_rate.name if p.tax_rate else None
        return data
    
    return success_response(paginate(query, serialize))


@product_bp.route('', methods=['POST'])
@jwt_required_with_user()
@permission_required('products.create')
def create_product():
    """Create product"""
    data = get_request_json()
    
    if not data.get('name'):
        return error_response('Product name required')
    
    # Generate SKU
    sku = sanitize_string(data.get('sku', '')).upper()
    if not sku:
        count = Product.query.filter_by(organization_id=g.organization_id).count() + 1
        sku = f"PRD{count:06d}"
    
    existing = Product.query.filter_by(organization_id=g.organization_id, sku=sku).first()
    if existing:
        return error_response('SKU already exists')
    
    if data.get('barcode'):
        existing = Product.query.filter_by(organization_id=g.organization_id, barcode=data['barcode']).first()
        if existing:
            return error_response('Barcode already exists')
    
    product = Product(
        organization_id=g.organization_id,
        name=sanitize_string(data['name']),
        sku=sku,
        barcode=sanitize_string(data.get('barcode', '')),
        product_type=data.get('product_type', 'goods'),
        category_id=data.get('category_id'),
        unit_id=data.get('unit_id'),
        secondary_unit_id=data.get('secondary_unit_id'),
        conversion_rate=data.get('conversion_rate', 1),
        tax_rate_id=data.get('tax_rate_id'),
        hsn_code=sanitize_string(data.get('hsn_code', '')),
        sac_code=sanitize_string(data.get('sac_code', '')),
        description=sanitize_string(data.get('description', '')),
        short_description=sanitize_string(data.get('short_description', '')),
        purchase_price=data.get('purchase_price', 0),
        selling_price=data.get('selling_price', 0),
        mrp=data.get('mrp'),
        wholesale_price=data.get('wholesale_price'),
        min_selling_price=data.get('min_selling_price'),
        opening_stock=data.get('opening_stock', 0),
        reorder_level=data.get('reorder_level', 0),
        reorder_quantity=data.get('reorder_quantity', 0),
        min_stock_level=data.get('min_stock_level', 0),
        max_stock_level=data.get('max_stock_level'),
        track_inventory=data.get('track_inventory', True),
        track_batch=data.get('track_batch', False),
        track_expiry=data.get('track_expiry', False),
        track_serial=data.get('track_serial', False),
        weight=data.get('weight'),
        weight_unit=data.get('weight_unit'),
        length=data.get('length'),
        width=data.get('width'),
        height=data.get('height'),
        dimension_unit=data.get('dimension_unit'),
        brand=sanitize_string(data.get('brand', '')),
        manufacturer=sanitize_string(data.get('manufacturer', '')),
        primary_image_url=data.get('image_url'),
        tags=data.get('tags', []),
        custom_fields=data.get('custom_fields', {}),
        is_active=True,
        is_sellable=data.get('is_sellable', True),
        is_purchasable=data.get('is_purchasable', True),
        created_by=g.current_user.id
    )
    
    db.session.add(product)
    db.session.flush()
    
    # Add variants
    if data.get('variants'):
        for var in data['variants']:
            variant = ProductVariant(
                product_id=product.id,
                name=sanitize_string(var.get('name', '')),
                sku=sanitize_string(var.get('sku', '')).upper(),
                barcode=sanitize_string(var.get('barcode', '')),
                attributes=var.get('attributes', {}),
                purchase_price=var.get('purchase_price', product.purchase_price),
                selling_price=var.get('selling_price', product.selling_price),
                mrp=var.get('mrp', product.mrp),
                current_stock=var.get('opening_stock', 0),
                image_url=var.get('image_url'),
                is_active=True
            )
            db.session.add(variant)
    
    # Add images
    if data.get('images'):
        for idx, img in enumerate(data['images']):
            image = ProductImage(
                product_id=product.id,
                image_url=img.get('url'),
                alt_text=sanitize_string(img.get('alt_text', '')),
                sort_order=img.get('sort_order', idx),
                is_primary=img.get('is_primary', idx == 0)
            )
            db.session.add(image)
    
    db.session.commit()

    log_audit('products', product.id, 'create', None, model_to_dict(product))
    log_activity(
        activity_type=ActivityType.CREATE,
        description=f"Created product '{product.name}' ({product.sku})",
        entity_type=EntityType.PRODUCT,
        entity_id=product.id,
        entity_number=product.sku
    )

    return success_response(model_to_dict(product), 'Product created', 201)


@product_bp.route('/<int:id>', methods=['GET'])
@jwt_required_with_user()
@permission_required('products.view')
def get_product(id):
    """Get product details"""
    product = Product.query.filter_by(id=id, organization_id=g.organization_id).first()
    if not product:
        return error_response('Product not found', status_code=404)
    
    data = model_to_dict(product)
    data['category'] = model_to_dict(product.category) if product.category else None
    data['unit'] = model_to_dict(product.unit) if product.unit else None
    data['tax_rate'] = model_to_dict(product.tax_rate) if product.tax_rate else None
    data['variants'] = [model_to_dict(v) for v in product.variants]
    data['images'] = [model_to_dict(i) for i in product.images]
    
    return success_response(data)


@product_bp.route('/<int:id>', methods=['PUT'])
@jwt_required_with_user()
@permission_required('products.edit')
def update_product(id):
    """Update product"""
    product = Product.query.filter_by(id=id, organization_id=g.organization_id).first()
    if not product:
        return error_response('Product not found', status_code=404)
    
    data = get_request_json()
    old_values = model_to_dict(product)
    
    updateable = [
        'name', 'barcode', 'product_type', 'category_id', 'unit_id', 'secondary_unit_id',
        'conversion_rate', 'tax_rate_id', 'hsn_code', 'sac_code', 'description',
        'short_description', 'purchase_price', 'selling_price', 'mrp', 'wholesale_price',
        'min_selling_price', 'opening_stock', 'reorder_level', 'reorder_quantity', 'min_stock_level',
        'max_stock_level', 'track_inventory', 'track_batch', 'track_expiry', 'track_serial',
        'weight', 'weight_unit', 'length', 'width', 'height', 'dimension_unit',
        'brand', 'manufacturer', 'primary_image_url', 'tags', 'custom_fields',
        'is_active', 'is_sellable', 'is_purchasable'
    ]
    
    for field in updateable:
        if field in data:
            value = data[field]
            if isinstance(value, str) and field not in ['tags', 'custom_fields']:
                value = sanitize_string(value)
            setattr(product, field, value)
    
    product.updated_at = datetime.utcnow()
    product.updated_by = g.current_user.id

    log_audit('products', product.id, 'update', old_values, model_to_dict(product))
    db.session.commit()

    log_activity(
        activity_type=ActivityType.UPDATE,
        description=f"Updated product '{product.name}' ({product.sku})",
        entity_type=EntityType.PRODUCT,
        entity_id=product.id,
        entity_number=product.sku
    )

    return success_response(model_to_dict(product), 'Product updated')


@product_bp.route('/<int:id>', methods=['DELETE'])
@jwt_required_with_user()
@permission_required('products.delete')
def delete_product(id):
    """Delete product (soft delete)"""
    product = Product.query.filter_by(id=id, organization_id=g.organization_id).first()
    if not product:
        return error_response('Product not found', status_code=404)
    
    if product.current_stock and product.current_stock > 0:
        return error_response('Cannot delete product with stock')
    
    product.is_active = False
    product.updated_at = datetime.utcnow()

    log_audit('products', product.id, 'delete', model_to_dict(product), None)
    db.session.commit()

    log_activity(
        activity_type=ActivityType.DELETE,
        description=f"Deleted product '{product.name}' ({product.sku})",
        entity_type=EntityType.PRODUCT,
        entity_id=product.id,
        entity_number=product.sku
    )

    return success_response(message='Product deleted')


# Product Variants
@product_bp.route('/<int:id>/variants', methods=['POST'])
@jwt_required_with_user()
@permission_required('products.edit')
def add_variant(id):
    """Add product variant"""
    product = Product.query.filter_by(id=id, organization_id=g.organization_id).first()
    if not product:
        return error_response('Product not found', status_code=404)
    
    data = get_request_json()
    
    variant = ProductVariant(
        product_id=product.id,
        name=sanitize_string(data.get('name', '')),
        sku=sanitize_string(data.get('sku', '')).upper(),
        barcode=sanitize_string(data.get('barcode', '')),
        attributes=data.get('attributes', {}),
        purchase_price=data.get('purchase_price', product.purchase_price),
        selling_price=data.get('selling_price', product.selling_price),
        mrp=data.get('mrp', product.mrp),
        current_stock=data.get('opening_stock', 0),
        image_url=data.get('image_url'),
        is_active=True
    )
    
    db.session.add(variant)
    db.session.commit()
    
    return success_response(model_to_dict(variant), 'Variant added', 201)


# Price Lists
@product_bp.route('/price-lists', methods=['GET'])
@jwt_required_with_user()
@permission_required('products.pricing')
def list_price_lists():
    """List price lists"""
    lists = PriceList.query.filter_by(organization_id=g.organization_id).all()

    def serialize(pl):
        data = model_to_dict(pl)
        data['items_count'] = ProductPriceList.query.filter_by(price_list_id=pl.id).count()
        return data

    return success_response([serialize(pl) for pl in lists])


@product_bp.route('/price-lists', methods=['POST'])
@jwt_required_with_user()
@permission_required('products.pricing')
def create_price_list():
    """Create price list"""
    data = get_request_json()
    
    if not data.get('name'):
        return error_response('Price list name required')
    
    code = sanitize_string(data.get('code', '')).upper()
    if not code:
        code = ''.join(e for e in data['name'][:6] if e.isalnum()).upper()
    
    price_list = PriceList(
        organization_id=g.organization_id,
        name=sanitize_string(data['name']),
        code=code,
        description=sanitize_string(data.get('description', '')),
        pricing_method=data.get('pricing_method', 'fixed'),
        percentage_adjustment=data.get('percentage_adjustment', 0),
        currency=data.get('currency', 'INR'),
        valid_from=data.get('valid_from'),
        valid_to=data.get('valid_to'),
        is_active=data.get('is_active', True)
    )
    
    db.session.add(price_list)
    db.session.flush()

    # Add items if provided
    if data.get('items'):
        for item in data['items']:
            if item.get('product_id'):
                ppl = ProductPriceList(
                    price_list_id=price_list.id,
                    product_id=item['product_id'],
                    variant_id=item.get('variant_id'),
                    price=item.get('special_price', item.get('price', 0)),
                    min_quantity=item.get('min_quantity', 1)
                )
                db.session.add(ppl)

    db.session.commit()

    return success_response(model_to_dict(price_list), 'Price list created', 201)


@product_bp.route('/price-lists/<int:id>', methods=['GET'])
@jwt_required_with_user()
@permission_required('products.pricing')
def get_price_list(id):
    """Get single price list"""
    price_list = PriceList.query.filter_by(id=id, organization_id=g.organization_id).first()
    if not price_list:
        return error_response('Price list not found', status_code=404)

    data = model_to_dict(price_list)

    # Include price list items with product details
    items = []
    for ppl in price_list.products.all():
        product = Product.query.get(ppl.product_id)
        if product:
            items.append({
                'product_id': ppl.product_id,
                'product_name': product.name,
                'product_sku': product.sku,
                'original_price': float(product.selling_price or 0),
                'price': float(ppl.price or 0),
                'min_quantity': float(ppl.min_quantity or 1),
                'variant_id': ppl.variant_id
            })
    data['items'] = items

    return success_response(data)


@product_bp.route('/price-lists/<int:id>', methods=['PUT'])
@jwt_required_with_user()
@permission_required('products.pricing')
def update_price_list(id):
    """Update price list"""
    price_list = PriceList.query.filter_by(id=id, organization_id=g.organization_id).first()
    if not price_list:
        return error_response('Price list not found', status_code=404)

    data = get_request_json()

    if 'name' in data:
        price_list.name = sanitize_string(data['name'])
    if 'description' in data:
        price_list.description = sanitize_string(data['description'])
    if 'pricing_method' in data:
        price_list.pricing_method = data['pricing_method']
    if 'percentage_adjustment' in data:
        price_list.percentage_adjustment = data['percentage_adjustment']
    if 'valid_from' in data:
        price_list.valid_from = data['valid_from']
    if 'valid_to' in data:
        price_list.valid_to = data['valid_to']
    if 'is_active' in data:
        price_list.is_active = data['is_active']

    # Handle items update
    if 'items' in data:
        # Delete existing items
        ProductPriceList.query.filter_by(price_list_id=id).delete()

        # Add new items
        for item in data['items']:
            if item.get('product_id'):
                ppl = ProductPriceList(
                    price_list_id=id,
                    product_id=item['product_id'],
                    variant_id=item.get('variant_id'),
                    price=item.get('special_price', item.get('price', 0)),
                    min_quantity=item.get('min_quantity', 1)
                )
                db.session.add(ppl)

    price_list.updated_at = datetime.utcnow()
    db.session.commit()

    return success_response(model_to_dict(price_list), 'Price list updated')


@product_bp.route('/price-lists/<int:id>', methods=['DELETE'])
@jwt_required_with_user()
@permission_required('products.pricing')
def delete_price_list(id):
    """Delete price list"""
    price_list = PriceList.query.filter_by(id=id, organization_id=g.organization_id).first()
    if not price_list:
        return error_response('Price list not found', status_code=404)

    # Delete associated product prices
    ProductPriceList.query.filter_by(price_list_id=id).delete()

    db.session.delete(price_list)
    db.session.commit()

    return success_response(message='Price list deleted')


@product_bp.route('/price-lists/<int:id>/products', methods=['POST'])
@jwt_required_with_user()
@permission_required('products.pricing')
def set_product_price(id):
    """Set product price in price list"""
    price_list = PriceList.query.filter_by(id=id, organization_id=g.organization_id).first()
    if not price_list:
        return error_response('Price list not found', status_code=404)
    
    data = get_request_json()
    
    if not data.get('product_id'):
        return error_response('Product ID required')
    
    # Check if product exists
    product = Product.query.filter_by(id=data['product_id'], organization_id=g.organization_id).first()
    if not product:
        return error_response('Product not found', status_code=404)
    
    # Update or create
    ppl = ProductPriceList.query.filter_by(
        price_list_id=id,
        product_id=data['product_id'],
        variant_id=data.get('variant_id')
    ).first()
    
    if ppl:
        ppl.price = data.get('price', 0)
        ppl.min_quantity = data.get('min_quantity', 1)
    else:
        ppl = ProductPriceList(
            price_list_id=id,
            product_id=data['product_id'],
            variant_id=data.get('variant_id'),
            price=data.get('price', 0),
            min_quantity=data.get('min_quantity', 1)
        )
        db.session.add(ppl)
    
    db.session.commit()
    
    return success_response(model_to_dict(ppl), 'Price set')


# Lookup for dropdown
@product_bp.route('/lookup', methods=['GET'])
@jwt_required_with_user()
def product_lookup():
    """Quick product lookup for dropdowns"""
    search = request.args.get('q', '')
    limit = min(request.args.get('limit', 20, type=int), 50)
    
    query = Product.query.filter_by(
        organization_id=g.organization_id,
        is_active=True
    )
    
    if search:
        search = f"%{search}%"
        query = query.filter(
            db.or_(
                Product.name.ilike(search),
                Product.sku.ilike(search),
                Product.barcode.ilike(search)
            )
        )
    
    products = query.limit(limit).all()
    
    result = [{
        'id': p.id,
        'name': p.name,
        'sku': p.sku,
        'selling_price': float(p.selling_price or 0),
        'purchase_price': float(p.purchase_price or 0),
        'current_stock': float(p.current_stock or 0),
        'unit': p.unit.code if p.unit else None,
        'tax_rate': p.tax_rate.rate if p.tax_rate else 0
    } for p in products]
    
    return success_response(result)