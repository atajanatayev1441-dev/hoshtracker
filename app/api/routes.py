import json
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify, current_app
from flask_login import current_user, login_user
import jwt
from app import db
from app.api import api
from app.models import User, Task, Subtask, Tag


def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            token = auth_header[7:]
        if not token:
            return jsonify({'error': 'Token required'}), 401
        try:
            payload = jwt.decode(token, current_app.config['JWT_SECRET_KEY'], algorithms=['HS256'])
            user = db.session.get(User, payload['user_id'])
            if user is None or not user.is_active:
                return jsonify({'error': 'Invalid token'}), 401
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid token'}), 401
        return f(user, *args, **kwargs)
    return decorated


@api.route('/auth/login', methods=['POST'])
def api_login():
    data = request.get_json(silent=True) or {}
    username = data.get('username', '').strip()
    password = data.get('password', '')
    if not username or not password:
        return jsonify({'error': 'username and password required'}), 400

    user = User.query.filter_by(username=username).first()
    if user is None or not user.is_active or not user.check_password(password):
        return jsonify({'error': 'Invalid credentials'}), 401

    if user.is_locked():
        return jsonify({'error': 'Account locked'}), 403

    expires = datetime.utcnow() + current_app.config['JWT_ACCESS_TOKEN_EXPIRES']
    token = jwt.encode(
        {'user_id': user.id, 'exp': expires},
        current_app.config['JWT_SECRET_KEY'],
        algorithm='HS256'
    )
    user.last_login = datetime.utcnow()
    db.session.commit()
    return jsonify({'token': token, 'expires': expires.isoformat()})


@api.route('/tasks', methods=['GET'])
@token_required
def api_tasks(current_api_user):
    status = request.args.get('status')
    priority = request.args.get('priority')
    query = Task.query.filter_by(user_id=current_api_user.id)
    if status and status in Task.STATUSES:
        query = query.filter_by(status=status)
    if priority and priority in Task.PRIORITIES:
        query = query.filter_by(priority=priority)
    task_list = query.order_by(Task.updated_at.desc()).all()
    return jsonify({'tasks': [t.to_dict() for t in task_list]})


@api.route('/tasks', methods=['POST'])
@token_required
def api_create_task(current_api_user):
    data = request.get_json(silent=True) or {}
    title = data.get('title', '').strip()
    if not title:
        return jsonify({'error': 'title is required'}), 400

    priority = data.get('priority', Task.PRIORITY_MEDIUM)
    if priority not in Task.PRIORITIES:
        return jsonify({'error': 'Invalid priority'}), 400

    deadline = None
    if data.get('deadline'):
        try:
            deadline = datetime.fromisoformat(data['deadline'])
        except ValueError:
            return jsonify({'error': 'Invalid deadline format (use ISO 8601)'}), 400

    task = Task(
        user_id=current_api_user.id,
        title=title,
        description=data.get('description', ''),
        priority=priority,
        status=Task.STATUS_TODO,
        deadline=deadline,
    )
    db.session.add(task)
    db.session.commit()
    return jsonify(task.to_dict()), 201


@api.route('/tasks/<int:task_id>', methods=['GET'])
@token_required
def api_get_task(current_api_user, task_id):
    task = Task.query.filter_by(id=task_id, user_id=current_api_user.id).first()
    if task is None:
        return jsonify({'error': 'Not found'}), 404
    return jsonify(task.to_dict())


@api.route('/tasks/<int:task_id>', methods=['PUT'])
@token_required
def api_update_task(current_api_user, task_id):
    task = Task.query.filter_by(id=task_id, user_id=current_api_user.id).first()
    if task is None:
        return jsonify({'error': 'Not found'}), 404

    data = request.get_json(silent=True) or {}
    if 'title' in data:
        task.title = data['title'].strip() or task.title
    if 'description' in data:
        task.description = data['description']
    if 'priority' in data:
        if data['priority'] not in Task.PRIORITIES:
            return jsonify({'error': 'Invalid priority'}), 400
        task.priority = data['priority']
    if 'status' in data:
        if data['status'] not in Task.STATUSES:
            return jsonify({'error': 'Invalid status'}), 400
        task.status = data['status']
    if 'deadline' in data:
        if data['deadline']:
            try:
                task.deadline = datetime.fromisoformat(data['deadline'])
            except ValueError:
                return jsonify({'error': 'Invalid deadline format'}), 400
        else:
            task.deadline = None
    task.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify(task.to_dict())


@api.route('/tasks/<int:task_id>', methods=['DELETE'])
@token_required
def api_delete_task(current_api_user, task_id):
    task = Task.query.filter_by(id=task_id, user_id=current_api_user.id).first()
    if task is None:
        return jsonify({'error': 'Not found'}), 404
    db.session.delete(task)
    db.session.commit()
    return jsonify({'success': True})


@api.route('/tasks/<int:task_id>/status', methods=['PATCH'])
@token_required
def api_update_status(current_api_user, task_id):
    task = Task.query.filter_by(id=task_id, user_id=current_api_user.id).first()
    if task is None:
        return jsonify({'error': 'Not found'}), 404
    data = request.get_json(silent=True) or {}
    status = data.get('status', '')
    if status not in Task.STATUSES:
        return jsonify({'error': 'Invalid status'}), 400
    task.status = status
    task.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify({'id': task.id, 'status': task.status})


@api.route('/tasks/<int:task_id>/subtasks', methods=['POST'])
@token_required
def api_add_subtask(current_api_user, task_id):
    task = Task.query.filter_by(id=task_id, user_id=current_api_user.id).first()
    if task is None:
        return jsonify({'error': 'Not found'}), 404
    data = request.get_json(silent=True) or {}
    title = data.get('title', '').strip()
    if not title:
        return jsonify({'error': 'title required'}), 400
    max_order = db.session.query(db.func.max(Subtask.order)).filter_by(task_id=task_id).scalar() or 0
    subtask = Subtask(task_id=task_id, title=title, order=max_order + 1)
    db.session.add(subtask)
    db.session.commit()
    return jsonify(subtask.to_dict()), 201


# ── User search for @mentions (requires session login, not JWT) ───────────────

from flask_login import login_required as _login_required  # noqa: E402

@api.route('/users/search')
@_login_required
def users_search():
    q = request.args.get('q', '').strip()
    project_id = request.args.get('project_id', type=int)
    if len(q) < 1:
        return jsonify([])

    from app.models import ProjectMember
    query = User.query.filter(
        User.is_active == True,
        User.username.ilike(f'{q}%')
    )
    if project_id:
        member_ids = db.session.query(ProjectMember.user_id)\
                               .filter_by(project_id=project_id)
        query = query.filter(User.id.in_(member_ids))

    users = query.order_by(User.username).limit(10).all()
    return jsonify([{'id': u.id, 'username': u.username} for u in users])
