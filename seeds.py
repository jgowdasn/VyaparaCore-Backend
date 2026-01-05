"""Comprehensive Seed data for VyaparaCore - All tables"""
from config.database import db
from app.models import (
    Permission, Role, Unit, TaxRate,
    Organization, User, OrganizationSettings, InvoiceSettings,
    user_roles, role_permissions, Branch, Warehouse, Category,
    Customer, CustomerAddress, CustomerContact,
    Supplier, SupplierAddress, SupplierContact,
    Product, ProductVariant, Stock,
    PaymentMode, BankAccount, SequenceNumber,
    Quotation, QuotationItem, SalesOrder, SalesOrderItem,
    Invoice, InvoiceItem, Payment, PaymentAllocation,
    PurchaseOrder, PurchaseOrderItem
)
from app.utils.security import hash_password
from datetime import datetime, date, timedelta
from decimal import Decimal
from sqlalchemy import insert
import random


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
    ('admin.audit', 'Admin audit access'),
]


# Default Roles with their permissions
DEFAULT_ROLES = {
    'super_admin': {
        'name': 'Super Admin',
        'description': 'Full system access',
        'is_system': True,
        'permissions': ['*']
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
            'reports.*', 'audit.view', 'admin.audit'
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
    ('NOS', 'Numbers', 'Quantity', 1),
    ('PCS', 'Pieces', 'Quantity', 1),
    ('SET', 'Sets', 'Quantity', 1),
    ('PAR', 'Pairs', 'Quantity', 1),
    ('DOZ', 'Dozens', 'Quantity', 12),
    ('BOX', 'Boxes', 'Quantity', 1),
    ('CTN', 'Cartons', 'Quantity', 1),
    ('PKT', 'Packets', 'Quantity', 1),
    ('KGS', 'Kilograms', 'Weight', 1),
    ('GMS', 'Grams', 'Weight', 0.001),
    ('LTR', 'Liters', 'Volume', 1),
    ('MLT', 'Milliliters', 'Volume', 0.001),
    ('MTR', 'Meters', 'Length', 1),
    ('SQM', 'Square Meters', 'Area', 1),
]


# Default Tax Rates (India GST)
DEFAULT_TAX_RATES = [
    {'name': 'GST 0%', 'rate': 0, 'cgst_rate': 0, 'sgst_rate': 0, 'igst_rate': 0, 'cess_rate': 0, 'description': 'Exempt/Nil rated', 'is_default': False},
    {'name': 'GST 5%', 'rate': 5, 'cgst_rate': 2.5, 'sgst_rate': 2.5, 'igst_rate': 5, 'cess_rate': 0, 'description': 'Essential items', 'is_default': False},
    {'name': 'GST 12%', 'rate': 12, 'cgst_rate': 6, 'sgst_rate': 6, 'igst_rate': 12, 'cess_rate': 0, 'description': 'Standard rate 1', 'is_default': False},
    {'name': 'GST 18%', 'rate': 18, 'cgst_rate': 9, 'sgst_rate': 9, 'igst_rate': 18, 'cess_rate': 0, 'description': 'Standard rate 2', 'is_default': True},
    {'name': 'GST 28%', 'rate': 28, 'cgst_rate': 14, 'sgst_rate': 14, 'igst_rate': 28, 'cess_rate': 0, 'description': 'Luxury items', 'is_default': False},
]


# Sample Customers
SAMPLE_CUSTOMERS = [
    {'name': 'Reliance Industries Ltd', 'code': 'CUST001', 'gstin': '27AAACR5055K1ZK', 'email': 'procurement@ril.com', 'phone': '+91 22 2278 5000', 'city': 'Mumbai', 'state': 'Maharashtra', 'state_code': '27', 'credit_limit': 500000, 'payment_terms': 30},
    {'name': 'Tata Steel Ltd', 'code': 'CUST002', 'gstin': '20AAACT2727Q1ZW', 'email': 'purchase@tatasteel.com', 'phone': '+91 657 242 5555', 'city': 'Jamshedpur', 'state': 'Jharkhand', 'state_code': '20', 'credit_limit': 750000, 'payment_terms': 45},
    {'name': 'Infosys Limited', 'code': 'CUST003', 'gstin': '29AAACI1681G1ZN', 'email': 'vendor@infosys.com', 'phone': '+91 80 2852 0261', 'city': 'Bangalore', 'state': 'Karnataka', 'state_code': '29', 'credit_limit': 300000, 'payment_terms': 30},
    {'name': 'Wipro Limited', 'code': 'CUST004', 'gstin': '29AABCW1234A1ZA', 'email': 'purchase@wipro.com', 'phone': '+91 80 2844 0011', 'city': 'Bangalore', 'state': 'Karnataka', 'state_code': '29', 'credit_limit': 250000, 'payment_terms': 30},
    {'name': 'HCL Technologies', 'code': 'CUST005', 'gstin': '09AAACH4849E1ZC', 'email': 'vendors@hcl.com', 'phone': '+91 120 438 8000', 'city': 'Noida', 'state': 'Uttar Pradesh', 'state_code': '09', 'credit_limit': 400000, 'payment_terms': 45},
    {'name': 'Mahindra & Mahindra', 'code': 'CUST006', 'gstin': '27AAACM0001K1ZJ', 'email': 'supply@mahindra.com', 'phone': '+91 22 2490 1441', 'city': 'Mumbai', 'state': 'Maharashtra', 'state_code': '27', 'credit_limit': 600000, 'payment_terms': 30},
    {'name': 'Larsen & Toubro', 'code': 'CUST007', 'gstin': '27AAACL0901A1Z5', 'email': 'procurement@lnt.com', 'phone': '+91 22 6752 5656', 'city': 'Mumbai', 'state': 'Maharashtra', 'state_code': '27', 'credit_limit': 1000000, 'payment_terms': 60},
    {'name': 'Bharti Airtel', 'code': 'CUST008', 'gstin': '07AAACB1833R1ZM', 'email': 'vendor.mgmt@airtel.com', 'phone': '+91 11 4666 6100', 'city': 'New Delhi', 'state': 'Delhi', 'state_code': '07', 'credit_limit': 350000, 'payment_terms': 30},
    {'name': 'HDFC Bank Ltd', 'code': 'CUST009', 'gstin': '27AAACH0779K1ZX', 'email': 'procurement@hdfcbank.com', 'phone': '+91 22 3395 8002', 'city': 'Mumbai', 'state': 'Maharashtra', 'state_code': '27', 'credit_limit': 200000, 'payment_terms': 15},
    {'name': 'ICICI Bank Ltd', 'code': 'CUST010', 'gstin': '27AAACI1195H1ZT', 'email': 'vendors@icicibank.com', 'phone': '+91 22 2653 1414', 'city': 'Mumbai', 'state': 'Maharashtra', 'state_code': '27', 'credit_limit': 200000, 'payment_terms': 15},
]


# Sample Suppliers
SAMPLE_SUPPLIERS = [
    {'name': 'ABC Electronics Pvt Ltd', 'code': 'SUP001', 'gstin': '29AABCE1234F1Z1', 'email': 'sales@abcelectronics.com', 'phone': '+91 80 4567 8900', 'city': 'Bangalore', 'state': 'Karnataka', 'state_code': '29', 'payment_terms': 30},
    {'name': 'Delhi Hardware Traders', 'code': 'SUP002', 'gstin': '07AABCD5678G1Z2', 'email': 'orders@delhihardware.com', 'phone': '+91 11 2345 6789', 'city': 'New Delhi', 'state': 'Delhi', 'state_code': '07', 'payment_terms': 15},
    {'name': 'Chennai Industrial Supplies', 'code': 'SUP003', 'gstin': '33AABCC9012H1Z3', 'email': 'supply@chennaiind.com', 'phone': '+91 44 2567 8901', 'city': 'Chennai', 'state': 'Tamil Nadu', 'state_code': '33', 'payment_terms': 30},
    {'name': 'Pune Plastics Ltd', 'code': 'SUP004', 'gstin': '27AABCP3456I1Z4', 'email': 'sales@puneplastics.com', 'phone': '+91 20 2789 0123', 'city': 'Pune', 'state': 'Maharashtra', 'state_code': '27', 'payment_terms': 45},
    {'name': 'Hyderabad Metals Corp', 'code': 'SUP005', 'gstin': '36AABCH7890J1Z5', 'email': 'orders@hydmetals.com', 'phone': '+91 40 2345 6780', 'city': 'Hyderabad', 'state': 'Telangana', 'state_code': '36', 'payment_terms': 30},
    {'name': 'Gujarat Chemicals Ltd', 'code': 'SUP006', 'gstin': '24AABCG1234K1Z6', 'email': 'sales@gujchem.com', 'phone': '+91 79 2567 8901', 'city': 'Ahmedabad', 'state': 'Gujarat', 'state_code': '24', 'payment_terms': 30},
    {'name': 'Kolkata Textiles', 'code': 'SUP007', 'gstin': '19AABCK5678L1Z7', 'email': 'orders@koltex.com', 'phone': '+91 33 2234 5678', 'city': 'Kolkata', 'state': 'West Bengal', 'state_code': '19', 'payment_terms': 45},
    {'name': 'Jaipur Gems & Jewels', 'code': 'SUP008', 'gstin': '08AABCJ9012M1Z8', 'email': 'sales@jaipurgems.com', 'phone': '+91 141 256 7890', 'city': 'Jaipur', 'state': 'Rajasthan', 'state_code': '08', 'payment_terms': 15},
]


# Sample Categories
SAMPLE_CATEGORIES = [
    {'name': 'Electronics', 'code': 'ELEC', 'description': 'Electronic items and gadgets'},
    {'name': 'Computers', 'code': 'COMP', 'description': 'Computers and accessories'},
    {'name': 'Furniture', 'code': 'FURN', 'description': 'Office and home furniture'},
    {'name': 'Stationery', 'code': 'STAT', 'description': 'Office stationery items'},
    {'name': 'Hardware', 'code': 'HARD', 'description': 'Hardware and tools'},
    {'name': 'Software', 'code': 'SOFT', 'description': 'Software licenses'},
    {'name': 'Services', 'code': 'SERV', 'description': 'Professional services'},
]


# Sample Products
SAMPLE_PRODUCTS = [
    {'name': 'Laptop Dell Inspiron 15', 'sku': 'PRD000001', 'hsn_code': '8471', 'category': 'COMP', 'purchase_price': 45000, 'selling_price': 55000, 'mrp': 60000, 'stock': 50},
    {'name': 'HP LaserJet Printer', 'sku': 'PRD000002', 'hsn_code': '8443', 'category': 'COMP', 'purchase_price': 12000, 'selling_price': 15000, 'mrp': 18000, 'stock': 30},
    {'name': 'Office Chair Ergonomic', 'sku': 'PRD000003', 'hsn_code': '9401', 'category': 'FURN', 'purchase_price': 5000, 'selling_price': 7500, 'mrp': 8500, 'stock': 100},
    {'name': 'Executive Desk 5x3', 'sku': 'PRD000004', 'hsn_code': '9403', 'category': 'FURN', 'purchase_price': 8000, 'selling_price': 12000, 'mrp': 15000, 'stock': 25},
    {'name': 'A4 Copier Paper (500 sheets)', 'sku': 'PRD000005', 'hsn_code': '4802', 'category': 'STAT', 'purchase_price': 200, 'selling_price': 280, 'mrp': 320, 'stock': 500},
    {'name': 'Ballpoint Pen (Box of 10)', 'sku': 'PRD000006', 'hsn_code': '9608', 'category': 'STAT', 'purchase_price': 80, 'selling_price': 120, 'mrp': 150, 'stock': 200},
    {'name': 'External Hard Drive 1TB', 'sku': 'PRD000007', 'hsn_code': '8471', 'category': 'ELEC', 'purchase_price': 3500, 'selling_price': 4500, 'mrp': 5000, 'stock': 75},
    {'name': 'USB Flash Drive 64GB', 'sku': 'PRD000008', 'hsn_code': '8523', 'category': 'ELEC', 'purchase_price': 400, 'selling_price': 600, 'mrp': 750, 'stock': 150},
    {'name': 'Wireless Mouse', 'sku': 'PRD000009', 'hsn_code': '8471', 'category': 'COMP', 'purchase_price': 500, 'selling_price': 800, 'mrp': 999, 'stock': 200},
    {'name': 'Mechanical Keyboard', 'sku': 'PRD000010', 'hsn_code': '8471', 'category': 'COMP', 'purchase_price': 2000, 'selling_price': 3000, 'mrp': 3500, 'stock': 80},
    {'name': 'Monitor 24 inch LED', 'sku': 'PRD000011', 'hsn_code': '8528', 'category': 'ELEC', 'purchase_price': 8000, 'selling_price': 11000, 'mrp': 13000, 'stock': 40},
    {'name': 'Webcam HD 1080p', 'sku': 'PRD000012', 'hsn_code': '8525', 'category': 'ELEC', 'purchase_price': 1500, 'selling_price': 2200, 'mrp': 2500, 'stock': 60},
    {'name': 'Ethernet Cable Cat6 (5m)', 'sku': 'PRD000013', 'hsn_code': '8544', 'category': 'HARD', 'purchase_price': 150, 'selling_price': 250, 'mrp': 300, 'stock': 300},
    {'name': 'Power Strip 6 Socket', 'sku': 'PRD000014', 'hsn_code': '8536', 'category': 'ELEC', 'purchase_price': 300, 'selling_price': 500, 'mrp': 600, 'stock': 120},
    {'name': 'UPS 600VA', 'sku': 'PRD000015', 'hsn_code': '8504', 'category': 'ELEC', 'purchase_price': 2500, 'selling_price': 3500, 'mrp': 4000, 'stock': 45},
    {'name': 'Filing Cabinet 4 Drawer', 'sku': 'PRD000016', 'hsn_code': '9403', 'category': 'FURN', 'purchase_price': 6000, 'selling_price': 8500, 'mrp': 10000, 'stock': 20},
    {'name': 'Whiteboard 4x3 feet', 'sku': 'PRD000017', 'hsn_code': '9610', 'category': 'STAT', 'purchase_price': 1200, 'selling_price': 1800, 'mrp': 2200, 'stock': 35},
    {'name': 'Stapler Heavy Duty', 'sku': 'PRD000018', 'hsn_code': '8305', 'category': 'STAT', 'purchase_price': 250, 'selling_price': 400, 'mrp': 500, 'stock': 100},
    {'name': 'Calculator Scientific', 'sku': 'PRD000019', 'hsn_code': '8470', 'category': 'STAT', 'purchase_price': 600, 'selling_price': 900, 'mrp': 1100, 'stock': 80},
    {'name': 'Projector Full HD', 'sku': 'PRD000020', 'hsn_code': '8528', 'category': 'ELEC', 'purchase_price': 35000, 'selling_price': 45000, 'mrp': 52000, 'stock': 15},
]


def seed_permissions():
    """Create default permissions"""
    print("Seeding permissions...")
    count = 0
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
            count += 1
    db.session.commit()
    print(f"Created {count} permissions")


def seed_roles_for_organization(org_id):
    """Create default roles for an organization"""
    print(f"Seeding roles for organization {org_id}...")
    all_permissions = {p.code: p for p in Permission.query.all()}

    for role_code, role_data in DEFAULT_ROLES.items():
        existing = Role.query.filter_by(organization_id=org_id, code=role_code).first()
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

            assigned_perm_ids = set()
            for perm_pattern in role_data['permissions']:
                if perm_pattern == '*':
                    for perm in all_permissions.values():
                        if perm.id not in assigned_perm_ids:
                            assigned_perm_ids.add(perm.id)
                            db.session.execute(role_permissions.insert().values(role_id=role.id, permission_id=perm.id))
                elif perm_pattern.endswith('.*'):
                    module = perm_pattern[:-2]
                    for code, perm in all_permissions.items():
                        if code.startswith(f"{module}.") and perm.id not in assigned_perm_ids:
                            assigned_perm_ids.add(perm.id)
                            db.session.execute(role_permissions.insert().values(role_id=role.id, permission_id=perm.id))
                else:
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
        existing = Unit.query.filter_by(organization_id=org_id, symbol=symbol).first()
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
        existing = TaxRate.query.filter_by(organization_id=org_id, name=tax_data['name']).first()
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


def seed_branches(org_id):
    """Create branches for organization"""
    print(f"Seeding branches for organization {org_id}...")

    branches_data = [
        {'name': 'Head Office', 'code': 'HO', 'branch_type': 'head_office', 'city': 'Bangalore', 'state': 'Karnataka', 'state_code': '29', 'is_head_office': True},
        {'name': 'Mumbai Branch', 'code': 'MUM', 'branch_type': 'branch', 'city': 'Mumbai', 'state': 'Maharashtra', 'state_code': '27', 'is_head_office': False},
        {'name': 'Delhi Branch', 'code': 'DEL', 'branch_type': 'branch', 'city': 'New Delhi', 'state': 'Delhi', 'state_code': '07', 'is_head_office': False},
    ]

    for b in branches_data:
        existing = Branch.query.filter_by(organization_id=org_id, code=b['code']).first()
        if not existing:
            branch = Branch(
                organization_id=org_id,
                name=b['name'],
                code=b['code'],
                branch_type=b['branch_type'],
                city=b['city'],
                state=b['state'],
                state_code=b['state_code'],
                country='India',
                is_head_office=b['is_head_office'],
                is_active=True
            )
            db.session.add(branch)
    db.session.commit()
    print("Created branches")


def seed_warehouses(org_id):
    """Create warehouses for organization"""
    print(f"Seeding warehouses for organization {org_id}...")

    branch = Branch.query.filter_by(organization_id=org_id, is_head_office=True).first()

    warehouses_data = [
        {'name': 'Main Warehouse', 'code': 'WH-MAIN', 'warehouse_type': 'main', 'city': 'Bangalore'},
        {'name': 'Secondary Warehouse', 'code': 'WH-SEC', 'warehouse_type': 'secondary', 'city': 'Bangalore'},
    ]

    for w in warehouses_data:
        existing = Warehouse.query.filter_by(organization_id=org_id, code=w['code']).first()
        if not existing:
            warehouse = Warehouse(
                organization_id=org_id,
                branch_id=branch.id if branch else None,
                name=w['name'],
                code=w['code'],
                warehouse_type=w['warehouse_type'],
                city=w['city'],
                state='Karnataka',
                country='India',
                is_active=True
            )
            db.session.add(warehouse)
    db.session.commit()
    print("Created warehouses")


def seed_categories(org_id):
    """Create product categories"""
    print(f"Seeding categories for organization {org_id}...")

    for cat in SAMPLE_CATEGORIES:
        existing = Category.query.filter_by(organization_id=org_id, code=cat['code']).first()
        if not existing:
            category = Category(
                organization_id=org_id,
                name=cat['name'],
                code=cat['code'],
                description=cat['description'],
                is_active=True
            )
            db.session.add(category)
    db.session.commit()
    print(f"Created {len(SAMPLE_CATEGORIES)} categories")


def seed_customers(org_id, user_id):
    """Create sample customers"""
    print(f"Seeding customers for organization {org_id}...")

    for cust in SAMPLE_CUSTOMERS:
        existing = Customer.query.filter_by(organization_id=org_id, code=cust['code']).first()
        if not existing:
            customer = Customer(
                organization_id=org_id,
                name=cust['name'],
                code=cust['code'],
                customer_type='business',
                gstin=cust['gstin'],
                email=cust['email'],
                phone=cust['phone'],
                billing_city=cust['city'],
                billing_state=cust['state'],
                billing_state_code=cust['state_code'],
                billing_country='India',
                credit_limit=cust['credit_limit'],
                payment_terms=cust['payment_terms'],
                is_active=True,
                created_by=user_id
            )
            db.session.add(customer)
    db.session.commit()
    print(f"Created {len(SAMPLE_CUSTOMERS)} customers")


def seed_suppliers(org_id, user_id):
    """Create sample suppliers"""
    print(f"Seeding suppliers for organization {org_id}...")

    for sup in SAMPLE_SUPPLIERS:
        existing = Supplier.query.filter_by(organization_id=org_id, supplier_code=sup['code']).first()
        if not existing:
            supplier = Supplier(
                organization_id=org_id,
                name=sup['name'],
                supplier_code=sup['code'],
                supplier_type='manufacturer',
                gstin=sup['gstin'],
                email=sup['email'],
                phone=sup['phone'],
                city=sup['city'],
                state=sup['state'],
                state_code=sup['state_code'],
                country='India',
                payment_terms=sup['payment_terms'],
                is_active=True,
                created_by=user_id
            )
            db.session.add(supplier)
    db.session.commit()
    print(f"Created {len(SAMPLE_SUPPLIERS)} suppliers")


def seed_products(org_id, user_id):
    """Create sample products with stock"""
    print(f"Seeding products for organization {org_id}...")

    # Get required references
    categories = {c.code: c for c in Category.query.filter_by(organization_id=org_id).all()}
    units = {u.symbol: u for u in Unit.query.filter_by(organization_id=org_id).all()}
    tax_rate = TaxRate.query.filter_by(organization_id=org_id, is_default=True).first()
    warehouse = Warehouse.query.filter_by(organization_id=org_id).first()

    default_unit = units.get('NOS') or units.get('PCS')

    for prod in SAMPLE_PRODUCTS:
        existing = Product.query.filter_by(organization_id=org_id, sku=prod['sku']).first()
        if not existing:
            category = categories.get(prod['category'])

            product = Product(
                organization_id=org_id,
                name=prod['name'],
                sku=prod['sku'],
                hsn_code=prod['hsn_code'],
                product_type='goods',
                category_id=category.id if category else None,
                unit_id=default_unit.id if default_unit else None,
                tax_rate_id=tax_rate.id if tax_rate else None,
                purchase_price=prod['purchase_price'],
                selling_price=prod['selling_price'],
                mrp=prod['mrp'],
                current_stock=prod['stock'],
                opening_stock=prod['stock'],
                reorder_level=10,
                track_inventory=True,
                is_active=True,
                is_sellable=True,
                is_purchasable=True,
                created_by=user_id
            )
            db.session.add(product)
            db.session.flush()

            # Create stock entry
            if warehouse:
                stock = Stock(
                    organization_id=org_id,
                    product_id=product.id,
                    warehouse_id=warehouse.id,
                    quantity=prod['stock'],
                    reserved_quantity=0
                )
                db.session.add(stock)

    db.session.commit()
    print(f"Created {len(SAMPLE_PRODUCTS)} products with stock")


def seed_payment_modes(org_id):
    """Create payment modes"""
    print(f"Seeding payment modes for organization {org_id}...")

    modes = [
        {'name': 'Cash', 'code': 'CASH', 'payment_type': 'cash'},
        {'name': 'Bank Transfer', 'code': 'BANK', 'payment_type': 'bank'},
        {'name': 'UPI', 'code': 'UPI', 'payment_type': 'upi'},
        {'name': 'Credit Card', 'code': 'CC', 'payment_type': 'card'},
        {'name': 'Debit Card', 'code': 'DC', 'payment_type': 'card'},
        {'name': 'Cheque', 'code': 'CHQ', 'payment_type': 'cheque'},
    ]

    for m in modes:
        existing = PaymentMode.query.filter_by(organization_id=org_id, code=m['code']).first()
        if not existing:
            mode = PaymentMode(
                organization_id=org_id,
                name=m['name'],
                code=m['code'],
                payment_type=m['payment_type'],
                is_active=True
            )
            db.session.add(mode)
    db.session.commit()
    print("Created payment modes")


def seed_bank_accounts(org_id):
    """Create bank accounts"""
    print(f"Seeding bank accounts for organization {org_id}...")

    accounts = [
        {'account_name': 'Demo Company - HDFC', 'bank_name': 'HDFC Bank', 'account_number': '50100123456789', 'ifsc_code': 'HDFC0001234', 'branch_name': 'Koramangala Branch', 'account_type': 'current'},
        {'account_name': 'Demo Company - ICICI', 'bank_name': 'ICICI Bank', 'account_number': '123456789012', 'ifsc_code': 'ICIC0001234', 'branch_name': 'MG Road Branch', 'account_type': 'current'},
    ]

    for a in accounts:
        existing = BankAccount.query.filter_by(organization_id=org_id, account_number=a['account_number']).first()
        if not existing:
            account = BankAccount(
                organization_id=org_id,
                account_name=a['account_name'],
                bank_name=a['bank_name'],
                account_number=a['account_number'],
                ifsc_code=a['ifsc_code'],
                branch_name=a['branch_name'],
                account_type=a['account_type'],
                is_active=True
            )
            db.session.add(account)
    db.session.commit()
    print("Created bank accounts")


def seed_sequence_numbers(org_id):
    """Create sequence numbers for documents"""
    print(f"Seeding sequence numbers for organization {org_id}...")

    sequences = [
        {'document_type': 'invoice', 'prefix': 'INV-', 'current_number': 0},
        {'document_type': 'quotation', 'prefix': 'QTN-', 'current_number': 0},
        {'document_type': 'sales_order', 'prefix': 'SO-', 'current_number': 0},
        {'document_type': 'purchase_order', 'prefix': 'PO-', 'current_number': 0},
        {'document_type': 'payment', 'prefix': 'PAY-', 'current_number': 0},
        {'document_type': 'credit_note', 'prefix': 'CN-', 'current_number': 0},
        {'document_type': 'debit_note', 'prefix': 'DN-', 'current_number': 0},
    ]

    for s in sequences:
        existing = SequenceNumber.query.filter_by(organization_id=org_id, document_type=s['document_type']).first()
        if not existing:
            seq = SequenceNumber(
                organization_id=org_id,
                document_type=s['document_type'],
                prefix=s['prefix'],
                current_number=s['current_number'],
                number_length=5
            )
            db.session.add(seq)
    db.session.commit()
    print("Created sequence numbers")


def seed_sample_invoices(org_id, user_id):
    """Create sample invoices"""
    print(f"Seeding sample invoices for organization {org_id}...")

    customers = Customer.query.filter_by(organization_id=org_id).limit(5).all()
    products = Product.query.filter_by(organization_id=org_id).limit(10).all()
    branch = Branch.query.filter_by(organization_id=org_id, is_head_office=True).first()

    if not customers or not products:
        print("No customers or products found, skipping invoices")
        return

    # Create 10 sample invoices
    for i in range(10):
        customer = random.choice(customers)
        invoice_date = date.today() - timedelta(days=random.randint(1, 30))

        # Get or create sequence
        seq = SequenceNumber.query.filter_by(organization_id=org_id, document_type='invoice').first()
        if seq:
            seq.current_number += 1
            invoice_number = f"{seq.prefix}{seq.current_number:05d}"
        else:
            invoice_number = f"INV-{i+1:05d}"

        invoice = Invoice(
            organization_id=org_id,
            branch_id=branch.id if branch else None,
            invoice_number=invoice_number,
            invoice_type='tax_invoice',
            customer_id=customer.id,
            customer_name=customer.name,
            customer_gstin=customer.gstin,
            billing_city=customer.billing_city,
            billing_state=customer.billing_state,
            billing_state_code=customer.billing_state_code,
            invoice_date=invoice_date,
            due_date=invoice_date + timedelta(days=customer.payment_terms or 30),
            place_of_supply=customer.billing_state_code,
            currency='INR',
            status='sent',
            payment_status='unpaid',
            created_by=user_id
        )
        db.session.add(invoice)
        db.session.flush()

        # Add 1-4 items per invoice
        subtotal = Decimal('0')
        total_tax = Decimal('0')

        selected_products = random.sample(products, min(random.randint(1, 4), len(products)))

        for product in selected_products:
            qty = random.randint(1, 10)
            unit_price = Decimal(str(product.selling_price))
            taxable = qty * unit_price

            # Calculate tax (assuming intra-state)
            tax_rate = product.tax_rate
            cgst = sgst = Decimal('0')
            if tax_rate:
                cgst = taxable * Decimal(str(tax_rate.cgst_rate)) / 100
                sgst = taxable * Decimal(str(tax_rate.sgst_rate)) / 100

            item_total = taxable + cgst + sgst

            item = InvoiceItem(
                invoice_id=invoice.id,
                product_id=product.id,
                name=product.name,
                hsn_code=product.hsn_code,
                quantity=qty,
                rate=float(unit_price),
                taxable_amount=float(taxable),
                cgst_rate=tax_rate.cgst_rate if tax_rate else 0,
                cgst_amount=float(cgst),
                sgst_rate=tax_rate.sgst_rate if tax_rate else 0,
                sgst_amount=float(sgst),
                total_tax=float(cgst + sgst)
            )
            db.session.add(item)

            subtotal += taxable
            total_tax += cgst + sgst

        grand_total = subtotal + total_tax

        invoice.subtotal = float(subtotal)
        invoice.tax_amount = float(total_tax)
        invoice.cgst_amount = float(total_tax / 2)
        invoice.sgst_amount = float(total_tax / 2)
        invoice.total_amount = float(grand_total)
        invoice.grand_total = float(grand_total)
        invoice.balance_due = float(grand_total)

        # Update customer outstanding
        customer.outstanding_amount = float(Decimal(str(customer.outstanding_amount or 0)) + grand_total)

    db.session.commit()
    print("Created 10 sample invoices")


def create_demo_organization():
    """Create a demo organization with admin user"""
    print("Creating demo organization...")

    existing = Organization.query.filter_by(name='Demo Company Pvt Ltd').first()
    if existing:
        print("Demo organization already exists, seeding missing data...")
        return existing

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

    # Create additional users
    users_data = [
        {'email': 'manager@demo.com', 'first_name': 'Manager', 'last_name': 'User', 'role': 'manager'},
        {'email': 'sales@demo.com', 'first_name': 'Sales', 'last_name': 'Executive', 'role': 'sales'},
        {'email': 'accountant@demo.com', 'first_name': 'Account', 'last_name': 'Manager', 'role': 'accountant'},
    ]

    for u in users_data:
        user = User(
            organization_id=org.id,
            email=u['email'],
            password_hash=hash_password('Demo@123'),
            first_name=u['first_name'],
            last_name=u['last_name'],
            is_active=True,
            is_email_verified=True,
            is_admin=False
        )
        db.session.add(user)

    db.session.commit()
    print(f"Demo organization created with ID: {org.id}")

    return org, admin


def run_all_seeds():
    """Run all seed functions"""
    print("=" * 60)
    print("Starting VyaparaCore Comprehensive Database Seeding")
    print("=" * 60)

    # Base data
    seed_permissions()

    # Create organization
    result = create_demo_organization()
    if isinstance(result, tuple):
        org, admin = result
    else:
        org = result
        admin = User.query.filter_by(organization_id=org.id, is_admin=True).first()

    # Organization-specific seeds
    seed_roles_for_organization(org.id)
    seed_units_for_organization(org.id)
    seed_tax_rates_for_organization(org.id)
    seed_organization_settings(org.id)
    seed_branches(org.id)
    seed_warehouses(org.id)
    seed_categories(org.id)
    seed_payment_modes(org.id)
    seed_bank_accounts(org.id)
    seed_sequence_numbers(org.id)

    # Assign super_admin role to admin
    super_admin_role = Role.query.filter_by(organization_id=org.id, code='super_admin').first()
    if super_admin_role and admin:
        existing = db.session.execute(
            user_roles.select().where(
                (user_roles.c.user_id == admin.id) &
                (user_roles.c.role_id == super_admin_role.id)
            )
        ).first()
        if not existing:
            db.session.execute(user_roles.insert().values(user_id=admin.id, role_id=super_admin_role.id))
            db.session.commit()

    # Business data
    if admin:
        seed_customers(org.id, admin.id)
        seed_suppliers(org.id, admin.id)
        seed_products(org.id, admin.id)
        seed_sample_invoices(org.id, admin.id)

    print("=" * 60)
    print("Seeding completed successfully!")
    print("=" * 60)
    print("\nLogin credentials:")
    print("  Admin: admin@demo.com / Admin@123")
    print("  Manager: manager@demo.com / Demo@123")
    print("  Sales: sales@demo.com / Demo@123")
    print("  Accountant: accountant@demo.com / Demo@123")
    print("=" * 60)

    return org


if __name__ == '__main__':
    from app import create_app
    app = create_app()
    with app.app_context():
        run_all_seeds()
