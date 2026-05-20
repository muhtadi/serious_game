from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import (Modul, Stage, Question, Answer, User, RoleEnum,
                        GameSession, AttemptLog, StageCompletion, ChallengeUnlock,
                        MODE_PRACTICE, MODE_CHALLENGE, LEVEL_ORDER)
from app.utils import role_required, get_student_competency_data
from datetime import datetime, timezone
from sqlalchemy import func
import json, random

siswa_bp = Blueprint('siswa', __name__)

# ── Dashboard ──────────────────────────────────────────────────────────────────
@siswa_bp.route('/dashboard')
@login_required
@role_required('siswa')
def dashboard():
    moduls = Modul.query.filter_by(is_active=True).order_by(Modul.order_index).all()

    # Best challenge completion per stage
    challenge_best = {}
    for c in StageCompletion.query.filter_by(user_id=current_user.id, mode=MODE_CHALLENGE).all():
        if c.stage_id not in challenge_best or c.score > challenge_best[c.stage_id].score:
            challenge_best[c.stage_id] = c

    # Sesi challenge aktif
    active_challenge = {
        s.stage_id: s for s in
        GameSession.query.filter_by(user_id=current_user.id, mode=MODE_CHALLENGE, is_active=True).all()
    }

    # Unlock remedial yang belum dipakai
    unlocks = {
        u.stage_id for u in
        ChallengeUnlock.query.filter_by(user_id=current_user.id, used=False).all()
    }

    # Path log per stage dan Session ID terakhir untuk Review
    stage_paths = {}
    last_session_ids = {}
    all_sessions = GameSession.query.filter_by(user_id=current_user.id)\
                                    .order_by(GameSession.attempt_number.desc()).all()
    seen_stages = set()
    for sess in all_sessions:
        if sess.stage_id not in seen_stages:
            seen_stages.add(sess.stage_id)
            last_session_ids[sess.stage_id] = sess.id
            logs = AttemptLog.query.filter_by(session_id=sess.id)\
                                   .order_by(AttemptLog.timestamp).all()
            stage_paths[sess.stage_id] = [
                {'is_correct': l.is_correct, 'level': l.level_at_attempt} 
                for l in logs
            ]

    return render_template('siswa/dashboard.html',
                           moduls=moduls,
                           challenge_best=challenge_best,
                           active_challenge=active_challenge,
                           unlocks=unlocks,
                           stage_paths=stage_paths,
                           last_session_ids=last_session_ids)

# ── Mulai Sesi ─────────────────────────────────────────────────────────────────
@siswa_bp.route('/stage/<int:stage_id>/start', methods=['POST'])
@login_required
@role_required('siswa')
def stage_start(stage_id):
    stage = Stage.query.filter_by(id=stage_id, is_active=True).first_or_404()
    if not stage.modul.is_active:
        flash('Stage ini tidak tersedia.', 'warning')
        return redirect(url_for('siswa.dashboard'))

    # Mode diambil dari stage, bukan dari modul
    mode = stage.mode

    if mode == MODE_CHALLENGE:
        # Cek apakah ada sesi challenge aktif
        active = GameSession.query.filter_by(
            user_id=current_user.id, stage_id=stage_id,
            mode=MODE_CHALLENGE, is_active=True).first()
        if active:
            return redirect(url_for('siswa.game', session_id=active.id))

        # Cek apakah sudah pernah challenge (dan tidak ada unlock)
        prev = GameSession.query.filter_by(
            user_id=current_user.id, stage_id=stage_id, mode=MODE_CHALLENGE
        ).filter(GameSession.is_active == False).first()

        if prev:
            unlock = ChallengeUnlock.query.filter_by(
                user_id=current_user.id, stage_id=stage_id, used=False).first()
            if not unlock:
                flash('Challenge Mode hanya 1 kali. Minta guru untuk membuka akses retry.', 'warning')
                return redirect(url_for('siswa.dashboard'))
            # Pakai unlock
            unlock.used = True
            db.session.commit()

    # Hitung attempt number per mode
    last = GameSession.query.filter_by(
        user_id=current_user.id, stage_id=stage_id, mode=mode
    ).order_by(GameSession.attempt_number.desc()).first()
    attempt_num = (last.attempt_number + 1) if last else 1

    sess = GameSession(
        user_id=current_user.id, stage_id=stage_id,
        mode=mode, attempt_number=attempt_num,
        current_level='Easy', nyawa=3, wrong_streak=0,
        is_active=True, is_cleared=False,
        used_question_ids='[]'
    )
    db.session.add(sess)
    db.session.commit()
    return redirect(url_for('siswa.game', session_id=sess.id))

# ── Halaman Game ───────────────────────────────────────────────────────────────
@siswa_bp.route('/game/<session_id>')
@login_required
@role_required('siswa')
def game(session_id):
    sess = _get_session(session_id)
    if not sess:
        flash('Sesi tidak ditemukan.', 'danger')
        return redirect(url_for('siswa.dashboard'))
    if not sess.is_active:
        return redirect(url_for('siswa.stage_result', session_id=session_id))

    q = _pick_question(sess)
    if q is None:
        flash('Soal habis untuk level ini. Hubungi guru untuk menambah soal.', 'warning')
        return redirect(url_for('siswa.dashboard'))

    answers_data = [{'id': a.id, 'text': a.text} for a in q.answers] \
                   if q.type == 'PG' else []

    # Hitung mastery & skor sementara dari sesi ini
    logs = AttemptLog.query.filter_by(session_id=session_id).all()
    temp_mastery = _calc_mastery(logs)
    temp_score   = _calc_current_session_score(sess)

    return render_template('siswa/game.html',
        sess=sess, stage=sess.stage, question=q,
        answers=answers_data,
        level_order=LEVEL_ORDER,
        is_practice=(sess.mode == MODE_PRACTICE),
        temp_mastery=temp_mastery,
        temp_score=temp_score
    )

# ── Submit Jawaban ─────────────────────────────────────────────────────────────
@siswa_bp.route('/game/<session_id>/submit', methods=['POST'])
@login_required
@role_required('siswa')
def game_submit(session_id):
    sess = _get_session(session_id)
    if not sess or not sess.is_active:
        return jsonify({'error': 'Sesi tidak valid'}), 400

    if not request.is_json:
        return jsonify({'error': 'Expected JSON'}), 400

    data        = request.get_json()
    question_id = data.get('question_id')
    user_answer = str(data.get('answer', '')).strip()
    time_spent  = float(data.get('time_spent', 0))

    q = Question.query.get_or_404(question_id)
    is_correct, correct_text, wrong_option = _check_answer(q, user_answer)

    # Tandai soal sudah dipakai
    used = json.loads(sess.used_question_ids)
    if question_id not in used:
        used.append(question_id)
        sess.used_question_ids = json.dumps(used)

    # Log
    log = AttemptLog(
        session_id           = sess.id,
        user_id              = current_user.id,
        stage_id             = sess.stage_id,
        modul_id             = sess.stage.modul_id,
        question_id          = question_id,
        mode                 = sess.mode,
        attempt_number       = sess.attempt_number,
        level_at_attempt     = sess.current_level,
        difficulty_tier      = q.difficulty_tier,
        answer_submitted     = user_answer,
        wrong_option_selected= wrong_option,
        is_correct           = is_correct,
        time_spent_seconds   = time_spent,
        timestamp            = datetime.now(timezone.utc)
    )
    db.session.add(log)

    # ── Adaptive Logic ─────────────────────────────────────────────────────────
    event = None
    if is_correct:
        sess.wrong_streak = 0
        idx = LEVEL_ORDER.index(sess.current_level)
        if idx < len(LEVEL_ORDER) - 1:
            sess.current_level = LEVEL_ORDER[idx + 1]
            event = 'level_up'
        else:
            event = 'stage_clear'
            sess.is_active  = False
            sess.is_cleared = True
            sess.completed_at = datetime.now(timezone.utc)
    else:
        sess.nyawa -= 1
        sess.wrong_streak += 1
        if sess.nyawa <= 0:
            event = 'game_over'
            sess.is_active = False
            sess.completed_at = datetime.now(timezone.utc)
        elif sess.wrong_streak >= 2:
            # Turun level hanya jika sudah salah 2x berturut-turut
            idx = LEVEL_ORDER.index(sess.current_level)
            if idx > 0:
                sess.current_level = LEVEL_ORDER[idx - 1]
                event = 'level_down'
            sess.wrong_streak = 0
        else:
            # Salah 1x -> tetap di level
            event = 'wrong_stay'

    db.session.commit()

    result_url = None
    if event in ('stage_clear', 'game_over'):
        _save_completion(sess)
        result_url = url_for('siswa.stage_result', session_id=sess.id)

    # Hint hanya untuk practice mode
    hint = None
    if not is_correct and sess.mode == MODE_PRACTICE and q.explanation:
        hint = q.explanation

    # Hitung skor sementara sesi ini untuk ditampilkan di HUD
    temp_score = _calc_current_session_score(sess)

    return jsonify({
        'is_correct'   : is_correct,
        'correct_text' : correct_text,
        'explanation'  : q.explanation or '',  # selalu kirim pembahasan
        'explanation_media_url': q.explanation_media_url or None,
        'hint'         : hint,
        'event'        : event,
        'nyawa'        : max(0, sess.nyawa),
        'current_level': sess.current_level,
        'result_url'   : result_url,
        'is_practice'  : sess.mode == MODE_PRACTICE,
        'current_score': temp_score
    })

# ── Hasil ──────────────────────────────────────────────────────────────────────
@siswa_bp.route('/result/<session_id>')
@login_required
@role_required('siswa')
def stage_result(session_id):
    sess = _get_session(session_id)
    if not sess:
        return redirect(url_for('siswa.dashboard'))
    completion = StageCompletion.query.filter_by(session_id=session_id).first()
    logs = AttemptLog.query.filter_by(session_id=session_id)\
                           .order_by(AttemptLog.timestamp).all()
    # Attach question object ke setiap log untuk tampil pembahasan
    for log in logs:
        log._question = Question.query.get(log.question_id)
    
    # Calculate detailed breakdown for the template
    breakdown = _calc_score_breakdown(sess, logs, completion)

    return render_template('siswa/result.html',
                           sess=sess, completion=completion, logs=logs,
                           is_practice=(sess.mode == MODE_PRACTICE),
                           breakdown=breakdown)

# ── Leaderboard Sorting Update ────────────────────────────────────────────────
@siswa_bp.route('/game/<session_id>/next')
@login_required
@role_required('siswa')
def game_next(session_id):
    """Ambil soal berikutnya tanpa reload halaman penuh."""
    sess = _get_session(session_id)
    if not sess or not sess.is_active:
        return jsonify({'error': 'Sesi tidak aktif'}), 400

    q = _pick_question(sess)
    if q is None:
        return jsonify({'error': 'Soal habis'}), 404

    answers_data = [{'id': a.id, 'text': a.text} for a in q.answers] \
                   if q.type == 'PG' else []

    # Hitung skor sementara sesi ini
    temp_score = _calc_current_session_score(sess)

    return jsonify({
        'question_id'  : q.id,
        'type'         : q.type,
        'content_text' : q.content_text,
        'media_url'    : (q.media_url if q.media_url and
                          (q.media_url.startswith('http') or q.media_url.startswith('/'))
                          else url_for('static', filename=q.media_url) if q.media_url else None),
        'difficulty_tier': q.difficulty_tier,
        'answers'      : answers_data,
        'current_score': temp_score
    })

@siswa_bp.route('/leaderboard/<int:stage_id>')
@login_required
@role_required('siswa')
def leaderboard(stage_id):
    stage = Stage.query.get_or_404(stage_id)
    
    # Ambil semua percobaan di stage ini (Challenge Mode)
    all_rows = StageCompletion.query.filter_by(
        stage_id=stage_id,
        mode=MODE_CHALLENGE
    ).order_by(StageCompletion.score.desc(), StageCompletion.total_time_seconds.asc()).all()

    # Filter unik per user (ambil yang terbaik saja)
    seen_users = set()
    rows = []
    for r in all_rows:
        if r.user_id not in seen_users:
            rows.append(r)
            seen_users.add(r.user_id)

    return render_template('siswa/leaderboard.html', stage=stage, rows=rows)

# ── Leaderboard Global ───────────────────────────────────────────────────────
@siswa_bp.route('/leaderboards')
@login_required
@role_required('siswa')
def leaderboards():
    """Semua leaderboard per stage + Peringkat Global."""
    # 1. Peringkat Global
    global_users = User.query.filter(User.role == RoleEnum.siswa)\
                             .order_by(User.total_points.desc(), User.username.asc()).all()

    # 2. Ringkasan Top 5 per Stage
    stages = Stage.query.filter_by(is_active=True).order_by(Stage.order_index).all()
    leaderboard_data = []
    for stage in stages:
        all_comp = StageCompletion.query.filter_by(
            stage_id=stage.id,
            mode=MODE_CHALLENGE
        ).order_by(StageCompletion.score.desc(), StageCompletion.total_time_seconds.asc()).all()

        seen_users = set()
        top_rows = []
        for r in all_comp:
            if r.user_id not in seen_users:
                # Attach user secara manual untuk memastikan aman di template
                r._user = User.query.get(r.user_id)
                top_rows.append(r)
                seen_users.add(r.user_id)
            if len(top_rows) >= 5:
                break
            
        leaderboard_data.append({
            'stage': stage,
            'rows': top_rows
        })

    return render_template('siswa/leaderboards.html', 
                           global_users=global_users,
                           leaderboard_data=leaderboard_data)

# ── Analytics Siswa ──────────────────────────────────────────────────────────
@siswa_bp.route('/analytics')
@login_required
@role_required('siswa')
def analytics():
    """Dashboard analytics untuk siswa sendiri."""
    # Semua completion siswa
    completions = StageCompletion.query.filter_by(
        user_id=current_user.id
    ).order_by(StageCompletion.completed_at.desc()).all()

    # Attach stage info
    for c in completions:
        c._stage = Stage.query.get(c.stage_id)
        c._modul = Modul.query.get(c._stage.modul_id) if c._stage else None

    # Statistik
    total_stages = len(set(c.stage_id for c in completions))
    total_score = sum(c.score for c in completions)
    avg_mastery = sum(c.mastery_percentage for c in completions) / len(completions) if completions else 0

    # Per modul
    modul_stats = {}
    for c in completions:
        mod_id = c._stage.modul_id if c._stage else None
        if mod_id:
            if mod_id not in modul_stats:
                modul_stats[mod_id] = {'modul': c._modul, 'stages': 0, 'total_score': 0, 'avg_mastery': []}
            modul_stats[mod_id]['stages'] += 1
            modul_stats[mod_id]['total_score'] += c.score
            modul_stats[mod_id]['avg_mastery'].append(c.mastery_percentage)
    for m in modul_stats:
        avg = modul_stats[m]['avg_mastery']
        modul_stats[m]['avg_mastery'] = sum(avg) / len(avg) if avg else 0

    # Competency Data for Spider Charts
    dt_data, ct_data = get_student_competency_data(current_user.id)

    return render_template('siswa/analytics.html',
                           completions=completions,
                           total_stages=total_stages,
                           total_score=total_score,
                           avg_mastery=round(avg_mastery, 1),
                           modul_stats=modul_stats.values(),
                           dt_data=dt_data,
                           ct_data=ct_data)

# ── Helpers ────────────────────────────────────────────────────────────────────
def _get_session(session_id):
    return GameSession.query.filter_by(
        id=session_id, user_id=current_user.id).first()

def _pick_question(sess):
    used = json.loads(sess.used_question_ids)
    q = Question.query.filter_by(
        stage_id=sess.stage_id,
        difficulty_tier=sess.current_level,
        is_active=True
    ).filter(~Question.id.in_(used) if used else True).all()
    return random.choice(q) if q else None

def _check_answer(q, user_answer):
    wrong_option = None
    if q.type == 'PG':
        correct = next((a for a in q.answers if a.is_correct), None)
        is_correct = bool(correct and str(correct.id) == user_answer)
        correct_text = correct.text if correct else ''
        if not is_correct:
            chosen = next((a for a in q.answers if str(a.id) == user_answer), None)
            wrong_option = chosen.text if chosen else user_answer
    else:
        variants = [a.text.strip().lower() for a in q.answers if a.is_correct]
        is_correct = user_answer.lower() in variants
        correct_text = ', '.join(a.text for a in q.answers if a.is_correct)
        if not is_correct:
            wrong_option = user_answer
    return is_correct, correct_text, wrong_option

def _calc_mastery(logs):
    if not logs:
        return 0.0
    return round(sum(1 for l in logs if l.is_correct) / len(logs) * 100, 1)

def _calc_current_session_score(sess):
    logs = AttemptLog.query.filter_by(session_id=sess.id).all()
    if not logs: return 0
    
    BASE_POINTS = {'Easy': 100, 'Medium': 150, 'Hard': 200}
    TARGET_TIME = {'Easy': 30, 'Medium': 60, 'Hard': 120}
    TIME_BONUS_FACTOR = 2
    
    score = 0
    for log in logs:
        if log.is_correct:
            base = BASE_POINTS.get(log.difficulty_tier, 100)
            target = TARGET_TIME.get(log.difficulty_tier, 60)
            time_spent = log.time_spent_seconds or 0
            time_bonus = 0
            if time_spent < target:
                time_bonus = int((target - time_spent) * TIME_BONUS_FACTOR)
                time_bonus = min(time_bonus, int(base * 0.5))
            score += (base + time_bonus)
            
    # Selama game berjalan, kita tidak tampilkan bonus nyawa/clear agar ada kejutan di akhir
    return score

def _calc_score_breakdown(sess, logs, completion):
    if not completion: return None
    
    BASE_POINTS = {'Easy': 100, 'Medium': 150, 'Hard': 200}
    TARGET_TIME = {'Easy': 30, 'Medium': 60, 'Hard': 120}
    TIME_BONUS_FACTOR = 2
    
    # Breakdown structure
    breakdown = {
        'questions': [], # {tier, base, time_bonus}
        'total_base': 0,
        'total_time_bonus': 0,
        'clear_bonus': 500 if completion.is_cleared else 0,
        'health_bonus': completion.nyawa_remaining * 100
    }
    
    for log in logs:
        if log.is_correct:
            base = BASE_POINTS.get(log.difficulty_tier, 100)
            target = TARGET_TIME.get(log.difficulty_tier, 60)
            time_spent = log.time_spent_seconds or 0
            time_bonus = 0
            if time_spent < target:
                time_bonus = int((target - time_spent) * TIME_BONUS_FACTOR)
                time_bonus = min(time_bonus, int(base * 0.5))
            
            breakdown['questions'].append({
                'tier': log.difficulty_tier,
                'base': base,
                'time_bonus': time_bonus
            })
            breakdown['total_base'] += base
            breakdown['total_time_bonus'] += time_bonus
            
    return breakdown

def _save_completion(sess):
    logs = AttemptLog.query.filter_by(session_id=sess.id).all()
    if not logs: return

    # ── Konstanta Scoring ──
    # Poin Dasar
    BASE_POINTS = {'Easy': 100, 'Medium': 150, 'Hard': 200}
    # Target Waktu (detik) untuk Bonus
    TARGET_TIME = {'Easy': 30, 'Medium': 60, 'Hard': 120}
    TIME_BONUS_FACTOR = 2  # Poin per detik sisa
    
    final_score = 0
    
    # 1. Hitung Poin dari Jawaban Benar + Bonus Waktu
    for log in logs:
        if log.is_correct:
            base = BASE_POINTS.get(log.difficulty_tier, 100)
            target = TARGET_TIME.get(log.difficulty_tier, 60)
            
            # Bonus Waktu: (Target - Waktu) * Faktor
            time_spent = log.time_spent_seconds or 0
            time_bonus = 0
            if time_spent < target:
                time_bonus = int((target - time_spent) * TIME_BONUS_FACTOR)
                # Batasi bonus waktu maksimal 50% dari poin dasar agar tidak terlalu timpang
                time_bonus = min(time_bonus, int(base * 0.5))
            
            final_score += (base + time_bonus)

    # 2. Bonus Penyelesaian Stage (Dihapus)
        
    # 3. Bonus Nyawa (Hanya jika clear atau di mode challenge)
    health_bonus = max(0, sess.nyawa) * 100
    final_score += health_bonus

    # 4. Kalkulasi Mastery % (Tetap untuk statistik/chart)
    weights = {'Easy': 1, 'Medium': 2, 'Hard': 3}
    sum_correct_weight = sum(weights.get(l.difficulty_tier, 1) for l in logs if l.is_correct)
    sum_total_weight   = sum(weights.get(l.difficulty_tier, 1) for l in logs)
    mastery_pct = round((sum_correct_weight / sum_total_weight * 100), 1) if sum_total_weight > 0 else 0

    comp = StageCompletion(
        session_id          = sess.id,
        user_id             = current_user.id,
        stage_id            = sess.stage_id,
        modul_id            = sess.stage.modul_id,
        mode                = sess.mode,
        attempt_number      = sess.attempt_number,
        total_answered      = len(logs),
        correct_easy        = sum(1 for l in logs if l.is_correct and l.difficulty_tier == 'Easy'),
        correct_medium      = sum(1 for l in logs if l.is_correct and l.difficulty_tier == 'Medium'),
        correct_hard        = sum(1 for l in logs if l.is_correct and l.difficulty_tier == 'Hard'),
        wrong_count         = sum(1 for l in logs if not l.is_correct),
        accuracy            = mastery_pct,
        mastery_percentage  = mastery_pct,
        final_level_reached = sess.current_level,
        is_cleared          = sess.is_cleared,
        nyawa_remaining     = max(0, sess.nyawa),
        total_time_seconds  = sum(l.time_spent_seconds or 0 for l in logs),
        score               = final_score,
        progression_path    = json.dumps([l.level_at_attempt for l in logs]),
        completed_at        = datetime.now(timezone.utc)
    )
    db.session.add(comp)
    db.session.flush()

    # Update total_points hanya dari challenge mode
    if sess.mode == MODE_CHALLENGE:
        # Hitung ulang total points dari semua skor terbaik per stage (Challenge Mode)
        best_scores = db.session.query(func.max(StageCompletion.score))\
            .filter_by(user_id=current_user.id, mode=MODE_CHALLENGE)\
            .group_by(StageCompletion.stage_id).all()
        
        current_user.total_points = sum(s[0] for s in best_scores)

    db.session.commit()
