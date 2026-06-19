from app import create_app, db
from app.models import User

app = create_app()
with app.app_context():
    db.drop_all()
    db.create_all()

    owner = User(username='owner', email='owner@owner.com', role='owner', is_active=True)
    owner.set_password('owner')
    db.session.add(owner)

    admin = User(username='admin', email='admin@admin.com', role='admin', is_active=True)
    admin.set_password('admin')
    db.session.add(admin)

    db.session.commit()
    print("Done!")
    print("  owner / owner")
    print("  admin / admin")
