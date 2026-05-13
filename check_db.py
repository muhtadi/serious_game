from app import create_app, db
from sqlalchemy import inspect

app = create_app()
with app.app_context():
    inspector = inspect(db.engine)
    columns = [c['name'] for c in inspector.get_columns('users')]
    print("Columns in users table:", columns)
    
    columns_comp = [c['name'] for c in inspector.get_columns('stage_completions')]
    print("Columns in stage_completions table:", columns_comp)
