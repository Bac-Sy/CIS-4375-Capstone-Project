import mysql.connector
from mysql.connector import Error


def DBconnection(hostname, uname, pwd, dbname):
    con = None
    try:
        con = mysql.connector.connect(
            host=hostname,
            user=uname,
            password=pwd,
            database=dbname
        )
        print("Connection successful")
    except Error as e:
        print("Connection unsuccessful due to Error ", e)
    return con


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
