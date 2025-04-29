# db_connection.py

import mysql.connector

def get_db_connection():
    connection = mysql.connector.connect(
        host='localhost',          # Your MySQL host
        user='root',    # Your MySQL username
        password='root', # Your MySQL password
        database='dqms'             # Your database name
    )
    return connection
