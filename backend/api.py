import os

import flask
from flask import jsonify
from flask_cors import CORS

import creds
from sql import DBconnection, execute_read_query

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


app.run(port=int(os.getenv("API_PORT", "5000")))
