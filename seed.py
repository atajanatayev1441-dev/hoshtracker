"""Seed script — populates the DB with sample data for testing."""
import os
from datetime import datetime, timedelta
from app import create_app, db
from app.models import User, Task, Subtask, Tag

app = create_app(os.environ.get('FLASK_ENV', 'development'))


def seed():
    with app.app_context():
        db.create_all()

        # Admin
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            admin = User(username='admin', email='admin@localhost', role='admin', is_active=True)
            admin.set_password('admin123')
            db.session.add(admin)

        # Demo user
        demo = User.query.filter_by(username='demo').first()
        if not demo:
            demo = User(username='demo', email='demo@localhost', role='user', is_active=True)
            demo.set_password('demo1234')
            db.session.add(demo)
            db.session.flush()

            # Tags
            tags_data = [
                ('work', '#6366f1'),
                ('personal', '#22c55e'),
                ('urgent', '#ef4444'),
                ('learning', '#f59e0b'),
            ]
            tags = {}
            for name, color in tags_data:
                t = Tag(user_id=demo.id, name=name, color=color)
                db.session.add(t)
                tags[name] = t
            db.session.flush()

            now = datetime.utcnow()

            # Tasks
            tasks_data = [
                dict(title='Set up project repository', description='Initialize git, add README and .gitignore.',
                     priority='high', status='done', deadline=now - timedelta(days=3),
                     tags=['work']),
                dict(title='Design database schema', description='ERD for users, tasks, subtasks, tags.',
                     priority='critical', status='done',
                     tags=['work']),
                dict(title='Implement authentication', description='Login / logout with CSRF and rate limiting.',
                     priority='high', status='in_progress', deadline=now + timedelta(days=1),
                     tags=['work'],
                     subtasks=['Create login form', 'Add bcrypt hashing', 'Add rate limiting', 'Test on mobile']),
                dict(title='Write unit tests', description='Cover models and auth routes.',
                     priority='medium', status='todo', deadline=now + timedelta(days=7),
                     tags=['work']),
                dict(title='Read "Clean Code"', description='Finish chapters 1–5 this week.',
                     priority='low', status='in_progress',
                     tags=['personal', 'learning']),
                dict(title='Fix overdue task (for demo)', description='This task is past its deadline.',
                     priority='critical', status='todo', deadline=now - timedelta(hours=6),
                     tags=['urgent']),
                dict(title='Update dependencies', description='Run pip-audit and upgrade packages.',
                     priority='low', status='todo', deadline=now + timedelta(days=14),
                     tags=['work']),
            ]

            for td in tasks_data:
                task = Task(
                    user_id=demo.id,
                    title=td['title'],
                    description=td.get('description', ''),
                    priority=td['priority'],
                    status=td['status'],
                    deadline=td.get('deadline'),
                )
                db.session.add(task)
                db.session.flush()
                for tag_name in td.get('tags', []):
                    if tag_name in tags:
                        task.tags.append(tags[tag_name])
                for i, st_title in enumerate(td.get('subtasks', [])):
                    db.session.add(Subtask(task_id=task.id, title=st_title, order=i))

        db.session.commit()
        print('Seed complete.')
        print('  admin / admin123')
        print('  demo  / demo1234')


if __name__ == '__main__':
    seed()
