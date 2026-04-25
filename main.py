from app import app
from flask_migrate import Migrate
from models import db  # Adjust if db is defined elsewhere

# Enable Fla (resk-Migratequired for database schema management on VPS)
migrate = Migrate(app, db)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)