from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from app import db
from app.models import (Modul, Stage, Question, Answer, User,
                        ChallengeUnlock, StageCompletion, AttemptLog, GameSession,
                        CURRICULUM_KEYS, CT_SKILL_KEYS, KELAS_CHOICES, DIFFICULTY_CHOICES,
                        MODE_CHALLENGE, MODE_PRACTICE)
from app.utils import role_required, save_upload
from sqlalchemy import func
import os

guru_bp = Blueprint('guru', __name__)

# ── Dashboard ──────────────────────────────────────────────────────────────────
@guru_bp.route('/dashboard')
@login_required
@role_required('guru', 'admin')
def dashboard():
    from sqlalchemy import func
    stats = {
        'total_siswa': User.query.filter_by(role='siswa').count(),
        'total_soal': Question.query.count(),
        'total_selesai': StageCompletion.query.count(),
        'avg_accuracy': db.session.query(func.avg(StageCompletion.accuracy)).scalar() or 0
    }
    return render_template('guru/dashboard_summary.html', stats=stats)

@guru_bp.route('/curriculum')
@login_required
@role_required('guru', 'admin')
def curriculum():
    moduls = Modul.query.order_by(Modul.order_index).all()
    return render_template('guru/dashboard.html', moduls=moduls)

# ── MODUL CRUD ─────────────────────────────────────────────────────────────────
@guru_bp.route('/modul/create', methods=['POST'])
@login_required
@role_required('guru', 'admin')
def modul_create():
    title = request.form.get('title', '').strip()
    order = int(float(request.form.get('order_index', 0)))
    if not title:
        flash('Judul modul tidak boleh kosong.', 'danger')
        return redirect(url_for('guru.curriculum'))
    db.session.add(Modul(title=title, order_index=order))
    db.session.commit()
    flash(f'Modul "{title}" berhasil dibuat.', 'success')
    return redirect(url_for('guru.curriculum'))

@guru_bp.route('/modul/<int:modul_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('guru', 'admin')
def modul_edit(modul_id):
    modul = Modul.query.get_or_404(modul_id)
    if request.method == 'POST':
        modul.title = request.form.get('title', modul.title).strip()
        modul.order_index = int(float(request.form.get('order_index', modul.order_index)))
        db.session.commit()
        flash('Modul berhasil diperbarui.', 'success')
        return redirect(url_for('guru.curriculum'))
    return render_template('guru/modul_edit.html', modul=modul)

@guru_bp.route('/modul/<int:modul_id>/delete', methods=['POST'])
@login_required
@role_required('guru', 'admin')
def modul_delete(modul_id):
    modul = Modul.query.get_or_404(modul_id)
    db.session.delete(modul)
    db.session.commit()
    flash('Modul berhasil dihapus.', 'info')
    return redirect(url_for('guru.curriculum'))

# ── STAGE CRUD ─────────────────────────────────────────────────────────────────
@guru_bp.route('/modul/<int:modul_id>/stage/create', methods=['GET', 'POST'])
@login_required
@role_required('guru', 'admin')
def stage_create(modul_id):
    modul = Modul.query.get_or_404(modul_id)
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        order = int(float(request.form.get('order_index', 0)))
        if not title:
            flash('Judul stage tidak boleh kosong.', 'danger')
            return redirect(request.url)

        audio_file = request.files.get('audio_bg')
        audio_filename = save_upload(audio_file, current_app.config['ALLOWED_AUDIO'])

        image_file = request.files.get('stage_image')
        image_filename = save_upload(image_file, current_app.config['ALLOWED_IMAGE'])

        stage = Stage(
            modul_id=modul_id, title=title, order_index=order,
            audio_bg_url=audio_filename,
            image_url=image_filename,
            kelas=request.form.get('kelas') or None,
            difficulty=request.form.get('difficulty') or None,
            mode=request.form.get('mode', 'practice'),
        )
        db.session.add(stage)
        db.session.commit()
        flash(f'Stage "{title}" berhasil dibuat.', 'success')
        return redirect(url_for('guru.dashboard'))
    return render_template('guru/stage_form.html', modul=modul, stage=None,
                           kelas_choices=KELAS_CHOICES,
                           difficulty_choices=DIFFICULTY_CHOICES)

@guru_bp.route('/stage/<int:stage_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('guru', 'admin')
def stage_edit(stage_id):
    stage = Stage.query.get_or_404(stage_id)
    if request.method == 'POST':
        stage.title = request.form.get('title', stage.title).strip()
        stage.order_index = int(float(request.form.get('order_index', stage.order_index)))
        stage.kelas = request.form.get('kelas') or None
        stage.difficulty = request.form.get('difficulty') or None
        stage.mode = request.form.get('mode', stage.mode)

        audio_file = request.files.get('audio_bg')
        audio_filename = save_upload(audio_file, current_app.config['ALLOWED_AUDIO'])
        if audio_filename:
            stage.audio_bg_url = audio_filename

        image_file = request.files.get('stage_image')
        image_filename = save_upload(image_file, current_app.config['ALLOWED_IMAGE'])
        if image_filename:
            stage.image_url = image_filename

        db.session.commit()
        flash('Stage berhasil diperbarui.', 'success')
        return redirect(url_for('guru.dashboard'))
    return render_template('guru/stage_form.html', modul=stage.modul, stage=stage,
                           kelas_choices=KELAS_CHOICES,
                           difficulty_choices=DIFFICULTY_CHOICES)

@guru_bp.route('/stage/<int:stage_id>/delete', methods=['POST'])
@login_required
@role_required('guru', 'admin')
def stage_delete(stage_id):
    stage = Stage.query.get_or_404(stage_id)
    db.session.delete(stage)
    db.session.commit()
    flash('Stage berhasil dihapus.', 'info')
    return redirect(url_for('guru.dashboard'))

# ── QUESTION CRUD ──────────────────────────────────────────────────────────────
@guru_bp.route('/stage/<int:stage_id>/questions')
@login_required
@role_required('guru', 'admin')
def question_list(stage_id):
    stage = Stage.query.get_or_404(stage_id)
    return render_template('guru/question_list.html', stage=stage)

@guru_bp.route('/stage/<int:stage_id>/question/create', methods=['GET', 'POST'])
@login_required
@role_required('guru', 'admin')
def question_create(stage_id):
    stage = Stage.query.get_or_404(stage_id)
    if request.method == 'POST':
        q = _build_question(request, stage_id)
        if q is None:
            return redirect(request.url)
        _apply_curriculum(q, request.form)
        db.session.add(q)
        db.session.flush()  # dapat q.id sebelum commit
        _save_answers(q, request.form)
        db.session.commit()
        flash('Soal berhasil ditambahkan.', 'success')
        return redirect(url_for('guru.question_list', stage_id=stage_id))
    return render_template('guru/question_form.html', stage=stage, question=None,
                           curriculum_keys=CURRICULUM_KEYS,
                           ct_skill_keys=CT_SKILL_KEYS)

@guru_bp.route('/question/<int:question_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('guru', 'admin')
def question_edit(question_id):
    q = Question.query.get_or_404(question_id)
    if request.method == 'POST':
        content = request.form.get('content_text', '').strip()
        import re
        if not re.sub(r'<[^>]+>', '', content).strip():
            flash('Teks soal tidak boleh kosong.', 'danger')
            return redirect(request.url)
        q.content_text = content
        q.difficulty_tier = request.form.get('difficulty_tier', q.difficulty_tier)
        q.type = request.form.get('type', q.type)
        q.explanation = request.form.get('explanation', '').strip()

        img_file = request.files.get('media')
        img_name = save_upload(img_file, current_app.config['ALLOWED_IMAGE'])
        if img_name:
            q.media_url = img_name

        # Explanation image
        exp_img_file = request.files.get('explanation_media')
        exp_img_name = save_upload(exp_img_file, current_app.config['ALLOWED_IMAGE'])
        if exp_img_name:
            q.explanation_media_url = exp_img_name

        _apply_curriculum(q, request.form)

        # Hapus jawaban lama, simpan yang baru
        Answer.query.filter_by(question_id=q.id).delete()
        _save_answers(q, request.form)
        db.session.commit()
        flash('Soal berhasil diperbarui.', 'success')
        return redirect(url_for('guru.question_list', stage_id=q.stage_id))
    return render_template('guru/question_form.html', stage=q.stage, question=q,
                           curriculum_keys=CURRICULUM_KEYS,
                           ct_skill_keys=CT_SKILL_KEYS)

@guru_bp.route('/question/<int:question_id>/delete', methods=['POST'])
@login_required
@role_required('guru', 'admin')
def question_delete(question_id):
    q = Question.query.get_or_404(question_id)
    stage_id = q.stage_id
    db.session.delete(q)
    db.session.commit()
    flash('Soal berhasil dihapus.', 'info')
    return redirect(url_for('guru.question_list', stage_id=stage_id))

# ── TOGGLE AKTIF ──────────────────────────────────────────────────────────────
@guru_bp.route('/modul/<int:modul_id>/toggle', methods=['POST'])
@login_required
@role_required('guru', 'admin')
def modul_toggle(modul_id):
    modul = Modul.query.get_or_404(modul_id)
    modul.is_active = not modul.is_active
    db.session.commit()
    status = 'diaktifkan' if modul.is_active else 'dinonaktifkan'
    flash(f'Modul "{modul.title}" {status}.', 'success')
    return redirect(url_for('guru.dashboard'))

@guru_bp.route('/stage/<int:stage_id>/toggle', methods=['POST'])
@login_required
@role_required('guru', 'admin')
def stage_toggle(stage_id):
    stage = Stage.query.get_or_404(stage_id)
    stage.is_active = not stage.is_active
    db.session.commit()
    status = 'diaktifkan' if stage.is_active else 'dinonaktifkan'
    flash(f'Stage "{stage.title}" {status}.', 'success')
    return redirect(url_for('guru.dashboard'))

@guru_bp.route('/question/<int:question_id>/toggle', methods=['POST'])
@login_required
@role_required('guru', 'admin')
def question_toggle(question_id):
    q = Question.query.get_or_404(question_id)
    q.is_active = not q.is_active
    db.session.commit()
    status = 'diaktifkan' if q.is_active else 'dinonaktifkan'
    flash(f'Soal {status}.', 'success')
    return redirect(url_for('guru.question_list', stage_id=q.stage_id))


def _apply_curriculum(target, form):
    for key in CURRICULUM_KEYS:
        setattr(target, key, key in form)  # checkbox: ada di form = True, tidak ada = False
    for key in CT_SKILL_KEYS:
        setattr(target, key, key in form)

def _build_question(req, stage_id):
    content = req.form.get('content_text', '').strip()
    # Quill mengirim '<p><br></p>' untuk editor kosong — strip tags untuk validasi
    from markupsafe import Markup
    import re
    content_text_only = re.sub(r'<[^>]+>', '', content).strip()
    if not content_text_only:
        flash('Teks soal tidak boleh kosong.', 'danger')
        return None
    img_file = req.files.get('media')
    img_name = save_upload(img_file, current_app.config['ALLOWED_IMAGE'])
    
    # Explanation image
    exp_img_file = req.files.get('explanation_media')
    exp_img_name = save_upload(exp_img_file, current_app.config['ALLOWED_IMAGE'])
    
    return Question(
        stage_id=stage_id,
        content_text=content,
        difficulty_tier=req.form.get('difficulty_tier', 'Easy'),
        type=req.form.get('type', 'PG'),
        explanation=req.form.get('explanation', '').strip(),
        media_url=img_name if img_name else None,
        explanation_media_url=exp_img_name if exp_img_name else None
    )

def _save_answers(question, form):
    q_type = form.get('type', question.type)
    if q_type == 'PG':
        texts   = form.getlist('option_text')
        correct = form.get('correct_option', '-1')
        for i, text in enumerate(texts):
            text = text.strip()
            if not text:
                continue
            question.answers.append(
                Answer(text=text, is_correct=(str(i) == correct))
            )
    else:  # Isian
        variants = form.get('correct_variants', '')
        for v in variants.split(','):
            v = v.strip()
            if v:
                question.answers.append(Answer(text=v, is_correct=True))

# ── ANALYTICS & REMEDIAL ───────────────────────────────────────────────────────
@guru_bp.route('/analytics')
@login_required
@role_required('guru', 'admin')
def analytics():
    """Halaman index analytics: daftar semua stage dengan ringkasan."""
    stages = Stage.query.order_by(Stage.modul_id, Stage.order_index).all()
    # Hitung ringkasan sederhana per stage
    stats = []
    for s in stages:
        count = StageCompletion.query.filter_by(stage_id=s.id, mode=MODE_CHALLENGE).count()
        stats.append({
            'stage': s,
            'attempt_count': count
        })
    return render_template('guru/analytics_index.html', stats=stats)

@guru_bp.route('/analytics/<int:stage_id>')
@login_required
@role_required('guru', 'admin')
def stage_analytics(stage_id):
    stage = Stage.query.get_or_404(stage_id)
    completions = StageCompletion.query.filter_by(
        stage_id=stage_id, mode=MODE_CHALLENGE
    ).order_by(StageCompletion.completed_at.desc()).all()

    # Stats per soal: total attempt & correct count
    from sqlalchemy import func
    q_stats_raw = db.session.query(
        AttemptLog.question_id,
        func.count(AttemptLog.id).label('total'),
        func.sum(func.cast(AttemptLog.is_correct, db.Integer)).label('correct')
    ).filter_by(stage_id=stage_id, mode=MODE_CHALLENGE)\
     .group_by(AttemptLog.question_id).all()

    # Wrong options per soal (untuk misconception detection)
    wrong_options_raw = db.session.query(
        AttemptLog.question_id,
        AttemptLog.wrong_option_selected,
        func.count(AttemptLog.id).label('freq')
    ).filter_by(stage_id=stage_id, mode=MODE_CHALLENGE, is_correct=False)\
     .filter(AttemptLog.wrong_option_selected.isnot(None))\
     .group_by(AttemptLog.question_id, AttemptLog.wrong_option_selected).all()

    # Gabungkan: {question_id: {total, correct, wrong_options: [...]}}
    q_stats = {}
    for row in q_stats_raw:
        q_stats[row.question_id] = {
            'question': Question.query.get(row.question_id),
            'total': row.total,
            'correct': row.correct or 0,
            'accuracy': round((row.correct or 0) / row.total * 100, 1) if row.total else 0,
            'wrong_options': []
        }
    for row in wrong_options_raw:
        if row.question_id in q_stats:
            q_stats[row.question_id]['wrong_options'].append({
                'text': row.wrong_option_selected,
                'freq': row.freq
            })

    # Siswa yang struggling (nyawa habis / tidak clear)
    struggling = db.session.query(User).join(
        StageCompletion, StageCompletion.user_id == User.id
    ).filter(
        StageCompletion.stage_id == stage_id,
        StageCompletion.mode == MODE_CHALLENGE,
        StageCompletion.is_cleared == False
    ).distinct().all()

    # Unlock list
    unlocks = ChallengeUnlock.query.filter_by(stage_id=stage_id).all()

    return render_template('guru/analytics.html',
        stage=stage, completions=completions, q_stats=q_stats,
        struggling=struggling, unlocks=unlocks)

@guru_bp.route('/unlock-challenge', methods=['POST'])
@login_required
@role_required('guru', 'admin')
def unlock_challenge():
    user_id  = request.form.get('user_id', type=int)
    stage_id = request.form.get('stage_id', type=int)
    note     = request.form.get('note', '').strip()

    if not user_id or not stage_id:
        flash('Data tidak lengkap.', 'danger')
        return redirect(request.referrer or url_for('guru.dashboard'))

    unlock = ChallengeUnlock(
        user_id=user_id, stage_id=stage_id,
        unlocked_by=current_user.id, note=note, used=False
    )
    db.session.add(unlock)
    db.session.commit()
    user = User.query.get(user_id)
    flash(f'Akses retry challenge untuk {user.username} berhasil dibuka.', 'success')
    return redirect(request.referrer or url_for('guru.dashboard'))

@guru_bp.route('/stage/<int:stage_id>/reset-scores', methods=['POST'])
@login_required
@role_required('guru', 'admin')
def reset_stage_scores(stage_id):
    stage = Stage.query.get_or_404(stage_id)
    
    # 1. Identifikasi user yang terpengaruh (hanya mode challenge yang masuk total_points)
    affected_users = db.session.query(StageCompletion.user_id).filter_by(
        stage_id=stage_id, mode=MODE_CHALLENGE
    ).distinct().all()
    user_ids = [u[0] for u in affected_users]
    
    # 2. Hapus data terkait stage ini TERLEBIH DAHULU (agar tidak ikut dalam perhitungan ulang)
    # Hapus StageCompletion
    StageCompletion.query.filter_by(stage_id=stage_id).delete()
    
    # Hapus AttemptLog
    AttemptLog.query.filter_by(stage_id=stage_id).delete()
    
    # Hapus GameSession
    GameSession.query.filter_by(stage_id=stage_id).delete()
    
    # Hapus ChallengeUnlock
    ChallengeUnlock.query.filter_by(stage_id=stage_id).delete()
    
    db.session.flush() # Pastikan penghapusan terdaftar di session sebelum hitung ulang

    # 3. Hitung ulang total_points untuk setiap user yang terpengaruh
    for uid in user_ids:
        user = User.query.get(uid)
        if user:
            # Hitung total dari skor terbaik di stage-stage yang TERSISA
            best_scores = db.session.query(func.max(StageCompletion.score))\
                .filter_by(user_id=uid, mode=MODE_CHALLENGE)\
                .group_by(StageCompletion.stage_id).all()
            
            user.total_points = sum(s[0] for s in best_scores)
    
    db.session.commit()
    
    flash(f'Seluruh skor dan riwayat pengerjaan untuk stage "{stage.title}" berhasil direset.', 'success')
    return redirect(url_for('guru.stage_analytics', stage_id=stage_id))
