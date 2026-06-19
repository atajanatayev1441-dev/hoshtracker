import os
from app import create_app, db
from app.models import User, Task, Subtask, Tag

app = create_app(os.environ.get('FLASK_ENV', 'development'))


@app.shell_context_processor
def make_shell_context():
    return dict(db=db, User=User, Task=Task, Subtask=Subtask, Tag=Tag)


def init_db():
    """Create tables and default admin user on first run."""
    with app.app_context():
        db.create_all()
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
            print('Default admin user created: admin / admin123')
            print('  Change the password immediately after first login!')


if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)
