import sqlite3
import os

def migrate():
    db_path = 'game.db'
    if not os.path.exists(db_path):
        print(f"Database {db_path} not found.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    curriculum_keys = [
        'abstraction', 'data_collection', 'data_representation', 'data_interpretation',
        'specification', 'algorithms', 'implementation', 'digital_systems', 'interactions', 'impact'
    ]
    ct_skill_keys = [
        'decomposition', 'abstraction_ct', 'modelling_simulation', 'algorithms_ct', 'evaluation'
    ]
    
    all_keys = curriculum_keys + ct_skill_keys
    
    # 1. Tambah kolom ke tabel questions
    for col_name in all_keys:
        try:
            print(f"Adding column {col_name} to questions...")
            cursor.execute(f"ALTER TABLE questions ADD COLUMN {col_name} BOOLEAN DEFAULT 0")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                print(f"Column {col_name} already exists in questions.")
            else:
                print(f"Error adding {col_name} to questions: {e}")

    # 2. (Opsional) Migrasi data dari stages ke questions
    # Jika guru sudah set di stage, kita copy ke semua soal di stage tersebut
    print("Migrating data from stages to questions...")
    cursor.execute("SELECT id, " + ", ".join(all_keys) + " FROM stages")
    stages = cursor.fetchall()
    
    for stage in stages:
        stage_id = stage[0]
        values = stage[1:]
        
        set_clause = ", ".join([f"{all_keys[i]} = ?" for i in range(len(all_keys))])
        cursor.execute(f"UPDATE questions SET {set_clause} WHERE stage_id = ?", values + (stage_id,))
    
    conn.commit()
    conn.close()
    print("Migration complete.")

if __name__ == "__main__":
    migrate()
