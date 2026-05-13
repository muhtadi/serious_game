from app import create_app, db
from app.models import Question, Stage
from sqlalchemy import func

app = create_app()
with app.app_context():
    # Hitung jumlah soal per stage dan per level
    counts = db.session.query(
        Stage.id, 
        Stage.title, 
        Question.difficulty_tier, 
        func.count(Question.id)
    ).outerjoin(Question, (Stage.id == Question.stage_id) & (Question.is_active == True))\
     .group_by(Stage.id, Question.difficulty_tier)\
     .all()
    
    print("REKAP JUMLAH SOAL PER STAGE & LEVEL:")
    print("-" * 50)
    current_id = None
    for sid, title, tier, count in counts:
        if sid != current_id:
            print(f"\nStage: {title} (ID: {sid})")
            current_id = sid
        print(f"  - {tier if tier else 'Tidak Ada'}: {count} soal")
