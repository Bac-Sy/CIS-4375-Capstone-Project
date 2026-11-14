"""Read-only reporting endpoints using the actual Capstone_Project SQL schema.

All queries use bound parameters; tables/columns are from database/create_capstone_tables.sql.
Endpoints share Flask's token gate installed by security.install_auth.
"""
import json
import os
from datetime import date, timedelta
from flask import jsonify, request, g


def register_reporting_routes(app, connect, read_query):
    def fetch(sql, params=()):
        con = connect()
        if con is None:
            raise ConnectionError('Cannot connect to MySQL')
        try:
            result = read_query(con, sql, params)
            if result is None:
                raise RuntimeError('SQL read failed; inspect the Flask terminal')
            return result
        finally:
            con.close()

    @app.errorhandler(ConnectionError)
    @app.errorhandler(RuntimeError)
    def report_unavailable(exc):
        app.logger.error('Reporting endpoint failed: %s', exc)
        return jsonify({'message': 'Database reporting is unavailable. See Flask logs.'}), 503

    # Store settings live in backend/settings.json (created the first time a manager saves one on the
    # Settings page, and not committed). Until then the threshold comes from LOW_STOCK_THRESHOLD in .env.
    settings_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'settings.json')

    def read_settings():
        try:
            with open(settings_path, encoding='utf-8') as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def threshold():
        saved = read_settings().get('low_stock_threshold')
        try:
            value = saved if saved is not None else os.getenv('LOW_STOCK_THRESHOLD', '5')
            return max(0, min(1000000, int(value)))
        except (ValueError, TypeError):
            return 5

    @app.get('/settings/store')
    def store_settings():
        return jsonify({'low_stock_threshold': threshold()})

    @app.put('/settings/store')
    def save_store_settings():
        if str(g.employee.get('Role', '')).casefold() != 'manager':
            return jsonify({'message': 'Only managers can change store settings.'}), 403
        data = request.get_json(silent=True) or {}
        try:
            value = int(data.get('low_stock_threshold'))
        except (ValueError, TypeError):
            return jsonify({'message': 'The low stock threshold must be a whole number.'}), 400
        if value < 0 or value > 1000:
            return jsonify({'message': 'The low stock threshold must be between 0 and 1000.'}), 400
        settings = read_settings()
        settings['low_stock_threshold'] = value
        temp_path = settings_path + '.tmp'
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=2)
        os.replace(temp_path, settings_path)
        return jsonify({'message': f'Low stock threshold set to {value}.', 'low_stock_threshold': value})

    @app.get('/inventory')
    def inventory_summary():
        rows = fetch('''
            SELECT v.Variant_ID AS variant_id, p.Product_ID AS product_id,
                   p.Name AS product, c.Category AS category, s.Size AS size,
                   co.Color AS color, l.Location_Name AS location,
                   i.Quantity AS quantity, v.Price AS price, sup.Name AS supplier,
                   p.Availability AS available
            FROM Inventory i
            JOIN Product_Variant v ON v.Variant_ID = i.Variant_ID
            JOIN Product p ON p.Product_ID = v.Product_ID
            JOIN Category c ON c.Category_ID = p.Category_ID
            JOIN Size s ON s.Size_ID = v.Size_ID
            JOIN Color co ON co.Color_ID = v.Color_ID
            LEFT JOIN Location l ON l.Location_ID = CAST(v.Location_ID AS UNSIGNED)
            LEFT JOIN Supplier sup ON sup.Supplier_ID = p.Supplier_ID
            ORDER BY p.Name, s.Size, co.Color, v.Variant_ID
        ''')
        return jsonify({'items': rows, 'low_stock_threshold': threshold()})

    ORDER_SELECT = '''
        SELECT i.Invoice_ID AS invoice_id, i.Date AS date,
               t.Transaction_Type AS transaction_type,
               p.Name AS product, s.Size AS size, co.Color AS color,
               i.Quantity_Change AS quantity_change,
               CONCAT(e.First_Name, ' ', e.Last_Name) AS employee,
               v.Price AS price, p.Product_ID AS product_id, v.Variant_ID AS variant_id,
               sup.Name AS supplier
        FROM Invoice i
        JOIN Transaction_Type t ON t.Transaction_Type_ID = i.Transaction_Type_ID
        JOIN Product_Variant v ON v.Variant_ID = i.Variant_ID
        JOIN Product p ON p.Product_ID = v.Product_ID
        JOIN Size s ON s.Size_ID = v.Size_ID
        JOIN Color co ON co.Color_ID = v.Color_ID
        JOIN Employee e ON e.Employee_ID = i.Employee_ID
        LEFT JOIN Supplier sup ON sup.Supplier_ID = p.Supplier_ID
    '''

    @app.get('/orders/<int:invoice_id>')
    def order_detail(invoice_id):
        rows = fetch(ORDER_SELECT + ' WHERE i.Invoice_ID = %s', (invoice_id,))
        if not rows:
            return jsonify({'message': 'Order not found.'}), 404
        row = rows[0]
        if row.get('date') is not None:
            row['date'] = str(row['date'])[:10]
        return jsonify(row)

    @app.get('/orders')
    def orders_summary():
        type_filter = str(request.args.get('type', '')).strip()[:50]
        try:
            limit = min(max(int(request.args.get('limit', 100)), 1), 200)
        except (TypeError, ValueError):
            limit = 100
        # offset lets the Orders page show older orders a page at a time
        try:
            offset = max(int(request.args.get('offset', 0)), 0)
        except (TypeError, ValueError):
            offset = 0
        types = [row['Transaction_Type'] for row in fetch(
            'SELECT Transaction_Type FROM Transaction_Type ORDER BY Transaction_Type')]
        if type_filter and type_filter not in types:
            return jsonify({'rows': [], 'types': types, 'limit': limit, 'offset': offset, 'has_more': False})
        conditions, params = [], []
        if type_filter:
            conditions.append('t.Transaction_Type = %s')
            params.append(type_filter)
        # ?q= search (Orders page only): every word must match the order #, product, size, color,
        # type or employee. Values are passed as parameters; % and _ are escaped so they're literal.
        search = ' '.join(str(request.args.get('q', '')).split())[:100]
        for word in search.split(' ') if search else []:
            like = '%' + word.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%'
            parts = ['p.Name LIKE %s', 's.Size LIKE %s', 'co.Color LIKE %s', 't.Transaction_Type LIKE %s',
                     "CONCAT(e.First_Name, ' ', e.Last_Name) LIKE %s"]
            word_params = [like] * len(parts)
            number = word.lstrip('#')
            if number.isdigit() and len(number) <= 9:
                parts.append('i.Invoice_ID = %s')     # "42" or "#42" finds order #42
                word_params.append(int(number))
            conditions.append('(' + ' OR '.join(parts) + ')')
            params.extend(word_params)
        # ?from= / ?to= (YYYY-MM-DD), both days included
        for key, sql in (('from', 'i.Date >= %s'), ('to', 'i.Date < DATE_ADD(%s, INTERVAL 1 DAY)')):
            value = str(request.args.get(key, '')).strip()
            if value:
                try:
                    date.fromisoformat(value)
                except ValueError:
                    return jsonify({'message': f'"{key}" must be a date like 2026-11-01.'}), 400
                conditions.append(sql)
                params.append(value)
        where = (' WHERE ' + ' AND '.join(conditions)) if conditions else ''
        params.extend([limit + 1, offset])
        rows = fetch(ORDER_SELECT + where + ' ORDER BY i.Date DESC, i.Invoice_ID DESC LIMIT %s OFFSET %s', tuple(params))
        has_more = len(rows) > limit
        rows = rows[:limit]
        for row in rows:
            if row.get('date') is not None:
                row['date'] = str(row['date'])[:10]
        return jsonify({'rows': rows, 'types': types, 'limit': limit, 'offset': offset, 'has_more': has_more})

    # ---------- REPORTS (R-10): inventory report and sales report ----------
    # Read-only. Sales are valued at each item's current price and cost (the database doesn't
    # keep the price at the time of the sale), the same as the Dashboard and Best sellers.

    @app.get('/report/inventory')
    def inventory_report():
        rows = fetch('''
            SELECT p.Product_ID AS product_id, p.Name AS product, c.Category AS category,
                   sup.Name AS supplier, p.Availability AS available,
                   v.Variant_ID AS variant_id, s.Size AS size, co.Color AS color,
                   l.Location_Name AS location, i.Quantity AS quantity,
                   v.Cost AS cost, v.Price AS price
            FROM Inventory i
            JOIN Product_Variant v ON v.Variant_ID = i.Variant_ID
            JOIN Product p ON p.Product_ID = v.Product_ID
            JOIN Category c ON c.Category_ID = p.Category_ID
            JOIN Size s ON s.Size_ID = v.Size_ID
            JOIN Color co ON co.Color_ID = v.Color_ID
            LEFT JOIN Location l ON l.Location_ID = CAST(v.Location_ID AS UNSIGNED)
            LEFT JOIN Supplier sup ON sup.Supplier_ID = p.Supplier_ID
            ORDER BY p.Name, s.Size, co.Color, v.Variant_ID
        ''')
        limit = threshold()
        totals = {'items': 0, 'units': 0, 'value_cost': 0.0, 'value_retail': 0.0, 'low': 0, 'out': 0}
        products = set()
        for row in rows:
            quantity = int(row['quantity'] or 0)
            cost = float(row['cost'] or 0)
            price = float(row['price'] or 0)
            row.update(quantity=quantity, cost=cost, price=price,
                       available=bool(int(row['available'] if row['available'] is not None else 1)),
                       value_cost=round(quantity * cost, 2), value_retail=round(quantity * price, 2),
                       status='Out' if quantity == 0 else ('Low' if quantity <= limit else ''))
            totals['items'] += 1
            totals['units'] += quantity
            totals['value_cost'] += row['value_cost']
            totals['value_retail'] += row['value_retail']
            totals['low'] += 1 if row['status'] == 'Low' else 0
            totals['out'] += 1 if row['status'] == 'Out' else 0
            products.add(row['product_id'])
        totals['products'] = len(products)
        totals['value_cost'] = round(totals['value_cost'], 2)
        totals['value_retail'] = round(totals['value_retail'], 2)
        return jsonify({'rows': rows, 'totals': totals, 'low_stock_threshold': limit,
                        'generated': date.today().isoformat()})

    @app.get('/report/sales')
    def sales_report():
        try:
            start = date.fromisoformat(str(request.args.get('from', '')))
            end = date.fromisoformat(str(request.args.get('to', '')))
        except ValueError:
            return jsonify({'message': 'from and to must be dates (YYYY-MM-DD).'}), 400
        if start > end:
            return jsonify({'message': 'The start date must be on or before the end date.'}), 400
        if (end - start).days > 3660:
            return jsonify({'message': 'Choose a range of 10 years or less.'}), 400
        # optional: only one product's sales (the Best sellers report links here)
        try:
            product_id = int(request.args['product_id']) if request.args.get('product_id') else None
        except ValueError:
            return jsonify({'message': 'product_id must be a whole number.'}), 400
        sales = fetch('''
            SELECT i.Invoice_ID AS invoice_id, i.Date AS date,
                   p.Product_ID AS product_id, p.Name AS product, c.Category AS category,
                   s.Size AS size, co.Color AS color,
                   -i.Quantity_Change AS units, v.Price AS price, v.Cost AS cost,
                   CONCAT(e.First_Name, ' ', e.Last_Name) AS employee
            FROM Invoice i
            JOIN Transaction_Type t ON t.Transaction_Type_ID = i.Transaction_Type_ID
            JOIN Product_Variant v ON v.Variant_ID = i.Variant_ID
            JOIN Product p ON p.Product_ID = v.Product_ID
            JOIN Category c ON c.Category_ID = p.Category_ID
            JOIN Size s ON s.Size_ID = v.Size_ID
            JOIN Color co ON co.Color_ID = v.Color_ID
            JOIN Employee e ON e.Employee_ID = i.Employee_ID
            WHERE t.Transaction_Type = 'Sale' AND i.Quantity_Change < 0
              AND i.Date >= %s AND i.Date <= %s
              AND (%s IS NULL OR p.Product_ID = %s)
            ORDER BY i.Date DESC, i.Invoice_ID DESC
        ''', (start, end, product_id, product_id))
        by_product, by_category, by_day = {}, {}, {}
        summary = {'revenue': 0.0, 'units': 0, 'sales': len(sales), 'cost': 0.0}
        for row in sales:
            units = int(row['units'] or 0)
            price = float(row['price'] or 0)
            cost = float(row['cost'] or 0)
            day = str(row['date'])[:10]
            revenue, cost_total = round(units * price, 2), round(units * cost, 2)
            row.update(date=day, units=units, price=price, cost=cost, revenue=revenue,
                       cost_total=cost_total, profit=round(revenue - cost_total, 2))
            summary['revenue'] += revenue
            summary['units'] += units
            summary['cost'] += cost_total
            for table, key, base in ((by_product, row['product_id'], {'product': row['product'], 'category': row['category']}),
                                     (by_category, row['category'], {'category': row['category']}),
                                     (by_day, day, {'date': day})):
                entry = table.setdefault(key, dict(base, sales=0, units=0, revenue=0.0, cost=0.0))
                entry['sales'] += 1
                entry['units'] += units
                entry['revenue'] += revenue
                entry['cost'] += cost_total
        def finish(entries):
            out = []
            for entry in entries:
                entry['revenue'] = round(entry['revenue'], 2)
                entry['cost'] = round(entry['cost'], 2)
                entry['profit'] = round(entry['revenue'] - entry['cost'], 2)
                out.append(entry)
            return out
        summary['revenue'] = round(summary['revenue'], 2)
        summary['cost'] = round(summary['cost'], 2)
        summary['profit'] = round(summary['revenue'] - summary['cost'], 2)
        summary['average_sale'] = round(summary['revenue'] / summary['sales'], 2) if summary['sales'] else 0
        summary['margin'] = round(summary['profit'] / summary['revenue'] * 100, 1) if summary['revenue'] else 0
        return jsonify({
            'from': start.isoformat(), 'to': end.isoformat(), 'summary': summary,
            'by_product': finish(sorted(by_product.values(), key=lambda e: (-e['revenue'], e['product']))),
            'by_category': finish(sorted(by_category.values(), key=lambda e: (-e['revenue'], e['category']))),
            'by_day': finish(sorted(by_day.values(), key=lambda e: e['date'])),
            'sales': sales, 'generated': date.today().isoformat()
        })

    @app.get('/employees')
    def employees_summary():
        rows = fetch('''
            SELECT Employee_ID AS id, First_Name AS first_name,
                   Last_Name AS last_name, Role AS role,
                   Username AS username, Email AS email
            FROM Employee ORDER BY Last_Name, First_Name, Employee_ID
        ''')
        return jsonify({'employees': rows})

    @app.get('/auth/me')
    def current_account():
        employee = g.employee
        data = {
            'id': str(employee['Employee_ID']),
            'firstName': employee['First_Name'],
            'lastName': employee['Last_Name'],
            'name': f"{employee['First_Name']} {employee['Last_Name']}",
            'username': employee['Username'],
            'email': employee['Email'],
            'role': employee['Role']
        }
        return jsonify({'user': data})

    @app.get('/dashboard')
    def dashboard():
        days = 30
        try:
            days = min(90, max(2, int(request.args.get('days', 30))))
        except (ValueError, TypeError):
            pass
        first_day = date.today() - timedelta(days=days - 1)
        sale_agg = fetch('''
            SELECT COALESCE(-SUM(i.Quantity_Change * v.Price), 0) AS revenue,
                   COALESCE(-SUM(i.Quantity_Change), 0) AS units
            FROM Invoice i
            JOIN Transaction_Type t ON t.Transaction_Type_ID = i.Transaction_Type_ID
            JOIN Product_Variant v ON v.Variant_ID = i.Variant_ID
            WHERE t.Transaction_Type='Sale' AND i.Quantity_Change < 0
              AND i.Date >= %s AND i.Date <= %s
        ''', (first_day, date.today()))
        by_category = fetch('''
            SELECT c.Category AS name,
                   -SUM(i.Quantity_Change * v.Price) AS revenue
            FROM Invoice i
            JOIN Transaction_Type t ON t.Transaction_Type_ID = i.Transaction_Type_ID
            JOIN Product_Variant v ON v.Variant_ID = i.Variant_ID
            JOIN Product p ON p.Product_ID = v.Product_ID
            JOIN Category c ON c.Category_ID = p.Category_ID
            WHERE t.Transaction_Type='Sale' AND i.Quantity_Change < 0
              AND i.Date >= %s AND i.Date <= %s
            GROUP BY c.Category ORDER BY revenue DESC
        ''', (first_day, date.today()))
        # The newest 5 of each type, so Adjustments (stock corrections) don't push real sales off the card.
        recent_by_type = {}
        for kind in ('Sale', 'Restock', 'Adjustment'):
            rows = fetch(ORDER_SELECT + ' WHERE t.Transaction_Type=%s ORDER BY i.Date DESC, i.Invoice_ID DESC LIMIT 5', (kind,))
            for row in rows:
                if row.get('date') is not None:
                    row['date'] = str(row['date'])[:10]
            recent_by_type[kind] = rows
        low = fetch('''
            SELECT p.Name AS product, s.Size AS size, co.Color AS color,
                   i.Quantity AS quantity
            FROM Inventory i
            JOIN Product_Variant v ON v.Variant_ID = i.Variant_ID
            JOIN Product p ON p.Product_ID = v.Product_ID
            JOIN Size s ON s.Size_ID = v.Size_ID
            JOIN Color co ON co.Color_ID = v.Color_ID
            WHERE i.Quantity <= %s
            ORDER BY i.Quantity, p.Name, v.Variant_ID LIMIT 5
        ''', (threshold(),))
        # Current inventory: total units in stock, how many items (variants) and products they make up.
        on_hand = fetch('''
            SELECT COALESCE(SUM(i.Quantity), 0) AS units, COUNT(*) AS items,
                   COUNT(DISTINCT v.Product_ID) AS products
            FROM Inventory i
            JOIN Product_Variant v ON v.Variant_ID = i.Variant_ID
        ''')
        on_hand = on_hand[0] if on_hand else {}
        # Stock in vs. out: units sold and units restocked in each of the last 4 weeks (7-day blocks
        # ending today). Adjustments are left out: they correct a count, they aren't stock coming in or going out.
        weeks_start = date.today() - timedelta(days=27)
        moves = fetch('''
            SELECT i.Date AS date, t.Transaction_Type AS kind, SUM(i.Quantity_Change) AS qty
            FROM Invoice i
            JOIN Transaction_Type t ON t.Transaction_Type_ID = i.Transaction_Type_ID
            WHERE t.Transaction_Type IN ('Sale', 'Restock') AND i.Date >= %s AND i.Date <= %s
            GROUP BY i.Date, t.Transaction_Type
        ''', (weeks_start, date.today()))
        weeks = [{'start': (weeks_start + timedelta(days=7 * n)).isoformat(), 'sold': 0, 'restocked': 0} for n in range(4)]
        for row in moves:
            day = row['date'] if isinstance(row['date'], date) else date.fromisoformat(str(row['date'])[:10])
            week = weeks[min(3, (day - weeks_start).days // 7)]
            if row['kind'] == 'Sale':
                week['sold'] += -int(row['qty'] or 0)
            else:
                week['restocked'] += int(row['qty'] or 0)
        sales = sale_agg[0] if sale_agg else {}
        return jsonify({
            'sales': {'revenue': sales.get('revenue') or 0,
                      'units': sales.get('units') or 0,
                      'days': days, 'by_category': by_category},
            'recent_orders': recent_by_type['Sale'],
            'recent_by_type': recent_by_type,
            'low_stock': low,
            'inventory_totals': {'units': int(on_hand.get('units') or 0),
                                 'items': int(on_hand.get('items') or 0),
                                 'products': int(on_hand.get('products') or 0)},
            'low_stock_threshold': threshold(),
            'stock_weeks': weeks
        })

    # the Edit history uses this to record threshold changes
    return threshold
