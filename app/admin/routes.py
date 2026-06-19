from functools import wraps
from datetime import datetime
from flask import render_template, redirect, url_for, flash, request, session, abort
from flask_login import login_required, current_user, login_user
from app import db
from app.admin import admin
from app.admin.forms import CreateUserForm, EditUserForm
from app.models import User, Task, Project, ProjectMember, ActivityLog
from app.utils import log_activity


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin():
            abort(403)
        return f(*args, **kwargs)
    return decorated


@admin.route('/')
@login_required
@admin_required
def index():
    total_users = User.query.count()
    active_users = User.query.filter_by(is_active=True).count()
    total_tasks = Task.query.count()
    tasks_by_status = {s: Task.query.filter_by(status=s).count() for s in Task.STATUSES}
    recent_users = User.query.order_by(User.created_at.desc()).limit(5).all()
    recent_activity = ActivityLog.query.order_by(ActivityLog.created_at.desc()).limit(20).all()
    return render_template('admin/index.html',
                           total_users=total_users, active_users=active_users,
                           total_tasks=total_tasks, tasks_by_status=tasks_by_status,
                           recent_users=recent_users, recent_activity=recent_activity)


@admin.route('/users')
@login_required
@admin_required
def user_list():
    search = request.args.get('q', '').strip()
    query = User.query
    if search:
        query = query.filter(
            db.or_(User.username.ilike(f'%{search}%'), User.email.ilike(f'%{search}%')))
    users = query.order_by(User.created_at.desc()).all()
    all_projects = Project.query.order_by(Project.name).all()
    return render_template('admin/user_list.html', users=users, search=search,
                           all_projects=all_projects)


@admin.route('/users/new', methods=['GET', 'POST'])
@login_required
@admin_required
def create_user():
    form = CreateUserForm()
    if form.validate_on_submit():
        user = User(username=form.username.data.strip(),
                    email=form.email.data.strip().lower(),
                    role=form.role.data, is_active=True)
        user.set_password(form.password.data)
        db.session.add(user)
        log_activity(current_user.id, 'user_created',
                     f'Создал(а) пользователя {user.username}', 'user', None)
        db.session.commit()
        flash(f'Пользователь «{user.username}» создан.', 'success')
        return redirect(url_for('admin.user_list'))
    return render_template('admin/user_form.html', form=form, title='Новый пользователь', user=None)


@admin.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_user(user_id):
    user = db.session.get(User, user_id)
    if user is None:
        abort(404)
    form = EditUserForm(obj=user)
    if form.validate_on_submit():
        existing = User.query.filter(User.email == form.email.data.strip().lower(),
                                     User.id != user_id).first()
        if existing:
            flash('Email уже используется другим аккаунтом.', 'danger')
            return render_template('admin/user_form.html', form=form,
                                   title='Редактировать пользователя', user=user)
        user.email = form.email.data.strip().lower()
        user.role = form.role.data
        user.is_active = form.is_active.data
        if form.new_password.data:
            user.set_password(form.new_password.data)
            user.must_change_password = True
        db.session.commit()
        flash(f'Пользователь «{user.username}» обновлён.', 'success')
        return redirect(url_for('admin.user_list'))
    return render_template('admin/user_form.html', form=form,
                           title='Редактировать пользователя', user=user)


@admin.route('/users/<int:user_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    user = db.session.get(User, user_id)
    if user is None:
        abort(404)
    if user.id == current_user.id:
        flash('Нельзя удалить свой аккаунт.', 'danger')
        return redirect(url_for('admin.user_list'))
    username = user.username
    db.session.delete(user)
    db.session.commit()
    flash(f'Пользователь «{username}» и все его данные удалены.', 'info')
    return redirect(url_for('admin.user_list'))


@admin.route('/users/<int:user_id>/toggle-active', methods=['POST'])
@login_required
@admin_required
def toggle_user_active(user_id):
    user = db.session.get(User, user_id)
    if user is None:
        abort(404)
    if user.id == current_user.id:
        flash('Нельзя деактивировать свой аккаунт.', 'danger')
        return redirect(url_for('admin.user_list'))
    user.is_active = not user.is_active
    db.session.commit()
    flash(f'Пользователь «{user.username}» {"активирован" if user.is_active else "деактивирован"}.', 'success')
    return redirect(url_for('admin.user_list'))


@admin.route('/users/<int:user_id>/add-to-project', methods=['POST'])
@login_required
@admin_required
def add_user_to_project(user_id):
    user = db.session.get(User, user_id)
    if user is None:
        abort(404)
    project_id = request.form.get('project_id', type=int)
    role = request.form.get('role', ProjectMember.ROLE_VIEWER)
    p = db.session.get(Project, project_id)
    if p is None:
        flash('Проект не найден.', 'danger')
        return redirect(url_for('admin.user_list'))
    existing = ProjectMember.query.filter_by(project_id=project_id, user_id=user_id).first()
    if existing:
        flash('Пользователь уже состоит в этом проекте.', 'warning')
    else:
        db.session.add(ProjectMember(project_id=project_id, user_id=user_id, role=role))
        db.session.commit()
        flash(f'Пользователь добавлен в проект «{p.name}».', 'success')
    return redirect(url_for('admin.user_list'))


@admin.route('/users/<int:user_id>/impersonate', methods=['POST'])
@login_required
@admin_required
def impersonate(user_id):
    user = db.session.get(User, user_id)
    if user is None:
        abort(404)
    session['impersonating_as'] = user_id
    session['original_admin_id'] = current_user.id
    login_user(user)
    flash(f'Просматривается как {user.username}. '
          f'<a href="{url_for("admin.stop_impersonate")}" class="underline">Вернуться</a>', 'warning')
    return redirect(url_for('tasks.dashboard'))


@admin.route('/stop-impersonate')
@login_required
def stop_impersonate():
    original_id = session.pop('original_admin_id', None)
    session.pop('impersonating_as', None)
    if original_id:
        admin_user = db.session.get(User, original_id)
        if admin_user:
            login_user(admin_user)
            flash('Вернулись к аккаунту администратора.', 'info')
            return redirect(url_for('admin.user_list'))
    return redirect(url_for('tasks.dashboard'))


@admin.route('/activity')
@login_required
@admin_required
def activity_log():
    page = request.args.get('page', 1, type=int)
    logs = ActivityLog.query.order_by(ActivityLog.created_at.desc()).limit(100).all()
    return render_template('admin/activity_log.html', logs=logs)
