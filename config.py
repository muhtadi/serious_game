import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-ganti-di-production')
    
    # Database (Enforce PostgreSQL/Supabase)
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        raise ValueError("DATABASE_URL must be set in Environment Variables (Supabase).")
    
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    SQLALCHEMY_DATABASE_URI = db_url
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Supabase Storage (Enforce)
    SUPABASE_URL = os.environ.get('SUPABASE_URL')
    SUPABASE_KEY = os.environ.get('SUPABASE_KEY')
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set.")
        
    SUPABASE_BUCKET = os.environ.get('SUPABASE_BUCKET', 'media')
    
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5 MB limit
    ALLOWED_IMAGE = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    ALLOWED_AUDIO = {'mp3', 'ogg', 'wav'}
