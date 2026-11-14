import os
import flask
from flask import Flask, jsonify, request, g
from flask_cors import CORS

# importing database credentials
import creds
from sql import DBconnection, execute_read_query, execute_update_query

# needed for password hashing
from argon2 import PasswordHasher, exceptions
from datetime import date
from security import auth_secret, issue_token, install_auth, forget_employee
from reporting import register_reporting_routes
from history import register_history

# Initialize Flask app
app = Flask(__name__)

# --- RESTORED CORS & DEBUG LOGIC ---
frontend_url = os.getenv("FRONTEND_URL", "http://localhost:8080")
CORS(app, supports_credentials=True, origins=[frontend_url, "http://localhost:8080", "http://127.0.0.1:8080"])
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
    # Restored "ok" and "env" per review
    return jsonify({
        "status": "ok",
        "env": creds.APP_ENV,
        "message": "API is healthy and running!"
    }), 200

@app.route('/db/check', methods=['GET'])
def db_check():
    mycon = get_connection()
    if mycon is None:
        return jsonify({"connected": False}), 500
    result = execute_read_query(mycon, "select database() as db")
    mycon.close()
    return jsonify({"connected": True, "database": result[0]["db"]})


# --- WRITE HELPERS FOR THE CRUD ROUTES BELOW ---
# execute_update_query only prints database errors, so a failed save still looked like it worked.
# run_write does the same insert/update/delete but hands the error back so the route can return it.
def run_write(mycon, query, params):
    cursor = mycon.cursor()
    try:
        cursor.execute(query, params)
        mycon.commit()
        return None
    except Exception as e:
        mycon.rollback()
        return e

# Turns a database error from run_write into a real error response (and closes the connection).
def db_error_response(mycon, error):
    mycon.close()
    code = getattr(error, 'errno', None)
    if code == 1062:
        return jsonify({"message": "That already exists (the same name or email is already saved). Try a different one."}), 409
    if code == 1451:
        return jsonify({"message": "This is still used by other records (for example products or variants), so it can't be deleted."}), 409
    if code == 1452:
        return jsonify({"message": "One of the linked records (like the size, color, product or location) doesn't exist."}), 404
    return jsonify({"message": "The database rejected this change."}), 400

# True if a row with this ID exists in the table.
def row_exists(mycon, table, id_column, row_id):
    rows = execute_read_query(mycon, "SELECT " + id_column + " FROM " + table + " WHERE " + id_column + "=%s", (row_id,))
    return bool(rows)


# ==========================================
# 1. SUPPLIER CRUD
# Columns: Supplier_ID (PK), Name, Email, Phone
# ==========================================
@app.route('/api/suppliers', methods=['GET'])
def get_suppliers():
    mycon = get_connection()
    suppliers = execute_read_query(mycon, "SELECT * FROM Supplier", ())
    mycon.close()
    return jsonify(suppliers), 200

@app.route('/api/suppliers', methods=['POST'])
def add_supplier():
    data = request.json
    mycon = get_connection()
    query = "INSERT INTO Supplier (Name, Email, Phone) VALUES (%s, %s, %s)"
    #Email is UNIQUE, so a blank email is saved as NULL (several suppliers can have none) instead of ''
    params = (data['Name'], (data.get('Email') or '').strip() or None, (data.get('Phone') or '').strip() or None)
    error = run_write(mycon, query, params)
    if error:
        return db_error_response(mycon, error)
    mycon.close()
    return jsonify({"message": "Supplier added!"}), 201

@app.route('/api/suppliers/<int:supplier_id>', methods=['PUT'])
def update_supplier(supplier_id):
    data = request.json
    mycon = get_connection()
    if not row_exists(mycon, "Supplier", "Supplier_ID", supplier_id):
        mycon.close()
        return jsonify({"message": "Supplier not found."}), 404
    query = "UPDATE Supplier SET Name=%s, Email=%s, Phone=%s WHERE Supplier_ID=%s"
    params = (data['Name'], (data.get('Email') or '').strip() or None, (data.get('Phone') or '').strip() or None, supplier_id)
    error = run_write(mycon, query, params)
    if error:
        return db_error_response(mycon, error)
    mycon.close()
    return jsonify({"message": "Supplier updated!"}), 200

@app.route('/api/suppliers/<int:supplier_id>', methods=['DELETE'])
def delete_supplier(supplier_id):
    mycon = get_connection()
    #a supplier with products can't be deleted because the products reference its Supplier_ID
    products = execute_read_query(mycon, "SELECT Product_ID FROM Product WHERE Supplier_ID=%s", (supplier_id,))
    if products:
        mycon.close()
        return jsonify({"message": "This supplier has products and can't be deleted."}), 409
    error = run_write(mycon, "DELETE FROM Supplier WHERE Supplier_ID=%s", (supplier_id,))
    if error:
        return db_error_response(mycon, error)
    mycon.close()
    return jsonify({"message": "Supplier deleted!"}), 200


# ==========================================
# 2. CATEGORY CRUD
# Columns: Category_ID (PK), Category
# ==========================================
@app.route('/api/categories', methods=['GET'])
def get_categories():
    mycon = get_connection()
    categories = execute_read_query(mycon, "SELECT * FROM Category", ())
    mycon.close()
    return jsonify(categories), 200

@app.route('/api/categories', methods=['POST'])
def add_category():
    data = request.json
    mycon = get_connection()
    #category names have to be unique
    existing = execute_read_query(mycon, "SELECT Category_ID FROM Category WHERE Category=%s", (data['Category'],))
    if existing:
        mycon.close()
        return jsonify({"message": "A category with that name already exists."}), 409
    query = "INSERT INTO Category (Category) VALUES (%s)"
    params = (data['Category'],)
    error = run_write(mycon, query, params)
    if error:
        return db_error_response(mycon, error)
    mycon.close()
    return jsonify({"message": "Category added!"}), 201

@app.route('/api/categories/<int:category_id>', methods=['PUT'])
def update_category(category_id):
    data = request.json
    mycon = get_connection()
    if not row_exists(mycon, "Category", "Category_ID", category_id):
        mycon.close()
        return jsonify({"message": "Category not found."}), 404
    #can't rename to a name another category already has
    existing = execute_read_query(mycon, "SELECT Category_ID FROM Category WHERE Category=%s AND Category_ID<>%s", (data['Category'], category_id))
    if existing:
        mycon.close()
        return jsonify({"message": "A category with that name already exists."}), 409
    query = "UPDATE Category SET Category=%s WHERE Category_ID=%s"
    params = (data['Category'], category_id)
    error = run_write(mycon, query, params)
    if error:
        return db_error_response(mycon, error)
    mycon.close()
    return jsonify({"message": "Category updated!"}), 200

@app.route('/api/categories/<int:category_id>', methods=['DELETE'])
def delete_category(category_id):
    mycon = get_connection()
    #a category with products can't be deleted because the products reference its Category_ID
    products = execute_read_query(mycon, "SELECT Product_ID FROM Product WHERE Category_ID=%s", (category_id,))
    if products:
        mycon.close()
        return jsonify({"message": "This category has products and can't be deleted."}), 409
    error = run_write(mycon, "DELETE FROM Category WHERE Category_ID=%s", (category_id,))
    if error:
        return db_error_response(mycon, error)
    mycon.close()
    return jsonify({"message": "Category deleted!"}), 200

# CRUD for the Employee Table

#Read (Pulls all of the employees in the db)
@app.route('/all/employees', methods = ['GET'])
def allEmployees():
    mycon = get_connection()
    sql = "select Employee_ID, First_Name, Last_Name, Role, Email, Username from Employee"
    allEmployees = execute_read_query(mycon, sql)
    mycon.close()
    return jsonify(allEmployees)

#Read (Pulls a single employees information from the DB.)
@app.route('/get/employee', methods = ['GET'])
def employeeInformation():
    mycon = get_connection()
    userinput = request.get_json()
    email = userinput['Email']
    sql = "select First_Name, Last_Name, Role, Username, Email from Employee where Email = %s"
    employeeInformation = execute_read_query(mycon, sql, (email,))
    mycon.close()
    if (employeeInformation):
        return jsonify (employeeInformation)
    else:
        return jsonify({"message": "No employee found"}), 404


#Create (Add a new employee to the database)
@app.route('/add/employee', methods=['POST'])
def addEmployee():
    data = request.get_json(silent=True) or {}
    required = ('First_Name', 'Last_Name', 'Role', 'Username', 'Email', 'Password')
    if any(not str(data.get(key) or '').strip() for key in required):
        return jsonify({'message': 'All employee fields are required.'}), 400
    if data['Role'] not in ('Manager', 'Employee'):
        return jsonify({'message': 'Invalid employee role.'}), 400
    if len(data['Password']) < 8:
        return jsonify({'message': 'Password must have at least 8 characters.'}), 400
    con = get_connection()
    if con is None:
        return jsonify({'message': 'Database unavailable.'}), 503
    try:
        if execute_read_query(con, 'SELECT Employee_ID FROM Employee WHERE Email=%s', (data['Email'],)):
            return jsonify({'message': 'An account with this email already exists.'}), 409
        if execute_read_query(con, 'SELECT Employee_ID FROM Employee WHERE Username=%s', (data['Username'],)):
            return jsonify({'message': 'An account with this username already exists.'}), 409
        hashed = PasswordHasher().hash(data['Password'])
        error = run_write(con,
            'INSERT INTO Employee (First_Name, Last_Name, Role, Username, Email, Password_Hash) '
            'VALUES (%s, %s, %s, %s, %s, %s)',
            (data['First_Name'], data['Last_Name'], data['Role'],
             data['Username'], data['Email'], hashed))
        if error:
            return jsonify({'message': 'Employee could not be created. Check unique fields.'}), 409
        return jsonify({'message': 'Employee successfully added to the system.'}), 201
    finally:
        con.close()

#Update
@app.route('/update/employee', methods=['PUT'])
#To update an employees information, the query uses their email as the identifier. The 'Current_Email' must be sent in the response body for this updater to work.

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
        sql = "update Employee set First_Name = %s where Email =  %s "
        execute_update_query(mycon, sql, (firstName,currentEmail))
       
    if lastName:
        sql = "update Employee set Last_Name  = %s where Email = %s "
        execute_update_query(mycon, sql, (lastName, currentEmail))
       
    if role:
        sql = "update Employee set Role = %s where Email = %s "
        execute_update_query(mycon, sql, (role, currentEmail))
        
    if username:
        sql = "update Employee set username = %s where Email = %s"
        execute_update_query(mycon, sql, (username, currentEmail))
        
    if password:
        ph = PasswordHasher()
        hashedPassword = ph.hash(password)
        sql = "update Employee set Password_Hash = %s where Email = %s"
        execute_update_query(mycon, sql, (hashedPassword, currentEmail))

    if newEmail:
            sql = "update Employee set Email = %s where Email= %s"
            execute_update_query(mycon, sql, (newEmail, currentEmail))
    
    mycon.close()
    #clears the remembered login info so a role change takes effect right away
    forget_employee()
    return jsonify({'message': 'Employee information was successfully updated.'})

#Delete
@app.route('/delete/employee',methods=['DELETE'])
def deleteEmployee():
    mycon = get_connection()
    userinput = request.get_json()
    email = userinput['Email']

    #checks that the employee exists
    sql = "select Employee_ID from Employee where Email = %s"
    employee = execute_read_query(mycon, sql, (email,))
    if not employee:
        mycon.close()
        return jsonify({'message' : 'Employee not found. Try a different email.'}), 404

    #an employee with invoices can't be deleted because the invoices reference their Employee_ID
    employeeID = employee[0]['Employee_ID']
    sql1 = "select Invoice_ID from Invoice where Employee_ID = %s"
    invoices = execute_read_query(mycon, sql1, (employeeID,))
    if invoices:
        mycon.close()
        return jsonify({'message' : "This employee has invoices and can't be deleted."}), 409

    sql2 = "delete from Employee where Email = %s "
    execute_update_query(mycon, sql2, (email,))
    mycon.close()
    #clears the remembered login info so the deleted employee is logged out right away
    forget_employee(employeeID)
    return jsonify({'message' : 'Employee deleted from the system.'})
# Below is the API for the login system
@app.route('/login', methods=['POST'])
@app.route('/auth/login', methods=['POST'])
def login():
    # Support both the original form (Username/Password) and the newer
    # client (username/password). Always bind input as SQL parameters.
    data = request.get_json(silent=True) or {}
    username = str(data.get('Username') or data.get('username') or '').strip()
    password = data.get('Password') or data.get('password') or ''
    if not username or not password:
        return jsonify({'message': 'Username and password are required.'}), 400
    if not auth_secret():
        return jsonify({'message': 'AUTH_TOKEN_SECRET is missing from the backend environment.'}), 503
    con = get_connection()
    if con is None:
        return jsonify({'message': 'Database unavailable.'}), 503
    try:
        rows = execute_read_query(con,
            'SELECT Employee_ID, First_Name, Last_Name, Role, Username, Email, Password_Hash '
            'FROM Employee WHERE Username=%s', (username,))
    finally:
        con.close()
    if rows is None:
        return jsonify({'message': 'Database login query failed.'}), 503
    if not rows:
        return jsonify({'message': 'Incorrect username or password.'}), 401
    employee = rows[0]
    try:
        PasswordHasher().verify(employee['Password_Hash'], password)
    except exceptions.VerificationError:
        return jsonify({'message': 'Incorrect username or password.'}), 401
    except Exception:
        app.logger.exception('Password verification error')
        return jsonify({'message': 'Unable to verify credentials.'}), 503
    token = issue_token(employee['Employee_ID'])
    user = {
        'id': str(employee['Employee_ID']),
        'firstName': employee['First_Name'],
        'lastName': employee['Last_Name'],
        'name': f"{employee['First_Name']} {employee['Last_Name']}",
        'username': employee['Username'],
        'email': employee['Email'],
        'role': employee['Role']
    }
    # Keep legacy names for the original server and modern shapes for
    # the newer EJS client. Never send the password hash to Express.
    return jsonify({
        'message': 'Login successful.', 'token': token,
        'Employee_ID': employee['Employee_ID'],
        'First_Name': employee['First_Name'],
        'Last_Name': employee['Last_Name'],
        'Email': employee['Email'],
        'Username': employee['Username'],
        'Role': employee['Role'],
        'user': user,
        'employee': {
            'id': user['id'], 'first_name': user['firstName'],
            'last_name': user['lastName'], 'username': user['username'],
            'email': user['email'], 'role': user['role']
        }
    }), 200

#Change my password (Settings page). Any signed-in employee can change their OWN password, but only
#after entering their current one. The account comes from the login token, never from the request body,
#so nobody can change someone else's password here. Managers reset other people's passwords on Employees.
@app.route('/change/password', methods=['POST'])
def changeMyPassword():
    data = request.get_json(silent=True) or {}
    currentPassword = str(data.get('Current_Password') or '')
    newPassword = str(data.get('New_Password') or '')
    if not currentPassword or not newPassword:
        return jsonify({'message': 'Enter your current password and a new password.'}), 400
    if len(newPassword) < 8 or len(newPassword) > 128:
        return jsonify({'message': 'The new password must be between 8 and 128 characters.'}), 400
    employeeID = int(g.employee['Employee_ID'])
    con = get_connection()
    if con is None:
        return jsonify({'message': 'Database unavailable.'}), 503
    try:
        rows = execute_read_query(con, 'SELECT Password_Hash FROM Employee WHERE Employee_ID=%s', (employeeID,))
        if not rows:
            return jsonify({'message': 'Your account could not be found.'}), 404
        ph = PasswordHasher()
        try:
            ph.verify(rows[0]['Password_Hash'], currentPassword)
        except exceptions.VerificationError:
            return jsonify({'message': 'Your current password is incorrect.'}), 400
        error = run_write(con, 'UPDATE Employee SET Password_Hash=%s WHERE Employee_ID=%s', (ph.hash(newPassword), employeeID))
        if error:
            return db_error_response(con, error)
        return jsonify({'message': 'Your password was changed.'}), 200
    finally:
        con.close()

#Below is the CRUD for the Invoice table.
#Read (The api to read a single entry in the Invoice table)
@app.route('/get/invoice', methods = ['GET'])
def getInvoice():
    mycon = get_connection()
    userinput = request.get_json()
    invoiceID = userinput['Invoice_ID']
    sql = "select * from Invoice where Invoice_ID = %s"
    invoice = execute_read_query(mycon, sql, (invoiceID,))
    mycon.close()
    if invoice:
        return jsonify(invoice)
    else:
        return jsonify({'message' : 'Invoice not found. Try a different Invoice_ID.'}), 404

#Read (The api to pull all of the invoices from the invoice table.)
@app.route('/show/all/invoices', methods = ['GET'])
def showAllInvoices():
    mycon = get_connection()
    sql ="select * from Invoice"
    allInvoices = execute_read_query(mycon,sql)
    mycon.close()
    return jsonify(allInvoices)

#Create (adding a new invoice to the Invoice table.)
#The invoice and the stock change are saved together in one transaction (or not at all), and the stock row is
#locked while it's checked, so two sales at the same moment can't both take the last item.
@app.route('/create/invoice', methods =['POST'])
def createInvoice():
    userinput = request.get_json(silent=True) or {}
    try:
        transactionTypeID = int(userinput['Transaction_Type_ID'])
        quantityChange = int(userinput['Quantity_Change']) #Needs to be a positive number for additions and a negative number for removals.
        variantID = int(userinput['Variant_ID'])
    except (KeyError, ValueError, TypeError):
        return jsonify({'message' : 'Transaction_Type_ID, Quantity_Change and Variant_ID are required whole numbers.'}), 400
    if quantityChange == 0:
        return jsonify({'message' : 'Quantity_Change cannot be 0.'}), 400
    #the employee comes from the login token, so an invoice is always recorded under the person who made it.
    employeeID = int(g.employee['Employee_ID'])
    supplied = userinput.get('Employee_ID')
    if supplied is not None and str(supplied) != str(employeeID):
        return jsonify({'message' : 'Employee_ID must match the signed-in account.'}), 403

    mycon = get_connection()
    if mycon is None:
        return jsonify({'message' : 'Database unavailable.'}), 503
    cursor = None
    try:
        cursor = mycon.cursor(dictionary=True)
        #these verify that the IDs exist in the system. If they do not, then the call fails.
        cursor.execute("select Transaction_Type from Transaction_Type where Transaction_Type_ID = %s", (transactionTypeID,))
        transaction = cursor.fetchone()
        if transaction is None:
            mycon.rollback()
            return jsonify({'message' : 'Transaction type does not exist. Try a different transaction type.'}), 404
        #a Sale takes stock away and a Restock adds it
        kind = transaction['Transaction_Type']
        if (kind == 'Sale' and quantityChange > 0) or (kind == 'Restock' and quantityChange < 0):
            mycon.rollback()
            return jsonify({'message' : 'A Sale must be negative and a Restock must be positive.'}), 400
        cursor.execute("select Quantity from Inventory where Variant_ID = %s FOR UPDATE", (variantID,))
        stock = cursor.fetchone()
        if stock is None:
            mycon.rollback()
            return jsonify({'message': 'No inventory record for that variant'}), 404
        #below here checks to make sure that the current stock plus the quantity change from the user is >= 0.
        currentStock = int(stock['Quantity'])
        if currentStock + quantityChange < 0:
            mycon.rollback()
            return jsonify({'message' : 'There is not enough stock to complete this request. %s items are in stock.' % (currentStock)}), 400
        # date.today() uses this computer's date. CURDATE() used the database's UTC clock, so evening sales were saved as tomorrow.
        cursor.execute("insert into Invoice (Transaction_Type_ID, Quantity_Change, Date, Variant_ID, Employee_ID) values (%s, %s, %s, %s, %s)",
                       (transactionTypeID, quantityChange, date.today(), variantID, employeeID))
        cursor.execute("update Inventory set Quantity = Quantity + %s where Variant_ID = %s", (quantityChange, variantID))
        mycon.commit()
        return jsonify({'message' : 'Invoice created and inventory updated.'}), 201
    except Exception:
        mycon.rollback()
        app.logger.exception('Invoice create failed')
        return jsonify({'message' : 'The transaction could not be saved. Nothing was changed.'}), 503
    finally:
        if cursor:
            cursor.close()
        mycon.close()

#Update (updates an invoice. The Invoice_ID must be sent in the request body to identify which invoice to change.)
#Any of these can be changed: Transaction_Type_ID, Quantity_Change, Variant_ID (the item) and Date (YYYY-MM-DD).
#Changing the quantity or the item moves the stock: the old change is undone on the old item and the new
#change is applied to the new item. Everything is saved together, or nothing is if a check fails.
@app.route('/update/invoice', methods=['PUT'])
def updateInvoice():
    userinput = request.get_json(silent=True) or {}
    invoiceID = userinput.get('Invoice_ID')
    if not invoiceID:
        return jsonify({'message' : 'Invoice_ID is required.'}), 400
    try:
        invoiceID = int(invoiceID)
        transactionTypeID = int(userinput['Transaction_Type_ID']) if userinput.get('Transaction_Type_ID') else None
        newVariantID = int(userinput['Variant_ID']) if userinput.get('Variant_ID') else None
        quantityChange = int(userinput['Quantity_Change']) if userinput.get('Quantity_Change') is not None else None
        newDate = date.fromisoformat(str(userinput['Date'])) if userinput.get('Date') else None
    except (ValueError, TypeError):
        return jsonify({'message' : 'Invoice_ID, Transaction_Type_ID, Variant_ID and Quantity_Change must be whole numbers, and Date must be YYYY-MM-DD.'}), 400
    if quantityChange == 0:
        return jsonify({'message' : 'Quantity_Change cannot be 0.'}), 400
    if newDate is not None and newDate > date.today():
        return jsonify({'message' : 'The date cannot be in the future.'}), 400

    mycon = get_connection()
    if mycon is None:
        return jsonify({'message' : 'Database unavailable.'}), 503
    cursor = None
    try:
        cursor = mycon.cursor(dictionary=True)
        #pulls the original invoice so the inventory can be corrected
        cursor.execute('SELECT Quantity_Change, Variant_ID FROM Invoice WHERE Invoice_ID=%s FOR UPDATE', (invoiceID,))
        invoice = cursor.fetchone()
        if invoice is None:
            mycon.rollback()
            return jsonify({'message' : 'Invoice not found. Try a different Invoice_ID.'}), 404
        oldQuantity = int(invoice['Quantity_Change'])
        oldVariantID = int(invoice['Variant_ID'])
        newQuantity = oldQuantity if quantityChange is None else quantityChange
        variantID = oldVariantID if newVariantID is None else newVariantID

        #checks that the new transaction type exists
        if transactionTypeID is not None:
            cursor.execute('SELECT Transaction_Type_ID FROM Transaction_Type WHERE Transaction_Type_ID=%s', (transactionTypeID,))
            if cursor.fetchone() is None:
                mycon.rollback()
                return jsonify({'message' : 'Transaction type does not exist. Try a different transaction type.'}), 404

        #locks the stock rows involved so two edits can't change them at the same time
        cursor.execute('SELECT Variant_ID, Quantity FROM Inventory WHERE Variant_ID IN (%s, %s) FOR UPDATE', (oldVariantID, variantID))
        stock = {int(row['Variant_ID']): int(row['Quantity']) for row in cursor.fetchall()}
        if variantID not in stock or oldVariantID not in stock:
            mycon.rollback()
            return jsonify({'message' : 'No inventory record for that variant.'}), 404

        #undo the old change on the old item, then apply the new change to the new item
        before = dict(stock)
        stock[oldVariantID] -= oldQuantity
        stock[variantID] += newQuantity
        for checkedID in {oldVariantID, variantID}:
            if stock[checkedID] < 0:
                mycon.rollback()
                cursor.execute('SELECT p.Name, s.Size, c.Color FROM Product_Variant v JOIN Product p ON p.Product_ID=v.Product_ID '
                               'JOIN Size s ON s.Size_ID=v.Size_ID JOIN Color c ON c.Color_ID=v.Color_ID WHERE v.Variant_ID=%s', (checkedID,))
                item = cursor.fetchone() or {}
                name = '%s (%s / %s)' % (item.get('Name', 'This item'), item.get('Size', '?'), item.get('Color', '?'))
                return jsonify({'message' : 'There is not enough stock. %s has %s in stock.' % (name, before[checkedID])}), 400

        #if all checks pass, then the update will be applied to the system.
        if transactionTypeID is not None:
            cursor.execute('UPDATE Invoice SET Transaction_Type_ID=%s WHERE Invoice_ID=%s', (transactionTypeID, invoiceID))
        if newDate is not None:
            cursor.execute('UPDATE Invoice SET Date=%s WHERE Invoice_ID=%s', (newDate, invoiceID))
        cursor.execute('UPDATE Invoice SET Quantity_Change=%s, Variant_ID=%s WHERE Invoice_ID=%s', (newQuantity, variantID, invoiceID))
        for changedID in {oldVariantID, variantID}:
            cursor.execute('UPDATE Inventory SET Quantity=%s WHERE Variant_ID=%s', (stock[changedID], changedID))
        mycon.commit()
        return jsonify({'message' : 'Order updated.'})
    except Exception:
        mycon.rollback()
        app.logger.exception('Invoice update failed')
        return jsonify({'message' : 'The order could not be updated. Nothing was changed.'}), 503
    finally:
        if cursor:
            cursor.close()
        mycon.close()

#Delete (deletes an invoice and undoes its change to the inventory. The Invoice_ID must be sent in the request body.)
#Deleting and undoing the stock change happen together in one transaction, or not at all.
@app.route('/delete/invoice', methods=['DELETE'])
def deleteInvoice():
    userinput = request.get_json(silent=True) or {}
    try:
        invoiceID = int(userinput.get('Invoice_ID'))
    except (ValueError, TypeError):
        return jsonify({'message' : 'Invoice_ID is required.'}), 400

    mycon = get_connection()
    if mycon is None:
        return jsonify({'message' : 'Database unavailable.'}), 503
    cursor = None
    try:
        cursor = mycon.cursor(dictionary=True)
        #pulls the invoice so its quantity can be taken back out of the inventory
        cursor.execute("select Quantity_Change, Variant_ID from Invoice where Invoice_ID = %s FOR UPDATE", (invoiceID,))
        invoice = cursor.fetchone()
        if invoice is None:
            mycon.rollback()
            return jsonify({'message' : 'Invoice not found. Try a different Invoice_ID.'}), 404
        oldQuantity = int(invoice['Quantity_Change'])
        variantID = invoice['Variant_ID']
        #undoing a restock removes stock, so this checks the stock won't go below 0
        cursor.execute("select Quantity from Inventory where Variant_ID = %s FOR UPDATE", (variantID,))
        stock = cursor.fetchone()
        if stock is None:
            mycon.rollback()
            return jsonify({'message' : 'No inventory record for that variant'}), 404
        currentStock = int(stock['Quantity'])
        if currentStock - oldQuantity < 0:
            mycon.rollback()
            return jsonify({'message' : 'This invoice cannot be deleted. Undoing it would take the stock below 0. %s items are in stock.' % (currentStock)}), 400
        #deletes the invoice and reverses its change to the inventory
        cursor.execute("delete from Invoice where Invoice_ID = %s", (invoiceID,))
        cursor.execute("update Inventory set Quantity = Quantity - %s where Variant_ID = %s", (oldQuantity, variantID))
        mycon.commit()
        return jsonify({'message' : 'Invoice deleted and inventory updated.'})
    except Exception:
        mycon.rollback()
        app.logger.exception('Invoice delete failed')
        return jsonify({'message' : 'The order could not be deleted. Nothing was changed.'}), 503
    finally:
        if cursor:
            cursor.close()
        mycon.close()

#Update (the inventory edit form. Sets a variant's stock to a new quantity and records the change as an Adjustment invoice.)
#Variant_ID and New_Quantity come from the edit form. The employee ID gets filled in from the session store.
#This replaces editing the Inventory table directly, so every stock change has an invoice behind it.
@app.route('/adjust/inventory', methods=['PUT'])
def adjustInventory():
    data = request.get_json(silent=True) or {}
    try:
        variant_id = int(data.get('Variant_ID'))
        new_quantity = int(data.get('New_Quantity'))
    except (ValueError, TypeError):
        return jsonify({'message': 'Variant_ID and New_Quantity must be integers.'}), 400
    if variant_id < 1 or new_quantity < 0:
        return jsonify({'message': 'Variant_ID must be positive and New_Quantity cannot be negative.'}), 400
    employee_id = int(g.employee['Employee_ID'])
    supplied_id = data.get('Employee_ID')
    if supplied_id is not None and str(supplied_id) != str(employee_id):
        return jsonify({'message': 'Employee_ID must match the signed-in account.'}), 403
    con = get_connection()
    if con is None:
        return jsonify({'message': 'Database unavailable.'}), 503
    cursor = None
    try:
        cursor = con.cursor(dictionary=True)
        cursor.execute('SELECT Quantity FROM Inventory WHERE Variant_ID=%s FOR UPDATE', (variant_id,))
        stock = cursor.fetchone()
        if stock is None:
            con.rollback()
            return jsonify({'message': 'No inventory record for that variant.'}), 404
        current = int(stock['Quantity'])
        difference = new_quantity - current
        if difference == 0:
            con.rollback()
            return jsonify({'message': f'Stock is already {current}. No changes made.'}), 200
        cursor.execute('SELECT Transaction_Type_ID FROM Transaction_Type WHERE Transaction_Type=%s', ('Adjustment',))
        adjustment = cursor.fetchone()
        if adjustment is None:
            con.rollback()
            return jsonify({'message': 'Adjustment transaction type is missing.'}), 503
        cursor.execute("""INSERT INTO Invoice
            (Transaction_Type_ID, Quantity_Change, Date, Variant_ID, Employee_ID)
            VALUES (%s, %s, %s, %s, %s)""",
            (adjustment['Transaction_Type_ID'], difference, date.today(), variant_id, employee_id))
        cursor.execute('UPDATE Inventory SET Quantity=%s WHERE Variant_ID=%s', (new_quantity, variant_id))
        con.commit()
        return jsonify({'message': f'Stock updated from {current} to {new_quantity}.'}), 200
    except Exception:
        con.rollback()
        app.logger.exception('Inventory adjustment failed')
        return jsonify({'message': 'Stock adjustment failed. Nothing was committed.'}), 503
    finally:
        if cursor:
            cursor.close()
        con.close()

#Below is the CRUD for the Color table
#Read (pulls all of the colors, used for the color dropdown)
@app.route('/show/all/colors', methods = ['GET'])
def showAllColors():
    mycon = get_connection()
    sql = "select * from Color"
    allColors = execute_read_query(mycon,sql)
    mycon.close()
    return jsonify(allColors)

#Create (adds a new color. The color name must be unique.)
@app.route('/create/color', methods = ['POST'])
def createColor():
    mycon = get_connection()
    userinput = request.get_json()
    color = userinput.get('Color')

    if not color:
        mycon.close()
        return jsonify({'message' : 'Color is required.'}), 400

    #checks to make sure the color isn't already in the table
    sql = "select Color_ID from Color where Color = %s"
    storedColor = execute_read_query(mycon, sql, (color,))
    if storedColor:
        mycon.close()
        return jsonify({'message' : 'That color already exists.'}), 409

    sql1 = "insert into Color (Color) values (%s)"
    execute_update_query(mycon, sql1, (color,))
    mycon.close()
    return jsonify({'message' : 'Color added.'}), 201

#Update (renames a color. The Color_ID must be sent in the request body.)
@app.route('/update/color', methods = ['PUT'])
def updateColor():
    mycon = get_connection()
    userinput = request.get_json()
    colorID = userinput.get('Color_ID')
    color = userinput.get('Color')

    if not colorID or not color:
        mycon.close()
        return jsonify({'message' : 'Color_ID and Color are required.'}), 400

    #checks that the color exists
    sql = "select Color_ID from Color where Color_ID = %s"
    storedColor = execute_read_query(mycon, sql, (colorID,))
    if not storedColor:
        mycon.close()
        return jsonify({'message' : 'Color not found. Try a different Color_ID.'}), 404

    #checks that a different color doesn't already have the new name
    sql1 = "select Color_ID from Color where Color = %s and Color_ID != %s"
    duplicate = execute_read_query(mycon, sql1, (color, colorID))
    if duplicate:
        mycon.close()
        return jsonify({'message' : 'That color already exists.'}), 409

    sql2 = "update Color set Color = %s where Color_ID = %s"
    execute_update_query(mycon, sql2, (color, colorID))
    mycon.close()
    return jsonify({'message' : 'Color updated.'})

#Delete (deletes a color. The Color_ID must be sent in the request body.)
@app.route('/delete/color', methods = ['DELETE'])
def deleteColor():
    mycon = get_connection()
    userinput = request.get_json()
    colorID = userinput.get('Color_ID')

    if not colorID:
        mycon.close()
        return jsonify({'message' : 'Color_ID is required.'}), 400

    #checks that the color exists
    sql = "select Color_ID from Color where Color_ID = %s"
    storedColor = execute_read_query(mycon, sql, (colorID,))
    if not storedColor:
        mycon.close()
        return jsonify({'message' : 'Color not found. Try a different Color_ID.'}), 404

    #a color used by a product variant can't be deleted
    sql1 = "select Variant_ID from Product_Variant where Color_ID = %s"
    variants = execute_read_query(mycon, sql1, (colorID,))
    if variants:
        mycon.close()
        return jsonify({'message' : "This color is used by product variants and can't be deleted."}), 409

    sql2 = "delete from Color where Color_ID = %s"
    execute_update_query(mycon, sql2, (colorID,))
    mycon.close()
    return jsonify({'message' : 'Color deleted.'})


#Below is the CRUD for the Size table
#Read (pulls all of the sizes, used for the size dropdown)
@app.route('/show/all/sizes', methods = ['GET'])
def showAllSizes():
    mycon = get_connection()
    sql = "select * from Size"
    allSizes = execute_read_query(mycon,sql)
    mycon.close()
    return jsonify(allSizes)

#Create (adds a new size. The size name must be unique.)
@app.route('/create/size', methods = ['POST'])
def createSize():
    mycon = get_connection()
    userinput = request.get_json()
    size = userinput.get('Size')

    if not size:
        mycon.close()
        return jsonify({'message' : 'Size is required.'}), 400

    #checks to make sure the size isn't already in the table
    sql = "select Size_ID from Size where Size = %s"
    storedSize = execute_read_query(mycon, sql, (size,))
    if storedSize:
        mycon.close()
        return jsonify({'message' : 'That size already exists.'}), 409

    sql1 = "insert into Size (Size) values (%s)"
    execute_update_query(mycon, sql1, (size,))
    mycon.close()
    return jsonify({'message' : 'Size added.'}), 201

#Update (renames a size. The Size_ID must be sent in the request body.)
@app.route('/update/size', methods = ['PUT'])
def updateSize():
    mycon = get_connection()
    userinput = request.get_json()
    sizeID = userinput.get('Size_ID')
    size = userinput.get('Size')

    if not sizeID or not size:
        mycon.close()
        return jsonify({'message' : 'Size_ID and Size are required.'}), 400

    #checks that the size exists
    sql = "select Size_ID from Size where Size_ID = %s"
    storedSize = execute_read_query(mycon, sql, (sizeID,))
    if not storedSize:
        mycon.close()
        return jsonify({'message' : 'Size not found. Try a different Size_ID.'}), 404

    #checks that a different size doesn't already have the new name
    sql1 = "select Size_ID from Size where Size = %s and Size_ID != %s"
    duplicate = execute_read_query(mycon, sql1, (size, sizeID))
    if duplicate:
        mycon.close()
        return jsonify({'message' : 'That size already exists.'}), 409

    sql2 = "update Size set Size = %s where Size_ID = %s"
    execute_update_query(mycon, sql2, (size, sizeID))
    mycon.close()
    return jsonify({'message' : 'Size updated.'})

#Delete (deletes a size. The Size_ID must be sent in the request body.)
@app.route('/delete/size', methods = ['DELETE'])
def deleteSize():
    mycon = get_connection()
    userinput = request.get_json()
    sizeID = userinput.get('Size_ID')

    if not sizeID:
        mycon.close()
        return jsonify({'message' : 'Size_ID is required.'}), 400

    #checks that the size exists
    sql = "select Size_ID from Size where Size_ID = %s"
    storedSize = execute_read_query(mycon, sql, (sizeID,))
    if not storedSize:
        mycon.close()
        return jsonify({'message' : 'Size not found. Try a different Size_ID.'}), 404

    #a size used by a product variant can't be deleted
    sql1 = "select Variant_ID from Product_Variant where Size_ID = %s"
    variants = execute_read_query(mycon, sql1, (sizeID,))
    if variants:
        mycon.close()
        return jsonify({'message' : "This size is used by product variants and can't be deleted."}), 409

    sql2 = "delete from Size where Size_ID = %s"
    execute_update_query(mycon, sql2, (sizeID,))
    mycon.close()
    return jsonify({'message' : 'Size deleted.'})


#Below is the CRUD for the Transaction_Type table
#Restock, Sale, and Adjustment are used by the invoice system, so they are protected from being renamed or deleted.
#Read (pulls all of the transaction types, used for the invoice dropdown)
@app.route('/show/all/transaction/types', methods = ['GET'])
def showAllTransactionTypes():
    mycon = get_connection()
    sql = "select * from Transaction_Type"
    allTransactionTypes = execute_read_query(mycon,sql)
    mycon.close()
    return jsonify(allTransactionTypes)

#Create (adds a new transaction type. The name must be unique.)
@app.route('/create/transaction/type', methods = ['POST'])
def createTransactionType():
    mycon = get_connection()
    userinput = request.get_json()
    transactionType = userinput.get('Transaction_Type')

    if not transactionType:
        mycon.close()
        return jsonify({'message' : 'Transaction_Type is required.'}), 400

    #checks to make sure the transaction type isn't already in the table
    sql = "select Transaction_Type_ID from Transaction_Type where Transaction_Type = %s"
    storedType = execute_read_query(mycon, sql, (transactionType,))
    if storedType:
        mycon.close()
        return jsonify({'message' : 'That transaction type already exists.'}), 409

    sql1 = "insert into Transaction_Type (Transaction_Type) values (%s)"
    execute_update_query(mycon, sql1, (transactionType,))
    mycon.close()
    return jsonify({'message' : 'Transaction type added.'}), 201

#Update (renames a transaction type. The Transaction_Type_ID must be sent in the request body.)
@app.route('/update/transaction/type', methods = ['PUT'])
def updateTransactionType():
    mycon = get_connection()
    userinput = request.get_json()
    transactionTypeID = userinput.get('Transaction_Type_ID')
    transactionType = userinput.get('Transaction_Type')

    if not transactionTypeID or not transactionType:
        mycon.close()
        return jsonify({'message' : 'Transaction_Type_ID and Transaction_Type are required.'}), 400

    #checks that the transaction type exists
    sql = "select Transaction_Type from Transaction_Type where Transaction_Type_ID = %s"
    storedType = execute_read_query(mycon, sql, (transactionTypeID,))
    if not storedType:
        mycon.close()
        return jsonify({'message' : 'Transaction type not found. Try a different Transaction_Type_ID.'}), 404

    #Restock, Sale, and Adjustment can't be renamed because the invoice system depends on them
    if storedType[0]['Transaction_Type'] in ('Restock', 'Sale', 'Adjustment'):
        mycon.close()
        return jsonify({'message' : "Restock, Sale, and Adjustment are used by the invoice system and can't be changed."}), 409

    #checks that a different transaction type doesn't already have the new name
    sql1 = "select Transaction_Type_ID from Transaction_Type where Transaction_Type = %s and Transaction_Type_ID != %s"
    duplicate = execute_read_query(mycon, sql1, (transactionType, transactionTypeID))
    if duplicate:
        mycon.close()
        return jsonify({'message' : 'That transaction type already exists.'}), 409

    sql2 = "update Transaction_Type set Transaction_Type = %s where Transaction_Type_ID = %s"
    execute_update_query(mycon, sql2, (transactionType, transactionTypeID))
    mycon.close()
    return jsonify({'message' : 'Transaction type updated.'})

#Delete (deletes a transaction type. The Transaction_Type_ID must be sent in the request body.)
@app.route('/delete/transaction/type', methods = ['DELETE'])
def deleteTransactionType():
    mycon = get_connection()
    userinput = request.get_json()
    transactionTypeID = userinput.get('Transaction_Type_ID')

    if not transactionTypeID:
        mycon.close()
        return jsonify({'message' : 'Transaction_Type_ID is required.'}), 400

    #checks that the transaction type exists
    sql = "select Transaction_Type from Transaction_Type where Transaction_Type_ID = %s"
    storedType = execute_read_query(mycon, sql, (transactionTypeID,))
    if not storedType:
        mycon.close()
        return jsonify({'message' : 'Transaction type not found. Try a different Transaction_Type_ID.'}), 404

    #Restock, Sale, and Adjustment can't be deleted because the invoice system depends on them
    if storedType[0]['Transaction_Type'] in ('Restock', 'Sale', 'Adjustment'):
        mycon.close()
        return jsonify({'message' : "Restock, Sale, and Adjustment are used by the invoice system and can't be deleted."}), 409

    #a transaction type used by an invoice can't be deleted
    sql1 = "select Invoice_ID from Invoice where Transaction_Type_ID = %s"
    invoices = execute_read_query(mycon, sql1, (transactionTypeID,))
    if invoices:
        mycon.close()
        return jsonify({'message' : "This transaction type is used by invoices and can't be deleted."}), 409

    sql2 = "delete from Transaction_Type where Transaction_Type_ID = %s"
    execute_update_query(mycon, sql2, (transactionTypeID,))
    mycon.close()
    return jsonify({'message' : 'Transaction type deleted.'})


# ==========================================
# 3. LOCATION CRUD
# Columns: Location_ID (PK), Location_Name
# ==========================================
@app.route('/api/locations', methods=['GET'])
def get_locations():
    mycon = get_connection()
    locations = execute_read_query(mycon, "SELECT * FROM Location", ())
    mycon.close()
    return jsonify(locations), 200

@app.route('/api/locations', methods=['POST'])
def add_location():
    data = request.json
    mycon = get_connection()
    query = "INSERT INTO Location (Location_Name) VALUES (%s)"
    params = (data['Location_Name'],)
    error = run_write(mycon, query, params)
    if error:
        return db_error_response(mycon, error)
    mycon.close()
    return jsonify({"message": "Location added!"}), 201

@app.route('/api/locations/<int:location_id>', methods=['PUT'])
def update_location(location_id):
    data = request.json
    mycon = get_connection()
    if not row_exists(mycon, "Location", "Location_ID", location_id):
        mycon.close()
        return jsonify({"message": "Location not found."}), 404
    query = "UPDATE Location SET Location_Name=%s WHERE Location_ID=%s"
    params = (data['Location_Name'], location_id)
    error = run_write(mycon, query, params)
    if error:
        return db_error_response(mycon, error)
    mycon.close()
    return jsonify({"message": "Location updated!"}), 200

@app.route('/api/locations/<int:location_id>', methods=['DELETE'])
def delete_location(location_id):
    mycon = get_connection()
    #a location with product variants can't be deleted because the variants reference its Location_ID
    variants = execute_read_query(mycon, "SELECT Variant_ID FROM Product_Variant WHERE Location_ID=%s", (location_id,))
    if variants:
        mycon.close()
        return jsonify({"message": "This location has product variants and can't be deleted."}), 409
    error = run_write(mycon, "DELETE FROM Location WHERE Location_ID=%s", (location_id,))
    if error:
        return db_error_response(mycon, error)
    mycon.close()
    return jsonify({"message": "Location deleted!"}), 200


# ==========================================
# 4. PRODUCT CRUD
# Columns: Product_ID (PK), Name, Category_ID (FK), Availability, Supplier_ID (FK)
# ==========================================
# Checks that the category and supplier a product points to actually exist. Returns an error response or None.
def check_product_links(mycon, data):
    if not row_exists(mycon, "Category", "Category_ID", data['Category_ID']):
        mycon.close()
        return jsonify({"message": "That category doesn't exist."}), 404
    if not row_exists(mycon, "Supplier", "Supplier_ID", data['Supplier_ID']):
        mycon.close()
        return jsonify({"message": "That supplier doesn't exist."}), 404
    return None

@app.route('/api/products', methods=['GET'])
def get_products():
    mycon = get_connection()
    products = execute_read_query(mycon, "SELECT * FROM Product", ())
    mycon.close()
    return jsonify(products), 200

@app.route('/api/products', methods=['POST'])
def add_product():
    data = request.json
    mycon = get_connection()
    link_error = check_product_links(mycon, data)
    if link_error:
        return link_error
    query = "INSERT INTO Product (Name, Category_ID, Availability, Supplier_ID) VALUES (%s, %s, %s, %s)"
    params = (data['Name'], data['Category_ID'], data['Availability'], data['Supplier_ID'])
    error = run_write(mycon, query, params)
    if error:
        return db_error_response(mycon, error)
    new_id = execute_read_query(mycon, "SELECT LAST_INSERT_ID() AS id")[0]["id"]
    mycon.close()
    return jsonify({"message": "Product added!", "Product_ID": new_id}), 201
@app.route('/api/products/<int:product_id>', methods=['PUT'])
def update_product(product_id):
    data = request.json
    mycon = get_connection()
    if not row_exists(mycon, "Product", "Product_ID", product_id):
        mycon.close()
        return jsonify({"message": "Product not found."}), 404
    link_error = check_product_links(mycon, data)
    if link_error:
        return link_error
    query = "UPDATE Product SET Name=%s, Category_ID=%s, Availability=%s, Supplier_ID=%s WHERE Product_ID=%s"
    params = (data['Name'], data['Category_ID'], data['Availability'], data['Supplier_ID'], product_id)
    error = run_write(mycon, query, params)
    if error:
        return db_error_response(mycon, error)
    mycon.close()
    return jsonify({"message": "Product updated!"}), 200

@app.route('/api/products/<int:product_id>', methods=['DELETE'])
def delete_product(product_id):
    mycon = get_connection()
    #a product with variants can't be deleted because the variants reference its Product_ID
    variants = execute_read_query(mycon, "SELECT Variant_ID FROM Product_Variant WHERE Product_ID=%s", (product_id,))
    if variants:
        mycon.close()
        return jsonify({"message": "This product has variants and can't be deleted."}), 409
    error = run_write(mycon, "DELETE FROM Product WHERE Product_ID=%s", (product_id,))
    if error:
        return db_error_response(mycon, error)
    mycon.close()
    return jsonify({"message": "Product deleted!"}), 200


# ==========================================
# 5. PRODUCT VARIANT CRUD
# Columns: Variant_ID (PK), Size_ID (FK), Color_ID (FK), Product_ID (FK), Location_ID (FK), Price, Cost
# ==========================================
@app.route('/api/product_variants', methods=['GET'])
def get_product_variants():
    mycon = get_connection()
    variants = execute_read_query(mycon, "SELECT * FROM Product_Variant", ())
    mycon.close()
    return jsonify(variants), 200

@app.route('/api/product_variants', methods=['POST'])
def add_product_variant():
    data = request.json
    mycon = get_connection()
    query = "INSERT INTO Product_Variant (Size_ID, Color_ID, Product_ID, Location_ID, Price, Cost) VALUES (%s, %s, %s, %s, %s, %s)"
    params = (data['Size_ID'], data['Color_ID'], data['Product_ID'], data['Location_ID'], data['Price'], data['Cost'])
    error = run_write(mycon, query, params)
    if error:
        return db_error_response(mycon, error)
    new_id = execute_read_query(mycon, "SELECT LAST_INSERT_ID() AS id")[0]["id"]
    mycon.close()
    return jsonify({"message": "Product Variant added!", "Variant_ID": new_id}), 201

@app.route('/api/product_variants/<int:variant_id>', methods=['PUT'])
def update_product_variant(variant_id):
    data = request.json
    mycon = get_connection()
    if not row_exists(mycon, "Product_Variant", "Variant_ID", variant_id):
        mycon.close()
        return jsonify({"message": "Product variant not found."}), 404
    query = "UPDATE Product_Variant SET Size_ID=%s, Color_ID=%s, Product_ID=%s, Location_ID=%s, Price=%s, Cost=%s WHERE Variant_ID=%s"
    params = (data['Size_ID'], data['Color_ID'], data['Product_ID'], data['Location_ID'], data['Price'], data['Cost'], variant_id)
    error = run_write(mycon, query, params)
    if error:
        return db_error_response(mycon, error)
    mycon.close()
    return jsonify({"message": "Product Variant updated!"}), 200

@app.route('/api/product_variants/<int:variant_id>', methods=['DELETE'])
def delete_product_variant(variant_id):
    mycon = get_connection()
    #a variant with orders (invoices) or stock can't be deleted, so its history and stock are never lost.
    #(in practice: a variant added by mistake with 0 starting stock and never sold or adjusted can be deleted.)
    #every variant gets an Inventory row when it's created, so an empty one (0 in stock) is removed along with it.
    invoices = execute_read_query(mycon, "SELECT Invoice_ID FROM Invoice WHERE Variant_ID=%s", (variant_id,))
    if invoices:
        mycon.close()
        return jsonify({"message": "This variant has orders, so it can't be deleted. It keeps the sales and stock history."}), 409
    stock = execute_read_query(mycon, "SELECT COALESCE(SUM(Quantity), 0) AS units FROM Inventory WHERE Variant_ID=%s", (variant_id,))
    if stock and int(stock[0]['units'] or 0) > 0:
        mycon.close()
        return jsonify({"message": "This variant still has %s in stock, so it can't be deleted." % int(stock[0]['units'])}), 409
    error = run_write(mycon, "DELETE FROM Inventory WHERE Variant_ID=%s", (variant_id,))
    if error:
        return db_error_response(mycon, error)
    error = run_write(mycon, "DELETE FROM Product_Variant WHERE Variant_ID=%s", (variant_id,))
    if error:
        return db_error_response(mycon, error)
    mycon.close()
    return jsonify({"message": "Product Variant deleted!"}), 200


# ==========================================
# 6. INVENTORY CRUD
# Columns: Inventory_ID (PK), Quantity, Variant_ID (FK)
# ==========================================
@app.route('/api/inventory', methods=['GET'])
def get_inventory():
    mycon = get_connection()
    inventory = execute_read_query(mycon, "SELECT * FROM Inventory", ())
    mycon.close()
    return jsonify(inventory), 200

@app.route('/api/inventory', methods=['POST'])
def add_inventory():
    data = request.json
    mycon = get_connection()
    #each variant can only have one inventory row, otherwise the invoice routes update both and the stock goes wrong
    existing = execute_read_query(mycon, "SELECT Inventory_ID FROM Inventory WHERE Variant_ID=%s", (data['Variant_ID'],))
    if existing:
        mycon.close()
        return jsonify({"message": "This variant already has an inventory record."}), 409
    query = "INSERT INTO Inventory (Quantity, Variant_ID) VALUES (%s, %s)"
    params = (data['Quantity'], data['Variant_ID'])
    error = run_write(mycon, query, params)
    if error:
        return db_error_response(mycon, error)
    mycon.close()
    return jsonify({"message": "Inventory recorded!"}), 201

#There is no update route here on purpose. Stock changes go through PUT /adjust/inventory (in the Invoice section),
#which records every change as an Adjustment invoice so the stock always has a record behind it.

@app.route('/api/inventory/<int:inventory_id>', methods=['DELETE'])
def delete_inventory(inventory_id):
    mycon = get_connection()
    error = run_write(mycon, "DELETE FROM Inventory WHERE Inventory_ID=%s", (inventory_id,))
    if error:
        return db_error_response(mycon, error)
    mycon.close()
    return jsonify({"message": "Inventory record deleted!"}), 200


#Below is the API for the best sellers report.
#It counts how many of each item sold (Sale invoices only) and ranks them from the most sold to the least.
#It returns two lists: by_product (all sizes and colors added together) and by_item (each size and color separately).
#Items that haven't sold are included at the bottom with 0, so the owner can also see what isn't selling.
#Optional: ?days=30 only counts sales from the last 30 days. Leave it out (or days=0) for all time.
@app.route('/report/best/sellers', methods = ['GET'])
def bestSellers():
    try:
        days = int(request.args.get('days', 0))
    except ValueError:
        return jsonify({'message': 'days must be a whole number.'}), 400
    if days < 0:
        return jsonify({'message': 'days cannot be negative.'}), 400

    #Sales are saved as negative Quantity_Change (a sale of 3 is -3), so -SUM gives the number sold.
    dateFilter = ''
    params = ()
    if days > 0:
        dateFilter = 'and i.Date >= %s'
        from datetime import timedelta
        params = (date.today() - timedelta(days = days - 1),)
    salesPerVariant = """select i.Variant_ID, -sum(i.Quantity_Change) as Units
        from Invoice i
        join Transaction_Type t on t.Transaction_Type_ID = i.Transaction_Type_ID
        where t.Transaction_Type = 'Sale' and i.Quantity_Change < 0 """ + dateFilter + """
        group by i.Variant_ID"""

    mycon = get_connection()
    if mycon is None:
        return jsonify({'message': 'Database unavailable.'}), 503

    sql = """select p.Product_ID, p.Name as Product, c.Category,
            coalesce(sum(sales.Units), 0) as Units_Sold,
            coalesce(sum(sales.Units * v.Price), 0) as Revenue
        from Product p
        join Category c on c.Category_ID = p.Category_ID
        left join Product_Variant v on v.Product_ID = p.Product_ID
        left join (""" + salesPerVariant + """) sales on sales.Variant_ID = v.Variant_ID
        group by p.Product_ID, p.Name, c.Category
        order by Units_Sold desc, Revenue desc, p.Name"""
    byProduct = execute_read_query(mycon, sql, params)

    sql2 = """select v.Variant_ID, p.Name as Product, s.Size, co.Color, v.Price,
            coalesce(sales.Units, 0) as Units_Sold,
            coalesce(sales.Units, 0) * v.Price as Revenue
        from Product_Variant v
        join Product p on p.Product_ID = v.Product_ID
        join Size s on s.Size_ID = v.Size_ID
        join Color co on co.Color_ID = v.Color_ID
        left join (""" + salesPerVariant + """) sales on sales.Variant_ID = v.Variant_ID
        order by Units_Sold desc, Revenue desc, p.Name, s.Size, co.Color"""
    byItem = execute_read_query(mycon, sql2, params)
    mycon.close()

    if byProduct is None or byItem is None:
        return jsonify({'message': 'The best sellers report could not be loaded.'}), 503

    #Give each row a rank. Items that sold the same amount share a rank (1, 2, 2, 4).
    for rows in (byProduct, byItem):
        rank = 0
        previousUnits = None
        for position, row in enumerate(rows, start = 1):
            row['Units_Sold'] = int(row['Units_Sold'])
            row['Revenue'] = float(row['Revenue'])
            if 'Price' in row:
                row['Price'] = float(row['Price'])
            if row['Units_Sold'] != previousUnits:
                rank = position
                previousUnits = row['Units_Sold']
            row['Rank'] = rank

    totalUnits = sum(row['Units_Sold'] for row in byProduct)
    totalRevenue = sum(row['Revenue'] for row in byProduct)
    return jsonify({
        'days' : days,
        'total_units' : totalUnits,
        'total_revenue' : totalRevenue,
        'by_product' : byProduct,
        'by_item' : byItem
    }), 200


# Add reporting endpoints, then protect all routes except health/login.
current_threshold = register_reporting_routes(app, get_db_connection, execute_read_query)
install_auth(app, get_db_connection, execute_read_query)
# Edit history (backend/history.py) is registered after install_auth, so it knows who is making each change.
register_history(app, get_db_connection, execute_read_query, current_threshold)

# --- START THE API ---
if __name__ == '__main__':
    app.run(port=int(os.getenv("API_PORT", "5000")))