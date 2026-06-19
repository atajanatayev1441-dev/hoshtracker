"""Shared helpers: task visibility, permission checks, activity logging, notifications."""
import re
from functools import wraps
from datetime import datetime
from flask import url_for, abort
from flask_login import current_user
from app import db


def owner_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_owner():
            abort(403)
        return f(*args, **kwargs)
    return decorated


def admin_or_owner_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin():
            abort(403)
        return f(*args, **kwargs)
    return decorated


def visible_tasks_query(user_id):
    """Return a Task query scoped to all tasks the user is allowed to see.

    Visibility rule:
    - Task owned by user                        (user_id == me)
    - Task assigned to user                     (assigned_to_id == me)
    - Task in a project where user is a member  (project_id in my memberships)

    Admins see everything via a separate code-path; this function is for regular users.
    """
    from app.models import Task, ProjectMember

    member_project_ids = db.session.query(ProjectMember.project_id)\
                                   .filter_by(user_id=user_id)

    return Task.query.filter(
        db.or_(
            Task.user_id == user_id,
            Task.assigned_to_id == user_id,
            db.and_(
                Task.project_id.isnot(None),
                Task.project_id.in_(member_project_ids)
            )
        )
    )


def can_edit_task(task, user):
    """User can edit a task if they own it or are a project editor/owner."""
    if user.is_admin():
        return True
    if task.user_id == user.id:
        return True
    if task.project_id:
        from app.models import ProjectMember
        m = ProjectMember.query.filter_by(project_id=task.project_id, user_id=user.id).first()
        if m and m.can_edit():
            return True
    return False


def can_view_task(task, user):
    """User can view a task if it's visible to them per visibility_query rules."""
    if user.is_admin():
        return True
    if task.user_id == user.id:
        return True
    if task.assigned_to_id == user.id:
        return True
    if task.project_id:
        from app.models import ProjectMember
        if ProjectMember.query.filter_by(project_id=task.project_id, user_id=user.id).first():
            return True
    return False


def get_project_role(project_id, user_id):
    """Return the user's role in a project, or None if not a member."""
    from app.models import ProjectMember
    m = ProjectMember.query.filter_by(project_id=project_id, user_id=user_id).first()
    return m.role if m else None


def log_activity(user_id, action, description, entity_type=None, entity_id=None):
    from app.models import ActivityLog
    entry = ActivityLog(
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        description=description,
        created_at=datetime.utcnow(),
    )
    db.session.add(entry)


def notify_user(user_id, notification_type, message, link=None):
    """Create an in-app notification for a user (skip if sending to yourself)."""
    if user_id == current_user.id:
        return
    from app.models import Notification
    n = Notification(
        user_id=user_id,
        type=notification_type,
        message=message,
        link=link,
        created_at=datetime.utcnow(),
    )
    db.session.add(n)


def parse_mentions(text, project_id=None):
    """Extract @usernames from text; return list of User objects found."""
    from app.models import User, ProjectMember
    names = set(re.findall(r'@([\w]+)', text))
    if not names:
        return []
    query = User.query.filter(User.username.in_(names), User.is_active == True)
    users = query.all()
    if project_id:
        member_ids = {m.user_id for m in ProjectMember.query.filter_by(project_id=project_id).all()}
        users = [u for u in users if u.id in member_ids]
    return users


def highlight_mentions(text):
    """Wrap @username in a styled span for HTML display."""
    return re.sub(
        r'@([\w]+)',
        r'<span class="inline-flex items-center text-brand-600 dark:text-brand-400 font-medium">@\1</span>',
        text
    )
