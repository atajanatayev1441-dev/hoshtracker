import sqlite3, os

p = os.path.join('data', 'tasktracker.db')
con = sqlite3.connect(p)
cur = con.cursor()

cur.execute("""CREATE TABLE IF NOT EXISTS project (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES "user"(id),
    name VARCHAR(100) NOT NULL,
    description TEXT,
    color VARCHAR(7) NOT NULL DEFAULT '#6366f1',
    created_at DATETIME,
    is_archived BOOLEAN NOT NULL DEFAULT 0
)""")

cols = [r[1] for r in cur.execute("PRAGMA table_info(task)").fetchall()]
if 'project_id' not in cols:
    cur.execute('ALTER TABLE task ADD COLUMN project_id INTEGER REFERENCES project(id)')
    print("Added project_id to task")
if 'order' not in cols:
    cur.execute('ALTER TABLE task ADD COLUMN "order" INTEGER NOT NULL DEFAULT 0')
    print("Added order to task")

con.commit()
print("task:", [r[1] for r in cur.execute("PRAGMA table_info(task)").fetchall()])
print("project:", [r[1] for r in cur.execute("PRAGMA table_info(project)").fetchall()])
con.close()
print("Migration done.")
