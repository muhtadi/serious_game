from functools import wraps
from flask import abort, current_app, request, jsonify
from flask_login import current_user
import os, uuid, io, requests as http_requests
from PIL import Image

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
        'scores': [round(dt_stats[k]['correct'] / dt_stats[k]['total'] * 100, 1) if dt_stats[k]['total'] > 0 else 0 for k in CURRICULUM_KEYS]
    }
    ct_data = {
        'labels': [ct_labels[k] for k in CT_SKILL_KEYS],
        'scores': [round(ct_stats[k]['correct'] / ct_stats[k]['total'] * 100, 1) if ct_stats[k]['total'] > 0 else 0 for k in CT_SKILL_KEYS]
    }

    return dt_data, ct_data

def _compress_image(file_data: bytes, max_px: int = 1200, quality: int = 82) -> tuple[bytes, str]:
    """
    Kompresi gambar:
    - Resize ke max_px di sisi terpanjang (preserve aspect ratio)
    - Konversi ke WebP (lossy, quality=82 — hampir tidak terlihat bedanya)
    - Return (compressed_bytes, 'webp')
    """
    img = Image.open(io.BytesIO(file_data))

    # Konversi mode agar WebP support (RGBA → RGB jika perlu)
    if img.mode in ('RGBA', 'LA'):
        bg = Image.new('RGB', img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[-1])
        img = bg
    elif img.mode != 'RGB':
        img = img.convert('RGB')

    # Resize jika lebih besar dari max_px
    w, h = img.size
    if max(w, h) > max_px:
        ratio = max_px / max(w, h)
        img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, format='WEBP', quality=quality, method=6)
    return buf.getvalue(), 'webp'


def save_upload(file, allowed_set):
    """
    Upload file ke Supabase Storage via REST API.
    Gambar dikompresi ke WebP sebelum upload.
    Return: public URL (string) jika sukses, None jika gagal.
    """
    if not file or file.filename == '':
        return None
    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
    if ext not in allowed_set:
        return None

    file_data = file.read()
    if not file_data:
        current_app.logger.error("Upload error: file data kosong")
        return None

    # Kompresi gambar → WebP
    image_exts = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    if ext in image_exts:
        try:
            file_data, ext = _compress_image(file_data)
            original_size = len(file.read()) if hasattr(file, 'read') else 0
            current_app.logger.info(
                f"Gambar dikompres ke WebP: {len(file_data)/1024:.1f} KB"
            )
        except Exception as e:
            current_app.logger.warning(f"Kompresi gambar gagal, pakai original: {e}")

    mime_map = {
        'webp': 'image/webp', 'jpg': 'image/jpeg', 'jpeg': 'image/jpeg',
        'png': 'image/png', 'gif': 'image/gif',
        'mp3': 'audio/mpeg', 'ogg': 'audio/ogg', 'wav': 'audio/wav'
    }
    mime_type = mime_map.get(ext, 'application/octet-stream')
    filename  = f"{uuid.uuid4().hex}.{ext}"

    supabase_url = current_app.config.get('SUPABASE_URL', '').rstrip('/')
    supabase_key = current_app.config.get('SUPABASE_KEY', '')
    bucket       = current_app.config.get('SUPABASE_BUCKET', 'media')

    if supabase_url and supabase_key:
        try:
            upload_url = f"{supabase_url}/storage/v1/object/{bucket}/{filename}"
            headers = {
                "Authorization": f"Bearer {supabase_key}",
                "apikey": supabase_key,
                "Content-Type": mime_type,
                "x-upsert": "true"
            }
            resp = http_requests.post(upload_url, headers=headers,
                                      data=file_data, timeout=30)
            if resp.status_code in (200, 201):
                public_url = f"{supabase_url}/storage/v1/object/public/{bucket}/{filename}"
                current_app.logger.info(f"Upload sukses: {public_url}")
                return public_url
            else:
                current_app.logger.error(
                    f"Supabase upload gagal [{resp.status_code}]: {resp.text}"
                )
                return None
        except Exception as e:
            current_app.logger.error(f"Upload exception: {type(e).__name__}: {e}")
            if current_app.debug:
                raise
            return None
    else:
        # Fallback lokal
        upload_dir = current_app.config.get('UPLOAD_FOLDER', 'static/uploads')
        os.makedirs(upload_dir, exist_ok=True)
        with open(os.path.join(upload_dir, filename), 'wb') as f:
            f.write(file_data)
        return f"uploads/{filename}"
