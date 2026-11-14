"""Edit history: who changed what, when, and what it was before and after.

Every successful change made through the API is written as one line of JSON to backend/edit_history.jsonl
(not committed to git). It's a file rather than a database table so the database design (ERD, data
dictionary) doesn't change. The app runs on one computer, so one file holds the whole history.
Back the file up along with the database.

How it works, without touching each route:
  - before_request: for a change we track, look up the record as it is now (the "before" snapshot)
  - after_request: if the change succeeded, look it up again (the "after"), compare, and write one entry
New sales and restocks aren't repeated here (they're already on the Orders page); logins aren't changes.
Passwords are never written: the history only says that a password was changed.
"""
import json
import os
import threading
from datetime import date, datetime
from decimal import Decimal

from flask import g, jsonify, request

HISTORY_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'edit_history.jsonl')
_write_lock = threading.Lock()

# Friendly names for database columns.
FIELD_LABELS = {
    'Name': 'Name', 'Email': 'Email', 'Phone': 'Phone', 'Category': 'Category', 'Location_Name': 'Name',
    'Category_ID': 'Category', 'Supplier_ID': 'Supplier', 'Availability': 'Availability',
    'Size_ID': 'Size', 'Color_ID': 'Color', 'Product_ID': 'Product', 'Location_ID': 'Location',
    'Price': 'Price', 'Cost': 'Cost', 'Color': 'Color', 'Size': 'Size', 'Transaction_Type': 'Name',
    'First_Name': 'First name', 'Last_Name': 'Last name', 'Role': 'Role', 'Username': 'Username',
    'Quantity': 'In stock', 'Quantity_Change': 'Quantity change', 'Transaction_Type_ID': 'Type',
    'Variant_ID': 'Item', 'Date': 'Date', 'low_stock_threshold': 'Low stock threshold',
}
# Never written to the history.
HIDDEN_FIELDS = {'Password_Hash', 'Employee_ID', 'Inventory_ID', 'Invoice_ID'}
# ID columns shown as the name they point to: column -> (table, id column, name column)
LOOKUPS = {
    'Category_ID': ('Category', 'Category_ID', 'Category'),
    'Supplier_ID': ('Supplier', 'Supplier_ID', 'Name'),
    'Size_ID': ('Size', 'Size_ID', 'Size'),
    'Color_ID': ('Color', 'Color_ID', 'Color'),
    'Location_ID': ('Location', 'Location_ID', 'Location_Name'),
    'Product_ID': ('Product', 'Product_ID', 'Name'),
    'Transaction_Type_ID': ('Transaction_Type', 'Transaction_Type_ID', 'Transaction_Type'),
}

# What each tracked API route changes:
#   area, kind (shown as "Supplier", "Order"…), table, key column, where the key comes from
#   ('path:<name>', 'body:<field>', 'response:<field>' for new records, or 'me' for the signed-in employee)
TRACKED = {
    ('POST', '/api/suppliers'): ('Catalog', 'Supplier', 'Supplier', 'Name', 'body:Name'),
    ('PUT', '/api/suppliers/<int:supplier_id>'): ('Catalog', 'Supplier', 'Supplier', 'Supplier_ID', 'path:supplier_id'),
    ('DELETE', '/api/suppliers/<int:supplier_id>'): ('Catalog', 'Supplier', 'Supplier', 'Supplier_ID', 'path:supplier_id'),
    ('POST', '/api/categories'): ('Catalog', 'Category', 'Category', 'Category', 'body:Category'),
    ('PUT', '/api/categories/<int:category_id>'): ('Catalog', 'Category', 'Category', 'Category_ID', 'path:category_id'),
    ('DELETE', '/api/categories/<int:category_id>'): ('Catalog', 'Category', 'Category', 'Category_ID', 'path:category_id'),
    ('POST', '/api/locations'): ('Catalog', 'Location', 'Location', 'Location_Name', 'body:Location_Name'),
    ('PUT', '/api/locations/<int:location_id>'): ('Catalog', 'Location', 'Location', 'Location_ID', 'path:location_id'),
    ('DELETE', '/api/locations/<int:location_id>'): ('Catalog', 'Location', 'Location', 'Location_ID', 'path:location_id'),
    ('POST', '/create/color'): ('Catalog', 'Color', 'Color', 'Color', 'body:Color'),
    ('PUT', '/update/color'): ('Catalog', 'Color', 'Color', 'Color_ID', 'body:Color_ID'),
    ('DELETE', '/delete/color'): ('Catalog', 'Color', 'Color', 'Color_ID', 'body:Color_ID'),
    ('POST', '/create/size'): ('Catalog', 'Size', 'Size', 'Size', 'body:Size'),
    ('PUT', '/update/size'): ('Catalog', 'Size', 'Size', 'Size_ID', 'body:Size_ID'),
    ('DELETE', '/delete/size'): ('Catalog', 'Size', 'Size', 'Size_ID', 'body:Size_ID'),
    ('POST', '/create/transaction/type'): ('Catalog', 'Transaction type', 'Transaction_Type', 'Transaction_Type', 'body:Transaction_Type'),
    ('PUT', '/update/transaction/type'): ('Catalog', 'Transaction type', 'Transaction_Type', 'Transaction_Type_ID', 'body:Transaction_Type_ID'),
    ('DELETE', '/delete/transaction/type'): ('Catalog', 'Transaction type', 'Transaction_Type', 'Transaction_Type_ID', 'body:Transaction_Type_ID'),
    ('POST', '/api/products'): ('Products', 'Product', 'Product', 'Product_ID', 'response:Product_ID'),
    ('PUT', '/api/products/<int:product_id>'): ('Products', 'Product', 'Product', 'Product_ID', 'path:product_id'),
    ('DELETE', '/api/products/<int:product_id>'): ('Products', 'Product', 'Product', 'Product_ID', 'path:product_id'),
    ('POST', '/api/product_variants'): ('Products', 'Variant', 'Product_Variant', 'Variant_ID', 'response:Variant_ID'),
    ('PUT', '/api/product_variants/<int:variant_id>'): ('Products', 'Variant', 'Product_Variant', 'Variant_ID', 'path:variant_id'),
    ('DELETE', '/api/product_variants/<int:variant_id>'): ('Products', 'Variant', 'Product_Variant', 'Variant_ID', 'path:variant_id'),
    ('PUT', '/update/invoice'): ('Orders', 'Order', 'Invoice', 'Invoice_ID', 'body:Invoice_ID'),
    ('DELETE', '/delete/invoice'): ('Orders', 'Order', 'Invoice', 'Invoice_ID', 'body:Invoice_ID'),
    ('PUT', '/adjust/inventory'): ('Stock', 'Stock', 'Inventory', 'Variant_ID', 'body:Variant_ID'),
    ('POST', '/add/employee'): ('Employees', 'Employee', 'Employee', 'Email', 'body:Email'),
    ('PUT', '/update/employee'): ('Employees', 'Employee', 'Employee', 'Email', 'body:Current_Email'),
    ('DELETE', '/delete/employee'): ('Employees', 'Employee', 'Employee', 'Email', 'body:Email'),
    ('POST', '/change/password'): ('Employees', 'Employee', 'Employee', 'Employee_ID', 'me'),
    ('PUT', '/settings/store'): ('Settings', 'Store settings', None, None, None),
}
ACTIONS = {'POST': 'Added', 'PUT': 'Edited', 'DELETE': 'Deleted'}
# Each table's own ID column (not shown as a change: it's the record itself).
OWN_ID = {'Supplier': 'Supplier_ID', 'Category': 'Category_ID', 'Location': 'Location_ID', 'Color': 'Color_ID',
          'Size': 'Size_ID', 'Transaction_Type': 'Transaction_Type_ID', 'Product': 'Product_ID',
          'Product_Variant': 'Variant_ID', 'Invoice': 'Invoice_ID', 'Inventory': 'Inventory_ID', 'Employee': 'Employee_ID'}
AREAS = ['Orders', 'Stock', 'Products', 'Catalog', 'Employees', 'Settings']


def _plain(value):
    """Make a database value readable and JSON-safe."""
    if value is None:
        return ''
    if isinstance(value, Decimal):
        return f'{value:.2f}'
    if isinstance(value, (date, datetime)):
        return value.isoformat()[:10]
    return str(value)


def register_history(app, connect, read_query, read_settings):
    def query(sql, params=()):
        con = connect()
        if con is None:
            return []
        try:
            return read_query(con, sql, params) or []
        finally:
            con.close()

    def lookup_name(column, value):
        if value in (None, ''):
            return ''
        if column == 'Variant_ID':
            return variant_label(value)
        if column in LOOKUPS:
            table, id_col, name_col = LOOKUPS[column]
            rows = query(f'SELECT {name_col} AS n FROM {table} WHERE {id_col}=%s', (value,))
            return _plain(rows[0]['n']) if rows else f'#{value} (deleted)'
        if column == 'Availability':
            return 'Available' if str(value) in ('1', 'True', 'true') else 'Not available'
        return _plain(value)

    def variant_label(variant_id):
        rows = query('SELECT p.Name, s.Size, c.Color FROM Product_Variant v JOIN Product p ON p.Product_ID=v.Product_ID '
                     'JOIN Size s ON s.Size_ID=v.Size_ID JOIN Color c ON c.Color_ID=v.Color_ID WHERE v.Variant_ID=%s', (variant_id,))
        return f"{rows[0]['Name']} – {rows[0]['Size']} / {rows[0]['Color']}" if rows else f'Item #{variant_id}'

    def snapshot(table, key_col, key):
        if not table or key in (None, ''):
            return None
        rows = query(f'SELECT * FROM {table} WHERE {key_col}=%s', (key,))
        return dict(rows[0]) if rows else None

    def describe(kind, row, key):
        """A readable name for the record, e.g. 'Satin Midi Dress – M / Black' or 'Order #25'."""
        row = row or {}
        if kind == 'Order':
            item = variant_label(row['Variant_ID']) if row.get('Variant_ID') else ''
            return f"Order #{key}" + (f" ({lookup_name('Transaction_Type_ID', row.get('Transaction_Type_ID'))}, {item})" if item else '')
        if kind in ('Variant', 'Stock'):
            return variant_label(row.get('Variant_ID') or key)
        if kind == 'Employee':
            name = f"{row.get('First_Name', '')} {row.get('Last_Name', '')}".strip()
            return name or str(key)
        for col in ('Name', 'Category', 'Location_Name', 'Color', 'Size', 'Transaction_Type'):
            if row.get(col):
                return _plain(row[col])
        return str(key)

    def readable(row, own_key):
        """{column: (raw value, readable value)}, looked up now, while the records it points to still exist."""
        out = {}
        for col, value in (row or {}).items():
            if col in HIDDEN_FIELDS or col == own_key:
                continue
            out[col] = (_plain(value), lookup_name(col, value))
        return out

    def changes_between(before, after):
        out = []
        for col in sorted(set(before or {}) | set(after or {})):
            old, new = (before or {}).get(col, ('', '')), (after or {}).get(col, ('', ''))
            if old[0] == new[0]:
                continue
            out.append({'field': FIELD_LABELS.get(col, col.replace('_', ' ')), 'from': old[1], 'to': new[1]})
        return out

    def write(entry):
        line = json.dumps(entry, ensure_ascii=False)
        with _write_lock:
            with open(HISTORY_PATH, 'a', encoding='utf-8') as f:
                f.write(line + '\n')
                f.flush()
                os.fsync(f.fileno())

    def key_from(source, body, response_json=None):
        if source == 'me':
            return g.employee['Employee_ID']
        where, _, name = (source or '').partition(':')
        if where == 'path':
            return (request.view_args or {}).get(name)
        if where == 'body':
            return body.get(name)
        if where == 'response':
            return (response_json or {}).get(name)
        return None

    @app.before_request
    def history_before():
        rule = request.url_rule.rule if request.url_rule else None
        tracked = TRACKED.get((request.method, rule))
        if not tracked or not getattr(g, 'employee', None):
            return None
        area, kind, table, key_col, source = tracked
        body = request.get_json(silent=True) or {}
        g.history_before, g.history_target = None, None
        try:
            if kind == 'Store settings':
                g.history_before = readable({'low_stock_threshold': read_settings()}, None)
            elif not (request.method == 'POST' and source.startswith('body:')):   # a new record has nothing before
                key = key_from(source, body)
                row = snapshot(table, key_col, key)
                g.history_before = readable(row, OWN_ID.get(table))
                g.history_target = describe(kind, row, key) if row else None
        except Exception:
            app.logger.exception('Edit history: could not read the record before the change')
        g.history_tracked = (area, kind, table, key_col, source, body)
        return None

    @app.after_request
    def history_after(response):
        tracked = getattr(g, 'history_tracked', None)
        if not tracked or response.status_code >= 300:
            return response
        area, kind, table, key_col, source, body = tracked
        try:
            before = getattr(g, 'history_before', None)
            response_json = response.get_json(silent=True) if response.is_json else None
            action = ACTIONS[request.method]
            if kind == 'Store settings':
                after = readable({'low_stock_threshold': read_settings()}, None)
                target = 'Store settings'
            elif request.method == 'DELETE':
                after = None
                target = getattr(g, 'history_target', None) or str(key_from(source, body))
            elif request.method == 'POST' and source.startswith('body:'):
                # new record without an ID in the response: look it up by the name it was saved with
                key = key_from(source, body)
                row = snapshot(table, key_col, key)
                after, target = readable(row, OWN_ID.get(table)), describe(kind, row, key)
            else:
                key = key_from(source, body, response_json)
                if kind == 'Employee' and request.method == 'PUT' and body.get('Email'):
                    key = body['Email']        # the email itself may have changed
                row = snapshot(table, key_col, key)
                after = readable(row, OWN_ID.get(table))
                target = describe(kind, row, key) if row else (getattr(g, 'history_target', None) or str(key))
            if kind == 'Stock':
                action = 'Adjusted'
            if request.path == '/change/password':
                action = 'Changed own password'   # target is already the employee's name
            changes = changes_between(before, after)
            if kind == 'Employee' and (body.get('Password') or request.path == '/change/password'):
                changes.append({'field': 'Password', 'from': '', 'to': '(changed)'})
            if request.method == 'PUT' and not changes:
                return response               # saved without changing anything: nothing to record
            employee = g.employee
            write({
                'time': datetime.now().isoformat(timespec='seconds'),
                'employee_id': str(employee['Employee_ID']),
                'employee': f"{employee['First_Name']} {employee['Last_Name']}",
                'area': area, 'kind': kind, 'action': action, 'target': target,
                'changes': changes,
            })
        except Exception:
            # The change itself already succeeded; a history problem must never undo or block it.
            app.logger.exception('Edit history: could not record the change')
        return response

    @app.get('/history')
    def edit_history():
        if str(g.employee.get('Role', '')).casefold() != 'manager':
            return jsonify({'message': 'Only managers can see the edit history.'}), 403
        area = str(request.args.get('area', '')).strip()
        person = str(request.args.get('employee', '')).strip()
        start = str(request.args.get('from', '')).strip()[:10]
        end = str(request.args.get('to', '')).strip()[:10]
        try:
            limit = min(max(int(request.args.get('limit', 100)), 1), 1000)
            offset = max(int(request.args.get('offset', 0)), 0)
        except (TypeError, ValueError):
            limit, offset = 100, 0
        entries, people = [], {}
        if os.path.exists(HISTORY_PATH):
            with open(HISTORY_PATH, encoding='utf-8') as f:
                for line in f:
                    try:
                        entry = json.loads(line)
                    except ValueError:
                        continue                 # skip a damaged line instead of failing the page
                    people[entry.get('employee_id')] = entry.get('employee')
                    day = str(entry.get('time', ''))[:10]
                    if area and entry.get('area') != area:
                        continue
                    if person and entry.get('employee_id') != person:
                        continue
                    if (start and day < start) or (end and day > end):
                        continue
                    entries.append(entry)
        entries.reverse()                        # newest first
        return jsonify({
            'entries': entries[offset:offset + limit], 'total': len(entries),
            'has_more': offset + limit < len(entries), 'limit': limit, 'offset': offset,
            'areas': AREAS, 'people': [{'id': k, 'name': v} for k, v in sorted(people.items(), key=lambda kv: str(kv[1]))],
        })
