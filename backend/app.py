import mysql.connector
from flask import Flask, jsonify
from flask_cors import CORS

import config

app = Flask(__name__)
CORS(app)


def get_db():
    return mysql.connector.connect(**config.DB_CONFIG)


@app.get("/api/health")
def health():
    return jsonify(status="ok", env=config.APP_ENV)


@app.get("/api/db-check")
def db_check():
    try:
        conn = get_db()
        conn.close()
        return jsonify(database=config.DB_CONFIG["database"], connected=True)
    except mysql.connector.Error as err:
        return jsonify(connected=False, error=str(err)), 500


if __name__ == "__main__":
    app.run(port=config.API_PORT, debug=config.DEBUG)
