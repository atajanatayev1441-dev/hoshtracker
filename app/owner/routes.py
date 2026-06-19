from datetime import datetime, timedelta
from flask import render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from app import db
from app.owner import owner
from app.owner.forms import AssignTaskForm
from app.models import User, Task, ActivityLog, Notification
from app.utils import owner_required, log_activity, notify_user


def _active_users():
    return User.query.filter_by(is_active=True).order_by(User.username).all()


@owner.route('/')
@login_required
@owner_required
def index():
    now = datetime.utcnow()
    today_start = datetime(now.year, now.month, now.day)
    week_start = today_start - timedelta(days=today_start.weekday())

    users = _active_users()

    total_tasks = Task.query.count()
    done_today_all = Task.query.filter(
        Task.status == Task.STATUS_DONE,
        Task.updated_at >= today_start
    ).count()
    overdue_total = Task.query.filter(
        Task.status.notin_([Task.STATUS_DONE, Task.STATUS_CANCELLED]),
        Task.deadline.isnot(None),
        Task.deadline < now
    ).count()

    user_stats = []
    for u in users:
        active = Task.query.filter_by(user_id=u.id).filter(
            Task.status.notin_([Task.STATUS_DONE, Task.STATUS_CANCELLED])
        ).count()

        done_today = Task.query.filter_by(user_id=u.id, status=Task.STATUS_DONE).filter(
            Task.updated_at >= today_start
        ).count()

        week_done = Task.query.filter_by(user_id=u.id, status=Task.STATUS_DONE).filter(
            Task.completed_at >= week_start
        ).count()

        overdue = Task.query.filter_by(user_id=u.id).filter(
            Task.status.notin_([Task.STATUS_DONE, Task.STATUS_CANCELLED]),
            Task.deadline.isnot(None),
            Task.deadline < now
        ).count()

        last_log = ActivityLog.query.filter_by(user_id=u.id).order_by(
            ActivityLog.created_at.desc()
        ).first()
        last_activity = last_log.created_at if last_log else u.last_login

        week_total = week_done + active
        week_pct = int(week_done / week_total * 100) if week_total > 0 else 0

        if overdue == 0:
            color = 'green'
        elif overdue <= 2:
            color = 'yellow'
        else:
            color = 'red'

        user_stats.append({
            'user': u,
            'active': active,
            'done_today': done_today,
            'week_done': week_done,
            'week_pct': week_pct,
            'overdue': overdue,
            'last_activity': last_activity,
            'color': color,
        })

    user_stats.sort(key=lambda x: (-x['overdue'], x['user'].username))

    assign_form = AssignTaskForm()
    assign_form.assigned_to_id.choices = [(u.id, u.username) for u in users]

    return render_template('owner/index.html',
                           user_stats=user_stats,
                           total_users=len(users),
                           total_tasks=total_tasks,
                           done_today_all=done_today_all,
                           overdue_total=overdue_total,
                           assign_form=assign_form,
                           now=now)


@owner.route('/tasks')
@login_required
@owner_required
def task_list():
    now = datetime.utcnow()
    user_filter = request.args.get('user', '')
    status_filter = request.args.get('status', '')
    priority_filter = request.args.get('priority', '')
    overdue_only = request.args.get('overdue', '') == '1'

    query = Task.query

    if user_filter and user_filter.isdigit():
        query = query.filter_by(user_id=int(user_filter))
    if status_filter and status_filter in Task.STATUSES:
        query = query.filter_by(status=status_filter)
    if priority_filter and priority_filter in Task.PRIORITIES:
        query = query.filter_by(priority=priority_filter)
    if overdue_only:
        query = query.filter(
            Task.status.notin_([Task.STATUS_DONE, Task.STATUS_CANCELLED]),
            Task.deadline.isnot(None),
            Task.deadline < now
        )

    tasks = query.order_by(Task.updated_at.desc()).all()
    all_users = _active_users()

    return render_template('owner/tasks.html',
                           tasks=tasks, all_users=all_users,
                           user_filter=user_filter,
                           status_filter=status_filter,
                           priority_filter=priority_filter,
                           overdue_only=overdue_only,
                           now=now, Task=Task)


@owner.route('/assign', methods=['POST'])
@login_required
@owner_required
def assign_task():
    users = _active_users()
    form = AssignTaskForm()
    form.assigned_to_id.choices = [(u.id, u.username) for u in users]

    if form.validate_on_submit():
        aid = form.assigned_to_id.data
        assignee = db.session.get(User, aid)
        task = Task(
            user_id=current_user.id,
            assigned_to_id=aid,
            title=form.title.data.strip(),
            description=form.description.data or '',
            priority=form.priority.data,
            status=Task.STATUS_TODO,
            deadline=form.deadline.data,
            is_owner_assigned=True,
        )
        db.session.add(task)
        db.session.flush()

        if assignee:
            notify_user(aid, Notification.TYPE_ASSIGNED,
                        f'Владелец поручил(а) вам задачу «{task.title}»',
                        url_for('tasks.task_detail', task_id=task.id))
            log_activity(current_user.id, 'task_created',
                         f'Поручил(а) задачу «{task.title}» пользователю {assignee.username}',
                         'task', task.id)

        db.session.commit()
        flash(f'Задача «{task.title}» поручена.', 'success')
    else:
        for errors in form.errors.values():
            for e in errors:
                flash(e, 'danger')

    return redirect(url_for('owner.index'))


@owner.route('/tasks/<int:task_id>/update', methods=['POST'])
@login_required
@owner_required
def update_task(task_id):
    task = db.session.get(Task, task_id)
    if task is None:
        abort(404)

    new_status = request.form.get('status')
    new_assignee_raw = request.form.get('assigned_to_id', '')
    new_assignee = int(new_assignee_raw) if new_assignee_raw.isdigit() else None

    changed = False

    if new_status and new_status in Task.STATUSES and new_status != task.status:
        old_status = task.status
        task.status = new_status
        task.updated_at = datetime.utcnow()
        if new_status == Task.STATUS_DONE and old_status != Task.STATUS_DONE:
            task.completed_at = datetime.utcnow()
        elif new_status != Task.STATUS_DONE:
            task.completed_at = None
        changed = True

    if new_assignee and new_assignee != task.assigned_to_id:
        task.assigned_to_id = new_assignee
        task.updated_at = datetime.utcnow()
        notify_user(new_assignee, Notification.TYPE_ASSIGNED,
                    f'Владелец назначил(а) вам задачу «{task.title}»',
                    url_for('tasks.task_detail', task_id=task.id))
        changed = True

    if changed:
        log_activity(current_user.id, 'task_updated',
                     f'[Владелец] Обновил(а) задачу «{task.title}»', 'task', task.id)
        db.session.commit()
        flash('Задача обновлена.', 'success')

    return redirect(request.referrer or url_for('owner.task_list'))
