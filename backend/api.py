import os
import flask
from flask import Flask, jsonify, request
from flask_cors import CORS

# importing database credentials
import creds
from sql import DBconnection, execute_read_query, execute_update_query

# needed for password hashing
from argon2 import PasswordHasher, exceptions

# Initialize Flask app (This was missing from the dev branch!)
app = Flask(__name__)

# --- RESTORED CORS & DEBUG LOGIC ---
CORS(app, supports_credentials=True,
     resources={r"/*": {"origins": os.getenv("FRONTEND_URL", "http://localhost:8080")}})
app.config['DEBUG'] = creds.APP_ENV == "development"

# --- DATABASE CONNECTION ---
def get_db_connection():
    mycreds = creds.mycreds()
    return DBconnection(mycreds.hostname, mycreds.username, mycreds.password, mycreds.database)

# Fix for older routes that might still use the old function name
get_connection = get_db_connection


# --- RESTORED HEALTH CHECKS ---
@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "API is healthy and running!"}), 200

@app.route('/db/check', methods=['GET'])
def db_check():
    mycon = get_connection()
    if mycon is None:
        return jsonify({"connected": False}), 500
    result = execute_read_query(mycon, "select database() as db")
    mycon.close()
    return jsonify({"connected": True, "database": result[0]["db"]})


# 1. SUPPLIER CRUD
@app.route('/api/suppliers', methods=['GET'])
def get_suppliers():
    mycon = get_db_connection()
    suppliers = execute_read_query(mycon, "SELECT * FROM Supplier")
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


# 2. CATEGORY CRUD
@app.route('/api/categories', methods=['GET'])
def get_categories():
    mycon = get_db_connection()
    categories = execute_read_query(mycon, "SELECT * FROM Category")
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


# 3. LOCATION CRUD
@app.route('/api/locations', methods=['GET'])
def get_locations():
    mycon = get_db_connection()
    locations = execute_read_query(mycon, "SELECT * FROM Location")
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


# 4. PRODUCT CRUD
@app.route('/api/products', methods=['GET'])
def get_products():
    mycon = get_db_connection()
    products = execute_read_query(mycon, "SELECT * FROM Product")
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


# 5. PRODUCT VARIANT CRUD
@app.route('/api/product_variants', methods=['GET'])
def get_product_variants():
    mycon = get_db_connection()
    variants = execute_read_query(mycon, "SELECT * FROM Product_Variant")
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


# 6. INVENTORY CRUD
@app.route('/api/inventory', methods=['GET'])
def get_inventory():
    mycon = get_db_connection()
    inventory = execute_read_query(mycon, "SELECT * FROM Inventory")
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


# CRUD for the Employee Table
@app.route('/all/employees', methods = ['GET'])
def allEmployees():
    mycon = get_connection()
    sql = "select Employee_ID, First_Name, Last_Name, Role, Email, Username from Employee"
    allEmployees = execute_read_query(mycon, sql)
    mycon.close()
    return jsonify(allEmployees)

@app.route('/get/employee', methods = ['GET'])
def employeeInformation():
    mycon = get_connection()
    userinput = request.get_json()
    email = userinput['Email']
    sql = "select First_Name, Last_Name, Role, Username, Email from Employee where Email = '%s'" % (email)
    employeeInformation = execute_read_query(mycon,sql)
    mycon.close()
    if (employeeInformation):
        return jsonify (employeeInformation)
    else:
        return jsonify({"message": "No employee found"}), 404

@app.route('/add/employee',methods=['POST'])
def addEmployee():
        mycon = get_connection()
        userinput = request.get_json()
        firstName = userinput['First_Name']
        lastName = userinput['Last_Name']
        role = userinput['Role']
        username = userinput['Username']
        email = userinput['Email']
        password= userinput['Password']

        sql = "select Email from Employee where Email = '%s' " % (email)
        sql2 = "select Username from Employee where Username = '%s'" % (username)

        storedEmail = execute_read_query(mycon,sql)
        storedUsername = execute_read_query(mycon,sql2)

        if storedEmail:
            mycon.close()
            return jsonify({'message' : 'An account with this email already exists. Try a different email address.'}), 409
        elif storedUsername:
            mycon.close()
            return jsonify ({'message': 'An account with that username already exists. Try a different username.'}), 409
        else: 
            ph = PasswordHasher()
            hashedPassword = ph.hash(password)
            sql = "insert into Employee (First_Name, Last_Name, Role, Username, Email, Password_Hash) Values ('%s','%s','%s','%s','%s','%s')" % (firstName, lastName, role, username, email,hashedPassword )
            execute_update_query(mycon,sql)
            mycon.close()
            return jsonify({'message': 'Employee successfully added to the system.'}), 201

@app.route('/update/employee', methods=['PUT'])
def updateEmployee():
    mycon = get_connection()
    userinput = request.get_json()
    firstName = userinput.get('First_Name')
    lastName = userinput.get('Last_Name')
    role = userinput.get('Role')
    username = userinput.get('Username')
    newEmail = userinput.get('Email')
    currentEmail = userinput.get('Current_Email')
    password= userinput.get('Password')

    if firstName:
        sql = "update Employee set First_Name = '%s' where Email =  '%s' " % (firstName,currentEmail)
        execute_update_query(mycon,sql)
       
    if lastName:
        sql ="update Employee set Last_Name  = '%s' where Email = '%s' " % (lastName, currentEmail)
        execute_update_query(mycon, sql)
       
    if role:
        sql = "update Employee set Role = '%s' where Email = '%s' " % (role, currentEmail)
        execute_update_query(mycon,sql)
        
    if username:
        sql = "update Employee set username = '%s' where Email = '%s'" % (username, currentEmail)
        execute_update_query(mycon, sql)
        
    if password:
        ph = PasswordHasher()
        hashedPassword = ph.hash(password)
        sql = "update Employee set Password_Hash = '%s' where Email = '%s'" % (hashedPassword, currentEmail)
        execute_update_query(mycon, sql)

    if newEmail:
            sql = "update Employee set Email = '%s' where Email= '%s'" % (newEmail, currentEmail)
            execute_update_query(mycon,sql)
    
    mycon.close()
    return jsonify({'message': 'Employee information was successfully updated.'})

@app.route('/delete/employee',methods=['DELETE'])
def deleteEmployee():
    mycon = get_connection()
    userinput = request.get_json()
    email = userinput['Email']

    sql = "select Employee_ID from Employee where Email = '%s'" % (email)
    employee = execute_read_query(mycon,sql)
    if not employee:
        mycon.close()
        return jsonify({'message' : 'Employee not found. Try a different email.'}), 404

    employeeID = employee[0]['Employee_ID']
    sql1 = "select Invoice_ID from Invoice where Employee_ID = '%s'" % (employeeID)
    invoices = execute_read_query(mycon,sql1)
    if invoices:
        mycon.close()
        return jsonify({'message' : "This employee has invoices and can't be deleted."}), 409

    sql2 = "delete from Employee where Email = '%s' " % (email)
    execute_update_query(mycon,sql2)
    mycon.close()
    return jsonify({'message' : 'Employee deleted from the system.'})

# Below is the API for the login system
@app.route('/login', methods=['POST'])
def login():
    mycon = get_connection()
    userinput = request.get_json()
    username = userinput['Username']
    password = userinput['Password']

    sql = "select Email, Password_Hash, First_Name, Last_Name, Role, Username, Employee_ID from Employee where Username = '%s'" % (username)
    results = execute_read_query(mycon,sql)
    mycon.close()
    if not results:
        return jsonify({'message' : 'Username not found, try again'}), 404
    
    storedEmail = results[0]['Email']
    storedPasswordHash = results[0]['Password_Hash']
    storedFirstName = results[0]['First_Name']
    storedLastName = results[0]['Last_Name']
    storedRole = results[0]['Role']
    storedUsername = results[0]['Username']
    storedEmployeeID = results[0]['Employee_ID']

    ph = PasswordHasher()

    try:
        if (ph.verify(storedPasswordHash, password)):
            return jsonify({
                    "message" : "Login Successful.",
                    "Email" : storedEmail,
                    "First_Name" : storedFirstName,
                    "Last_Name" : storedLastName,
                    "Role" : storedRole,
                    "Username" : storedUsername,
                    "Employee_ID" : storedEmployeeID
            }), 200
        
    except exceptions.VerificationError: 
        return jsonify({'message':'Invalid password.' }), 401
    except Exception as e:
        return jsonify({'message' : 'An error occurred'}), 500

# Below is the CRUD for the Invoice table.
@app.route('/get/invoice', methods = ['GET'])
def getInvoice():
    mycon = get_connection()
    userinput = request.get_json()
    invoiceID = userinput['Invoice_ID']
    sql = "select * from Invoice where Invoice_ID = '%s'" % (invoiceID)
    invoice = execute_read_query(mycon,sql)
    mycon.close()
    if invoice:
        return jsonify(invoice)
    else:
        return jsonify({'message' : 'Invoice not found. Try a different Invoice_ID.'}), 404

@app.route('/show/all/invoices', methods = ['GET'])
def showAllInvoices():
    mycon = get_connection()
    sql ="select * from Invoice"
    allInvoices = execute_read_query(mycon,sql)
    mycon.close()
    return jsonify(allInvoices)

@app.route('/create/invoice', methods =['POST'])
def createInvoice():
    mycon = get_connection()
    userinput = request.get_json()
    transactionTypeID = userinput['Transaction_Type_ID']
    quantityChange = int(userinput['Quantity_Change']) 
    variantID = userinput['Variant_ID']
    employeeID = userinput['Employee_ID'] 

    sql = "select Variant_ID from Product_Variant where Variant_ID ='%s' " % (variantID)
    sql1 = "select Transaction_Type_ID from Transaction_Type where Transaction_Type_ID = '%s' " % (transactionTypeID)
    sql2= "select Employee_ID from Employee where Employee_ID = '%s'" % (employeeID)

    variant = execute_read_query(mycon,sql)
    transaction = execute_read_query(mycon, sql1)
    employee = execute_read_query(mycon,sql2)

    if not variant:
        mycon.close()
        return jsonify({'message' : 'There are no variants with that ID. Try another ID number.'}), 404
    if not transaction:
        mycon.close()
        return jsonify({'message' : 'Transaction type does not exist. Try a different transaction type.'}), 404
    if not employee:
        mycon.close()
        return jsonify({'message' : 'Employee does not exist. Try another ID.'}), 404

    sql3 = "select Quantity from Inventory where Variant_ID = '%s'" % (variantID)
    stock = execute_read_query(mycon,sql3)
    if not stock:
        mycon.close()
        return jsonify({'message': 'No inventory record for that variant'}), 404

    currentStock = stock[0]['Quantity']
    if currentStock + quantityChange < 0:
        mycon.close()
        return jsonify({'message' : 'There is not enough stock to complete this request. %s items are in stock.' % (currentStock)}), 400

    sql4 = "insert into Invoice (Transaction_Type_ID, Quantity_Change, Date, Variant_ID, Employee_ID) values ('%s', '%s', CURDATE(), '%s', '%s')" % (transactionTypeID, quantityChange, variantID, employeeID)
    execute_update_query(mycon, sql4)
    sql5 = "update Inventory set Quantity = Quantity + %s where Variant_ID = '%s'" % (quantityChange, variantID)
    execute_update_query(mycon, sql5)

    mycon.close()
    return jsonify({'message' : 'Invoice created and inventory updated.'}), 201

@app.route('/update/invoice', methods=['PUT'])
def updateInvoice():
    mycon = get_connection()
    userinput = request.get_json()
    invoiceID = userinput.get('Invoice_ID')
    transactionTypeID = userinput.get('Transaction_Type_ID')
    quantityChange = userinput.get('Quantity_Change') 

    if not invoiceID:
        mycon.close()
        return jsonify({'message' : 'Invoice_ID is required.'}), 400

    sql = "select Quantity_Change, Variant_ID from Invoice where Invoice_ID = '%s'" % (invoiceID)
    invoice = execute_read_query(mycon,sql)
    if not invoice:
        mycon.close()
        return jsonify({'message' : 'Invoice not found. Try a different Invoice_ID.'}), 404

    oldQuantity = invoice[0]['Quantity_Change']
    variantID = invoice[0]['Variant_ID']

    if transactionTypeID:
        sql1 = "select Transaction_Type_ID from Transaction_Type where Transaction_Type_ID = '%s'" % (transactionTypeID)
        transaction = execute_read_query(mycon,sql1)
        if not transaction:
            mycon.close()
            return jsonify({'message' : 'Transaction type does not exist. Try a different transaction type.'}), 404

    if quantityChange is not None:
        quantityChange = int(quantityChange)
        difference = quantityChange - oldQuantity
        sql2 = "select Quantity from Inventory where Variant_ID = '%s'" % (variantID)
        stock = execute_read_query(mycon,sql2)
        if not stock:
            mycon.close()
            return jsonify({'message' : 'No inventory record for that variant'}), 404
        currentStock = stock[0]['Quantity']
        if currentStock + difference < 0:
            mycon.close()
            return jsonify({'message' : 'There is not enough stock to complete this request. %s items are in stock.' % (currentStock)}), 400

    if transactionTypeID:
        sql3 = "update Invoice set Transaction_Type_ID = '%s' where Invoice_ID = '%s'" % (transactionTypeID, invoiceID)
        execute_update_query(mycon,sql3)

    if quantityChange is not None:
        sql4 = "update Invoice set Quantity_Change = '%s' where Invoice_ID = '%s'" % (quantityChange, invoiceID)
        execute_update_query(mycon,sql4)
        sql5 = "update Inventory set Quantity = Quantity + %s where Variant_ID = '%s'" % (difference, variantID)
        execute_update_query(mycon,sql5)

    mycon.close()
    return jsonify({'message' : 'Invoice updated.'})

@app.route('/delete/invoice', methods=['DELETE'])
def deleteInvoice():
    mycon = get_connection()
    userinput = request.get_json()
    invoiceID = userinput.get('Invoice_ID')

    if not invoiceID:
        mycon.close()
        return jsonify({'message' : 'Invoice_ID is required.'}), 400

    sql = "select Quantity_Change, Variant_ID from Invoice where Invoice_ID = '%s'" % (invoiceID)
    invoice = execute_read_query(mycon,sql)
    if not invoice:
        mycon.close()
        return jsonify({'message' : 'Invoice not found. Try a different Invoice_ID.'}), 404

    oldQuantity = invoice[0]['Quantity_Change']
    variantID = invoice[0]['Variant_ID']

    sql1 = "select Quantity from Inventory where Variant_ID = '%s'" % (variantID)
    stock = execute_read_query(mycon,sql1)
    if not stock:
        mycon.close()
        return jsonify({'message' : 'No inventory record for that variant'}), 404
    currentStock = stock[0]['Quantity']
    if currentStock - oldQuantity < 0:
        mycon.close()
        return jsonify({'message' : 'This invoice cannot be deleted. Undoing it would take the stock below 0. %s items are in stock.' % (currentStock)}), 400

    sql2 = "delete from Invoice where Invoice_ID = '%s'" % (invoiceID)
    execute_update_query(mycon,sql2)
    sql3 = "update Inventory set Quantity = Quantity - %s where Variant_ID = '%s'" % (oldQuantity, variantID)
    execute_update_query(mycon,sql3)

    mycon.close()
    return jsonify({'message' : 'Invoice deleted and inventory updated.'})


# Below is the CRUD for the Color table
@app.route('/show/all/colors', methods = ['GET'])
def showAllColors():
    mycon = get_connection()
    sql = "select * from Color"
    allColors = execute_read_query(mycon,sql)
    mycon.close()
    return jsonify(allColors)

@app.route('/create/color', methods = ['POST'])
def createColor():
    mycon = get_connection()
    userinput = request.get_json()
    color = userinput.get('Color')

    if not color:
        mycon.close()
        return jsonify({'message' : 'Color is required.'}), 400

    sql = "select Color_ID from Color where Color = '%s'" % (color)
    storedColor = execute_read_query(mycon,sql)
    if storedColor:
        mycon.close()
        return jsonify({'message' : 'That color already exists.'}), 409

    sql1 = "insert into Color (Color) values ('%s')" % (color)
    execute_update_query(mycon,sql1)
    mycon.close()
    return jsonify({'message' : 'Color added.'}), 201

@app.route('/update/color', methods = ['PUT'])
def updateColor():
    mycon = get_connection()
    userinput = request.get_json()
    colorID = userinput.get('Color_ID')
    color = userinput.get('Color')

    if not colorID or not color:
        mycon.close()
        return jsonify({'message' : 'Color_ID and Color are required.'}), 400

    sql = "select Color_ID from Color where Color_ID = '%s'" % (colorID)
    storedColor = execute_read_query(mycon,sql)
    if not storedColor:
        mycon.close()
        return jsonify({'message' : 'Color not found. Try a different Color_ID.'}), 404

    sql1 = "select Color_ID from Color where Color = '%s' and Color_ID != '%s'" % (color, colorID)
    duplicate = execute_read_query(mycon,sql1)
    if duplicate:
        mycon.close()
        return jsonify({'message' : 'That color already exists.'}), 409

    sql2 = "update Color set Color = '%s' where Color_ID = '%s'" % (color, colorID)
    execute_update_query(mycon,sql2)
    mycon.close()
    return jsonify({'message' : 'Color updated.'})

@app.route('/delete/color', methods = ['DELETE'])
def deleteColor():
    mycon = get_connection()
    userinput = request.get_json()
    colorID = userinput.get('Color_ID')

    if not colorID:
        mycon.close()
        return jsonify({'message' : 'Color_ID is required.'}), 400

    sql = "select Color_ID from Color where Color_ID = '%s'" % (colorID)
    storedColor = execute_read_query(mycon,sql)
    if not storedColor:
        mycon.close()
        return jsonify({'message' : 'Color not found. Try a different Color_ID.'}), 404

    sql1 = "select Variant_ID from Product_Variant where Color_ID = '%s'" % (colorID)
    variants = execute_read_query(mycon,sql1)
    if variants:
        mycon.close()
        return jsonify({'message' : "This color is used by product variants and can't be deleted."}), 409

    sql2 = "delete from Color where Color_ID = '%s'" % (colorID)
    execute_update_query(mycon,sql2)
    mycon.close()
    return jsonify({'message' : 'Color deleted.'})


# Below is the CRUD for the Size table
@app.route('/show/all/sizes', methods = ['GET'])
def showAllSizes():
    mycon = get_connection()
    sql = "select * from Size"
    allSizes = execute_read_query(mycon,sql)
    mycon.close()
    return jsonify(allSizes)

@app.route('/create/size', methods = ['POST'])
def createSize():
    mycon = get_connection()
    userinput = request.get_json()
    size = userinput.get('Size')

    if not size:
        mycon.close()
        return jsonify({'message' : 'Size is required.'}), 400

    sql = "select Size_ID from Size where Size = '%s'" % (size)
    storedSize = execute_read_query(mycon,sql)
    if storedSize:
        mycon.close()
        return jsonify({'message' : 'That size already exists.'}), 409

    sql1 = "insert into Size (Size) values ('%s')" % (size)
    execute_update_query(mycon,sql1)
    mycon.close()
    return jsonify({'message' : 'Size added.'}), 201

@app.route('/update/size', methods = ['PUT'])
def updateSize():
    mycon = get_connection()
    userinput = request.get_json()
    sizeID = userinput.get('Size_ID')
    size = userinput.get('Size')

    if not sizeID or not size:
        mycon.close()
        return jsonify({'message' : 'Size_ID and Size are required.'}), 400

    sql = "select Size_ID from Size where Size_ID = '%s'" % (sizeID)
    storedSize = execute_read_query(mycon,sql)
    if not storedSize:
        mycon.close()
        return jsonify({'message' : 'Size not found. Try a different Size_ID.'}), 404

    sql1 = "select Size_ID from Size where Size = '%s' and Size_ID != '%s'" % (size, sizeID)
    duplicate = execute_read_query(mycon,sql1)
    if duplicate:
        mycon.close()
        return jsonify({'message' : 'That size already exists.'}), 409

    sql2 = "update Size set Size = '%s' where Size_ID = '%s'" % (size, sizeID)
    execute_update_query(mycon,sql2)
    mycon.close()
    return jsonify({'message' : 'Size updated.'})

@app.route('/delete/size', methods = ['DELETE'])
def deleteSize():
    mycon = get_connection()
    userinput = request.get_json()
    sizeID = userinput.get('Size_ID')

    if not sizeID:
        mycon.close()
        return jsonify({'message' : 'Size_ID is required.'}), 400

    sql = "select Size_ID from Size where Size_ID = '%s'" % (sizeID)
    storedSize = execute_read_query(mycon,sql)
    if not storedSize:
        mycon.close()
        return jsonify({'message' : 'Size not found. Try a different Size_ID.'}), 404

    sql1 = "select Variant_ID from Product_Variant where Size_ID = '%s'" % (sizeID)
    variants = execute_read_query(mycon,sql1)
    if variants:
        mycon.close()
        return jsonify({'message' : "This size is used by product variants and can't be deleted."}), 409

    sql2 = "delete from Size where Size_ID = '%s'" % (sizeID)
    execute_update_query(mycon,sql2)
    mycon.close()
    return jsonify({'message' : 'Size deleted.'})


# Below is the CRUD for the Transaction_Type table
@app.route('/show/all/transaction/types', methods = ['GET'])
def showAllTransactionTypes():
    mycon = get_connection()
    sql = "select * from Transaction_Type"
    allTransactionTypes = execute_read_query(mycon,sql)
    mycon.close()
    return jsonify(allTransactionTypes)

@app.route('/create/transaction/type', methods = ['POST'])
def createTransactionType():
    mycon = get_connection()
    userinput = request.get_json()
    transactionType = userinput.get('Transaction_Type')

    if not transactionType:
        mycon.close()
        return jsonify({'message' : 'Transaction_Type is required.'}), 400

    sql = "select Transaction_Type_ID from Transaction_Type where Transaction_Type = '%s'" % (transactionType)
    storedType = execute_read_query(mycon,sql)
    if storedType:
        mycon.close()
        return jsonify({'message' : 'That transaction type already exists.'}), 409

    sql1 = "insert into Transaction_Type (Transaction_Type) values ('%s')" % (transactionType)
    execute_update_query(mycon,sql1)
    mycon.close()
    return jsonify({'message' : 'Transaction type added.'}), 201

@app.route('/update/transaction/type', methods = ['PUT'])
def updateTransactionType():
    mycon = get_connection()
    userinput = request.get_json()
    transactionTypeID = userinput.get('Transaction_Type_ID')
    transactionType = userinput.get('Transaction_Type')

    if not transactionTypeID or not transactionType:
        mycon.close()
        return jsonify({'message' : 'Transaction_Type_ID and Transaction_Type are required.'}), 400

    if int(transactionTypeID) in (1, 2):
        mycon.close()
        return jsonify({'message' : "Restock and Sale are used by the invoice system and can't be changed."}), 409

    sql = "select Transaction_Type_ID from Transaction_Type where Transaction_Type_ID = '%s'" % (transactionTypeID)
    storedType = execute_read_query(mycon,sql)
    if not storedType:
        mycon.close()
        return jsonify({'message' : 'Transaction type not found. Try a different Transaction_Type_ID.'}), 404

    sql1 = "select Transaction_Type_ID from Transaction_Type where Transaction_Type = '%s' and Transaction_Type_ID != '%s'" % (transactionType, transactionTypeID)
    duplicate = execute_read_query(mycon,sql1)
    if duplicate:
        mycon.close()
        return jsonify({'message' : 'That transaction type already exists.'}), 409

    sql2 = "update Transaction_Type set Transaction_Type = '%s' where Transaction_Type_ID = '%s'" % (transactionType, transactionTypeID)
    execute_update_query(mycon,sql2)
    mycon.close()
    return jsonify({'message' : 'Transaction type updated.'})

@app.route('/delete/transaction/type', methods = ['DELETE'])
def deleteTransactionType():
    mycon = get_connection()
    userinput = request.get_json()
    transactionTypeID = userinput.get('Transaction_Type_ID')

    if not transactionTypeID:
        mycon.close()
        return jsonify({'message' : 'Transaction_Type_ID is required.'}), 400

    if int(transactionTypeID) in (1, 2):
        mycon.close()
        return jsonify({'message' : "Restock and Sale are used by the invoice system and can't be deleted."}), 409

    sql = "select Transaction_Type_ID from Transaction_Type where Transaction_Type_ID = '%s'" % (transactionTypeID)
    storedType = execute_read_query(mycon,sql)
    if not storedType:
        mycon.close()
        return jsonify({'message' : 'Transaction type not found. Try a different Transaction_Type_ID.'}), 404

    sql1 = "select Invoice_ID from Invoice where Transaction_Type_ID = '%s'" % (transactionTypeID)
    invoices = execute_read_query(mycon,sql1)
    if invoices:
        mycon.close()
        return jsonify({'message' : "This transaction type is used by invoices and can't be deleted."}), 409

    sql2 = "delete from Transaction_Type where Transaction_Type_ID = '%s'" % (transactionTypeID)
    execute_update_query(mycon,sql2)
    mycon.close()
    return jsonify({'message' : 'Transaction type deleted.'})


# --- START THE API ---
if __name__ == '__main__':
    app.run(port=int(os.getenv("API_PORT", "5000")))