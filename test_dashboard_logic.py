from app import create_app, db
from app.models import (Modul, Stage, Question, Answer, User,
                        GameSession, AttemptLog, StageCompletion, ChallengeUnlock,
                        MODE_PRACTICE, MODE_CHALLENGE, LEVEL_ORDER)
from flask_login import login_user

app = create_app()

with app.app_context():
    # Try to find a student user
    student = User.query.filter_by(username='siswa1').first()
    if not student:
        student = User.query.filter_by(role='siswa').first()
    
    if not student:
        print("No student found")
        exit()

    print(f"Testing for user: {student.username} (ID: {student.id})")

    try:
        moduls = Modul.query.filter_by(is_active=True).order_by(Modul.order_index).all()
        print(f"Moduls found: {len(moduls)}")

        challenge_best = {}
        for c in StageCompletion.query.filter_by(user_id=student.id, mode=MODE_CHALLENGE).all():
            if c.stage_id not in challenge_best or c.score > challenge_best[c.stage_id].score:
                challenge_best[c.stage_id] = c
        print(f"Challenge best found: {len(challenge_best)}")

        active_challenge = {
            s.stage_id: s for s in
            GameSession.query.filter_by(user_id=student.id, mode=MODE_CHALLENGE, is_active=True).all()
        }
        print(f"Active challenges found: {len(active_challenge)}")

        unlocks = {
            u.stage_id for u in
            ChallengeUnlock.query.filter_by(user_id=student.id, used=False).all()
        }
        print(f"Unlocks found: {len(unlocks)}")

        stage_paths = {}
        all_sessions = GameSession.query.filter_by(user_id=student.id)\
                                        .order_by(GameSession.attempt_number.desc()).all()
        seen_stages = set()
        for sess in all_sessions:
            if sess.stage_id not in seen_stages:
                seen_stages.add(sess.stage_id)
                logs = AttemptLog.query.filter_by(session_id=sess.id)\
                                       .order_by(AttemptLog.timestamp).all()
                stage_paths[sess.stage_id] = [{'is_correct': l.is_correct} for l in logs]
        print(f"Stage paths found: {len(stage_paths)}")

        print("Success!")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
