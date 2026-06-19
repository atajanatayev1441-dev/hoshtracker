from datetime import datetime
from app import db, login_manager
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

task_tags = db.Table(
    'task_tags',
    db.Column('task_id', db.Integer, db.ForeignKey('task.id'), primary_key=True),
    db.Column('tag_id', db.Integer, db.ForeignKey('tag.id'), primary_key=True)
)


class User(UserMixin, db.Model):
    __tablename__ = 'user'

    ROLE_OWNER = 'owner'
    ROLE_ADMIN = 'admin'
    ROLE_USER = 'user'
    ROLES = [ROLE_OWNER, ROLE_ADMIN, ROLE_USER]

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(16), nullable=False, default='user')
    created_at = db.Column(db.DateTime, default=lambda: datetime.utcnow())
    last_login = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    must_change_password = db.Column(db.Boolean, default=False)

    tasks = db.relationship('Task', foreign_keys='Task.user_id',
                            backref='owner', lazy='dynamic', cascade='all, delete-orphan')
    assigned_tasks = db.relationship('Task', foreign_keys='Task.assigned_to_id',
                                     backref='assignee', lazy='dynamic')
    tags = db.relationship('Tag', backref='owner', lazy='dynamic', cascade='all, delete-orphan')
    projects = db.relationship('Project', backref='owner', lazy='dynamic', cascade='all, delete-orphan')
    project_memberships = db.relationship('ProjectMember', backref='user',
                                          lazy='dynamic', cascade='all, delete-orphan')
    comments = db.relationship('Comment', backref='author', lazy='dynamic', cascade='all, delete-orphan')
    notifications = db.relationship('Notification', backref='user',
                                    lazy='dynamic', cascade='all, delete-orphan')
    activity_logs = db.relationship('ActivityLog', backref='actor',
                                    lazy='dynamic', cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def is_owner(self):
        return self.role == 'owner'

    def is_admin(self):
        return self.role in ('admin', 'owner')

    def task_count(self):
        return self.tasks.count()

    def unread_notification_count(self):
        return self.notifications.filter_by(is_read=False).count()

    def __repr__(self):
        return f'<User {self.username}>'


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


class Project(db.Model):
    __tablename__ = 'project'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    color = db.Column(db.String(7), nullable=False, default='#6366f1')
    created_at = db.Column(db.DateTime, default=lambda: datetime.utcnow())
    is_archived = db.Column(db.Boolean, default=False, nullable=False)

    tasks = db.relationship('Task', backref='project', lazy='dynamic')
    members = db.relationship('ProjectMember', backref='project',
                              lazy='dynamic', cascade='all, delete-orphan')

    def task_count(self):
        return self.tasks.count()

    def open_count(self):
        return self.tasks.filter(Task.status.notin_([Task.STATUS_DONE, Task.STATUS_CANCELLED])).count()

    def get_member_role(self, user_id):
        m = self.members.filter_by(user_id=user_id).first()
        return m.role if m else None

    def is_member(self, user_id):
        return self.members.filter_by(user_id=user_id).first() is not None

    def to_dict(self):
        return {'id': self.id, 'name': self.name, 'color': self.color}

    def __repr__(self):
        return f'<Project {self.name}>'


class ProjectMember(db.Model):
    __tablename__ = 'project_member'

    ROLE_OWNER = 'owner'
    ROLE_EDITOR = 'editor'
    ROLE_VIEWER = 'viewer'
    ROLES = [ROLE_OWNER, ROLE_EDITOR, ROLE_VIEWER]

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    role = db.Column(db.String(20), nullable=False, default=ROLE_VIEWER)
    joined_at = db.Column(db.DateTime, default=lambda: datetime.utcnow())

    __table_args__ = (db.UniqueConstraint('project_id', 'user_id', name='uq_project_member'),)

    def can_edit(self):
        return self.role in (self.ROLE_OWNER, self.ROLE_EDITOR)

    def __repr__(self):
        return f'<ProjectMember project={self.project_id} user={self.user_id} role={self.role}>'


class Task(db.Model):
    __tablename__ = 'task'

    STATUS_TODO = 'todo'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_REVIEW = 'review'
    STATUS_DONE = 'done'
    STATUS_CANCELLED = 'cancelled'
    STATUSES = [STATUS_TODO, STATUS_IN_PROGRESS, STATUS_REVIEW, STATUS_DONE, STATUS_CANCELLED]

    PRIORITY_LOW = 'low'
    PRIORITY_MEDIUM = 'medium'
    PRIORITY_HIGH = 'high'
    PRIORITY_CRITICAL = 'critical'
    PRIORITIES = [PRIORITY_LOW, PRIORITY_MEDIUM, PRIORITY_HIGH, PRIORITY_CRITICAL]

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=True, index=True)
    assigned_to_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True, index=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), nullable=False, default=STATUS_TODO)
    priority = db.Column(db.String(20), nullable=False, default=PRIORITY_MEDIUM)
    deadline = db.Column(db.DateTime, nullable=True)
    order = db.Column(db.Integer, default=0, nullable=False)
    time_estimate = db.Column(db.Integer, nullable=True)
    is_owner_assigned = db.Column(db.Boolean, default=False, nullable=False, server_default='0')
    created_at = db.Column(db.DateTime, default=lambda: datetime.utcnow())
    updated_at = db.Column(db.DateTime, default=lambda: datetime.utcnow(),
                           onupdate=lambda: datetime.utcnow())
    completed_at = db.Column(db.DateTime, nullable=True)

    subtasks = db.relationship('Subtask', backref='task', lazy='dynamic',
                               cascade='all, delete-orphan', order_by='Subtask.order')
    tags = db.relationship('Tag', secondary=task_tags, backref='tasks', lazy='subquery')
    time_entries = db.relationship('TimeEntry', backref='task', lazy='dynamic',
                                   cascade='all, delete-orphan')
    comments = db.relationship('Comment', backref='task', lazy='dynamic',
                               cascade='all, delete-orphan', order_by='Comment.created_at')

    def is_overdue(self):
        if self.deadline and self.status not in (self.STATUS_DONE, self.STATUS_CANCELLED):
            return self.deadline.replace(tzinfo=None) < datetime.utcnow()
        return False

    def subtask_progress(self):
        total = self.subtasks.count()
        if total == 0:
            return None
        done = self.subtasks.filter_by(is_done=True).count()
        return {'done': done, 'total': total, 'pct': int(done / total * 100)}

    @property
    def time_spent(self):
        result = db.session.query(db.func.sum(TimeEntry.minutes))\
                           .filter_by(task_id=self.id).scalar()
        return result or 0

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'status': self.status,
            'priority': self.priority,
            'deadline': self.deadline.isoformat() if self.deadline else None,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'is_overdue': self.is_overdue(),
            'order': self.order,
            'project_id': self.project_id,
            'assigned_to_id': self.assigned_to_id,
            'time_estimate': self.time_estimate,
            'time_spent': self.time_spent,
            'tags': [{'id': t.id, 'name': t.name, 'color': t.color} for t in self.tags],
            'subtasks': [s.to_dict() for s in self.subtasks],
        }

    def __repr__(self):
        return f'<Task {self.id}: {self.title[:30]}>'


class Comment(db.Model):
    __tablename__ = 'comment'

    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('task.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.utcnow())
    updated_at = db.Column(db.DateTime, nullable=True)

    mentions = db.relationship('Mention', backref='comment',
                               lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Comment {self.id} task={self.task_id}>'


class Mention(db.Model):
    __tablename__ = 'mention'

    id = db.Column(db.Integer, primary_key=True)
    comment_id = db.Column(db.Integer, db.ForeignKey('comment.id'), nullable=False, index=True)
    mentioned_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    mentioned_user = db.relationship('User', foreign_keys=[mentioned_user_id])

    def __repr__(self):
        return f'<Mention comment={self.comment_id} user={self.mentioned_user_id}>'


class Notification(db.Model):
    __tablename__ = 'notification'

    TYPE_ASSIGNED = 'assigned'
    TYPE_MENTIONED = 'mentioned'
    TYPE_COMMENT = 'comment'
    TYPE_STATUS = 'status'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    type = db.Column(db.String(30), nullable=False)
    message = db.Column(db.String(300), nullable=False)
    link = db.Column(db.String(200), nullable=True)
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.utcnow())

    def __repr__(self):
        return f'<Notification {self.id} user={self.user_id}>'


class ActivityLog(db.Model):
    __tablename__ = 'activity_log'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    action = db.Column(db.String(50), nullable=False)
    entity_type = db.Column(db.String(30), nullable=True)
    entity_id = db.Column(db.Integer, nullable=True)
    description = db.Column(db.String(400), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.utcnow(), index=True)

    def __repr__(self):
        return f'<ActivityLog {self.action} by user={self.user_id}>'


class TimeEntry(db.Model):
    __tablename__ = 'time_entry'

    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('task.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    started_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.utcnow())
    ended_at = db.Column(db.DateTime, nullable=True)
    minutes = db.Column(db.Integer, nullable=True)
    note = db.Column(db.String(200), nullable=True)

    def to_dict(self):
        return {'id': self.id, 'task_id': self.task_id, 'minutes': self.minutes}

    def __repr__(self):
        return f'<TimeEntry {self.id} {self.minutes}m>'


class Subtask(db.Model):
    __tablename__ = 'subtask'

    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('task.id'), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    is_done = db.Column(db.Boolean, default=False, nullable=False)
    order = db.Column(db.Integer, default=0, nullable=False)

    def to_dict(self):
        return {'id': self.id, 'task_id': self.task_id, 'title': self.title,
                'is_done': self.is_done, 'order': self.order}

    def __repr__(self):
        return f'<Subtask {self.id}: {self.title[:30]}>'


class Tag(db.Model):
    __tablename__ = 'tag'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    name = db.Column(db.String(50), nullable=False)
    color = db.Column(db.String(7), nullable=False, default='#6366f1')

    __table_args__ = (db.UniqueConstraint('user_id', 'name', name='uq_tag_user_name'),)

    def to_dict(self):
        return {'id': self.id, 'name': self.name, 'color': self.color}

    def __repr__(self):
        return f'<Tag {self.name}>'
