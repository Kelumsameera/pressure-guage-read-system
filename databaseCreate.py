import mysql.connector
from mysql.connector import errorcode

# --- MySQL Config ---
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': 'Flexi@123',
    'database': 'modbus_data'
}

# --- Create Database and Table ---
def initialize_database():
    try:
        # Connect to MySQL server (without specifying DB first)
        conn = mysql.connector.connect(
            host=db_config['host'],
            user=db_config['user'],
            password=db_config['password']
        )
        cursor = conn.cursor()

        # Create database if not exists
        cursor.execute("CREATE DATABASE IF NOT EXISTS modbus_data")
        print("✅ Database 'modbus_data' checked/created successfully.")

        # Connect to that database
        conn.database = db_config['database']

        # Create readings table if not exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS readings (
                id INT AUTO_INCREMENT PRIMARY KEY,
                device_name VARCHAR(100),
                value FLOAT,
                timestamp DATETIME
            )
        """)
        print("✅ Table 'readings' checked/created successfully.")

        cursor.close()
        conn.close()

    except mysql.connector.Error as err:
        print("❌ MySQL Error:", err)


if __name__ == "__main__":
    initialize_database()
