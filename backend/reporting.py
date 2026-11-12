"""Read-only reporting endpoints using the actual Capstone_Project SQL schema.

All queries use bound parameters; tables/columns are from database/create_capstone_tables.sql.
Endpoints share Flask's token gate installed by security.install_auth.
"""
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

    def threshold():
        try:
            return max(0, min(1000000, int(os.getenv('LOW_STOCK_THRESHOLD', '5'))))
        except (ValueError, TypeError):
            return 5

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
               v.Price AS price, p.Product_ID AS product_id, v.Variant_ID AS variant_id
        FROM Invoice i
        JOIN Transaction_Type t ON t.Transaction_Type_ID = i.Transaction_Type_ID
        JOIN Product_Variant v ON v.Variant_ID = i.Variant_ID
        JOIN Product p ON p.Product_ID = v.Product_ID
        JOIN Size s ON s.Size_ID = v.Size_ID
        JOIN Color co ON co.Color_ID = v.Color_ID
        JOIN Employee e ON e.Employee_ID = i.Employee_ID
    '''

    @app.get('/orders')
    def orders_summary():
        type_filter = str(request.args.get('type', '')).strip()[:50]
        try:
            limit = min(max(int(request.args.get('limit', 100)), 1), 200)
        except (TypeError, ValueError):
            limit = 100
        types = [row['Transaction_Type'] for row in fetch(
            'SELECT Transaction_Type FROM Transaction_Type ORDER BY Transaction_Type')]
        if type_filter and type_filter not in types:
            return jsonify({'rows': [], 'types': types, 'limit': limit})
        where = 'WHERE t.Transaction_Type = %s' if type_filter else ''
        params = (type_filter, limit) if type_filter else (limit,)
        rows = fetch(ORDER_SELECT + where + ' ORDER BY i.Date DESC, i.Invoice_ID DESC LIMIT %s', params)
        for row in rows:
            if row.get('date') is not None:
                row['date'] = str(row['date'])[:10]
        return jsonify({'rows': rows, 'types': types, 'limit': limit})

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
        recent = fetch(ORDER_SELECT + ' ORDER BY i.Date DESC, i.Invoice_ID DESC LIMIT 5')
        for row in recent:
            if row.get('date') is not None:
                row['date'] = str(row['date'])[:10]
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
        total_rows = fetch('SELECT COALESCE(SUM(Quantity),0) AS total FROM Inventory')
        total = int(total_rows[0]['total'] or 0) if total_rows else 0
        changes = fetch('''
            SELECT Date AS date, SUM(Quantity_Change) AS delta
            FROM Invoice WHERE Date >= %s AND Date <= %s
            GROUP BY Date ORDER BY Date ASC
        ''', (first_day, date.today()))
        delta_by_day = {str(row['date'])[:10]: int(row['delta'] or 0) for row in changes}
        stock_before_period = total - sum(delta_by_day.values())
        running = stock_before_period
        trend = []
        for day_index in range(days):
            d = first_day + timedelta(days=day_index)
            running += delta_by_day.get(d.isoformat(), 0)
            trend.append({'date': d.isoformat(), 'total_units': running})
        sales = sale_agg[0] if sale_agg else {}
        return jsonify({
            'sales': {'revenue': sales.get('revenue') or 0,
                      'units': sales.get('units') or 0,
                      'days': days, 'by_category': by_category},
            'recent_orders': recent,
            'low_stock': low,
            'low_stock_threshold': threshold(),
            'trend': trend,
            'trend_note': 'Historical stock reconstructed from current inventory and posted invoice changes.'
        })
