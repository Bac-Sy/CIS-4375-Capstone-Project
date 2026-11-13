"""Authentication gate for the existing Flask API.

The Express server authenticates employees using /login and stores the returned
short-lived token server-side in the Express session. No browser gets the token.
All other Flask endpoints require the signed token, including direct writes.
"""
import base64
import hashlib
import hmac
import json
import os
import time
from flask import g, jsonify, request

TOKEN_AGE_SECONDS = 8 * 60 * 60
PUBLIC_ENDPOINTS = frozenset({'/health', '/login', '/auth/login'})

# Employee_ID -> (employee row, time it expires). Role changes or deleted accounts
# take effect within this many seconds; updating or deleting an employee clears it right away.
EMPLOYEE_CACHE_SECONDS = 60
_employee_cache = {}


def forget_employee(employee_id=None):
    """Clear the cached login info for one employee, or everyone (None)."""
    if employee_id is None:
        _employee_cache.clear()
    else:
        _employee_cache.pop(int(employee_id), None)


def auth_secret():
    value = os.getenv('AUTH_TOKEN_SECRET', '')
    return value.encode('utf-8') if len(value) >= 32 and not value.startswith('REPLACE_') else None


def _encode(raw):
    return base64.urlsafe_b64encode(raw).rstrip(b'=').decode('ascii')


def _decode(value):
    return base64.urlsafe_b64decode(value + '=' * (-len(value) % 4))


def issue_token(employee_id):
    secret = auth_secret()
    if not secret:
        raise RuntimeError('AUTH_TOKEN_SECRET must be set to a random 32+ character value in backend/.env.<environment>.')
    payload = _encode(json.dumps({
        'sub': str(employee_id),
        'exp': int(time.time()) + TOKEN_AGE_SECONDS
    }, separators=(',', ':')).encode('utf-8'))
    signature = _encode(hmac.new(secret, payload.encode('ascii'), hashlib.sha256).digest())
    return payload + '.' + signature


def verify_token(token):
    secret = auth_secret()
    if not secret or not isinstance(token, str) or token.count('.') != 1:
        return None
    try:
        payload, signature = token.split('.', 1)
        correct = _encode(hmac.new(secret, payload.encode('ascii'), hashlib.sha256).digest())
        if not hmac.compare_digest(correct, signature):
            return None
        decoded = json.loads(_decode(payload))
        sub = decoded.get('sub')
        if not str(sub).isdigit() or int(sub) <= 0:
            return None
        if type(decoded.get('exp')) is not int or decoded['exp'] <= int(time.time()):
            return None
        return int(sub)
    except (ValueError, TypeError, UnicodeError):
        return None


def install_auth(app, connect, read_query):
    """Apply to all routes except public health and login; check current DB role."""
    @app.before_request
    def authenticate_request():
        if request.method == 'OPTIONS' or request.path in PUBLIC_ENDPOINTS:
            return None
        if not auth_secret():
            return jsonify({'message': 'Backend AUTH_TOKEN_SECRET has not been configured.'}), 503
        authorization = request.headers.get('Authorization', '')
        if not authorization.startswith('Bearer '):
            return jsonify({'message': 'Authentication required.'}), 401
        employee_id = verify_token(authorization[7:])
        if employee_id is None:
            return jsonify({'message': 'Session expired or invalid. Log in again.'}), 401
        # A page makes several API calls at once, so the employee lookup is remembered for
        # EMPLOYEE_CACHE_SECONDS instead of querying the database on every call.
        cached = _employee_cache.get(employee_id)
        if cached and cached[1] > time.monotonic():
            matches = [cached[0]]
        else:
            con = connect()
            if con is None:
                return jsonify({'message': 'Database unavailable.'}), 503
            try:
                matches = read_query(con,
                    'SELECT Employee_ID, First_Name, Last_Name, Username, Email, Role '
                    'FROM Employee WHERE Employee_ID=%s', (employee_id,))
            except Exception:
                app.logger.exception('Authentication database query failed')
                return jsonify({'message': 'Authentication database unavailable.'}), 503
            finally:
                con.close()
            if matches is None:
                return jsonify({'message': 'Authentication database unavailable.'}), 503
            if not matches:
                _employee_cache.pop(employee_id, None)
                return jsonify({'message': 'Employee account no longer exists.'}), 401
            _employee_cache[employee_id] = (matches[0], time.monotonic() + EMPLOYEE_CACHE_SECONDS)
        g.employee = matches[0]
        is_manager = str(g.employee.get('Role', '')).casefold() == 'manager'
        if request.method == 'DELETE' and not is_manager:
            return jsonify({'message': 'Manager role required to delete records.'}), 403
        if request.path in ('/add/employee', '/update/employee', '/delete/employee') and not is_manager:
            return jsonify({'message': 'Manager role required for employee administration.'}), 403
        return None
