import sqlite3
import os

def migrate():
    db_path = 'game.db'
    if not os.path.exists(db_path):
        print(f"Database {db_path} not found.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    new_columns = [
        ('decomposition', 'BOOLEAN DEFAULT 0'),
        ('abstraction_ct', 'BOOLEAN DEFAULT 0'),
        ('modelling_simulation', 'BOOLEAN DEFAULT 0'),
        ('algorithms_ct', 'BOOLEAN DEFAULT 0'),
        ('evaluation', 'BOOLEAN DEFAULT 0')
    ]
    
    for col_name, col_type in new_columns:
        try:
            print(f"Adding column {col_name}...")
            cursor.execute(f"ALTER TABLE stages ADD COLUMN {col_name} {col_type}")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                print(f"Column {col_name} already exists.")
            else:
                print(f"Error adding {col_name}: {e}")
    
    conn.commit()
    conn.close()
    print("Migration complete.")

if __name__ == "__main__":
    migrate()
