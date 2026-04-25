# utils/qr.py
import os
import qrcode
from flask import current_app

def generate_qr_for_link(link, filename=None):
    """
    Generate a PNG QR image for given link and save it under:
        <your-fla>/static/uploads/qr/<filename>.png

    Returns relative path like 'uploads/qr/<filename>.png' (so you can use url_for('static', filename=...))
    """
    # ensure static folder exists and the uploads/qr subdir exists
    save_dir = os.path.join(current_app.static_folder, "uploads", "qr")
    os.makedirs(save_dir, exist_ok=True)

    if not filename:
        import uuid
        filename = f"qr_{uuid.uuid4().hex[:8]}.png"

    full_path = os.path.join(save_dir, filename)

    # create the QR image
    img = qrcode.make(link)
    img.save(full_path)

    # return path relative to static/ so you can do url_for('static', filename=qr_relative_path)
    return f"uploads/qr/{filename}"
