from app import create_app, db
from sqlalchemy import text

app = create_app()
with app.app_context():
    try:
        db.session.execute(text("ALTER TABLE questions ADD COLUMN explanation_media_url VARCHAR(255)"))
        db.session.commit()
        print("Column explanation_media_url added successfully.")
    except Exception as e:
        db.session.rollback()
        print(f"Error or column already exists: {e}")
