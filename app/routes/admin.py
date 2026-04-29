from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required
from app import db, bcrypt
from app.models import User, RoleEnum
from app.utils import role_required

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/dashboard')
@login_required
@role_required('admin')
def dashboard():
    users = User.query.order_by(User.role, User.username).all()
    return render_template('admin/dashboard.html', users=users)

@admin_bp.route('/create-user', methods=['POST'])
@login_required
@role_required('admin')
def create_user():
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')
    role = request.form.get('role', 'siswa')

    if not username or not password:
        flash('Username dan password tidak boleh kosong.', 'danger')
        return redirect(url_for('admin.dashboard'))

    if User.query.filter_by(username=username).first():
        flash(f'Username "{username}" sudah digunakan.', 'danger')
        return redirect(url_for('admin.dashboard'))

    try:
        role_enum = RoleEnum(role)
    except ValueError:
        flash('Role tidak valid.', 'danger')
        return redirect(url_for('admin.dashboard'))

    hashed_pw = bcrypt.generate_password_hash(password).decode('utf-8')
    new_user = User(username=username, password=hashed_pw, role=role_enum)
    db.session.add(new_user)
    db.session.commit()
    flash(f'Akun "{username}" berhasil dibuat sebagai {role}.', 'success')
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/reset-password/<int:user_id>', methods=['POST'])
@login_required
@role_required('admin')
def reset_password(user_id):
    user = User.query.get_or_404(user_id)
    new_password = request.form.get('new_password', '')

    if not new_password:
        flash('Password baru tidak boleh kosong.', 'danger')
        return redirect(url_for('admin.dashboard'))

    user.password = bcrypt.generate_password_hash(new_password).decode('utf-8')
    db.session.commit()
    flash(f'Password untuk "{user.username}" berhasil direset.', 'success')
    return redirect(url_for('admin.dashboard'))
