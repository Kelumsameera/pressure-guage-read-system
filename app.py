import eventlet
eventlet.monkey_patch()

from flask import Flask, render_template, request, flash, send_file
from flask_socketio import SocketIO
from pymodbus.payload import BinaryPayloadDecoder, Endian
from pyModbusTCP.client import ModbusClient
import mysql.connector
import threading
import time
from datetime import datetime
import pandas as pd
import io

app = Flask(__name__)
app.secret_key = 'your_secret_key'
socketio = SocketIO(app, cors_allowed_origins="*")

# MySQL Config
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': 'flexi@123',
    'database': 'modbus_data'
}

# Modbus Device List
modbus_devices = [
    {"name": "assembly_room", "ip": "192.168.0.7", "port": 502, "register": 0, "unit": 1},
    {"name": "testing_room", "ip": "192.168.0.17", "port": 502, "register": 0, "unit": 2},
]

# Save to DB
def save_to_db(device_name, value):
    try:
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO readings (device_name, value, timestamp) VALUES (%s, %s, %s)",
            (device_name, value, current_time)
        )
        conn.commit()
        cursor.close()
        conn.close()
        print(f"Saved {device_name} value {value} at {current_time}")
    except mysql.connector.Error as err:
        print("MySQL Error:", err)

# Modbus Read Loop
def read_modbus_loop():
    while True:
        for device in modbus_devices:
            try:
                client = ModbusClient(
                    host=device["ip"],
                    port=device["port"],
                    unit_id=device["unit"],
                    timeout=1,
                    auto_open=True,
                    auto_close=False
                )
                if client.open():
                    rr = client.read_holding_registers(device["register"], 2)
                    if rr:
                        decoder = BinaryPayloadDecoder.fromRegisters(
                            rr,
                            byteorder=Endian.BIG,
                            wordorder=Endian.LITTLE
                        )
                        value = decoder.decode_32bit_float()
                        formatted = round(value, 2)
                        print(f"{device['name']} -> {formatted}")
                        save_to_db(device['name'], formatted)
                        socketio.emit('modbus_update', {
                            'device': device['name'],
                            'value': formatted
                        })
                    client.close()
            except Exception as e:
                print(f"Error reading {device['name']}: {e}")
        time.sleep(5)

# Get Filtered DB Data
def get_data_for_date(selected_date, start_time, end_time):
    try:
        start_datetime = f"{selected_date} {start_time}:00"
        end_datetime = f"{selected_date} {end_time}:00"

        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        query = "SELECT * FROM readings WHERE timestamp BETWEEN %s AND %s ORDER BY timestamp ASC"
        cursor.execute(query, (start_datetime, end_datetime))
        rows = cursor.fetchall()
        return rows

    except mysql.connector.Error as e:
        print(f"MySQL Error: {e}")
        return []

    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()

# Export to Excel
def export_data_to_excel(data):
    df = pd.DataFrame(data, columns=['ID', 'Device Name', 'Value', 'Timestamp'])
    excel_file = io.BytesIO()
    df.to_excel(excel_file, index=False, engine='openpyxl')
    excel_file.seek(0)
    return excel_file

# Web Route: Home
@app.route('/database', methods=['GET', 'POST'])
def index():
    data = None
    selected_date = None
    start_time = None
    end_time = None

    if request.method == 'POST':
        selected_date = request.form.get('date')
        start_time = request.form.get('start_time')
        end_time = request.form.get('end_time')

        if not selected_date or not start_time or not end_time:
            flash('All fields are required!', 'danger')
        elif start_time >= end_time:
            flash('Start time must be before end time.', 'danger')
        else:
            data = get_data_for_date(selected_date, start_time, end_time)
            if not data:
                flash('No data found for the selected date and time range.', 'warning')

    return render_template('database.html',
                           data=data,
                           selected_date=selected_date,
                           start_time=start_time,
                           end_time=end_time)

# Route: Export Excel
@app.route('/export_excel', methods=['POST'])
def export_excel():
    import openpyxl
    selected_date = request.form.get('date')
    start_time = request.form.get('start_time')
    end_time = request.form.get('end_time')

    if not selected_date or not start_time or not end_time:
        flash('Missing date/time parameters for export.', 'danger')
        return "Missing date/time parameters.", 400

    data = get_data_for_date(selected_date, start_time, end_time)
    if not data:
        flash('No data found to export.', 'warning')
        return "No data found to export.", 404

    filename = f"data_{selected_date}_{start_time}_to_{end_time}.xlsx".replace(":", "-")
    excel_file = export_data_to_excel(data)

    return send_file(
        excel_file,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=filename
    )
from flask import jsonify

# Real-time values page
@app.route('/')
def realtime():
    return render_template('realtime.html')

# Chart view page
@app.route('/chart', methods=['GET', 'POST'])
def chart():
    data = []
    selected_date = None
    start_time = None
    end_time = None

    if request.method == 'POST':
        selected_date = request.form.get('date')
        start_time = request.form.get('start_time')
        end_time = request.form.get('end_time')

        if selected_date and start_time and end_time:
            data = get_data_for_date(selected_date, start_time, end_time)
    
    # Format data for Chart.js (timestamps and values)
    chart_data = []
    for row in data:
        # row[3] is timestamp, row[2] is value
        # If your timestamp is string, parse it to datetime before formatting
        ts = row[3]
        if isinstance(ts, str):
            from datetime import datetime as dt
            ts = dt.strptime(ts, "%Y-%m-%d %H:%M:%S")
        chart_data.append({
            "timestamp": ts.strftime("%Y-%m-%d %H:%M:%S"),
            "value": row[2],
            "device": row[1]  # include device name for multiple devices
        })

    return render_template('chart.html',
                           data=chart_data,
                           selected_date=selected_date,
                           start_time=start_time,
                           end_time=end_time)


# Start App
if __name__ == '__main__':
    threading.Thread(target=read_modbus_loop, daemon=True).start()
    socketio.run(app, port=5000, debug=True)
