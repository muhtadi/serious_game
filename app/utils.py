from functools import wraps
from flask import abort, current_app, request, jsonify
from flask_login import current_user
from werkzeug.utils import secure_filename
import os, uuid

def role_required(*roles):
    """Decorator untuk membatasi akses berdasarkan role."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                if request.is_json:
                    return jsonify({'error': 'Unauthorized'}), 401
                abort(401)
            if current_user.role.value not in roles:
                if request.is_json:
                    return jsonify({'error': 'Forbidden'}), 403
                abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def save_upload(file, allowed_set):
    """Simpan file upload, return nama file atau None jika tidak valid."""
    if not file or file.filename == '':
        return None
    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
    if ext not in allowed_set:
        return None
    filename = f"{uuid.uuid4().hex}.{ext}"
    upload_dir = current_app.config['UPLOAD_FOLDER']
    os.makedirs(upload_dir, exist_ok=True)
    file.save(os.path.join(upload_dir, filename))
    return filename

