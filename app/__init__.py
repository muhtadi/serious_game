from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_bcrypt import Bcrypt
from config import Config

db = SQLAlchemy()
login_manager = LoginManager()
bcrypt = Bcrypt()

def create_app():
    app = Flask(__name__, template_folder='../templates', static_folder='../static')
    app.config.from_object(Config)

    db.init_app(app)
    bcrypt.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Silakan login terlebih dahulu.'
    login_manager.login_message_category = 'warning'

    # Custom Jinja2 filter
    app.jinja_env.filters['enumerate'] = enumerate
    app.jinja_env.filters['from_json'] = lambda s: __import__('json').loads(s or '[]')

    # Filter media_url: return as-is jika sudah URL penuh, else buat static URL
    def media_url(path):
        if not path:
            return ''
        if path.startswith('http://') or path.startswith('https://'):
            return path
        from flask import url_for
        return url_for('static', filename=path)
    app.jinja_env.filters['media_url'] = media_url

    # Return JSON 401 untuk fetch/AJAX request agar tidak redirect ke login
    @login_manager.unauthorized_handler
    def unauthorized():
        from flask import request as req, jsonify, redirect, url_for
        if req.is_json or req.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'error': 'Unauthorized', 'redirect': url_for('auth.login')}), 401
        return redirect(url_for('auth.login'))

    from app.routes.auth import auth_bp
    from app.routes.admin import admin_bp
    from app.routes.guru import guru_bp
    from app.routes.siswa import siswa_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(guru_bp, url_prefix='/guru')
    app.register_blueprint(siswa_bp, url_prefix='/siswa')

    # Database Initialization
    with app.app_context():
        db.create_all()
        
        # Otopmatis buat admin jika database masih kosong (sangat berguna untuk deploy pertama)
        from app.models import User, RoleEnum
        if not User.query.filter_by(role=RoleEnum.admin).first():
            admin_user = User(
                username='admin',
                password=bcrypt.generate_password_hash('admin123').decode('utf-8'),
                role=RoleEnum.admin
            )
            db.session.add(admin_user)
            db.session.commit()
            app.logger.info("Default admin created: admin / admin123")

    return app
