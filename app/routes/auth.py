from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required
from app import db, bcrypt
from app.models import User, RoleEnum

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/', methods=['GET', 'POST'])
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        user = User.query.filter_by(username=username).first()

        if user and bcrypt.check_password_hash(user.password, password):
            login_user(user)
            # Redirect berdasarkan role
            if user.role == RoleEnum.admin:
                return redirect(url_for('admin.dashboard'))
            elif user.role == RoleEnum.guru:
                return redirect(url_for('guru.dashboard'))
            else:
                return redirect(url_for('siswa.dashboard'))
        else:
            flash('Username atau password salah.', 'danger')

    return render_template('auth/login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Anda telah logout.', 'info')
    return redirect(url_for('auth.login'))
