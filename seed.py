from app import create_app, db, bcrypt
from app.models import User, RoleEnum

app = create_app()

with app.app_context():
    db.create_all()

    # Cek apakah admin sudah ada
    if not User.query.filter_by(username='admin').first():
        hashed_pw = bcrypt.generate_password_hash('admin123').decode('utf-8')
        admin = User(username='admin', password=hashed_pw, role=RoleEnum.admin)
        db.session.add(admin)
        db.session.commit()
        print('✅ Super Admin berhasil dibuat: username=admin, password=admin123')
    else:
        print('ℹ️  Akun admin sudah ada, skip.')
