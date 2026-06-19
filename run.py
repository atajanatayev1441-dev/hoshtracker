import os
from app import create_app, db
from app.models import User, Task, Subtask, Tag
from sqlalchemy import text, inspect

app = create_app(os.environ.get('FLASK_ENV', 'development'))


@app.shell_context_processor
def make_shell_context():
    return dict(db=db, User=User, Task=Task, Subtask=Subtask, Tag=Tag)


def _apply_schema_migrations():
    """Idempotent column additions for schema changes not covered by create_all()."""
    inspector = inspect(db.engine)

    # task.is_owner_assigned — added in owner-role feature
    if 'task' in inspector.get_table_names():
        cols = [c['name'] for c in inspector.get_columns('task')]
        if 'is_owner_assigned' not in cols:
            db.session.execute(text(
                'ALTER TABLE task ADD COLUMN is_owner_assigned BOOLEAN NOT NULL DEFAULT FALSE'
            ))
            db.session.commit()
            print('[migration] Added task.is_owner_assigned')


def init_db():
    """Create tables, apply column migrations, and seed default users."""
    with app.app_context():
        db.create_all()
        _apply_schema_migrations()

        if not User.query.filter_by(username='owner').first():
            owner = User(
                username='owner',
                email='owner@localhost',
                role='owner',
                is_active=True,
                must_change_password=True,
            )
            owner.set_password('owner123')
            db.session.add(owner)
            db.session.commit()
            print('Owner user created: owner / owner123')

        if not User.query.filter_by(username='admin').first():
            admin = User(
                username='admin',
                email='admin@localhost',
                role='admin',
                is_active=True,
                must_change_password=True,
            )
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()
            print('Admin user created: admin / admin123')


if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)
