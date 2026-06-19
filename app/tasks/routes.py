import json
import calendar as cal_mod
from datetime import datetime, date
from flask import render_template, redirect, url_for, flash, request, jsonify, abort
from flask_login import login_required, current_user
from app import db
from app.tasks import tasks
from app.tasks.forms import TaskForm, TagForm, CommentForm
from app.models import Task, Subtask, Tag, Project, TimeEntry, Comment, Mention, Notification, User
from app.utils import (visible_tasks_query, can_view_task, can_edit_task,
                       log_activity, notify_user, parse_mentions, highlight_mentions)

MONTH_NAMES_RU = ['', 'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
                  'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь']


def _active_users():
    return User.query.filter_by(is_active=True).order_by(User.username).all()


def _populate_task_form(form):
    """Fill project and assignee dropdown choices."""
    user_projects = Project.query.filter_by(user_id=current_user.id, is_archived=False)\
                                 .order_by(Project.name).all()
    form.project_id.choices = [('', '— Без проекта —')] + [(str(p.id), p.name) for p in user_projects]
    form.assigned_to_id.choices = [('', '— Не назначено —')] + \
        [(str(u.id), u.username) for u in _active_users() if u.id != current_user.id]
    return user_projects


def _get_task_for_view(task_id):
    task = db.session.get(Task, task_id)
    if task is None or not can_view_task(task, current_user):
        abort(404)
    return task


def _get_task_for_edit(task_id):
    task = db.session.get(Task, task_id)
    if task is None or not can_edit_task(task, current_user):
        abort(403)
    return task


# ── Dashboard ─────────────────────────────────────────────────────────────────

@tasks.route('/dashboard')
@login_required
def dashboard():
    now = datetime.utcnow()
    today_start = datetime(now.year, now.month, now.day)
    uid = current_user.id

    if current_user.is_admin():
        base = Task.query
    else:
        base = visible_tasks_query(uid)

    total = base.count()
    done_today = base.filter(Task.status == Task.STATUS_DONE,
                             Task.updated_at >= today_start).count()
    overdue_count = sum(1 for t in base.filter(
        Task.status.notin_([Task.STATUS_DONE, Task.STATUS_CANCELLED]),
        Task.deadline.isnot(None)).all() if t.deadline < now)

    by_priority = {
        'critical': base.filter_by(priority=Task.PRIORITY_CRITICAL).filter(
            Task.status.notin_([Task.STATUS_DONE, Task.STATUS_CANCELLED])).count(),
        'high': base.filter_by(priority=Task.PRIORITY_HIGH).filter(
            Task.status.notin_([Task.STATUS_DONE, Task.STATUS_CANCELLED])).count(),
    }

    # Tasks assigned to me
    assigned_to_me = Task.query.filter_by(assigned_to_id=uid).filter(
        Task.status.notin_([Task.STATUS_DONE, Task.STATUS_CANCELLED])
    ).order_by(Task.deadline.asc().nullslast()).limit(5).all()

    recent_tasks = base.filter(
        Task.status.notin_([Task.STATUS_DONE, Task.STATUS_CANCELLED]),
        Task.user_id == uid
    ).order_by(Task.updated_at.desc()).limit(8).all()

    overdue_tasks = [t for t in base.filter(
        Task.status.notin_([Task.STATUS_DONE, Task.STATUS_CANCELLED]),
        Task.deadline.isnot(None)
    ).order_by(Task.deadline).all() if t.deadline < now][:5]

    user_projects = Project.query.filter_by(user_id=uid, is_archived=False)\
                                 .order_by(Project.created_at.desc()).limit(6).all()

    # Notifications
    notifications = current_user.notifications.filter_by(is_read=False)\
                                              .order_by(Notification.created_at.desc()).limit(5).all()

    return render_template('tasks/dashboard.html',
                           total=total, done_today=done_today,
                           overdue_count=overdue_count, by_priority=by_priority,
                           recent_tasks=recent_tasks, overdue_tasks=overdue_tasks,
                           user_projects=user_projects, assigned_to_me=assigned_to_me,
                           notifications=notifications, now=now)


# ── Task list ─────────────────────────────────────────────────────────────────

@tasks.route('/')
@login_required
def task_list():
    uid = current_user.id
    status_filter = request.args.get('status', '')
    priority_filter = request.args.get('priority', '')
    tag_filter = request.args.get('tag', '')
    project_filter = request.args.get('project', '')
    assigned_filter = request.args.get('assigned_to', '')
    sort_by = request.args.get('sort', 'updated_at')
    search = request.args.get('q', '').strip()

    if current_user.is_admin():
        query = Task.query
    else:
        query = visible_tasks_query(uid)

    if status_filter and status_filter in Task.STATUSES:
        query = query.filter_by(status=status_filter)
    if priority_filter and priority_filter in Task.PRIORITIES:
        query = query.filter_by(priority=priority_filter)
    if tag_filter:
        tag = Tag.query.filter_by(user_id=uid, name=tag_filter).first()
        if tag:
            query = query.filter(Task.tags.contains(tag))
    if project_filter == 'none':
        query = query.filter(Task.project_id.is_(None))
    elif project_filter and project_filter.isdigit():
        query = query.filter_by(project_id=int(project_filter))
    if assigned_filter == 'me':
        query = query.filter_by(assigned_to_id=uid)
    elif assigned_filter and assigned_filter.isdigit():
        query = query.filter_by(assigned_to_id=int(assigned_filter))
    if search:
        query = query.filter(Task.title.ilike(f'%{search}%'))

    sort_map = {
        'deadline': Task.deadline.asc().nullslast(),
        'priority': Task.priority.desc(),
        'created_at': Task.created_at.desc(),
        'updated_at': Task.updated_at.desc(),
        'title': Task.title.asc(),
    }
    query = query.order_by(sort_map.get(sort_by, Task.updated_at.desc()))

    all_tasks = query.all()
    user_tags = Tag.query.filter_by(user_id=uid).order_by(Tag.name).all()
    user_projects = Project.query.filter_by(user_id=uid, is_archived=False).order_by(Project.name).all()
    all_users = _active_users()
    now = datetime.utcnow()

    return render_template('tasks/task_list.html',
                           tasks=all_tasks, user_tags=user_tags,
                           user_projects=user_projects, all_users=all_users,
                           status_filter=status_filter, priority_filter=priority_filter,
                           tag_filter=tag_filter, project_filter=project_filter,
                           assigned_filter=assigned_filter,
                           sort_by=sort_by, search=search, now=now, Task=Task)


# ── New task ──────────────────────────────────────────────────────────────────

@tasks.route('/new', methods=['GET', 'POST'])
@login_required
def new_task():
    form = TaskForm()
    user_tags = Tag.query.filter_by(user_id=current_user.id).order_by(Tag.name).all()
    user_projects = _populate_task_form(form)

    if form.validate_on_submit():
        pid = int(form.project_id.data) if form.project_id.data else None
        aid = int(form.assigned_to_id.data) if form.assigned_to_id.data else None
        task = Task(
            user_id=current_user.id, project_id=pid, assigned_to_id=aid,
            title=form.title.data.strip(), description=form.description.data,
            priority=form.priority.data, status=form.status.data,
            deadline=form.deadline.data, time_estimate=form.time_estimate.data,
        )
        db.session.add(task)
        db.session.flush()

        for tid in (form.tag_ids.data or '').split(','):
            if tid.strip().isdigit():
                tag = db.session.get(Tag, int(tid))
                if tag and tag.user_id == current_user.id:
                    task.tags.append(tag)

        subtasks_data = json.loads(form.subtasks_json.data or '[]')
        for i, st in enumerate(subtasks_data):
            if st.get('title', '').strip():
                db.session.add(Subtask(task_id=task.id, title=st['title'].strip(), order=i))

        # Notify assignee
        if aid:
            notify_user(aid, Notification.TYPE_ASSIGNED,
                        f'{current_user.username} назначил(а) вам задачу «{task.title}»',
                        url_for('tasks.task_detail', task_id=task.id))

        log_activity(current_user.id, 'task_created', f'Создал(а) задачу «{task.title}»',
                     'task', task.id)
        db.session.commit()
        flash('Задача создана.', 'success')
        return redirect(url_for('tasks.task_detail', task_id=task.id))

    if request.args.get('project'):
        form.project_id.data = request.args.get('project')

    return render_template('tasks/task_form.html', form=form, user_tags=user_tags,
                           user_projects=user_projects, task=None, title='Новая задача')


# ── Task detail ───────────────────────────────────────────────────────────────

@tasks.route('/<int:task_id>')
@login_required
def task_detail(task_id):
    task = _get_task_for_view(task_id)
    comment_form = CommentForm()
    comments = task.comments.order_by(Comment.created_at).all()
    now = datetime.utcnow()
    return render_template('tasks/task_detail.html', task=task, now=now, Task=Task,
                           comment_form=comment_form, comments=comments,
                           highlight_mentions=highlight_mentions,
                           can_edit=can_edit_task(task, current_user))


# ── Edit task ─────────────────────────────────────────────────────────────────

@tasks.route('/<int:task_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_task(task_id):
    task = _get_task_for_edit(task_id)
    form = TaskForm(obj=task)
    user_tags = Tag.query.filter_by(user_id=current_user.id).order_by(Tag.name).all()
    user_projects = _populate_task_form(form)

    if form.validate_on_submit():
        old_assignee = task.assigned_to_id
        pid = int(form.project_id.data) if form.project_id.data else None
        aid = int(form.assigned_to_id.data) if form.assigned_to_id.data else None

        task.project_id = pid
        task.assigned_to_id = aid
        task.title = form.title.data.strip()
        task.description = form.description.data
        task.priority = form.priority.data
        task.status = form.status.data
        task.deadline = form.deadline.data
        task.time_estimate = form.time_estimate.data
        task.updated_at = datetime.utcnow()

        # completed_at
        if form.status.data == Task.STATUS_DONE and task.completed_at is None:
            task.completed_at = datetime.utcnow()
        elif form.status.data != Task.STATUS_DONE:
            task.completed_at = None

        task.tags.clear()
        for tid in (form.tag_ids.data or '').split(','):
            if tid.strip().isdigit():
                tag = db.session.get(Tag, int(tid))
                if tag and tag.user_id == current_user.id:
                    task.tags.append(tag)

        for st in task.subtasks.all():
            db.session.delete(st)
        db.session.flush()

        subtasks_data = json.loads(form.subtasks_json.data or '[]')
        for i, st in enumerate(subtasks_data):
            if st.get('title', '').strip():
                db.session.add(Subtask(task_id=task.id, title=st['title'].strip(),
                                       is_done=st.get('is_done', False), order=i))

        if aid and aid != old_assignee:
            notify_user(aid, Notification.TYPE_ASSIGNED,
                        f'{current_user.username} назначил(а) вам задачу «{task.title}»',
                        url_for('tasks.task_detail', task_id=task.id))

        log_activity(current_user.id, 'task_updated', f'Обновил(а) задачу «{task.title}»',
                     'task', task.id)
        db.session.commit()
        flash('Задача обновлена.', 'success')
        return redirect(url_for('tasks.task_detail', task_id=task.id))

    if request.method == 'GET':
        form.tag_ids.data = ','.join(str(t.id) for t in task.tags)
        form.subtasks_json.data = json.dumps(
            [{'title': s.title, 'is_done': s.is_done} for s in task.subtasks])
        form.project_id.data = str(task.project_id) if task.project_id else ''
        form.assigned_to_id.data = str(task.assigned_to_id) if task.assigned_to_id else ''
        if task.deadline:
            form.deadline.data = task.deadline

    return render_template('tasks/task_form.html', form=form, user_tags=user_tags,
                           user_projects=user_projects, task=task, title='Редактировать задачу')


# ── Delete task ───────────────────────────────────────────────────────────────

@tasks.route('/<int:task_id>/delete', methods=['POST'])
@login_required
def delete_task(task_id):
    task = _get_task_for_edit(task_id)
    title = task.title
    db.session.delete(task)
    log_activity(current_user.id, 'task_deleted', f'Удалил(а) задачу «{title}»')
    db.session.commit()
    flash('Задача удалена.', 'info')
    return redirect(url_for('tasks.task_list'))


# ── Status change ─────────────────────────────────────────────────────────────

@tasks.route('/<int:task_id>/status', methods=['POST'])
@login_required
def update_status(task_id):
    task = _get_task_for_view(task_id)
    if not can_edit_task(task, current_user):
        if request.is_json:
            return jsonify({'error': 'Forbidden'}), 403
        flash('Нет прав для изменения статуса.', 'danger')
        return redirect(url_for('tasks.task_detail', task_id=task_id))

    new_status = (request.get_json(silent=True) or {}).get('status') if request.is_json \
        else request.form.get('status', '')
    if new_status not in Task.STATUSES:
        if request.is_json:
            return jsonify({'error': 'Invalid status'}), 400
        flash('Неверный статус.', 'danger')
        return redirect(url_for('tasks.task_detail', task_id=task_id))

    old_status = task.status
    task.status = new_status
    task.updated_at = datetime.utcnow()
    if new_status == Task.STATUS_DONE and old_status != Task.STATUS_DONE:
        task.completed_at = datetime.utcnow()
    elif new_status != Task.STATUS_DONE:
        task.completed_at = None

    log_activity(current_user.id, 'status_changed',
                 f'Изменил(а) статус «{task.title}» → {new_status}', 'task', task.id)
    db.session.commit()
    if request.is_json:
        return jsonify({'success': True, 'status': task.status})
    flash('Статус обновлён.', 'success')
    return redirect(request.referrer or url_for('tasks.task_list'))


# ── Subtask toggle ────────────────────────────────────────────────────────────

@tasks.route('/<int:task_id>/subtasks/<int:subtask_id>/toggle', methods=['POST'])
@login_required
def toggle_subtask(task_id, subtask_id):
    task = _get_task_for_view(task_id)
    if not can_edit_task(task, current_user):
        abort(403)
    subtask = db.session.get(Subtask, subtask_id)
    if subtask is None or subtask.task_id != task.id:
        abort(404)
    subtask.is_done = not subtask.is_done
    db.session.commit()
    if request.is_json:
        return jsonify({'success': True, 'is_done': subtask.is_done})
    return redirect(url_for('tasks.task_detail', task_id=task_id))


# ── Comments ──────────────────────────────────────────────────────────────────

@tasks.route('/<int:task_id>/comments', methods=['POST'])
@login_required
def add_comment(task_id):
    task = _get_task_for_view(task_id)
    form = CommentForm()
    if form.validate_on_submit():
        comment = Comment(task_id=task.id, user_id=current_user.id,
                          content=form.content.data.strip())
        db.session.add(comment)
        db.session.flush()

        # Parse @mentions and notify
        mentioned = parse_mentions(form.content.data, project_id=task.project_id)
        for u in mentioned:
            m = Mention(comment_id=comment.id, mentioned_user_id=u.id)
            db.session.add(m)
            notify_user(u.id, Notification.TYPE_MENTIONED,
                        f'{current_user.username} упомянул(а) вас в комментарии к «{task.title}»',
                        url_for('tasks.task_detail', task_id=task.id))

        # Notify task owner (not the commenter)
        if task.user_id != current_user.id:
            notify_user(task.user_id, Notification.TYPE_COMMENT,
                        f'{current_user.username} прокомментировал(а) задачу «{task.title}»',
                        url_for('tasks.task_detail', task_id=task.id))

        log_activity(current_user.id, 'comment_added',
                     f'Прокомментировал(а) задачу «{task.title}»', 'task', task.id)
        db.session.commit()
        flash('Комментарий добавлен.', 'success')
    return redirect(url_for('tasks.task_detail', task_id=task_id))


@tasks.route('/<int:task_id>/comments/<int:comment_id>/delete', methods=['POST'])
@login_required
def delete_comment(task_id, comment_id):
    task = _get_task_for_view(task_id)
    comment = db.session.get(Comment, comment_id)
    if comment is None or comment.task_id != task.id:
        abort(404)
    if comment.user_id != current_user.id and not current_user.is_admin():
        abort(403)
    db.session.delete(comment)
    db.session.commit()
    flash('Комментарий удалён.', 'info')
    return redirect(url_for('tasks.task_detail', task_id=task_id))


# ── Timer ─────────────────────────────────────────────────────────────────────

@tasks.route('/<int:task_id>/timer/stop', methods=['POST'])
@login_required
def timer_stop(task_id):
    task = _get_task_for_view(task_id)
    data = request.get_json(silent=True) or {}
    minutes = int(data.get('minutes', 0))
    if minutes <= 0:
        return jsonify({'error': 'minutes must be > 0'}), 400
    entry = TimeEntry(task_id=task.id, user_id=current_user.id,
                      started_at=datetime.utcnow(), ended_at=datetime.utcnow(),
                      minutes=minutes, note=data.get('note', ''))
    db.session.add(entry)
    db.session.commit()
    return jsonify({'ok': True, 'time_spent': task.time_spent, 'minutes': minutes})


# ── Notifications ─────────────────────────────────────────────────────────────

@tasks.route('/notifications/mark-read', methods=['POST'])
@login_required
def mark_notifications_read():
    current_user.notifications.update({'is_read': True})
    db.session.commit()
    return jsonify({'ok': True})


@tasks.route('/notifications')
@login_required
def notifications():
    notifs = current_user.notifications.order_by(Notification.created_at.desc()).limit(50).all()
    current_user.notifications.update({'is_read': True})
    db.session.commit()
    return render_template('tasks/notifications.html', notifications=notifs)


# ── Calendar ──────────────────────────────────────────────────────────────────

@tasks.route('/calendar')
@login_required
def calendar():
    now = datetime.utcnow()
    year = int(request.args.get('year', now.year))
    month = max(1, min(12, int(request.args.get('month', now.month))))

    first = datetime(year, month, 1)
    last = datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)

    if current_user.is_admin():
        base = Task.query
    else:
        base = visible_tasks_query(current_user.id)

    month_tasks = base.filter(
        Task.deadline.isnot(None),
        Task.deadline >= first,
        Task.deadline < last
    ).order_by(Task.deadline).all()

    tasks_by_day = {}
    for t in month_tasks:
        key = t.deadline.strftime('%Y-%m-%d')
        tasks_by_day.setdefault(key, []).append(t)

    print(f'[calendar] {year}-{month:02d}: {len(month_tasks)} tasks, keys={list(tasks_by_day.keys())}')

    grid = cal_mod.monthcalendar(year, month)
    prev_month, prev_year = (month - 1, year) if month > 1 else (12, year - 1)
    next_month, next_year = (month + 1, year) if month < 12 else (1, year + 1)

    return render_template('tasks/calendar.html',
                           grid=grid, tasks_by_day=tasks_by_day, year=year, month=month,
                           month_name=MONTH_NAMES_RU[month],
                           prev_year=prev_year, prev_month=prev_month,
                           next_year=next_year, next_month=next_month,
                           today=now, Task=Task)


# ── Tags ──────────────────────────────────────────────────────────────────────

@tasks.route('/tags')
@login_required
def tags():
    user_tags = Tag.query.filter_by(user_id=current_user.id).order_by(Tag.name).all()
    return render_template('tasks/tags.html', tags=user_tags, form=TagForm())


@tasks.route('/tags/new', methods=['POST'])
@login_required
def new_tag():
    form = TagForm()
    if form.validate_on_submit():
        existing = Tag.query.filter_by(user_id=current_user.id, name=form.name.data.strip()).first()
        if existing:
            if request.is_json:
                return jsonify({'error': 'exists', 'tag': existing.to_dict()}), 409
            flash('Метка с таким именем уже существует.', 'warning')
        else:
            tag = Tag(user_id=current_user.id, name=form.name.data.strip(), color=form.color.data)
            db.session.add(tag)
            db.session.commit()
            if request.is_json:
                return jsonify({'success': True, 'tag': tag.to_dict()}), 201
            flash('Метка создана.', 'success')
    else:
        if request.is_json:
            return jsonify({'error': 'Validation failed'}), 400
    return redirect(url_for('tasks.tags'))


@tasks.route('/tags/<int:tag_id>/delete', methods=['POST'])
@login_required
def delete_tag(tag_id):
    tag = Tag.query.filter_by(id=tag_id, user_id=current_user.id).first_or_404()
    db.session.delete(tag)
    db.session.commit()
    flash('Метка удалена.', 'info')
    return redirect(url_for('tasks.tags'))
