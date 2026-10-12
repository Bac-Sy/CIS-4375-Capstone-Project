from flask import Flask, request, jsonify
from sql import execute_read_query, execute_update_query, DBconnection
import creds 

app = Flask(__name__)

# --- DATABASE CONNECTION ---
def get_db_connection():
    mycreds = creds.mycreds()
    return DBconnection(mycreds.hostname, mycreds.username, mycreds.password, mycreds.database)


# ==========================================
# 1. SUPPLIER CRUD
# Columns: Supplier_ID (PK), Name, Email, Phone
# ==========================================
@app.route('/api/suppliers', methods=['GET'])
def get_suppliers():
    mycon = get_db_connection()
    suppliers = execute_read_query(mycon, "SELECT * FROM Supplier", ())
    return jsonify(suppliers), 200

@app.route('/api/suppliers', methods=['POST'])
def add_supplier():
    data = request.json
    mycon = get_db_connection()
    query = "INSERT INTO Supplier (Name, Email, Phone) VALUES (%s, %s, %s)"
    params = (data['Name'], data['Email'], data['Phone'])
    execute_update_query(mycon, query, params)
    return jsonify({"message": "Supplier added!"}), 201

@app.route('/api/suppliers/<int:supplier_id>', methods=['PUT'])
def update_supplier(supplier_id):
    data = request.json
    mycon = get_db_connection()
    query = "UPDATE Supplier SET Name=%s, Email=%s, Phone=%s WHERE Supplier_ID=%s"
    params = (data['Name'], data['Email'], data['Phone'], supplier_id)
    execute_update_query(mycon, query, params)
    return jsonify({"message": "Supplier updated!"}), 200

@app.route('/api/suppliers/<int:supplier_id>', methods=['DELETE'])
def delete_supplier(supplier_id):
    mycon = get_db_connection()
    execute_update_query(mycon, "DELETE FROM Supplier WHERE Supplier_ID=%s", (supplier_id,))
    return jsonify({"message": "Supplier deleted!"}), 200


# ==========================================
# 2. CATEGORY CRUD
# Columns: Category_ID (PK), Category
# ==========================================
@app.route('/api/categories', methods=['GET'])
def get_categories():
    mycon = get_db_connection()
    categories = execute_read_query(mycon, "SELECT * FROM Category", ())
    return jsonify(categories), 200

@app.route('/api/categories', methods=['POST'])
def add_category():
    data = request.json
    mycon = get_db_connection()
    query = "INSERT INTO Category (Category) VALUES (%s)"
    params = (data['Category'],)
    execute_update_query(mycon, query, params)
    return jsonify({"message": "Category added!"}), 201

@app.route('/api/categories/<int:category_id>', methods=['PUT'])
def update_category(category_id):
    data = request.json
    mycon = get_db_connection()
    query = "UPDATE Category SET Category=%s WHERE Category_ID=%s"
    params = (data['Category'], category_id)
    execute_update_query(mycon, query, params)
    return jsonify({"message": "Category updated!"}), 200

@app.route('/api/categories/<int:category_id>', methods=['DELETE'])
def delete_category(category_id):
    mycon = get_db_connection()
    execute_update_query(mycon, "DELETE FROM Category WHERE Category_ID=%s", (category_id,))
    return jsonify({"message": "Category deleted!"}), 200


# ==========================================
# 3. LOCATION CRUD
# Columns: Location_ID (PK), Location_Name
# ==========================================
@app.route('/api/locations', methods=['GET'])
def get_locations():
    mycon = get_db_connection()
    locations = execute_read_query(mycon, "SELECT * FROM Location", ())
    return jsonify(locations), 200

@app.route('/api/locations', methods=['POST'])
def add_location():
    data = request.json
    mycon = get_db_connection()
    query = "INSERT INTO Location (Location_Name) VALUES (%s)"
    params = (data['Location_Name'],)
    execute_update_query(mycon, query, params)
    return jsonify({"message": "Location added!"}), 201

@app.route('/api/locations/<int:location_id>', methods=['PUT'])
def update_location(location_id):
    data = request.json
    mycon = get_db_connection()
    query = "UPDATE Location SET Location_Name=%s WHERE Location_ID=%s"
    params = (data['Location_Name'], location_id)
    execute_update_query(mycon, query, params)
    return jsonify({"message": "Location updated!"}), 200

@app.route('/api/locations/<int:location_id>', methods=['DELETE'])
def delete_location(location_id):
    mycon = get_db_connection()
    execute_update_query(mycon, "DELETE FROM Location WHERE Location_ID=%s", (location_id,))
    return jsonify({"message": "Location deleted!"}), 200


# ==========================================
# 4. PRODUCT CRUD
# Columns: Product_ID (PK), Name, Category_ID (FK), Availability, Supplier_ID (FK)
# ==========================================
@app.route('/api/products', methods=['GET'])
def get_products():
    mycon = get_db_connection()
    products = execute_read_query(mycon, "SELECT * FROM Product", ())
    return jsonify(products), 200

@app.route('/api/products', methods=['POST'])
def add_product():
    data = request.json
    mycon = get_db_connection()
    query = "INSERT INTO Product (Name, Category_ID, Availability, Supplier_ID) VALUES (%s, %s, %s, %s)"
    params = (data['Name'], data['Category_ID'], data['Availability'], data['Supplier_ID'])
    execute_update_query(mycon, query, params)
    return jsonify({"message": "Product added!"}), 201

@app.route('/api/products/<int:product_id>', methods=['PUT'])
def update_product(product_id):
    data = request.json
    mycon = get_db_connection()
    query = "UPDATE Product SET Name=%s, Category_ID=%s, Availability=%s, Supplier_ID=%s WHERE Product_ID=%s"
    params = (data['Name'], data['Category_ID'], data['Availability'], data['Supplier_ID'], product_id)
    execute_update_query(mycon, query, params)
    return jsonify({"message": "Product updated!"}), 200

@app.route('/api/products/<int:product_id>', methods=['DELETE'])
def delete_product(product_id):
    mycon = get_db_connection()
    execute_update_query(mycon, "DELETE FROM Product WHERE Product_ID=%s", (product_id,))
    return jsonify({"message": "Product deleted!"}), 200


# ==========================================
# 5. PRODUCT VARIANT CRUD
# Columns: Variant_ID (PK), Size_ID (FK), Color_ID (FK), Product_ID (FK), Location_ID (FK), Price, Cost
# ==========================================
@app.route('/api/product_variants', methods=['GET'])
def get_product_variants():
    mycon = get_db_connection()
    variants = execute_read_query(mycon, "SELECT * FROM Product_Variant", ())
    return jsonify(variants), 200

@app.route('/api/product_variants', methods=['POST'])
def add_product_variant():
    data = request.json
    mycon = get_db_connection()
    query = "INSERT INTO Product_Variant (Size_ID, Color_ID, Product_ID, Location_ID, Price, Cost) VALUES (%s, %s, %s, %s, %s, %s)"
    params = (data['Size_ID'], data['Color_ID'], data['Product_ID'], data['Location_ID'], data['Price'], data['Cost'])
    execute_update_query(mycon, query, params)
    return jsonify({"message": "Product Variant added!"}), 201

@app.route('/api/product_variants/<int:variant_id>', methods=['PUT'])
def update_product_variant(variant_id):
    data = request.json
    mycon = get_db_connection()
    query = "UPDATE Product_Variant SET Size_ID=%s, Color_ID=%s, Product_ID=%s, Location_ID=%s, Price=%s, Cost=%s WHERE Variant_ID=%s"
    params = (data['Size_ID'], data['Color_ID'], data['Product_ID'], data['Location_ID'], data['Price'], data['Cost'], variant_id)
    execute_update_query(mycon, query, params)
    return jsonify({"message": "Product Variant updated!"}), 200

@app.route('/api/product_variants/<int:variant_id>', methods=['DELETE'])
def delete_product_variant(variant_id):
    mycon = get_db_connection()
    execute_update_query(mycon, "DELETE FROM Product_Variant WHERE Variant_ID=%s", (variant_id,))
    return jsonify({"message": "Product Variant deleted!"}), 200


# ==========================================
# 6. INVENTORY CRUD
# Columns: Inventory_ID (PK), Quantity, Variant_ID (FK)
# ==========================================
@app.route('/api/inventory', methods=['GET'])
def get_inventory():
    mycon = get_db_connection()
    inventory = execute_read_query(mycon, "SELECT * FROM Inventory", ())
    return jsonify(inventory), 200

@app.route('/api/inventory', methods=['POST'])
def add_inventory():
    data = request.json
    mycon = get_db_connection()
    query = "INSERT INTO Inventory (Quantity, Variant_ID) VALUES (%s, %s)"
    params = (data['Quantity'], data['Variant_ID'])
    execute_update_query(mycon, query, params)
    return jsonify({"message": "Inventory recorded!"}), 201

@app.route('/api/inventory/<int:inventory_id>', methods=['PUT'])
def update_inventory(inventory_id):
    data = request.json
    mycon = get_db_connection()
    query = "UPDATE Inventory SET Quantity=%s, Variant_ID=%s WHERE Inventory_ID=%s"
    params = (data['Quantity'], data['Variant_ID'], inventory_id)
    execute_update_query(mycon, query, params)
    return jsonify({"message": "Inventory updated!"}), 200

@app.route('/api/inventory/<int:inventory_id>', methods=['DELETE'])
def delete_inventory(inventory_id):
    mycon = get_db_connection()
    execute_update_query(mycon, "DELETE FROM Inventory WHERE Inventory_ID=%s", (inventory_id,))
    return jsonify({"message": "Inventory record deleted!"}), 200


# --- START THE API ---
if __name__ == '__main__':
    app.run(port=5000, debug=True)