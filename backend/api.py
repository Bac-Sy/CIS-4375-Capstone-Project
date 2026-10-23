import os


import flask
from flask import jsonify
from flask_cors import CORS
from flask import request

#importing database credentials
import creds
from sql import DBconnection, execute_read_query
from sql import execute_update_query

#needed for password hashing
from argon2 import PasswordHasher
from argon2 import exceptions


app = flask.Flask(__name__)
CORS(app, supports_credentials=True,
     resources={r"/*": {"origins": os.getenv("FRONTEND_URL", "http://localhost:8080")}})
app.config['DEBUG'] = creds.APP_ENV == "development"


def get_connection():
    mycreds = creds.mycreds()
    return DBconnection(mycreds.hostname, mycreds.username, mycreds.password, mycreds.database)


# Health check: confirms the API is running and which environment it's in.
@app.route("/health", methods=['GET'])
def health():
    return jsonify({"status": "ok", "env": creds.APP_ENV})


# Database check: confirms the API can reach the RDS database.
@app.route("/db/check", methods=['GET'])
def db_check():
    mycon = get_connection()
    if mycon is None:
        return jsonify({"connected": False}), 500
    result = execute_read_query(mycon, "select database() as db")
    mycon.close()
    return jsonify({"connected": True, "database": result[0]["db"]})

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
    sql = "select First_Name, Last_Name, Role, Username, Email from Employee where Email = '%s'" % (email)
    employeeInformation = execute_read_query(mycon,sql)
    mycon.close()
    if (employeeInformation):
        return jsonify (employeeInformation)
    else:
        return jsonify({"message": "No employee found"}), 404


#Create (Add a new employee to the database)
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

        #check to make sure the email and username are unique to the DB
        if storedEmail:
            mycon.close()
            return jsonify({'message' : 'An account with this email already exists. Try a different email address.'}), 409
        elif storedUsername:
            mycon.close()
            return jsonify ({'message': 'An account with that username already exists. Try a different username.'}), 409
        else: 
            #password hashing below
            ph = PasswordHasher()
            hashedPassword = ph.hash(password)
            #inserting new employee
            sql = "insert into Employee (First_Name, Last_Name, Role, Username, Email, Password_Hash) Values ('%s','%s','%s','%s','%s','%s')" % (firstName, lastName, role, username, email,hashedPassword )
            execute_update_query(mycon,sql)
            mycon.close()
            return jsonify({'message': 'Employee successfully added to the system.'}), 201

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

#Delete
@app.route('/delete/employee',methods=['DELETE'])
def deleteEmployee():
    mycon = get_connection()
    userinput = request.get_json()
    email = userinput['Email']

    #checks that the employee exists
    sql = "select Employee_ID from Employee where Email = '%s'" % (email)
    employee = execute_read_query(mycon,sql)
    if not employee:
        mycon.close()
        return jsonify({'message' : 'Employee not found. Try a different email.'}), 404

    #an employee with invoices can't be deleted because the invoices reference their Employee_ID
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

    #This part verifies that the username is in the system. If it is, it pulls the other value's in the Employee table that belong to that user 
    sql = "select Email, Password_Hash, First_Name, Last_Name, Role, Username, Employee_ID from Employee where Username = '%s'" % (username)
    results = execute_read_query(mycon,sql)
    mycon.close()
    if not results:
        return jsonify({'message' : 'Username not found, try again'}), 404
    #These stored values can be used in the node server for session management. The values get sent back in the return statement and get saved in the session store. 
    storedEmail = results[0]['Email']
    storedPasswordHash = results[0]['Password_Hash']
    storedFirstName = results[0]['First_Name']
    storedLastName = results[0]['Last_Name']
    storedRole = results[0]['Role']
    storedUsername = results[0]['Username']
    storedEmployeeID = results[0]['Employee_ID']

    ph = PasswordHasher()

# The funtion verifies if the password matches the hash. The username and password combination must match, or the login fails.
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

#Below is the CRUD for the Invoice table.
#Read (The api to read a single entry in the Invoice table)
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

#Read (The api to pull all of the invoices from the invoice table.)
@app.route('/show/all/invoices', methods = ['GET'])
def showAllInvoices():
    mycon = get_connection()
    sql ="select * from Invoice"
    allInvoices = execute_read_query(mycon,sql)
    mycon.close()
    return jsonify(allInvoices)

#Create (adding a new invoice to the Invoice table.)
@app.route('/create/invoice', methods =['POST'])
def createInvoice():
    mycon = get_connection()
    userinput = request.get_json()
    transactionTypeID = userinput['Transaction_Type_ID']
    quantityChange = int(userinput['Quantity_Change']) #Needs to be a positive number for additions and a negative number for removals. 
    variantID = userinput['Variant_ID']
    employeeID = userinput['Employee_ID'] #the employee ID gets filled in from the session store. the user does not have to manually input this.

    #these get used below to verify that these IDs exist in the system. If they do not, then the call fails. 
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


    #The code below here checks to make sure the product variant exists.
    sql3 = "select Quantity from Inventory where Variant_ID = '%s'" % (variantID)
    stock = execute_read_query(mycon,sql3)
    if not stock:
        mycon.close()
        return jsonify({'message': 'No inventory record for that variant'}), 404
    #below here checks to make sure that the current stock plus the quantity change from the user is > 0.
    #If it is not, then the server rejects the request.
    currentStock = stock[0]['Quantity']
    if currentStock + quantityChange < 0:
        mycon.close()
        return jsonify({'message' : 'There is not enough stock to complete this request. %s items are in stock.' % (currentStock)}), 400
    #This updates the inventoy amount based on the amount added or removed
    sql4 = "insert into Invoice (Transaction_Type_ID, Quantity_Change, Date, Variant_ID, Employee_ID) values ('%s', '%s', CURDATE(), '%s', '%s')" % (transactionTypeID, quantityChange, variantID, employeeID)
    execute_update_query(mycon, sql4)
    sql5 = "update Inventory set Quantity = Quantity + %s where Variant_ID = '%s'" % (quantityChange, variantID)
    execute_update_query(mycon, sql5)

    mycon.close()
    return jsonify({'message' : 'Invoice created and inventory updated.'}), 201

#Update (updates an invoice. The Invoice_ID must be sent in the request body to identify which invoice to change.)
@app.route('/update/invoice', methods=['PUT'])
def updateInvoice():
    mycon = get_connection()
    userinput = request.get_json()
    invoiceID = userinput.get('Invoice_ID')
    transactionTypeID = userinput.get('Transaction_Type_ID')
    quantityChange = userinput.get('Quantity_Change') #positive for additions, negative for removals

    if not invoiceID:
        mycon.close()
        return jsonify({'message' : 'Invoice_ID is required.'}), 400

    #pulls the original invoice so the inventory can be corrected by the difference
    sql = "select Quantity_Change, Variant_ID from Invoice where Invoice_ID = '%s'" % (invoiceID)
    invoice = execute_read_query(mycon,sql)
    if not invoice:
        mycon.close()
        return jsonify({'message' : 'Invoice not found. Try a different Invoice_ID.'}), 404

    oldQuantity = invoice[0]['Quantity_Change']
    variantID = invoice[0]['Variant_ID']

    #checks that the new transaction type exists
    if transactionTypeID:
        sql1 = "select Transaction_Type_ID from Transaction_Type where Transaction_Type_ID = '%s'" % (transactionTypeID)
        transaction = execute_read_query(mycon,sql1)
        if not transaction:
            mycon.close()
            return jsonify({'message' : 'Transaction type does not exist. Try a different transaction type.'}), 404

    #checks that the new quantity won't take the stock below 0
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

    #if all checks passe, then the update will be applied to the system.
    if transactionTypeID:
        sql3 = "update Invoice set Transaction_Type_ID = '%s' where Invoice_ID = '%s'" % (transactionTypeID, invoiceID)
        execute_update_query(mycon,sql3)

    if quantityChange is not None:
        sql4 = "update Invoice set Quantity_Change = '%s' where Invoice_ID = '%s'" % (quantityChange, invoiceID)
        execute_update_query(mycon,sql4)
        #corrects the inventory by the difference between the new and old quantity
        sql5 = "update Inventory set Quantity = Quantity + %s where Variant_ID = '%s'" % (difference, variantID)
        execute_update_query(mycon,sql5)

    mycon.close()
    return jsonify({'message' : 'Invoice updated.'})

#Delete (deletes an invoice and undoes its change to the inventory. The Invoice_ID must be sent in the request body.)
@app.route('/delete/invoice', methods=['DELETE'])
def deleteInvoice():
    mycon = get_connection()
    userinput = request.get_json()
    invoiceID = userinput.get('Invoice_ID')

    if not invoiceID:
        mycon.close()
        return jsonify({'message' : 'Invoice_ID is required.'}), 400

    #pulls the invoice so its quantity can be taken back out of the inventory
    sql = "select Quantity_Change, Variant_ID from Invoice where Invoice_ID = '%s'" % (invoiceID)
    invoice = execute_read_query(mycon,sql)
    if not invoice:
        mycon.close()
        return jsonify({'message' : 'Invoice not found. Try a different Invoice_ID.'}), 404

    oldQuantity = invoice[0]['Quantity_Change']
    variantID = invoice[0]['Variant_ID']

    #undoing a restock removes stock, so this checks the stock won't go below 0
    sql1 = "select Quantity from Inventory where Variant_ID = '%s'" % (variantID)
    stock = execute_read_query(mycon,sql1)
    if not stock:
        mycon.close()
        return jsonify({'message' : 'No inventory record for that variant'}), 404
    currentStock = stock[0]['Quantity']
    if currentStock - oldQuantity < 0:
        mycon.close()
        return jsonify({'message' : 'This invoice cannot be deleted. Undoing it would take the stock below 0. %s items are in stock.' % (currentStock)}), 400

    #deletes the invoice and reverses its change to the inventory
    sql2 = "delete from Invoice where Invoice_ID = '%s'" % (invoiceID)
    execute_update_query(mycon,sql2)
    sql3 = "update Inventory set Quantity = Quantity - %s where Variant_ID = '%s'" % (oldQuantity, variantID)
    execute_update_query(mycon,sql3)

    mycon.close()
    return jsonify({'message' : 'Invoice deleted and inventory updated.'})

#Update (the inventory edit form. Sets a variant's stock to a new quantity and records the change as an Adjustment invoice.)
#Variant_ID and New_Quantity come from the edit form. The employee ID gets filled in from the session store.
#This replaces editing the Inventory table directly, so every stock change has an invoice behind it.
@app.route('/adjust/inventory', methods=['PUT'])
def adjustInventory():
    mycon = get_connection()
    userinput = request.get_json()
    variantID = userinput.get('Variant_ID')
    newQuantity = userinput.get('New_Quantity')
    employeeID = userinput.get('Employee_ID')

    if not variantID or newQuantity is None or not employeeID:
        mycon.close()
        return jsonify({'message' : 'Variant_ID, New_Quantity, and Employee_ID are required.'}), 400

    newQuantity = int(newQuantity)
    if newQuantity < 0:
        mycon.close()
        return jsonify({'message' : 'New_Quantity cannot be below 0.'}), 400

    #pulls the current stock so the difference can be worked out
    sql = "select Quantity from Inventory where Variant_ID = '%s'" % (variantID)
    stock = execute_read_query(mycon,sql)
    if not stock:
        mycon.close()
        return jsonify({'message' : 'No inventory record for that variant'}), 404

    #checks that the employee exists
    sql1 = "select Employee_ID from Employee where Employee_ID = '%s'" % (employeeID)
    employee = execute_read_query(mycon,sql1)
    if not employee:
        mycon.close()
        return jsonify({'message' : 'Employee does not exist. Try another ID.'}), 404

    #looks up the Adjustment type by name, since its ID is different on each database
    sql2 = "select Transaction_Type_ID from Transaction_Type where Transaction_Type = 'Adjustment'"
    adjustment = execute_read_query(mycon,sql2)
    if not adjustment:
        mycon.close()
        return jsonify({'message' : 'The Adjustment transaction type is missing from the database.'}), 500

    currentStock = stock[0]['Quantity']
    difference = newQuantity - currentStock
    adjustmentID = adjustment[0]['Transaction_Type_ID']

    #if the count matches the stock already in the system, there is nothing to record
    if difference == 0:
        mycon.close()
        return jsonify({'message' : 'Stock is already %s. No changes made.' % (currentStock)})

    #records the change as an Adjustment invoice and sets the stock to the new quantity
    sql3 = "insert into Invoice (Transaction_Type_ID, Quantity_Change, Date, Variant_ID, Employee_ID) values ('%s', '%s', CURDATE(), '%s', '%s')" % (adjustmentID, difference, variantID, employeeID)
    execute_update_query(mycon,sql3)
    sql4 = "update Inventory set Quantity = '%s' where Variant_ID = '%s'" % (newQuantity, variantID)
    execute_update_query(mycon,sql4)

    mycon.close()
    return jsonify({'message' : 'Stock updated from %s to %s.' % (currentStock, newQuantity)})


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
    sql = "select Color_ID from Color where Color = '%s'" % (color)
    storedColor = execute_read_query(mycon,sql)
    if storedColor:
        mycon.close()
        return jsonify({'message' : 'That color already exists.'}), 409

    sql1 = "insert into Color (Color) values ('%s')" % (color)
    execute_update_query(mycon,sql1)
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
    sql = "select Color_ID from Color where Color_ID = '%s'" % (colorID)
    storedColor = execute_read_query(mycon,sql)
    if not storedColor:
        mycon.close()
        return jsonify({'message' : 'Color not found. Try a different Color_ID.'}), 404

    #checks that a different color doesn't already have the new name
    sql1 = "select Color_ID from Color where Color = '%s' and Color_ID != '%s'" % (color, colorID)
    duplicate = execute_read_query(mycon,sql1)
    if duplicate:
        mycon.close()
        return jsonify({'message' : 'That color already exists.'}), 409

    sql2 = "update Color set Color = '%s' where Color_ID = '%s'" % (color, colorID)
    execute_update_query(mycon,sql2)
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
    sql = "select Color_ID from Color where Color_ID = '%s'" % (colorID)
    storedColor = execute_read_query(mycon,sql)
    if not storedColor:
        mycon.close()
        return jsonify({'message' : 'Color not found. Try a different Color_ID.'}), 404

    #a color used by a product variant can't be deleted
    sql1 = "select Variant_ID from Product_Variant where Color_ID = '%s'" % (colorID)
    variants = execute_read_query(mycon,sql1)
    if variants:
        mycon.close()
        return jsonify({'message' : "This color is used by product variants and can't be deleted."}), 409

    sql2 = "delete from Color where Color_ID = '%s'" % (colorID)
    execute_update_query(mycon,sql2)
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
    sql = "select Size_ID from Size where Size = '%s'" % (size)
    storedSize = execute_read_query(mycon,sql)
    if storedSize:
        mycon.close()
        return jsonify({'message' : 'That size already exists.'}), 409

    sql1 = "insert into Size (Size) values ('%s')" % (size)
    execute_update_query(mycon,sql1)
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
    sql = "select Size_ID from Size where Size_ID = '%s'" % (sizeID)
    storedSize = execute_read_query(mycon,sql)
    if not storedSize:
        mycon.close()
        return jsonify({'message' : 'Size not found. Try a different Size_ID.'}), 404

    #checks that a different size doesn't already have the new name
    sql1 = "select Size_ID from Size where Size = '%s' and Size_ID != '%s'" % (size, sizeID)
    duplicate = execute_read_query(mycon,sql1)
    if duplicate:
        mycon.close()
        return jsonify({'message' : 'That size already exists.'}), 409

    sql2 = "update Size set Size = '%s' where Size_ID = '%s'" % (size, sizeID)
    execute_update_query(mycon,sql2)
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
    sql = "select Size_ID from Size where Size_ID = '%s'" % (sizeID)
    storedSize = execute_read_query(mycon,sql)
    if not storedSize:
        mycon.close()
        return jsonify({'message' : 'Size not found. Try a different Size_ID.'}), 404

    #a size used by a product variant can't be deleted
    sql1 = "select Variant_ID from Product_Variant where Size_ID = '%s'" % (sizeID)
    variants = execute_read_query(mycon,sql1)
    if variants:
        mycon.close()
        return jsonify({'message' : "This size is used by product variants and can't be deleted."}), 409

    sql2 = "delete from Size where Size_ID = '%s'" % (sizeID)
    execute_update_query(mycon,sql2)
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
    sql = "select Transaction_Type_ID from Transaction_Type where Transaction_Type = '%s'" % (transactionType)
    storedType = execute_read_query(mycon,sql)
    if storedType:
        mycon.close()
        return jsonify({'message' : 'That transaction type already exists.'}), 409

    sql1 = "insert into Transaction_Type (Transaction_Type) values ('%s')" % (transactionType)
    execute_update_query(mycon,sql1)
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
    sql = "select Transaction_Type from Transaction_Type where Transaction_Type_ID = '%s'" % (transactionTypeID)
    storedType = execute_read_query(mycon,sql)
    if not storedType:
        mycon.close()
        return jsonify({'message' : 'Transaction type not found. Try a different Transaction_Type_ID.'}), 404

    #Restock, Sale, and Adjustment can't be renamed because the invoice system depends on them
    if storedType[0]['Transaction_Type'] in ('Restock', 'Sale', 'Adjustment'):
        mycon.close()
        return jsonify({'message' : "Restock, Sale, and Adjustment are used by the invoice system and can't be changed."}), 409

    #checks that a different transaction type doesn't already have the new name
    sql1 = "select Transaction_Type_ID from Transaction_Type where Transaction_Type = '%s' and Transaction_Type_ID != '%s'" % (transactionType, transactionTypeID)
    duplicate = execute_read_query(mycon,sql1)
    if duplicate:
        mycon.close()
        return jsonify({'message' : 'That transaction type already exists.'}), 409

    sql2 = "update Transaction_Type set Transaction_Type = '%s' where Transaction_Type_ID = '%s'" % (transactionType, transactionTypeID)
    execute_update_query(mycon,sql2)
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
    sql = "select Transaction_Type from Transaction_Type where Transaction_Type_ID = '%s'" % (transactionTypeID)
    storedType = execute_read_query(mycon,sql)
    if not storedType:
        mycon.close()
        return jsonify({'message' : 'Transaction type not found. Try a different Transaction_Type_ID.'}), 404

    #Restock, Sale, and Adjustment can't be deleted because the invoice system depends on them
    if storedType[0]['Transaction_Type'] in ('Restock', 'Sale', 'Adjustment'):
        mycon.close()
        return jsonify({'message' : "Restock, Sale, and Adjustment are used by the invoice system and can't be deleted."}), 409

    #a transaction type used by an invoice can't be deleted
    sql1 = "select Invoice_ID from Invoice where Transaction_Type_ID = '%s'" % (transactionTypeID)
    invoices = execute_read_query(mycon,sql1)
    if invoices:
        mycon.close()
        return jsonify({'message' : "This transaction type is used by invoices and can't be deleted."}), 409

    sql2 = "delete from Transaction_Type where Transaction_Type_ID = '%s'" % (transactionTypeID)
    execute_update_query(mycon,sql2)
    mycon.close()
    return jsonify({'message' : 'Transaction type deleted.'})


app.run(port=int(os.getenv("API_PORT", "5000")))
