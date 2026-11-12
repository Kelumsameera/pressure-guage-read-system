# Pressure Gauge Read System

Early-stage Python/Flask service that polls industrial pressure devices over Modbus TCP, stores measurements in MySQL, and streams updates over Flask-SocketIO.

## Repository layout

- `app.py` — Flask routes, Modbus polling, database access and Socket.IO events
- `databaseCreate.py` — database setup script
- `history.py` — history-related script
- `templates/` — HTML templates
- `requirements.txt` — declared Python dependencies

## Local development

1. Create and activate a Python virtual environment.
2. Install packages with `pip install -r requirements.txt`.
3. Set up a MySQL database named `modbus_data` and verify the schema expected by `app.py`.
4. Configure the sensor IPs/unit IDs in `app.py`.
5. Run the Flask application only on an authorized local network.

> The current `main` branch contains hardcoded database settings. A separate draft security PR introduces runtime variables (`MYSQL_HOST`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_DATABASE`, `FLASK_SECRET_KEY`). Do not deploy the public source unchanged.

## Current limitations

- MySQL credentials were previously committed in source code. **Rotate any password that was actually used**; removing it from a new revision does not erase Git history.
- This is a legacy/in-progress implementation, not a production-hardened release.
- Socket.IO currently allows all origins; restrict allowed clients before external access.
- Check that the installed dependencies match the imports used by the scripts. `app.py` imports modules beyond the packages listed in `requirements.txt`.
- Validate that database access, polling, chart views and exports all work after configuration changes.

See the separate security pull request for the proposed credential cleanup.
