import os
import time
from flask import Flask, render_template, request, jsonify
from flask_mysqldb import MySQL
from dotenv import load_dotenv
from prometheus_client import generate_latest, Counter
from prometheus_flask_exporter import PrometheusMetrics

load_dotenv()
app = Flask(__name__)

# Fetch MySQL config from environment
app.config['MYSQL_HOST'] = os.environ['MYSQL_HOST']
app.config['MYSQL_USER'] = os.environ['MYSQL_USER']
app.config['MYSQL_PASSWORD'] = os.environ['MYSQL_PASSWORD']
app.config['MYSQL_DB'] = os.environ['MYSQL_DB']

# Initialize MySQL
mysql = MySQL(app)

REQUESTS = Counter("flask_requests_total", "Total Flask requests")

metrics = PrometheusMetrics(app)  

def wait_for_db_connection(max_retries=10, delay=5):
    """Retry DB connection to avoid startup issues"""
    for attempt in range(1, max_retries + 1):
        try:
            with app.app_context():
                cur = mysql.connection.cursor()
                cur.execute("SELECT 1;")
                cur.close()
                print("✅ Connected to DB.")
                return True
        except Exception as e:
            print(f"⏳ Attempt {attempt}/{max_retries} | Error: {e}")
            time.sleep(delay)
    print("❌ Failed to connect to DB.")
    return False


def init_db():
    """Create messages table if not exists"""
    with app.app_context():
        cur = mysql.connection.cursor()
        cur.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INT AUTO_INCREMENT PRIMARY KEY,
                message TEXT
            );
        ''')
        mysql.connection.commit()
        cur.close()
        print("📦 Database initialized.")


@app.route('/')
def index():
    cur = mysql.connection.cursor()
    cur.execute('SELECT id, message FROM messages')
    messages = cur.fetchall()
    cur.close()
    return render_template('index.html', messages=messages)


@app.route('/submit', methods=['POST'])
def submit():
    new_message = request.form.get('new_message')
    if not new_message:
        return jsonify({'error': 'Message required'}), 400

    cur = mysql.connection.cursor()
    cur.execute('INSERT INTO messages (message) VALUES (%s)', [new_message])
    mysql.connection.commit()
    message_id = cur.lastrowid
    cur.close()
    return jsonify({'message': new_message, 'id': message_id})


@app.route('/delete/<int:id>', methods=['POST'])
def delete(id):
    cur = mysql.connection.cursor()
    cur.execute('DELETE FROM messages WHERE id = %s', [id])
    mysql.connection.commit()
    cur.close()
    return jsonify({'status': 'deleted'})


@app.route('/edit/<int:id>', methods=['POST'])
def edit(id):
    new_content = request.form.get('updated_message')
    if not new_content:
        return jsonify({'error': 'New message required'}), 400

    cur = mysql.connection.cursor()
    cur.execute('UPDATE messages SET message = %s WHERE id = %s', (new_content, id))
    mysql.connection.commit()
    cur.close()
    return jsonify({'status': 'updated', 'message': new_content})

@app.route("/metrics")
def metrics():
    return generate_latest(), 200, {'Content-Type': 'text/plain'}


if __name__ == '__main__':
    if wait_for_db_connection():
        init_db()
        app.run(host='0.0.0.0', port=5000)
    else:
        print("🚫 Could not connect to DB. Shutting down.")