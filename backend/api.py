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
from argon2 import verify_password


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
    sql = "delete from Employee where Email = '%s' " % (email)
    execute_update_query(mycon,sql)
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
    sql = "select Email, Password_Hash, First_Name, Last_Name, Role, Username from Employee where Username = '%s'" % (username)
    results = execute_read_query(mycon,sql)
    mycon.close()
    if not results:
        return jsonify({'message' : 'Username not found, try again'}), 404
    #These stored values can be used in the node server for session management. 
    storedEmail = results[0]['Email']
    storedPasswordHash = results[0]['Password_Hash']
    storedFirstName = results[0]['First_Name']
    storedLastName = results[0]['Last_Name']
    storedRole = results[0]['Role']
    storedUsername = results[0]['Username']

    ph = PasswordHasher()

# The funtion verifies if the password matches the hash. The username and password combination must match, or the login fails.
    try:
        if (ph.verify(storedPasswordHash, password)):
            return jsonify({
                    "message" : "Login Successful",
                    "Email" : storedEmail,
                    "First_Name" : storedFirstName,
                    "Last_Name" : storedLastName,
                    "Role" : storedRole,
                    "Username" : storedUsername
            }), 200
        
    except exceptions.VerificationError: 
        return jsonify({'message':'Invalid password.' }), 401
    except Exception as e:
        return jsonify({'message' : 'An error occurred'}), 500

#Below is the CRUD for the Invoice table.

app.run(port=int(os.getenv("API_PORT", "5000")))
