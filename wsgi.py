#!/usr/bin/env python3
"""
WSGI Entry Point for Gunicorn deployment
Usage: gunicorn -w 4 -b 0.0.0.0:8000 wsgi:app
"""

import os
from app import create_app

# Create the Flask application
app = create_app()

if __name__ == "__main__":
    # For development testing
    app.run(host='0.0.0.0', port=8000, debug=False)