from datetime import datetime, timedelta
import pytz
import mysql.connector
from flask import request, render_template
# MySQL Config
db_config = {
    'host': '127.0.0.1',
    'user': 'root',
    'password': 'Flexi@123',
    'database': 'modbus_data'

@app.route('/history')
def history():
    start = request.args.get('start_datetime')
    end = request.args.get('end_datetime')
    selected_device = request.args.get('device')
    interval = request.args.get('interval', 'seconds')

    labels_dict = {}
    values_dict = {}
    conn = None
    cursor = None

    # 🕒 Default to last 1 hour if no time provided
    if not start or not end:
        colombo_tz = pytz.timezone("Asia/Colombo")
        end_dt = datetime.now(colombo_tz)
        start_dt = end_dt - timedelta(hours=1)
        start = start_dt.strftime('%Y-%m-%dT%H:%M:%S')
        end = end_dt.strftime('%Y-%m-%dT%H:%M:%S')

    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()

        # Select time grouping based on interval
        if interval == "hours":
            time_group = "DATE_FORMAT(timestamp, '%Y-%m-%d %H:00:00')"
        elif interval == "minutes":
            time_group = "DATE_FORMAT(timestamp, '%Y-%m-%d %H:%i:00')"
        else:
            time_group = "DATE_FORMAT(timestamp, '%Y-%m-%d %H:%i:%s')"

        query = f"""
            SELECT device_name, {time_group} AS grouped_time, AVG(value)
            FROM readings
            WHERE timestamp BETWEEN %s AND %s
        """
        params = [start, end]

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
        if cursor is not None:
            cursor.close()
        if conn is not None and conn.is_connected():
            conn.close()

    return render_template(
        "history.html",
        labels=labels_dict,
        values=values_dict,
        devices=devices,
        selected_device=selected_device,
        start=start,
        end=end,
        interval=interval
    )
