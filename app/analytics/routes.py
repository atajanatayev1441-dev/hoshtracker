from datetime import datetime, timedelta
from flask import render_template, jsonify
from flask_login import login_required, current_user
from sqlalchemy import func, and_
from app import db
from app.analytics import analytics
from app.models import Task, TimeEntry


@analytics.route('/')
@login_required
def index():
    return render_template('analytics/index.html')


@analytics.route('/api/stats')
@login_required
def api_stats():
    now = datetime.utcnow()
    week_ago = now - timedelta(days=7)
    uid = current_user.id

    total = Task.query.filter_by(user_id=uid).count()
    done_total = Task.query.filter_by(user_id=uid, status=Task.STATUS_DONE).count()
    done_week = Task.query.filter(
        Task.user_id == uid,
        Task.status == Task.STATUS_DONE,
        Task.completed_at >= week_ago
    ).count()
    overdue = sum(1 for t in Task.query.filter(
        Task.user_id == uid,
        Task.status.notin_([Task.STATUS_DONE, Task.STATUS_CANCELLED]),
        Task.deadline.isnot(None)
    ).all() if t.deadline < now)

    rate = round(done_total / total * 100) if total else 0

    return jsonify({
        'total': total,
        'done_total': done_total,
        'done_week': done_week,
        'overdue': overdue,
        'completion_rate': rate,
    })


@analytics.route('/api/productivity')
@login_required
def api_productivity():
    """Tasks completed per day for last 30 days."""
    now = datetime.utcnow()
    uid = current_user.id
    days = 30

    # Build a dict date→count from DB
    start = now - timedelta(days=days - 1)
    rows = db.session.query(
        func.date(Task.completed_at).label('day'),
        func.count(Task.id).label('cnt')
    ).filter(
        Task.user_id == uid,
        Task.status == Task.STATUS_DONE,
        Task.completed_at >= start,
        Task.completed_at.isnot(None)
    ).group_by(func.date(Task.completed_at)).all()

    counts = {str(r.day): r.cnt for r in rows}

    labels, data = [], []
    for i in range(days):
        d = (start + timedelta(days=i)).date()
        labels.append(d.strftime('%d.%m'))
        data.append(counts.get(str(d), 0))

    return jsonify({'labels': labels, 'data': data})


@analytics.route('/api/weekly')
@login_required
def api_weekly():
    """Tasks completed per week for last 12 weeks."""
    now = datetime.utcnow()
    uid = current_user.id
    labels, data = [], []
    for w in range(11, -1, -1):
        week_end = now - timedelta(weeks=w)
        week_start = week_end - timedelta(days=7)
        cnt = Task.query.filter(
            Task.user_id == uid,
            Task.status == Task.STATUS_DONE,
            Task.completed_at >= week_start,
            Task.completed_at < week_end,
            Task.completed_at.isnot(None)
        ).count()
        labels.append(week_end.strftime('%d.%m'))
        data.append(cnt)
    return jsonify({'labels': labels, 'data': data})


@analytics.route('/api/by-status')
@login_required
def api_by_status():
    uid = current_user.id
    result = {}
    for s in Task.STATUSES:
        result[s] = Task.query.filter_by(user_id=uid, status=s).count()
    return jsonify(result)


@analytics.route('/api/heatmap')
@login_required
def api_heatmap():
    """Completed tasks per day for last 365 days."""
    now = datetime.utcnow()
    uid = current_user.id
    start = now - timedelta(days=364)

    rows = db.session.query(
        func.date(Task.completed_at).label('day'),
        func.count(Task.id).label('cnt')
    ).filter(
        Task.user_id == uid,
        Task.status == Task.STATUS_DONE,
        Task.completed_at >= start,
        Task.completed_at.isnot(None)
    ).group_by(func.date(Task.completed_at)).all()

    counts = {str(r.day): r.cnt for r in rows}

    # Build 365 days
    cells = []
    for i in range(365):
        d = (start + timedelta(days=i)).date()
        cells.append({'date': str(d), 'count': counts.get(str(d), 0)})

    max_count = max((c['count'] for c in cells), default=1) or 1
    return jsonify({'cells': cells, 'max': max_count})
