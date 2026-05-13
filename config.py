import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'local-secret-key-ganti-jika-perlu')

    # SQLite — file tunggal, tidak perlu install apapun
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(BASE_DIR, 'game.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Upload lokal ke static/uploads
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10 MB
    ALLOWED_IMAGE = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    ALLOWED_AUDIO = {'mp3', 'ogg', 'wav'}

    # Supabase dikosongkan — tidak dipakai di mode lokal
    SUPABASE_URL    = None
    SUPABASE_KEY    = None
    SUPABASE_BUCKET = None
