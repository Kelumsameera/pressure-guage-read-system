# import mysql.connector

# mydb = mysql.connector.connect(
#   host="localhost",
#   user="root",
#   password="flexi@123"
# )

# mycursor = mydb.cursor()

# mycursor.execute("CREATE DATABASE modbus_data")
import mysql.connector

mydb = mysql.connector.connect(
  host="localhost",
  user="root",
  password="flexi@123",
  database="modbus_data"
)

mycursor = mydb.cursor()

mycursor.execute("""
CREATE TABLE readings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    device_name VARCHAR(100),
    value FLOAT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
)
""")
