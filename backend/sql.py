import threading
import time
import mysql.connector
from mysql.connector import Error

# Connection reuse: opening a new connection to AWS RDS takes seconds (network + login),
# so finished connections are kept and handed to the next request instead of being closed.
# Nothing changes for the routes: they still call DBconnection(...) and mycon.close().
# Connections are only opened when needed, and at most MAX_IDLE are kept waiting.
MAX_IDLE = 10
CHECK_AFTER_IDLE_SECONDS = 120   # a connection unused this long gets a quick ping before reuse
_idle = []                        # list of (connection, time it was handed back)
_idle_lock = threading.Lock()


class PooledConnection:
    """Wraps a real connection. Everything works the same, except close() hands it back for reuse."""

    def __init__(self, con):
        object.__setattr__(self, '_con', con)

    def __getattr__(self, name):
        return getattr(self._con, name)

    def close(self):
        con = self._con
        if con is None:
            return
        object.__setattr__(self, '_con', None)
        try:
            # End any open transaction (reads open one too), so the next request sees fresh data.
            if con.in_transaction:
                con.rollback()
            with _idle_lock:
                if len(_idle) < MAX_IDLE:
                    _idle.append((con, time.monotonic()))
                    return
        except Error:
            pass
        try:
            con.close()
        except Error:
            pass


def _reuse_idle_connection():
    while True:
        with _idle_lock:
            if not _idle:
                return None
            con, handed_back = _idle.pop()
        if time.monotonic() - handed_back < CHECK_AFTER_IDLE_SECONDS:
            return con
        try:
            if con.is_connected():   # pings the server; drops connections the network has cut
                return con
        except Error:
            pass
        try:
            con.close()
        except Error:
            pass


def DBconnection(hostname, uname, pwd, dbname):
    con = _reuse_idle_connection()
    if con is None:
        try:
            con = mysql.connector.connect(
                host=hostname,
                user=uname,
                password=pwd,
                database=dbname,
                connection_timeout=15
            )
            print("Connection successful")
        except Error as e:
            print("Connection unsuccessful due to Error ", e)
            return None
    return PooledConnection(con)


# Read rows from a table. Pass user input through params, never format it into the sql string:
#   execute_read_query(con, "select * from books where Title = %s", (title,))
def execute_read_query(con, sql, params=None):
    mycursor = con.cursor(dictionary=True)
    try:
        mycursor.execute(sql, params)
        return mycursor.fetchall()
    except Error as e:
        print("Error is: ", e)
    finally:
        mycursor.close()


# Insert, update, or delete rows. Same params rule as above.
def execute_update_query(con, sql, params=None):
    mycursor = con.cursor()
    try:
        mycursor.execute(sql, params)
        con.commit()
        print("DB update successful")
    except Error as e:
        print("Error is : ", e)
    finally:
        mycursor.close()
