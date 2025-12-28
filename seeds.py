"""Seed data for VyaparaCore - Default roles, permissions, tax rates, units"""
from config.database import db
from app.models import (
    Permission, Role, Unit, TaxRate,
    Organization, User, OrganizationSettings, InvoiceSettings,
    user_roles, role_permissions
)
from app.utils.security import hash_password
from datetime import datetime
from sqlalchemy import insert


# Default Permissions - module.action format
DEFAULT_PERMISSIONS = [
    # Dashboard
    ('dashboard.view', 'View dashboard'),
    
    # Organization
    ('organization.view', 'View organization'),
    ('organization.edit', 'Edit organization'),
    ('organization.settings', 'Manage settings'),
    
    # Branch
    ('branch.view', 'View branches'),
    ('branch.create', 'Create branch'),
    ('branch.edit', 'Edit branch'),
    ('branch.delete', 'Delete branch'),
    
    # Users
    ('users.view', 'View users'),
    ('users.create', 'Create user'),
    ('users.edit', 'Edit user'),
    ('users.delete', 'Delete user'),
    ('users.roles', 'Manage user roles'),
    
    # Roles
    ('roles.view', 'View roles'),
    ('roles.create', 'Create role'),
    ('roles.edit', 'Edit role'),
    ('roles.delete', 'Delete role'),
    
    # Customers
    ('customers.view', 'View customers'),
    ('customers.create', 'Create customer'),
    ('customers.edit', 'Edit customer'),
    ('customers.delete', 'Delete customer'),
    ('customers.export', 'Export customers'),
    
    # Suppliers
    ('suppliers.view', 'View suppliers'),
    ('suppliers.create', 'Create supplier'),
    ('suppliers.edit', 'Edit supplier'),
    ('suppliers.delete', 'Delete supplier'),
    ('suppliers.export', 'Export suppliers'),
    
    # Products
    ('products.view', 'View products'),
    ('products.create', 'Create product'),
    ('products.edit', 'Edit product'),
    ('products.delete', 'Delete product'),
    ('products.pricing', 'Manage pricing'),
    ('products.export', 'Export products'),
    
    # Categories
    ('categories.view', 'View categories'),
    ('categories.create', 'Create category'),
    ('categories.edit', 'Edit category'),
    ('categories.delete', 'Delete category'),
    
    # Inventory
    ('inventory.view', 'View inventory'),
    ('inventory.adjust', 'Adjust stock'),
    ('inventory.transfer', 'Transfer stock'),
    ('inventory.export', 'Export inventory'),
    
    # Warehouse
    ('warehouse.view', 'View warehouses'),
    ('warehouse.create', 'Create warehouse'),
    ('warehouse.edit', 'Edit warehouse'),
    ('warehouse.delete', 'Delete warehouse'),
    
    # Quotations
    ('quotations.view', 'View quotations'),
    ('quotations.create', 'Create quotation'),
    ('quotations.edit', 'Edit quotation'),
    ('quotations.delete', 'Delete quotation'),
    ('quotations.approve', 'Approve quotation'),
    ('quotations.convert', 'Convert to order'),
    ('quotations.print', 'Print quotation'),
    
    # Sales Orders
    ('sales_orders.view', 'View sales orders'),
    ('sales_orders.create', 'Create sales order'),
    ('sales_orders.edit', 'Edit sales order'),
    ('sales_orders.delete', 'Delete sales order'),
    ('sales_orders.approve', 'Approve sales order'),
    ('sales_orders.cancel', 'Cancel sales order'),
    
    # Purchase Orders
    ('purchase_orders.view', 'View purchase orders'),
    ('purchase_orders.create', 'Create purchase order'),
    ('purchase_orders.edit', 'Edit purchase order'),
    ('purchase_orders.delete', 'Delete purchase order'),
    ('purchase_orders.approve', 'Approve purchase order'),
    ('purchase_orders.receive', 'Receive goods'),
    
    # Invoices
    ('invoices.view', 'View invoices'),
    ('invoices.create', 'Create invoice'),
    ('invoices.edit', 'Edit invoice'),
    ('invoices.delete', 'Delete invoice'),
    ('invoices.void', 'Void invoice'),
    ('invoices.print', 'Print invoice'),
    ('invoices.email', 'Email invoice'),
    ('invoices.export', 'Export invoices'),
    
    # Credit Notes
    ('credit_notes.view', 'View credit notes'),
    ('credit_notes.create', 'Create credit note'),
    ('credit_notes.edit', 'Edit credit note'),
    ('credit_notes.delete', 'Delete credit note'),
    
    # Debit Notes
    ('debit_notes.view', 'View debit notes'),
    ('debit_notes.create', 'Create debit note'),
    ('debit_notes.edit', 'Edit debit note'),
    ('debit_notes.delete', 'Delete debit note'),
    
    # Payments
    ('payments.view', 'View payments'),
    ('payments.create', 'Record payment'),
    ('payments.edit', 'Edit payment'),
    ('payments.delete', 'Delete payment'),
    ('payments.approve', 'Approve payment'),
    ('payments.export', 'Export payments'),
    
    # Reports
    ('reports.sales', 'View sales reports'),
    ('reports.purchase', 'View purchase reports'),
    ('reports.inventory', 'View inventory reports'),
    ('reports.financial', 'View financial reports'),
    ('reports.tax', 'View tax reports'),
    ('reports.custom', 'Create custom reports'),
    
    # Audit
    ('audit.view', 'View audit logs'),
    ('audit.export', 'Export audit logs'),
]


# Default Roles with their permissions
DEFAULT_ROLES = {
    'super_admin': {
        'name': 'Super Admin',
        'description': 'Full system access',
        'is_system': True,
        'permissions': ['*']  # All permissions
    },
    'admin': {
        'name': 'Admin',
        'description': 'Organization administrator',
        'is_system': True,
        'permissions': [
            'dashboard.view', 'organization.view', 'organization.edit', 'organization.settings',
            'branch.*', 'users.*', 'roles.*', 'customers.*', 'suppliers.*', 'products.*',
            'categories.*', 'inventory.*', 'warehouse.*', 'quotations.*', 'sales_orders.*',
            'purchase_orders.*', 'invoices.*', 'credit_notes.*', 'debit_notes.*', 'payments.*',
            'reports.*', 'audit.view'
        ]
    },
    'manager': {
        'name': 'Manager',
        'description': 'Branch/Department manager',
        'is_system': True,
        'permissions': [
            'dashboard.view', 'customers.*', 'suppliers.*', 'products.view', 'products.edit',
            'categories.view', 'inventory.*', 'quotations.*', 'sales_orders.*', 'purchase_orders.*',
            'invoices.*', 'credit_notes.*', 'debit_notes.*', 'payments.*', 'reports.*'
        ]
    },
    'accountant': {
        'name': 'Accountant',
        'description': 'Accounting and finance',
        'is_system': True,
        'permissions': [
            'dashboard.view', 'customers.view', 'suppliers.view', 'invoices.*', 'credit_notes.*',
            'debit_notes.*', 'payments.*', 'reports.*', 'audit.view'
        ]
    },
    'sales': {
        'name': 'Sales Executive',
        'description': 'Sales team member',
        'is_system': True,
        'permissions': [
            'dashboard.view', 'customers.view', 'customers.create', 'customers.edit',
            'products.view', 'inventory.view', 'quotations.*', 'sales_orders.view',
            'sales_orders.create', 'sales_orders.edit', 'invoices.view', 'invoices.create',
            'invoices.print', 'payments.view', 'payments.create', 'reports.sales'
        ]
    },
    'purchase': {
        'name': 'Purchase Executive',
        'description': 'Purchase team member',
        'is_system': True,
        'permissions': [
            'dashboard.view', 'suppliers.view', 'suppliers.create', 'suppliers.edit',
            'products.view', 'inventory.view', 'purchase_orders.*', 'debit_notes.view',
            'debit_notes.create', 'payments.view', 'reports.purchase', 'reports.inventory'
        ]
    },
    'warehouse': {
        'name': 'Warehouse Staff',
        'description': 'Inventory management',
        'is_system': True,
        'permissions': [
            'dashboard.view', 'products.view', 'inventory.*', 'warehouse.view',
            'sales_orders.view', 'purchase_orders.view', 'purchase_orders.receive',
            'reports.inventory'
        ]
    },
    'viewer': {
        'name': 'Viewer',
        'description': 'Read-only access',
        'is_system': True,
        'permissions': [
            'dashboard.view', 'customers.view', 'suppliers.view', 'products.view',
            'inventory.view', 'quotations.view', 'sales_orders.view', 'purchase_orders.view',
            'invoices.view', 'payments.view'
        ]
    }
}


# Default Units
DEFAULT_UNITS = [
    # Quantity
    ('NOS', 'Numbers', 'Quantity', 1),
    ('PCS', 'Pieces', 'Quantity', 1),
    ('SET', 'Sets', 'Quantity', 1),
    ('PAR', 'Pairs', 'Quantity', 1),
    ('DOZ', 'Dozens', 'Quantity', 12),
    ('GRS', 'Gross', 'Quantity', 144),
    ('BOX', 'Boxes', 'Quantity', 1),
    ('CTN', 'Cartons', 'Quantity', 1),
    ('PKT', 'Packets', 'Quantity', 1),
    ('BAG', 'Bags', 'Quantity', 1),
    ('BTL', 'Bottles', 'Quantity', 1),
    ('CAN', 'Cans', 'Quantity', 1),
    ('DRM', 'Drums', 'Quantity', 1),
    ('ROL', 'Rolls', 'Quantity', 1),
    ('BDL', 'Bundles', 'Quantity', 1),
    ('SHT', 'Sheets', 'Quantity', 1),
    
    # Weight
    ('KGS', 'Kilograms', 'Weight', 1),
    ('GMS', 'Grams', 'Weight', 0.001),
    ('MGS', 'Milligrams', 'Weight', 0.000001),
    ('TON', 'Metric Tons', 'Weight', 1000),
    ('QTL', 'Quintals', 'Weight', 100),
    ('LBS', 'Pounds', 'Weight', 0.453592),
    ('OZS', 'Ounces', 'Weight', 0.0283495),
    
    # Length
    ('MTR', 'Meters', 'Length', 1),
    ('CMS', 'Centimeters', 'Length', 0.01),
    ('MMS', 'Millimeters', 'Length', 0.001),
    ('KMR', 'Kilometers', 'Length', 1000),
    ('FTS', 'Feet', 'Length', 0.3048),
    ('INS', 'Inches', 'Length', 0.0254),
    ('YDS', 'Yards', 'Length', 0.9144),
    
    # Area
    ('SQM', 'Square Meters', 'Area', 1),
    ('SQF', 'Square Feet', 'Area', 0.092903),
    ('SQY', 'Square Yards', 'Area', 0.836127),
    ('ACR', 'Acres', 'Area', 4046.86),
    
    # Volume
    ('LTR', 'Liters', 'Volume', 1),
    ('MLT', 'Milliliters', 'Volume', 0.001),
    ('CBM', 'Cubic Meters', 'Volume', 1000),
    ('GAL', 'Gallons', 'Volume', 3.78541),
    
    # Time
    ('HRS', 'Hours', 'Time', 1),
    ('DAY', 'Days', 'Time', 24),
    ('WKS', 'Weeks', 'Time', 168),
    ('MON', 'Months', 'Time', 720),
    ('YRS', 'Years', 'Time', 8760),
]


# Default Tax Rates (India GST)
DEFAULT_TAX_RATES = [
    # GST Rates
    {
        'name': 'GST 0%',
        'code': 'GST0',
        'rate': 0,
        'cgst_rate': 0,
        'sgst_rate': 0,
        'igst_rate': 0,
        'cess_rate': 0,
        'description': 'Exempt/Nil rated',
        'is_default': False
    },
    {
        'name': 'GST 0.25%',
        'code': 'GST0.25',
        'rate': 0.25,
        'cgst_rate': 0.125,
        'sgst_rate': 0.125,
        'igst_rate': 0.25,
        'cess_rate': 0,
        'description': 'Rough diamonds, precious stones',
        'is_default': False
    },
    {
        'name': 'GST 3%',
        'code': 'GST3',
        'rate': 3,
        'cgst_rate': 1.5,
        'sgst_rate': 1.5,
        'igst_rate': 3,
        'cess_rate': 0,
        'description': 'Gold, silver, platinum',
        'is_default': False
    },
    {
        'name': 'GST 5%',
        'code': 'GST5',
        'rate': 5,
        'cgst_rate': 2.5,
        'sgst_rate': 2.5,
        'igst_rate': 5,
        'cess_rate': 0,
        'description': 'Essential items, food products',
        'is_default': False
    },
    {
        'name': 'GST 12%',
        'code': 'GST12',
        'rate': 12,
        'cgst_rate': 6,
        'sgst_rate': 6,
        'igst_rate': 12,
        'cess_rate': 0,
        'description': 'Standard rate 1',
        'is_default': False
    },
    {
        'name': 'GST 18%',
        'code': 'GST18',
        'rate': 18,
        'cgst_rate': 9,
        'sgst_rate': 9,
        'igst_rate': 18,
        'cess_rate': 0,
        'description': 'Standard rate 2',
        'is_default': True
    },
    {
        'name': 'GST 28%',
        'code': 'GST28',
        'rate': 28,
        'cgst_rate': 14,
        'sgst_rate': 14,
        'igst_rate': 28,
        'cess_rate': 0,
        'description': 'Luxury items',
        'is_default': False
    },
    # With Cess
    {
        'name': 'GST 28% + 12% Cess',
        'code': 'GST28C12',
        'rate': 28,
        'cgst_rate': 14,
        'sgst_rate': 14,
        'igst_rate': 28,
        'cess_rate': 12,
        'description': 'Motor vehicles',
        'is_default': False
    },
    {
        'name': 'GST 28% + 22% Cess',
        'code': 'GST28C22',
        'rate': 28,
        'cgst_rate': 14,
        'sgst_rate': 14,
        'igst_rate': 28,
        'cess_rate': 22,
        'description': 'Luxury motor vehicles',
        'is_default': False
    },
]


# Indian States with codes
INDIAN_STATES = [
    ('01', 'Jammu & Kashmir'),
    ('02', 'Himachal Pradesh'),
    ('03', 'Punjab'),
    ('04', 'Chandigarh'),
    ('05', 'Uttarakhand'),
    ('06', 'Haryana'),
    ('07', 'Delhi'),
    ('08', 'Rajasthan'),
    ('09', 'Uttar Pradesh'),
    ('10', 'Bihar'),
    ('11', 'Sikkim'),
    ('12', 'Arunachal Pradesh'),
    ('13', 'Nagaland'),
    ('14', 'Manipur'),
    ('15', 'Mizoram'),
    ('16', 'Tripura'),
    ('17', 'Meghalaya'),
    ('18', 'Assam'),
    ('19', 'West Bengal'),
    ('20', 'Jharkhand'),
    ('21', 'Odisha'),
    ('22', 'Chhattisgarh'),
    ('23', 'Madhya Pradesh'),
    ('24', 'Gujarat'),
    ('26', 'Dadra & Nagar Haveli and Daman & Diu'),
    ('27', 'Maharashtra'),
    ('28', 'Andhra Pradesh'),
    ('29', 'Karnataka'),
    ('30', 'Goa'),
    ('31', 'Lakshadweep'),
    ('32', 'Kerala'),
    ('33', 'Tamil Nadu'),
    ('34', 'Puducherry'),
    ('35', 'Andaman & Nicobar Islands'),
    ('36', 'Telangana'),
    ('37', 'Andhra Pradesh (New)'),
    ('38', 'Ladakh'),
]


def seed_permissions():
    """Create default permissions"""
    print("Seeding permissions...")
    for code, description in DEFAULT_PERMISSIONS:
        existing = Permission.query.filter_by(code=code).first()
        if not existing:
            module = code.split('.')[0]
            permission = Permission(
                code=code,
                name=description,
                module=module,
                description=description
            )
            db.session.add(permission)
    db.session.commit()
    print(f"Created {len(DEFAULT_PERMISSIONS)} permissions")


def seed_roles_for_organization(org_id):
    """Create default roles for an organization"""
    print(f"Seeding roles for organization {org_id}...")
    all_permissions = {p.code: p for p in Permission.query.all()}

    for role_code, role_data in DEFAULT_ROLES.items():
        existing = Role.query.filter_by(
            organization_id=org_id,
            code=role_code
        ).first()

        if not existing:
            role = Role(
                organization_id=org_id,
                code=role_code,
                name=role_data['name'],
                description=role_data['description'],
                is_system_role=role_data['is_system'],
                is_active=True
            )
            db.session.add(role)
            db.session.flush()

            # Track assigned permission IDs to avoid duplicates
            assigned_perm_ids = set()

            # Assign permissions
            for perm_pattern in role_data['permissions']:
                if perm_pattern == '*':
                    # All permissions
                    for perm in all_permissions.values():
                        if perm.id not in assigned_perm_ids:
                            assigned_perm_ids.add(perm.id)
                            db.session.execute(role_permissions.insert().values(role_id=role.id, permission_id=perm.id))
                elif perm_pattern.endswith('.*'):
                    # Module wildcard
                    module = perm_pattern[:-2]
                    for code, perm in all_permissions.items():
                        if code.startswith(f"{module}.") and perm.id not in assigned_perm_ids:
                            assigned_perm_ids.add(perm.id)
                            db.session.execute(role_permissions.insert().values(role_id=role.id, permission_id=perm.id))
                else:
                    # Specific permission
                    if perm_pattern in all_permissions:
                        perm = all_permissions[perm_pattern]
                        if perm.id not in assigned_perm_ids:
                            assigned_perm_ids.add(perm.id)
                            db.session.execute(role_permissions.insert().values(role_id=role.id, permission_id=perm.id))

    db.session.commit()
    print(f"Created {len(DEFAULT_ROLES)} roles")


def seed_units_for_organization(org_id):
    """Create default units for an organization"""
    print(f"Seeding units for organization {org_id}...")
    for symbol, name, category, conversion in DEFAULT_UNITS:
        existing = Unit.query.filter_by(
            organization_id=org_id,
            symbol=symbol
        ).first()

        if not existing:
            unit = Unit(
                organization_id=org_id,
                symbol=symbol,
                name=name,
                conversion_factor=conversion,
                is_active=True
            )
            db.session.add(unit)

    db.session.commit()
    print(f"Created {len(DEFAULT_UNITS)} units")


def seed_tax_rates_for_organization(org_id):
    """Create default tax rates for an organization"""
    print(f"Seeding tax rates for organization {org_id}...")
    for tax_data in DEFAULT_TAX_RATES:
        existing = TaxRate.query.filter_by(
            organization_id=org_id,
            name=tax_data['name']
        ).first()

        if not existing:
            tax = TaxRate(
                organization_id=org_id,
                name=tax_data['name'],
                rate=tax_data['rate'],
                cgst_rate=tax_data['cgst_rate'],
                sgst_rate=tax_data['sgst_rate'],
                igst_rate=tax_data['igst_rate'],
                cess_rate=tax_data['cess_rate'],
                description=tax_data['description'],
                is_default=tax_data['is_default'],
                is_active=True
            )
            db.session.add(tax)

    db.session.commit()
    print(f"Created {len(DEFAULT_TAX_RATES)} tax rates")


def seed_organization_settings(org_id):
    """Create default settings for an organization"""
    print(f"Seeding settings for organization {org_id}...")

    # Organization settings (matching actual model fields)
    existing_org_settings = OrganizationSettings.query.filter_by(organization_id=org_id).first()
    if not existing_org_settings:
        org_settings = OrganizationSettings(
            organization_id=org_id,
            date_format='DD/MM/YYYY',
            time_format='12h',
            timezone='Asia/Kolkata',
            base_currency='INR',
            currency_symbol='₹',
            decimal_places=2,
            thousand_separator=',',
            decimal_separator='.',
            gst_enabled=True,
            round_off_enabled=True,
            negative_stock_allowed=False,
            low_stock_alert_enabled=True,
            expiry_alert_days=30
        )
        db.session.add(org_settings)

    # Invoice settings (matching actual model fields)
    existing_inv_settings = InvoiceSettings.query.filter_by(organization_id=org_id).first()
    if not existing_inv_settings:
        inv_settings = InvoiceSettings(
            organization_id=org_id,
            invoice_prefix='INV-',
            quotation_prefix='QTN-',
            sales_order_prefix='SO-',
            purchase_order_prefix='PO-',
            credit_note_prefix='CN-',
            debit_note_prefix='DN-',
            payment_prefix='REC-',
            reset_sequence='yearly',
            show_logo=True,
            show_signature=True,
            show_bank_details=True,
            default_terms='Payment due within 30 days',
            default_notes='Thank you for your business!'
        )
        db.session.add(inv_settings)

    db.session.commit()
    print("Settings created")


def create_demo_organization():
    """Create a demo organization with admin user"""
    print("Creating demo organization...")

    # Check if demo org exists by name
    existing = Organization.query.filter_by(name='Demo Company Pvt Ltd').first()
    if existing:
        print("Demo organization already exists, seeding missing data...")
        # Still seed data in case it's missing
        seed_roles_for_organization(existing.id)
        seed_units_for_organization(existing.id)
        seed_tax_rates_for_organization(existing.id)
        seed_organization_settings(existing.id)
        return existing

    # Create organization (using actual model fields)
    org = Organization(
        name='Demo Company Pvt Ltd',
        legal_name='Demo Company Private Limited',
        organization_type='company',
        industry_type='retail',
        gstin='29AABCU9603R1ZM',
        pan='AABCU9603R',
        email='admin@demo.com',
        phone='+91 9876543210',
        website='https://demo.example.com',
        address_line1='123 Demo Street',
        city='Bangalore',
        state='Karnataka',
        state_code='29',
        country='India',
        pincode='560001',
        plan_type='premium',
        is_active=True
    )
    db.session.add(org)
    db.session.flush()
    
    # Create admin user
    admin = User(
        organization_id=org.id,
        email='admin@demo.com',
        password_hash=hash_password('Admin@123'),
        first_name='Admin',
        last_name='User',
        phone='+91 9876543210',
        is_active=True,
        is_email_verified=True,
        is_admin=True
    )
    db.session.add(admin)
    db.session.flush()
    
    # Seed data for organization
    seed_roles_for_organization(org.id)
    seed_units_for_organization(org.id)
    seed_tax_rates_for_organization(org.id)
    seed_organization_settings(org.id)
    
    # Assign super_admin role to admin user
    super_admin_role = Role.query.filter_by(
        organization_id=org.id,
        code='super_admin'
    ).first()

    if super_admin_role:
        # Use the association table directly instead of UserRole class
        db.session.execute(
            user_roles.insert().values(
                user_id=admin.id,
                role_id=super_admin_role.id
            )
        )
    
    db.session.commit()
    print(f"Demo organization created with ID: {org.id}")
    print("Admin credentials: admin@demo.com / Admin@123")
    
    return org


def run_all_seeds():
    """Run all seed functions"""
    print("=" * 50)
    print("Starting VyaparaCore Database Seeding")
    print("=" * 50)
    
    seed_permissions()
    org = create_demo_organization()
    
    print("=" * 50)
    print("Seeding completed successfully!")
    print("=" * 50)
    
    return org


if __name__ == '__main__':
    from app import create_app
    app = create_app()
    with app.app_context():
        run_all_seeds()