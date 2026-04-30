from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required
from app import db, bcrypt
from app.models import User, RoleEnum
from app.utils import role_required, get_student_competency_data

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/dashboard')
@login_required
@role_required('admin')
def dashboard():
    from app.models import Modul, Stage, Question, StageCompletion
    stats = {
        'total_siswa': User.query.filter_by(role=RoleEnum.siswa).count(),
        'total_guru': User.query.filter_by(role=RoleEnum.guru).count(),
        'total_modul': Modul.query.count(),
        'total_stage': Stage.query.count(),
        'total_soal': Question.query.count(),
        'total_selesai': StageCompletion.query.count()
    }
    return render_template('admin/dashboard_summary.html', stats=stats)

@admin_bp.route('/users')
@login_required
@role_required('admin')
def user_management():
    users = User.query.order_by(User.role, User.username).all()
    return render_template('admin/user_management.html', users=users)

@admin_bp.route('/create-user', methods=['POST'])
@login_required
@role_required('admin')
def create_user():
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')
    role = request.form.get('role', 'siswa')

    if not username or not password:
        flash('Username dan password tidak boleh kosong.', 'danger')
        return redirect(url_for('admin.user_management'))

    if User.query.filter_by(username=username).first():
        flash(f'Username "{username}" sudah digunakan.', 'danger')
        return redirect(url_for('admin.user_management'))

    try:
        role_enum = RoleEnum(role)
    except ValueError:
        flash('Role tidak valid.', 'danger')
        return redirect(url_for('admin.user_management'))

    hashed_pw = bcrypt.generate_password_hash(password).decode('utf-8')
    new_user = User(username=username, password=hashed_pw, role=role_enum)
    db.session.add(new_user)
    db.session.commit()
    flash(f'Akun "{username}" berhasil dibuat sebagai {role}.', 'success')
    return redirect(url_for('admin.user_management'))

@admin_bp.route('/reset-password/<int:user_id>', methods=['POST'])
@login_required
@role_required('admin')
def reset_password(user_id):
    user = User.query.get_or_404(user_id)
    new_password = request.form.get('new_password', '')

    if not new_password:
        flash('Password baru tidak boleh kosong.', 'danger')
        return redirect(url_for('admin.user_management'))

    user.password = bcrypt.generate_password_hash(new_password).decode('utf-8')
    db.session.commit()
    flash(f'Password untuk "{user.username}" berhasil direset.', 'success')
    return redirect(url_for('admin.user_management'))

@admin_bp.route('/delete-user/<int:user_id>', methods=['POST'])
@login_required
@role_required('admin')
def delete_user(user_id):
    from flask_login import current_user
    if user_id == current_user.id:
        flash('Anda tidak bisa menghapus akun Anda sendiri.', 'danger')
        return redirect(url_for('admin.user_management'))
    
    user = User.query.get_or_404(user_id)
    username = user.username
    db.session.delete(user)
    db.session.commit()
    flash(f'User "{username}" berhasil dihapus.', 'info')
    return redirect(url_for('admin.user_management'))

# ── STUDENT ANALYTICS ───────────────────────────────────────────────────────
@admin_bp.route('/analytics/students')
@login_required
@role_required('admin', 'guru')
def student_analytics_index():
    from app.models import StageCompletion
    students = User.query.filter_by(role=RoleEnum.siswa).order_by(User.total_points.desc()).all()
    # Add some summary stats for each student
    for s in students:
        s.completion_count = StageCompletion.query.filter_by(user_id=s.id).count()
        s.last_activity = StageCompletion.query.filter_by(user_id=s.id).order_by(StageCompletion.completed_at.desc()).first()
    return render_template('admin/student_analytics_index.html', students=students)

@admin_bp.route('/analytics/student/<int:user_id>')
@login_required
@role_required('admin', 'guru')
def student_analytics_detail(user_id):
    from app.models import StageCompletion, Modul, Stage
    student = User.query.get_or_404(user_id)
    completions = StageCompletion.query.filter_by(
        user_id=user_id
    ).order_by(StageCompletion.completed_at.desc()).all()

    # Attach stage info
    for c in completions:
        c._stage = Stage.query.get(c.stage_id)
        c._modul = Modul.query.get(c._stage.modul_id) if c._stage else None

    # Statistik
    total_stages = len(set(c.stage_id for c in completions))
    total_score = sum(c.score for c in completions)
    avg_mastery = sum(c.mastery_percentage for c in completions) / len(completions) if completions else 0

    # Competency Data for Spider Charts
    dt_data, ct_data = get_student_competency_data(user_id)

    return render_template('admin/student_analytics_detail.html',
                           student=student,
                           completions=completions,
                           total_stages=total_stages,
                           total_score=total_score,
                           avg_mastery=round(avg_mastery, 1),
                           dt_data=dt_data,
                           ct_data=ct_data)
