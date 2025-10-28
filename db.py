import mysql.connector

# Database config
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': 'flexi@123',
    'database': 'modbus_data'  # Use the database where readings are saved
}

# Time range for query (use 24-hour format, leading zeros)
start_timestamp = '2025-06-21 16:45:00'
end_timestamp = '2025-06-21 17:00:00'

try:
    # Connect to MySQL
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()

    query = "SELECT * FROM readings WHERE timestamp LIKE %s"
    cursor.execute(query, ('2025-06-21%',))
    rows = cursor.fetchall()
    print(f"Rows found for date 2025-06-21: {len(rows)}")
    for row in rows:
        print(row)


except mysql.connector.Error as err:
    print("MySQL Error:", err)

finally:
    if conn.is_connected():
        cursor.close()
        conn.close()
