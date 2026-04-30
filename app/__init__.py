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

    # Auto-migration for new CT Skill columns
    with app.app_context():
        db.create_all()
        from sqlalchemy import text
        try:
            # Check existing columns
            res = db.session.execute(text("PRAGMA table_info(stages)")).fetchall()
            existing_cols = [row[1] for row in res]
            
            new_cols = [
                ('decomposition', 'BOOLEAN DEFAULT 0'),
                ('abstraction_ct', 'BOOLEAN DEFAULT 0'),
                ('modelling_simulation', 'BOOLEAN DEFAULT 0'),
                ('algorithms_ct', 'BOOLEAN DEFAULT 0'),
                ('evaluation', 'BOOLEAN DEFAULT 0')
            ]
            
            needs_commit = False
            for col_name, col_def in new_cols:
                if col_name not in existing_cols:
                    db.session.execute(text(f"ALTER TABLE stages ADD COLUMN {col_name} {col_def}"))
                    needs_commit = True
            
            if needs_commit:
                db.session.commit()
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Auto-migration failed: {e}")

    return app
