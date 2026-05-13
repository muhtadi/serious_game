from app import create_app, db
from sqlalchemy import text

app = create_app()
with app.app_context():
    columns = [
        ('full_name', 'VARCHAR(100)'),
        ('kelas', 'VARCHAR(20)'),
        ('profile_picture', 'VARCHAR(255)')
    ]
    
    for col_name, col_type in columns:
        try:
            db.session.execute(text(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}"))
            db.session.commit()
            print(f"Column {col_name} added successfully.")
        except Exception as e:
            db.session.rollback()
            print(f"Column {col_name} already exists or error: {e}")
