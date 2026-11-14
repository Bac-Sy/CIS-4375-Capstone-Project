"""Offline authentication-gate tests; requires no Flask or database server."""
import ast
import importlib.util
import os
import pathlib
import sys
import types

root = pathlib.Path(__file__).resolve().parent.parent.parent  # project root (this file is in frontend/tests)
backend = root / 'backend'
for path in [backend / 'api.py', backend / 'security.py', backend / 'reporting.py', backend / 'sql.py']:
    ast.parse(path.read_text(), filename=str(path))
print('PASS: Python backend files have valid syntax')

flask_stub = types.ModuleType('flask')
flask_stub.g = types.SimpleNamespace()
flask_stub.request = types.SimpleNamespace(method='GET', path='/health', headers={})
flask_stub.jsonify = lambda d: d
sys.modules['flask'] = flask_stub
spec = importlib.util.spec_from_file_location('capstone_security_test', backend / 'security.py')
security = importlib.util.module_from_spec(spec)
spec.loader.exec_module(security)
os.environ['AUTH_TOKEN_SECRET'] = 'TESTONLY-' + 'x' * 64
manager_token = security.issue_token(1)
assert security.verify_token(manager_token) == 1
assert security.verify_token(manager_token[:-1] + ('Z' if manager_token[-1] != 'Z' else 'Y')) is None
assert security.verify_token('no-token') is None
print('PASS: signed tokens verify; tampered tokens fail')

class MockApp:
    def before_request(self, callback):
        self.authenticate = callback
        return callback
    def logger(self):
        pass

app = MockApp()
def conn():
    class Connection:
        def close(self):
            pass
    return Connection()

def read_employee(_conn, _sql, _params):
    return [{'Employee_ID': 1, 'First_Name':'Test', 'Last_Name':'User',
             'Username':'testuser', 'Email':'test@example.org', 'Role':'Employee'}]

security.install_auth(app, conn, read_employee)
flask_stub.request.method = 'DELETE'
flask_stub.request.path = '/api/suppliers/1'
flask_stub.request.headers = {}
assert app.authenticate()[1] == 401
flask_stub.request.headers = {'Authorization':'Bearer ' + manager_token}
assert app.authenticate()[1] == 403, 'Employee must not delete a supplier'
flask_stub.request.method = 'GET'
assert app.authenticate() is None, 'Valid employee should read'
print('PASS: direct Flask calls require token; delete requires manager role')
