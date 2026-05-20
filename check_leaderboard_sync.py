from app import create_app, db
from app.models import User, StageCompletion, RoleEnum, MODE_CHALLENGE
from sqlalchemy import func

app = create_app()

with app.app_context():
    students = User.query.filter_by(role=RoleEnum.siswa).all()
    
    print(f"{'Username':<15} | {'DB Points':<10} | {'Calculated':<10} | {'Status'}")
    print("-" * 50)
    
    for s in students:
        # Get best score per stage for this student
        # Subquery to get max score per stage_id
        best_scores = db.session.query(
            func.max(StageCompletion.score)
        ).filter_by(
            user_id=s.id, 
            mode=MODE_CHALLENGE
        ).group_by(StageCompletion.stage_id).all()
        
        calculated_total = sum(score[0] for score in best_scores) if best_scores else 0
        
        status = "✅ OK" if s.total_points == calculated_total else "❌ MISMATCH"
        print(f"{s.username:<15} | {s.total_points:<10} | {calculated_total:<10} | {status}")
        
        if s.total_points != calculated_total:
            # Check if there are any StageCompletions at all
            all_comps = StageCompletion.query.filter_by(user_id=s.id).all()
            print(f"   -> Total StageCompletions: {len(all_comps)}")
            for c in all_comps:
                print(f"      - Stage {c.stage_id}: Score {c.score} ({c.mode})")
