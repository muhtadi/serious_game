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

def get_student_competency_data(user_id):
    """
    Hitung akurasi (mastery) siswa untuk setiap Digital Tech Key Concept dan CT Skill Alignment.
    Data diambil dari AttemptLog dan Stage terkait.
    """
    from app.models import AttemptLog, Stage, CURRICULUM_KEYS, CT_SKILL_KEYS
    from sqlalchemy import func

    # Kita ambil log dari challenge mode untuk akurasi yang lebih valid (penelitian)
    logs = AttemptLog.query.filter_by(user_id=user_id, mode='challenge').all()
    
    # Ambil info stage untuk setiap log untuk tahu konsep apa yang diwakili
    stage_ids = list(set(l.stage_id for l in logs))
    stages = {s.id: s for s in Stage.query.filter(Stage.id.in_(stage_ids)).all()} if stage_ids else {}

    # Accumulators
    # { 'abstraction': {'correct': 0, 'total': 0}, ... }
    dt_stats = {key: {'correct': 0, 'total': 0} for key in CURRICULUM_KEYS}
    ct_stats = {key: {'correct': 0, 'total': 0} for key in CT_SKILL_KEYS}

    for log in logs:
        stage = stages.get(log.stage_id)
        if not stage: continue
        
        # Digital Tech Concepts
        for key in CURRICULUM_KEYS:
            if getattr(stage, key, False):
                dt_stats[key]['total'] += 1
                if log.is_correct:
                    dt_stats[key]['correct'] += 1
        
        # CT Skills
        for key in CT_SKILL_KEYS:
            if getattr(stage, key, False):
                ct_stats[key]['total'] += 1
                if log.is_correct:
                    ct_stats[key]['correct'] += 1

    # Format untuk Chart.js (Spider Chart)
    dt_labels = {
        'abstraction': 'Abstraction', 'data_collection': 'Data Collection',
        'data_representation': 'Data Representation', 'data_interpretation': 'Data Interpretation',
        'specification': 'Specification', 'algorithms': 'Algorithms',
        'implementation': 'Implementation', 'digital_systems': 'Digital Systems',
        'interactions': 'Interactions', 'impact': 'Impact'
    }
    ct_labels = {
        'decomposition': 'Decomposition', 'abstraction_ct': 'Abstraction',
        'modelling_simulation': 'Modelling & Simulation', 'algorithms_ct': 'Algorithms',
        'evaluation': 'Evaluation'
    }

    dt_data = {
        'labels': [dt_labels[k] for k in CURRICULUM_KEYS],
        'values': [round(dt_stats[k]['correct'] / dt_stats[k]['total'] * 100, 1) if dt_stats[k]['total'] > 0 else 0 for k in CURRICULUM_KEYS]
    }
    ct_data = {
        'labels': [ct_labels[k] for k in CT_SKILL_KEYS],
        'values': [round(ct_stats[k]['correct'] / ct_stats[k]['total'] * 100, 1) if ct_stats[k]['total'] > 0 else 0 for k in CT_SKILL_KEYS]
    }

    return dt_data, ct_data

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

