from datetime import datetime
from config.database import db


class Category(db.Model):
    """Product/Service category with hierarchical support"""
    __tablename__ = 'categories'

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('categories.id'))
    
    name = db.Column(db.String(100), nullable=False)
    code = db.Column(db.String(20))
    description = db.Column(db.Text)
    image_url = db.Column(db.String(500))
    
    # For hierarchy
    level = db.Column(db.Integer, default=0)
    path = db.Column(db.String(500))  # e.g., "1/5/12" for breadcrumb
    
    is_active = db.Column(db.Boolean, default=True)
    display_order = db.Column(db.Integer, default=0)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Self-referential relationship
    children = db.relationship('Category', backref=db.backref('parent', remote_side=[id]))
    products = db.relationship('Product', backref='category', lazy='dynamic')
    
    def __repr__(self):
        return f'<Category {self.name}>'


class Unit(db.Model):
    """Unit of measurement"""
    __tablename__ = 'units'

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    
    name = db.Column(db.String(50), nullable=False)  # Pieces, Kilograms, Liters
    symbol = db.Column(db.String(10), nullable=False)  # pcs, kg, L
    
    # For unit conversion
    base_unit_id = db.Column(db.Integer, db.ForeignKey('units.id'))
    conversion_factor = db.Column(db.Numeric(15, 6), default=1)  # How many base units in this unit
    
    is_active = db.Column(db.Boolean, default=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        db.UniqueConstraint('organization_id', 'symbol', name='uq_unit_org_symbol'),
    )
    
    def __repr__(self):
        return f'<Unit {self.symbol}>'


class TaxRate(db.Model):
    """Tax rates (GST rates for India)"""
    __tablename__ = 'tax_rates'

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    
    name = db.Column(db.String(50), nullable=False)  # "GST 18%", "GST 12%"
    rate = db.Column(db.Numeric(5, 2), nullable=False)  # Total rate
    
    # GST Breakdown (for India)
    cgst_rate = db.Column(db.Numeric(5, 2), default=0)  # Central GST
    sgst_rate = db.Column(db.Numeric(5, 2), default=0)  # State GST
    igst_rate = db.Column(db.Numeric(5, 2), default=0)  # Integrated GST
    cess_rate = db.Column(db.Numeric(5, 2), default=0)  # Additional cess
    
    # HSN/SAC Code
    hsn_code = db.Column(db.String(10))  # For goods
    sac_code = db.Column(db.String(10))  # For services
    
    description = db.Column(db.String(200))
    is_active = db.Column(db.Boolean, default=True)
    is_default = db.Column(db.Boolean, default=False)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<TaxRate {self.name}>'


class Product(db.Model):
    """Product/Service master"""
    __tablename__ = 'products'

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'))
    
    # Basic Info
    sku = db.Column(db.String(50))  # Stock Keeping Unit
    barcode = db.Column(db.String(50))
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    short_description = db.Column(db.String(500))
    
    # Type
    product_type = db.Column(db.String(20), default='goods')  # goods, service
    is_inventory_item = db.Column(db.Boolean, default=True)  # Track inventory
    
    # Unit of Measurement
    unit_id = db.Column(db.Integer, db.ForeignKey('units.id'))
    secondary_unit_id = db.Column(db.Integer, db.ForeignKey('units.id'))
    conversion_rate = db.Column(db.Numeric(15, 6))  # Secondary to primary unit
    
    # Tax
    tax_rate_id = db.Column(db.Integer, db.ForeignKey('tax_rates.id'))
    hsn_code = db.Column(db.String(10))
    sac_code = db.Column(db.String(10))
    is_taxable = db.Column(db.Boolean, default=True)
    tax_inclusive = db.Column(db.Boolean, default=False)  # Price includes tax
    
    # Pricing
    purchase_price = db.Column(db.Numeric(15, 2), default=0)
    selling_price = db.Column(db.Numeric(15, 2), default=0)
    mrp = db.Column(db.Numeric(15, 2))  # Maximum Retail Price
    min_selling_price = db.Column(db.Numeric(15, 2))  # Minimum allowed
    wholesale_price = db.Column(db.Numeric(15, 2))
    
    # Inventory Settings
    track_inventory = db.Column(db.Boolean, default=True)
    opening_stock = db.Column(db.Numeric(15, 3), default=0)
    current_stock = db.Column(db.Numeric(15, 3), default=0)  # Denormalized for quick access
    reorder_level = db.Column(db.Numeric(15, 3), default=0)
    reorder_quantity = db.Column(db.Numeric(15, 3), default=0)
    min_stock_level = db.Column(db.Numeric(15, 3), default=0)
    max_stock_level = db.Column(db.Numeric(15, 3))
    
    # Batch/Expiry Tracking (for pharma, food, etc.)
    track_batch = db.Column(db.Boolean, default=False)
    track_expiry = db.Column(db.Boolean, default=False)
    shelf_life_days = db.Column(db.Integer)  # Default shelf life
    
    # Serial Number Tracking (for electronics, equipment)
    track_serial = db.Column(db.Boolean, default=False)
    
    # Dimensions & Weight (for shipping)
    weight = db.Column(db.Numeric(10, 3))  # in kg
    weight_unit = db.Column(db.String(10), default='kg')
    length = db.Column(db.Numeric(10, 2))
    width = db.Column(db.Numeric(10, 2))
    height = db.Column(db.Numeric(10, 2))
    dimension_unit = db.Column(db.String(10), default='cm')
    
    # Images
    primary_image_url = db.Column(db.String(500))
    
    # Brand & Manufacturer
    brand = db.Column(db.String(100))
    manufacturer = db.Column(db.String(200))
    manufacturer_part_number = db.Column(db.String(50))
    
    # Additional Info
    notes = db.Column(db.Text)
    tags = db.Column(db.JSON, default=list)
    custom_fields = db.Column(db.JSON, default=dict)  # Flexible fields for different industries
    
    # Status
    is_active = db.Column(db.Boolean, default=True)
    is_sellable = db.Column(db.Boolean, default=True)
    is_purchasable = db.Column(db.Boolean, default=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    # Relationships
    unit = db.relationship('Unit', foreign_keys=[unit_id])
    secondary_unit = db.relationship('Unit', foreign_keys=[secondary_unit_id])
    tax_rate = db.relationship('TaxRate')
    variants = db.relationship('ProductVariant', backref='product', lazy='dynamic', cascade='all, delete-orphan')
    images = db.relationship('ProductImage', backref='product', lazy='dynamic', cascade='all, delete-orphan')
    price_lists = db.relationship('ProductPriceList', backref='product', lazy='dynamic')
    stock = db.relationship('Stock', backref='product', lazy='dynamic')
    
    __table_args__ = (
        db.UniqueConstraint('organization_id', 'sku', name='uq_product_org_sku'),
        db.Index('idx_product_name', 'organization_id', 'name'),
        db.Index('idx_product_barcode', 'organization_id', 'barcode'),
    )
    
    def __repr__(self):
        return f'<Product {self.name}>'


class ProductVariant(db.Model):
    """Product variants (size, color, etc.)"""
    __tablename__ = 'product_variants'

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    
    sku = db.Column(db.String(50))
    barcode = db.Column(db.String(50))
    name = db.Column(db.String(200), nullable=False)  # "Red - Large"
    
    # Variant Attributes
    attributes = db.Column(db.JSON, default=dict)  # {"color": "Red", "size": "Large"}
    
    # Pricing (if different from parent)
    purchase_price = db.Column(db.Numeric(15, 2))
    selling_price = db.Column(db.Numeric(15, 2))
    mrp = db.Column(db.Numeric(15, 2))
    
    # Stock
    opening_stock = db.Column(db.Numeric(15, 3), default=0)
    reorder_level = db.Column(db.Numeric(15, 3), default=0)
    
    image_url = db.Column(db.String(500))
    
    is_active = db.Column(db.Boolean, default=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<ProductVariant {self.name}>'


class ProductImage(db.Model):
    """Multiple images for products"""
    __tablename__ = 'product_images'

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    
    image_url = db.Column(db.String(500), nullable=False)
    thumbnail_url = db.Column(db.String(500))
    alt_text = db.Column(db.String(200))
    display_order = db.Column(db.Integer, default=0)
    is_primary = db.Column(db.Boolean, default=False)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class PriceList(db.Model):
    """Price lists for different customer segments"""
    __tablename__ = 'price_lists'

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    
    name = db.Column(db.String(100), nullable=False)  # "Wholesale", "Retail", "VIP"
    code = db.Column(db.String(20))
    description = db.Column(db.String(200))
    
    # Pricing Method
    pricing_method = db.Column(db.String(20), default='fixed')  # fixed, percentage
    percentage_adjustment = db.Column(db.Numeric(5, 2), default=0)  # +/- from base price
    
    # Validity
    valid_from = db.Column(db.Date)
    valid_to = db.Column(db.Date)
    
    currency = db.Column(db.String(3), default='INR')
    is_active = db.Column(db.Boolean, default=True)
    is_default = db.Column(db.Boolean, default=False)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    products = db.relationship('ProductPriceList', backref='price_list', lazy='dynamic')
    
    def __repr__(self):
        return f'<PriceList {self.name}>'


class ProductPriceList(db.Model):
    """Product-specific prices in price lists"""
    __tablename__ = 'product_price_lists'

    id = db.Column(db.Integer, primary_key=True)
    price_list_id = db.Column(db.Integer, db.ForeignKey('price_lists.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    variant_id = db.Column(db.Integer, db.ForeignKey('product_variants.id'))
    
    price = db.Column(db.Numeric(15, 2), nullable=False)
    min_quantity = db.Column(db.Numeric(15, 3), default=1)  # Minimum qty for this price
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        db.UniqueConstraint('price_list_id', 'product_id', 'variant_id', 'min_quantity', 
                           name='uq_product_price_list'),
    )