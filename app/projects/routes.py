from datetime import datetime
from flask import render_template, redirect, url_for, flash, request, jsonify, abort
from flask_login import login_required, current_user
from app import db
from app.projects import projects
from app.projects.forms import ProjectForm
from app.models import Project, Task, ProjectMember, User, Notification
from app.utils import get_project_role, log_activity, notify_user, visible_tasks_query


def _get_project_or_404(project_id, require_role=None):
    """Fetch project; verify user is owner (or member if require_role is None)."""
    p = db.session.get(Project, project_id)
    if p is None:
        abort(404)
    if current_user.is_admin():
        return p
    role = p.get_member_role(current_user.id)
    owner = p.user_id == current_user.id
    if require_role == 'owner':
        if not owner:
            abort(403)
    elif not owner and role is None:
        abort(404)  # user can't even see it
    return p


@projects.route('/')
@login_required
def project_list():
    # Own projects
    own = Project.query.filter_by(user_id=current_user.id, is_archived=False)\
                       .order_by(Project.created_at.desc()).all()
    # Shared projects (member but not owner)
    member_ids = db.session.query(ProjectMember.project_id)\
                           .filter_by(user_id=current_user.id)\
                           .subquery()
    shared = Project.query.filter(
        Project.id.in_(member_ids),
        Project.user_id != current_user.id,
        Project.is_archived == False
    ).order_by(Project.created_at.desc()).all()

    archived = Project.query.filter_by(user_id=current_user.id, is_archived=True)\
                            .order_by(Project.created_at.desc()).all()
    form = ProjectForm()
    return render_template('projects/list.html', active=own, shared=shared,
                           archived=archived, form=form)


@projects.route('/create', methods=['POST'])
@login_required
def create():
    form = ProjectForm()
    if form.validate_on_submit():
        p = Project(user_id=current_user.id, name=form.name.data.strip(),
                    description=form.description.data, color=form.color.data)
        db.session.add(p)
        db.session.flush()
        # Owner gets an owner membership record too
        db.session.add(ProjectMember(project_id=p.id, user_id=current_user.id,
                                     role=ProjectMember.ROLE_OWNER))
        log_activity(current_user.id, 'project_created', f'Создал(а) проект «{p.name}»',
                     'project', p.id)
        db.session.commit()
        flash('Проект создан.', 'success')
    else:
        flash('Ошибка при создании проекта.', 'danger')
    return redirect(url_for('projects.project_list'))


@projects.route('/<int:project_id>')
@login_required
def detail(project_id):
    p = _get_project_or_404(project_id)
    status_filter = request.args.get('status', '')
    assigned_filter = request.args.get('assigned_to', '')

    query = Task.query.filter_by(project_id=project_id)
    if not current_user.is_admin():
        # Restrict task view within project to visible tasks
        query = visible_tasks_query(current_user.id).filter(Task.project_id == project_id)

    if status_filter and status_filter in Task.STATUSES:
        query = query.filter_by(status=status_filter)
    if assigned_filter == 'me':
        query = query.filter_by(assigned_to_id=current_user.id)
    elif assigned_filter and assigned_filter.isdigit():
        query = query.filter_by(assigned_to_id=int(assigned_filter))

    task_list = query.order_by(Task.order, Task.updated_at.desc()).all()
    member_role = p.get_member_role(current_user.id) or \
                  (ProjectMember.ROLE_OWNER if p.user_id == current_user.id else None)
    members = p.members.all()
    now = datetime.utcnow()
    return render_template('projects/detail.html', project=p, tasks=task_list,
                           status_filter=status_filter, assigned_filter=assigned_filter,
                           member_role=member_role, members=members, now=now, Task=Task)


@projects.route('/<int:project_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(project_id):
    p = _get_project_or_404(project_id, require_role='owner')
    form = ProjectForm(obj=p)
    if form.validate_on_submit():
        p.name = form.name.data.strip()
        p.description = form.description.data
        p.color = form.color.data
        log_activity(current_user.id, 'project_updated', f'Обновил(а) проект «{p.name}»',
                     'project', p.id)
        db.session.commit()
        flash('Проект обновлён.', 'success')
        return redirect(url_for('projects.detail', project_id=p.id))
    return render_template('projects/edit.html', form=form, project=p)


@projects.route('/<int:project_id>/delete', methods=['POST'])
@login_required
def delete(project_id):
    p = _get_project_or_404(project_id, require_role='owner')
    Task.query.filter_by(project_id=p.id).update({'project_id': None})
    db.session.delete(p)
    log_activity(current_user.id, 'project_deleted', f'Удалил(а) проект «{p.name}»')
    db.session.commit()
    flash('Проект удалён.', 'info')
    return redirect(url_for('projects.project_list'))


@projects.route('/<int:project_id>/archive', methods=['POST'])
@login_required
def archive(project_id):
    p = _get_project_or_404(project_id, require_role='owner')
    p.is_archived = not p.is_archived
    db.session.commit()
    flash(f'Проект {"архивирован" if p.is_archived else "восстановлен"}.', 'success')
    return redirect(url_for('projects.project_list'))


# ── Kanban ────────────────────────────────────────────────────────────────────

@projects.route('/<int:project_id>/kanban')
@login_required
def kanban(project_id):
    p = _get_project_or_404(project_id)
    columns = {s: [] for s in [Task.STATUS_TODO, Task.STATUS_IN_PROGRESS,
                                Task.STATUS_REVIEW, Task.STATUS_DONE]}

    base = visible_tasks_query(current_user.id) if not current_user.is_admin() else Task.query
    task_list = base.filter(
        Task.project_id == project_id,
        Task.status != Task.STATUS_CANCELLED
    ).order_by(Task.order, Task.updated_at.desc()).all()

    for t in task_list:
        if t.status in columns:
            columns[t.status].append(t)

    member_role = p.get_member_role(current_user.id) or \
                  (ProjectMember.ROLE_OWNER if p.user_id == current_user.id else None)
    now = datetime.utcnow()
    return render_template('projects/kanban.html', project=p, columns=columns,
                           member_role=member_role, now=now, Task=Task)


@projects.route('/kanban/move/<int:task_id>', methods=['POST'])
@login_required
def kanban_move(task_id):
    task = db.session.get(Task, task_id)
    if task is None:
        return jsonify({'error': 'Not found'}), 404
    from app.utils import can_edit_task
    if not can_edit_task(task, current_user):
        return jsonify({'error': 'Forbidden'}), 403
    data = request.get_json(silent=True) or {}
    new_status = data.get('status', '')
    if new_status not in Task.STATUSES:
        return jsonify({'error': 'Invalid status'}), 400
    old_status = task.status
    task.status = new_status
    task.order = data.get('order', task.order)
    task.updated_at = datetime.utcnow()
    if new_status == Task.STATUS_DONE and old_status != Task.STATUS_DONE:
        task.completed_at = datetime.utcnow()
    elif new_status != Task.STATUS_DONE:
        task.completed_at = None
    db.session.commit()
    return jsonify({'ok': True, 'status': task.status})


# ── Members ───────────────────────────────────────────────────────────────────

@projects.route('/<int:project_id>/members')
@login_required
def members(project_id):
    p = _get_project_or_404(project_id)
    member_role = p.get_member_role(current_user.id) or \
                  (ProjectMember.ROLE_OWNER if p.user_id == current_user.id else None)
    current_member_ids = {m.user_id for m in p.members.all()}
    available_users = User.query.filter(
        User.is_active == True,
        User.id.notin_(current_member_ids)
    ).order_by(User.username).all()
    return render_template('projects/members.html', project=p,
                           members=p.members.all(),
                           available_users=available_users,
                           member_role=member_role,
                           ProjectMember=ProjectMember)


@projects.route('/<int:project_id>/members/add', methods=['POST'])
@login_required
def add_member(project_id):
    p = _get_project_or_404(project_id, require_role='owner')
    user_id = request.form.get('user_id', type=int)
    role = request.form.get('role', ProjectMember.ROLE_VIEWER)
    if role not in ProjectMember.ROLES:
        flash('Неверная роль.', 'danger')
        return redirect(url_for('projects.members', project_id=project_id))

    user = db.session.get(User, user_id)
    if user is None or not user.is_active:
        flash('Пользователь не найден.', 'danger')
        return redirect(url_for('projects.members', project_id=project_id))

    existing = p.members.filter_by(user_id=user_id).first()
    if existing:
        flash('Пользователь уже является участником.', 'warning')
        return redirect(url_for('projects.members', project_id=project_id))

    member = ProjectMember(project_id=p.id, user_id=user_id, role=role)
    db.session.add(member)
    notify_user(user_id, Notification.TYPE_STATUS,
                f'{current_user.username} добавил(а) вас в проект «{p.name}»',
                url_for('projects.detail', project_id=p.id))
    log_activity(current_user.id, 'member_added',
                 f'Добавил(а) {user.username} в проект «{p.name}»', 'project', p.id)
    db.session.commit()
    flash(f'Пользователь {user.username} добавлен.', 'success')
    return redirect(url_for('projects.members', project_id=project_id))


@projects.route('/<int:project_id>/members/<int:user_id>/remove', methods=['POST'])
@login_required
def remove_member(project_id, user_id):
    p = _get_project_or_404(project_id, require_role='owner')
    if user_id == p.user_id:
        flash('Нельзя удалить владельца проекта.', 'danger')
        return redirect(url_for('projects.members', project_id=project_id))
    member = p.members.filter_by(user_id=user_id).first()
    if not member:
        abort(404)
    user = db.session.get(User, user_id)
    db.session.delete(member)
    log_activity(current_user.id, 'member_removed',
                 f'Удалил(а) {user.username if user else user_id} из проекта «{p.name}»',
                 'project', p.id)
    db.session.commit()
    flash('Участник удалён.', 'info')
    return redirect(url_for('projects.members', project_id=project_id))


@projects.route('/<int:project_id>/members/<int:user_id>/role', methods=['POST'])
@login_required
def change_member_role(project_id, user_id):
    p = _get_project_or_404(project_id, require_role='owner')
    if user_id == p.user_id:
        flash('Нельзя изменить роль владельца.', 'danger')
        return redirect(url_for('projects.members', project_id=project_id))
    member = p.members.filter_by(user_id=user_id).first_or_404()
    new_role = request.form.get('role', '')
    if new_role not in ProjectMember.ROLES:
        flash('Неверная роль.', 'danger')
        return redirect(url_for('projects.members', project_id=project_id))
    member.role = new_role
    db.session.commit()
    flash('Роль обновлена.', 'success')
    return redirect(url_for('projects.members', project_id=project_id))
