import eventlet
eventlet.monkey_patch()

from flask import Flask, render_template, request, flash, send_file, jsonify
from flask_socketio import SocketIO
from pyModbusTCP.client import ModbusClient
import mysql.connector
import threading
import time
from datetime import datetime, timedelta
import pytz
import pandas as pd
import io
from pymodbus.payload import BinaryPayloadDecoder
from pymodbus.constants import Endian

app = Flask(__name__)
app.secret_key = 'your_secret_key'
app.config['TEMPLATES_AUTO_RELOAD'] = True
socketio = SocketIO(app, cors_allowed_origins="*")

# MySQL Config
db_config = {
    'host': '127.0.0.1',
    'user': 'root',
    'password': 'Flexi@123',
    'database': 'modbus_data'
}

# Modbus Device List
modbus_devices = [
    {"name": "production_clean_room", "ip": "192.168.0.7", "port": 502, "register": 0, "unit": 1},
    {"name": "assembly_clean_room", "ip": "192.168.0.17", "port": 502, "register": 0, "unit": 2},
]

# Save to DB with Asia/Colombo time
def save_to_db(device_name, value):
    try:
        colombo_tz = pytz.timezone("Asia/Colombo")
        current_time = datetime.now(colombo_tz).strftime("%Y-%m-%d %H:%M:%S")

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
                            'value': formatted,
                            'timestamp': datetime.now(pytz.timezone("Asia/Colombo")).strftime("%Y-%m-%d %H:%M:%S")
                        })
                    client.close()
            except Exception as e:
                print(f"Error reading {device['name']}: {e}")
        time.sleep(5)

# Get Filtered DB Data
def get_data_for_date(start_datetime, end_datetime):
    try:
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
    import io
    import pandas as pd
    from openpyxl import Workbook  # Correct import

    # Create DataFrame
    df = pd.DataFrame(data, columns=['ID', 'Device Name', 'Value', 'Timestamp'])

    # Write DataFrame to Excel in memory
    excel_file = io.BytesIO()
    df.to_excel(excel_file, index=False, engine='openpyxl')

    # Reset pointer to the beginning of the file
    excel_file.seek(0)

    return excel_file


@app.route('/database', methods=['GET', 'POST'])
def index():
    data = None
    start_date = None
    end_date = None
    start_time = None
    end_time = None

    if request.method == 'POST':
        start_date = request.form.get('start_date')
        start_time = request.form.get('start_time')
        end_date = request.form.get('end_date')
        end_time = request.form.get('end_time')

        if not start_date or not start_time or not end_date or not end_time:
            flash('All fields are required!', 'danger')
        else:
            start_datetime = f"{start_date} {start_time}:00"
            end_datetime = f"{end_date} {end_time}:00"

            if start_datetime >= end_datetime:
                flash('Start datetime must be before end datetime.', 'danger')
            else:
                data = get_data_for_date(start_datetime, end_datetime)
                if not data:
                    flash('No data found for the selected date and time range.', 'warning')

    return render_template('database.html',
                           data=data,
                           start_date=start_date,
                           start_time=start_time,
                           end_date=end_date,
                           end_time=end_time)

@app.route('/export_excel', methods=['POST'])
def export_excel():
    
    start_date = request.form.get('start_date')
    start_time = request.form.get('start_time')
    end_date = request.form.get('end_date')
    end_time = request.form.get('end_time')

    if not start_date or not start_time or not end_date or not end_time:
        flash('Missing date/time parameters for export.', 'danger')
        return "Missing date/time parameters.", 400

    start_datetime = f"{start_date} {start_time}:00"
    end_datetime = f"{end_date} {end_time}:00"

    data = get_data_for_date(start_datetime, end_datetime)
    if not data:
        flash('No data found to export.', 'warning')
        return "No data found to export.", 404

    filename = f"data_{start_date}_{start_time}_to_{end_date}_{end_time}.xlsx".replace(":", "-")
    excel_file = export_data_to_excel(data)

    return send_file(
        excel_file,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=filename
    )

# Real-time values page
@app.route('/')
def realtime():
    return render_template('realtime.html')

# Chart page
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
    
    chart_data = []
    for row in data:
        ts = row[3]
        if isinstance(ts, str):
            from datetime import datetime as dt
            ts = dt.strptime(ts, "%Y-%m-%d %H:%M:%S")
        chart_data.append({
            "timestamp": ts.strftime("%Y-%m-%d %H:%M:%S"),
            "value": row[2],
            "device": row[1]
        })

    return render_template('chart.html',
                           data=chart_data,
                           selected_date=selected_date,
                           start_time=start_time,
                           end_time=end_time)

@app.route('/history')
def history():
    start = request.args.get('start_datetime')
    end = request.args.get('end_datetime')
    selected_device = request.args.get('device')
    interval = request.args.get('interval', 'seconds')

    labels_dict, values_dict = {}, {}
    conn = cursor = None

    # 🕒 Default to last 3 days if not provided
    from datetime import datetime, timedelta
    import pytz
    colombo_tz = pytz.timezone("Asia/Colombo")

    if not start or not end:
        end_dt = datetime.now(colombo_tz)
        start_dt = end_dt - timedelta(days=3)
    else:
        start_dt = datetime.strptime(start.replace("T", " "), "%Y-%m-%d %H:%M:%S")
        end_dt = datetime.strptime(end.replace("T", " "), "%Y-%m-%d %H:%M:%S")

    start_str = start_dt.strftime('%Y-%m-%d %H:%M:%S')
    end_str = end_dt.strftime('%Y-%m-%d %H:%M:%S')

    try:
        import mysql.connector
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()

        # 🧠 Choose time grouping based on interval
        if interval == "hours":
            time_group = "DATE_FORMAT(timestamp, '%Y-%m-%d %H:00:00')"
        elif interval == "minutes":
            time_group = "DATE_FORMAT(timestamp, '%Y-%m-%d %H:%i:00')"
        else:  # seconds
            time_group = "DATE_FORMAT(timestamp, '%Y-%m-%d %H:%i:%s')"

        query = f"""
            SELECT device_name, {time_group} AS grouped_time, AVG(value)
            FROM readings
            WHERE timestamp BETWEEN %s AND %s
        """
        params = [start_str, end_str]

        if selected_device:
            query += " AND device_name = %s"
            params.append(selected_device)

        query += " GROUP BY device_name, grouped_time ORDER BY grouped_time ASC"
        cursor.execute(query, params)
        rows = cursor.fetchall()

        for device, ts, val in rows:
            labels_dict.setdefault(device, []).append(ts)
            values_dict.setdefault(device, []).append(round(float(val), 2))

        cursor.execute("SELECT DISTINCT device_name FROM readings")
        devices = [r[0] for r in cursor.fetchall()]

    except mysql.connector.Error as e:
        print("❌ MySQL Error:", e)
        devices = []
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()

    return render_template(
        "history.html",
        labels=labels_dict,
        values=values_dict,
        devices=devices,
        selected_device=selected_device,
        start=start_dt.strftime("%Y-%m-%dT%H:%M:%S"),
        end=end_dt.strftime("%Y-%m-%dT%H:%M:%S"),
        interval=interval
    )

@app.route('/about')
def about():
    return render_template("about.html", datetime=datetime)

if __name__ == '__main__':
    threading.Thread(target=read_modbus_loop, daemon=True).start()
    socketio.run(app, host='192.168.23.3', port=5000, debug=True)