from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app import db, bcrypt
from app.models import User, RoleEnum, KELAS_CHOICES
from app.utils import save_upload

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/', methods=['GET', 'POST'])
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if current_user.role == RoleEnum.admin:
            return redirect(url_for('admin.dashboard'))
        elif current_user.role == RoleEnum.guru:
            return redirect(url_for('guru.dashboard'))
        else:
            return redirect(url_for('siswa.dashboard'))

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

@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        username  = request.form.get('username', '').strip()
        password  = request.form.get('password', '')
        kelas     = request.form.get('kelas', '').strip()
        
        # Logika pembatasan: Siswa tidak bisa ubah username, nama, dan kelas
        is_siswa = (current_user.role == RoleEnum.siswa)
        
        if not is_siswa:
            # Hanya Non-Siswa (Guru/Admin) yang bisa ubah data identitas
            if username and username != current_user.username:
                existing = User.query.filter_by(username=username).first()
                if existing:
                    flash('Username sudah digunakan.', 'danger')
                    return redirect(url_for('auth.profile'))
                current_user.username = username
            
            if full_name:
                current_user.full_name = full_name
            if kelas:
                current_user.kelas = kelas
        
        # Semua role (termasuk Siswa) bisa ubah password
        if password:
            current_user.password = bcrypt.generate_password_hash(password).decode('utf-8')
            
        # Semua role (termasuk Siswa) bisa ubah foto profil
        if 'profile_picture' in request.files:
            file = request.files['profile_picture']
            if file and file.filename != '':
                url = save_upload(file, {'png', 'jpg', 'jpeg', 'webp'})
                if url:
                    current_user.profile_picture = url
        
        db.session.commit()
        flash('Profil berhasil diperbarui.', 'success')
        return redirect(url_for('auth.profile'))
        
    return render_template('auth/profile.html', kelas_choices=KELAS_CHOICES)
