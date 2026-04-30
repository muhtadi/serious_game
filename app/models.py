from app import db, login_manager
from flask_login import UserMixin
import enum, uuid

def _uuid():
    return str(uuid.uuid4())

class RoleEnum(enum.Enum):
    admin = 'admin'
    guru  = 'guru'
    siswa = 'siswa'

# Mode bermain
MODE_PRACTICE  = 'practice'
MODE_CHALLENGE = 'challenge'

KELAS_CHOICES      = ['3&4', '5&6', '7&8', '9&10', '11&12']
DIFFICULTY_CHOICES = ['Easy', 'Medium', 'Hard']
LEVEL_ORDER        = ['Easy', 'Medium', 'Hard']
CURRICULUM_KEYS    = [
    'abstraction', 'data_collection', 'data_representation', 'data_interpretation',
    'specification', 'algorithms', 'implementation', 'digital_systems', 'interactions', 'impact'
]
CT_SKILL_KEYS = [
    'decomposition', 'abstraction_ct', 'modelling_simulation', 'algorithms_ct', 'evaluation'
]

# ── Auth ───────────────────────────────────────────────────────────────────────
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id           = db.Column(db.Integer, primary_key=True)
    username     = db.Column(db.String(80), unique=True, nullable=False)
    password     = db.Column(db.String(200), nullable=False)
    role         = db.Column(db.Enum(RoleEnum), nullable=False, default=RoleEnum.siswa)
    total_points = db.Column(db.Integer, default=0)

# ── Kurikulum ──────────────────────────────────────────────────────────────────
class Modul(db.Model):
    __tablename__ = 'moduls'
    id          = db.Column(db.Integer, primary_key=True)
    title       = db.Column(db.String(100), nullable=False)
    order_index = db.Column(db.Integer, nullable=False, default=0)
    is_active   = db.Column(db.Boolean, default=True)
    stages      = db.relationship('Stage', backref='modul', lazy=True,
                                  order_by='Stage.order_index')

class Stage(db.Model):
    __tablename__ = 'stages'
    id            = db.Column(db.Integer, primary_key=True)
    modul_id      = db.Column(db.Integer, db.ForeignKey('moduls.id'), nullable=False)
    title         = db.Column(db.String(100), nullable=False)
    audio_bg_url  = db.Column(db.String(255), nullable=True)
    image_url     = db.Column(db.String(255), nullable=True)
    kelas         = db.Column(db.String(10), nullable=True)
    difficulty    = db.Column(db.String(10), nullable=True)
    order_index   = db.Column(db.Integer, nullable=False, default=0)
    is_active     = db.Column(db.Boolean, default=True)
    mode          = db.Column(db.String(10), nullable=False, default=MODE_PRACTICE)  # 'practice'|'challenge'

    # Digital Technologies Key Concepts
    abstraction         = db.Column(db.Boolean, default=False)
    data_collection     = db.Column(db.Boolean, default=False)
    data_representation = db.Column(db.Boolean, default=False)
    data_interpretation = db.Column(db.Boolean, default=False)
    specification       = db.Column(db.Boolean, default=False)
    algorithms          = db.Column(db.Boolean, default=False)
    implementation      = db.Column(db.Boolean, default=False)
    digital_systems     = db.Column(db.Boolean, default=False)
    interactions        = db.Column(db.Boolean, default=False)
    impact              = db.Column(db.Boolean, default=False)

    # Computational Thinking Skill Alignment
    decomposition        = db.Column(db.Boolean, default=False)
    abstraction_ct       = db.Column(db.Boolean, default=False)
    modelling_simulation = db.Column(db.Boolean, default=False)
    algorithms_ct        = db.Column(db.Boolean, default=False)
    evaluation           = db.Column(db.Boolean, default=False)

    questions = db.relationship('Question', backref='stage', lazy=True,
                                cascade='all, delete-orphan')

class Question(db.Model):
    __tablename__ = 'questions'
    id              = db.Column(db.Integer, primary_key=True)
    stage_id        = db.Column(db.Integer, db.ForeignKey('stages.id'), nullable=False)
    difficulty_tier = db.Column(db.String(10), nullable=False, default='Easy')
    type            = db.Column(db.String(10), nullable=False)  # 'PG' | 'Isian'
    content_text    = db.Column(db.Text, nullable=False)
    media_url       = db.Column(db.String(255), nullable=True)
    explanation     = db.Column(db.Text, nullable=True)
    is_active       = db.Column(db.Boolean, default=True)

    answers = db.relationship('Answer', backref='question', lazy=True,
                              cascade='all, delete-orphan')

class Answer(db.Model):
    """Opsi jawaban guru: PG = pilihan, Isian = variasi jawaban benar."""
    __tablename__ = 'answers'
    id          = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id'), nullable=False)
    text        = db.Column(db.String(500), nullable=False)
    is_correct  = db.Column(db.Boolean, default=False)

# ── Game Session ───────────────────────────────────────────────────────────────
class GameSession(db.Model):
    """
    Satu sesi bermain (Practice atau Challenge).
    Challenge: hanya 1 attempt aktif per stage, tidak bisa retry tanpa unlock guru.
    Practice : bebas retry, ada hint & feedback.
    """
    __tablename__ = 'game_sessions'
    id             = db.Column(db.String(36), primary_key=True, default=_uuid)
    user_id        = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    stage_id       = db.Column(db.Integer, db.ForeignKey('stages.id'), nullable=False)
    mode           = db.Column(db.String(10), nullable=False, default=MODE_PRACTICE)
    attempt_number = db.Column(db.Integer, nullable=False, default=1)

    current_level  = db.Column(db.String(10), nullable=False, default='Easy')
    nyawa          = db.Column(db.Integer, nullable=False, default=3)
    wrong_streak   = db.Column(db.Integer, nullable=False, default=0)
    is_active      = db.Column(db.Boolean, default=True)
    is_cleared     = db.Column(db.Boolean, default=False)

    started_at        = db.Column(db.DateTime, nullable=False, server_default=db.func.now())
    completed_at      = db.Column(db.DateTime, nullable=True)
    used_question_ids = db.Column(db.Text, default='[]')

    stage        = db.relationship('Stage', foreign_keys=[stage_id], lazy=True)
    attempt_logs = db.relationship('AttemptLog', backref='session', lazy=True,
                                   cascade='all, delete-orphan')

# ── Logging ────────────────────────────────────────────────────────────────────
class AttemptLog(db.Model):
    """
    Log setiap jawaban siswa — data utama untuk analytics & penelitian.
    Mencatat mode, misconception (wrong option), dan waktu per soal.
    """
    __tablename__ = 'attempt_logs'
    id                   = db.Column(db.String(36), primary_key=True, default=_uuid)
    session_id           = db.Column(db.String(36), db.ForeignKey('game_sessions.id'), nullable=False)
    user_id              = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    stage_id             = db.Column(db.Integer, db.ForeignKey('stages.id'), nullable=False)
    modul_id             = db.Column(db.Integer, db.ForeignKey('moduls.id'), nullable=False)
    question_id          = db.Column(db.Integer, db.ForeignKey('questions.id'), nullable=False)
    mode                 = db.Column(db.String(10), nullable=False)   # 'practice'|'challenge'
    attempt_number       = db.Column(db.Integer, nullable=False)
    level_at_attempt     = db.Column(db.String(10), nullable=False)
    difficulty_tier      = db.Column(db.String(10), nullable=False)
    answer_submitted     = db.Column(db.Text, nullable=False)
    wrong_option_selected= db.Column(db.Text, nullable=True)  # teks opsi salah yg dipilih
    is_correct           = db.Column(db.Boolean, nullable=False)
    time_spent_seconds   = db.Column(db.Float, nullable=True)
    timestamp            = db.Column(db.DateTime, nullable=False, server_default=db.func.now())

    question = db.relationship('Question', foreign_keys=[question_id], lazy=True)

class StageCompletion(db.Model):
    """
    Ringkasan per sesi selesai. Mode challenge = data penelitian utama.
    Progress Score formula:
      (correct_easy×100) + (correct_medium×200) + (correct_hard×300) - (wrong×50) + (clear_bonus×200)
    Mastery % = correct / total × 100
    """
    __tablename__ = 'stage_completions'
    id                  = db.Column(db.String(36), primary_key=True, default=_uuid)
    session_id          = db.Column(db.String(36), db.ForeignKey('game_sessions.id'), nullable=False)
    user_id             = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    stage_id            = db.Column(db.Integer, db.ForeignKey('stages.id'), nullable=False)
    modul_id            = db.Column(db.Integer, db.ForeignKey('moduls.id'), nullable=False)
    mode                = db.Column(db.String(10), nullable=False)

    attempt_number      = db.Column(db.Integer, nullable=False)
    total_answered      = db.Column(db.Integer, nullable=False, default=0)
    correct_easy        = db.Column(db.Integer, nullable=False, default=0)
    correct_medium      = db.Column(db.Integer, nullable=False, default=0)
    correct_hard        = db.Column(db.Integer, nullable=False, default=0)
    wrong_count         = db.Column(db.Integer, nullable=False, default=0)
    accuracy            = db.Column(db.Float, nullable=False, default=0.0)
    mastery_percentage  = db.Column(db.Float, nullable=False, default=0.0)
    final_level_reached = db.Column(db.String(10), nullable=True)
    is_cleared          = db.Column(db.Boolean, nullable=False, default=False)
    nyawa_remaining     = db.Column(db.Integer, nullable=False, default=0)
    total_time_seconds  = db.Column(db.Float, nullable=False, default=0.0)
    score               = db.Column(db.Integer, nullable=False, default=0)
    progression_path    = db.Column(db.Text, default='[]')
    completed_at        = db.Column(db.DateTime, nullable=False, server_default=db.func.now())

    __table_args__ = (db.Index('ix_completion_user_stage_mode', 'user_id', 'stage_id', 'mode'),)

    user  = db.relationship('User',  foreign_keys=[user_id],  lazy=True)
    stage = db.relationship('Stage', foreign_keys=[stage_id], lazy=True)

class ChallengeUnlock(db.Model):
    """
    Guru membuka akses retry Challenge Mode untuk siswa tertentu.
    Tanpa record ini, siswa tidak bisa retry challenge setelah game over.
    """
    __tablename__ = 'challenge_unlocks'
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    stage_id   = db.Column(db.Integer, db.ForeignKey('stages.id'), nullable=False)
    unlocked_by= db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)  # guru id
    note       = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    used       = db.Column(db.Boolean, default=False)  # True setelah dipakai retry

    user  = db.relationship('User',  foreign_keys=[user_id],  lazy=True)
    stage = db.relationship('Stage', foreign_keys=[stage_id], lazy=True)
