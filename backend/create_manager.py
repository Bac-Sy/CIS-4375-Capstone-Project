"""Create the first Manager account (or reset a manager's password) on a new database.

Every way of adding an employee in the app needs a manager to be logged in already, so on a fresh
database run this once from the backend folder:

    python create_manager.py

It asks for the details, hashes the password with argon2 (the same way the app does) and saves the
account. If the username already exists it offers to make that account a Manager with the new password.
It uses the database in backend/.env.<APP_ENV> (development unless APP_ENV is set).
"""
import getpass
import re
import sys

from argon2 import PasswordHasher

import creds
from sql import DBconnection, execute_read_query

EMAIL = re.compile(r'^[^\s@]+@[^\s@]+\.[^\s@]+$')


def ask(label, check=None, message=''):
    while True:
        value = input(f'{label}: ').strip()
        if value and (check is None or check(value)):
            return value
        print(message or f'{label} is required.')


def main():
    print(f'Creating a Manager account in the "{creds.APP_ENV}" database.\n')
    first = ask('First name', lambda v: len(v) <= 50, 'Up to 50 characters.')
    last = ask('Last name', lambda v: len(v) <= 50, 'Up to 50 characters.')
    username = ask('Username', lambda v: len(v) <= 50, 'Up to 50 characters.')
    email = ask('Email', lambda v: len(v) <= 100 and EMAIL.match(v), 'Enter a valid email address.')
    while True:
        password = getpass.getpass('Password (at least 8 characters, not shown): ')
        if len(password) < 8 or len(password) > 128:
            print('The password must be between 8 and 128 characters.')
        elif getpass.getpass('Type it again: ') != password:
            print('The passwords did not match.')
        else:
            break

    db = creds.mycreds()
    con = DBconnection(db.hostname, db.username, db.password, db.database)
    if con is None:
        sys.exit('Could not connect to the database. Check backend/.env.' + creds.APP_ENV)
    try:
        hashed = PasswordHasher().hash(password)
        existing = execute_read_query(con, 'SELECT Employee_ID, Role FROM Employee WHERE Username=%s OR Email=%s', (username, email))
        cursor = con.cursor()
        if existing:
            answer = input(f'An account with that username or email already exists (role: {existing[0]["Role"]}). '
                           'Make it a Manager with this name and password? [y/N]: ').strip().lower()
            if answer != 'y':
                print('Nothing was changed.')
                return
            cursor.execute('UPDATE Employee SET First_Name=%s, Last_Name=%s, Role=%s, Username=%s, Email=%s, Password_Hash=%s '
                           'WHERE Employee_ID=%s', (first, last, 'Manager', username, email, hashed, existing[0]['Employee_ID']))
        else:
            cursor.execute('INSERT INTO Employee (First_Name, Last_Name, Role, Username, Email, Password_Hash) '
                           'VALUES (%s, %s, %s, %s, %s, %s)', (first, last, 'Manager', username, email, hashed))
        con.commit()
        cursor.close()
        print(f'\nDone. Log in at the website with username "{username}".')
    finally:
        con.close()


if __name__ == '__main__':
    main()
