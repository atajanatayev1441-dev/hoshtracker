import sqlite3, os

p = os.path.join('data', 'tasktracker.db')
con = sqlite3.connect(p)
cur = con.cursor()

task_cols = [r[1] for r in cur.execute("PRAGMA table_info(task)").fetchall()]
if 'assigned_to_id' not in task_cols:
    cur.execute("ALTER TABLE task ADD COLUMN assigned_to_id INTEGER REFERENCES \"user\"(id)")
    print("Added assigned_to_id to task")

cur.execute("""CREATE TABLE IF NOT EXISTS project_member (
    id INTEGER PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES project(id),
    user_id INTEGER NOT NULL REFERENCES "user"(id),
    role VARCHAR(20) NOT NULL DEFAULT 'viewer',
    joined_at DATETIME,
    UNIQUE (project_id, user_id)
)""")

cur.execute("""CREATE TABLE IF NOT EXISTS comment (
    id INTEGER PRIMARY KEY,
    task_id INTEGER NOT NULL REFERENCES task(id),
    user_id INTEGER NOT NULL REFERENCES "user"(id),
    content TEXT NOT NULL,
    created_at DATETIME,
    updated_at DATETIME
)""")

cur.execute("""CREATE TABLE IF NOT EXISTS mention (
    id INTEGER PRIMARY KEY,
    comment_id INTEGER NOT NULL REFERENCES comment(id),
    mentioned_user_id INTEGER NOT NULL REFERENCES "user"(id)
)""")

cur.execute("""CREATE TABLE IF NOT EXISTS notification (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES "user"(id),
    type VARCHAR(30) NOT NULL,
    message VARCHAR(300) NOT NULL,
    link VARCHAR(200),
    is_read BOOLEAN NOT NULL DEFAULT 0,
    created_at DATETIME
)""")

cur.execute("""CREATE TABLE IF NOT EXISTS activity_log (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES "user"(id),
    action VARCHAR(50) NOT NULL,
    entity_type VARCHAR(30),
    entity_id INTEGER,
    description VARCHAR(400) NOT NULL,
    created_at DATETIME
)""")

con.commit()

for tbl in ('project_member', 'comment', 'notification', 'activity_log'):
    cols = [r[1] for r in cur.execute(f"PRAGMA table_info({tbl})").fetchall()]
    print(f"{tbl}: {cols}")

con.close()
print("Migration 3 done.")
