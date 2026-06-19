import sqlite3, os
from werkzeug.security import generate_password_hash

p = os.path.join('data', 'tasktracker.db')
con = sqlite3.connect(p)
cur = con.cursor()

task_cols = [r[1] for r in cur.execute("PRAGMA table_info(task)").fetchall()]
if 'is_owner_assigned' not in task_cols:
    cur.execute("ALTER TABLE task ADD COLUMN is_owner_assigned BOOLEAN NOT NULL DEFAULT 0")
    print("Added is_owner_assigned to task")
else:
    print("is_owner_assigned already exists")

user_rows = cur.execute("SELECT id FROM user WHERE username='owner'").fetchall()
if not user_rows:
    pw_hash = generate_password_hash('owner')
    cur.execute(
        "INSERT INTO user (username, email, password_hash, role, is_active, must_change_password) "
        "VALUES (?,?,?,?,?,?)",
        ('owner', 'owner@owner.com', pw_hash, 'owner', 1, 0)
    )
    print("Created owner user: owner / owner")
else:
    print("Owner user already exists")

con.commit()
con.close()
print("Migration 4 done.")
