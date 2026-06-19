import sqlite3, os

p = os.path.join('data', 'tasktracker.db')
con = sqlite3.connect(p)
cur = con.cursor()

task_cols = [r[1] for r in cur.execute("PRAGMA table_info(task)").fetchall()]
if 'completed_at' not in task_cols:
    cur.execute("ALTER TABLE task ADD COLUMN completed_at DATETIME")
    print("Added completed_at to task")
if 'time_estimate' not in task_cols:
    cur.execute("ALTER TABLE task ADD COLUMN time_estimate INTEGER")
    print("Added time_estimate to task")

cur.execute("""CREATE TABLE IF NOT EXISTS time_entry (
    id INTEGER PRIMARY KEY,
    task_id INTEGER NOT NULL REFERENCES task(id),
    user_id INTEGER NOT NULL REFERENCES "user"(id),
    started_at DATETIME NOT NULL,
    ended_at DATETIME,
    minutes INTEGER,
    note VARCHAR(200)
)""")

con.commit()
print("task cols:", [r[1] for r in cur.execute("PRAGMA table_info(task)").fetchall()])
print("time_entry:", [r[1] for r in cur.execute("PRAGMA table_info(time_entry)").fetchall()])
con.close()
print("Migration 2 done.")
