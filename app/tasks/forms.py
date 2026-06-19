from flask_wtf import FlaskForm
from wtforms import (StringField, TextAreaField, SelectField,
                     DateTimeLocalField, SubmitField, HiddenField, IntegerField)
from wtforms.validators import DataRequired, Length, Optional, NumberRange
from app.models import Task


class TaskForm(FlaskForm):
    title = StringField('Название', validators=[DataRequired(), Length(1, 200)])
    description = TextAreaField('Описание', validators=[Optional(), Length(max=5000)])
    project_id = SelectField('Проект', choices=[], validators=[Optional()])
    assigned_to_id = SelectField('Исполнитель', choices=[], validators=[Optional()])
    priority = SelectField('Приоритет', choices=[
        (Task.PRIORITY_LOW, 'Низкий'), (Task.PRIORITY_MEDIUM, 'Средний'),
        (Task.PRIORITY_HIGH, 'Высокий'), (Task.PRIORITY_CRITICAL, 'Критический'),
    ], default=Task.PRIORITY_MEDIUM)
    status = SelectField('Статус', choices=[
        (Task.STATUS_TODO, 'К выполнению'), (Task.STATUS_IN_PROGRESS, 'В работе'),
        (Task.STATUS_REVIEW, 'На проверке'), (Task.STATUS_DONE, 'Выполнено'),
        (Task.STATUS_CANCELLED, 'Отменено'),
    ], default=Task.STATUS_TODO)
    deadline = DateTimeLocalField('Срок', format='%Y-%m-%dT%H:%M', validators=[Optional()])
    time_estimate = IntegerField('Оценка (мин)', validators=[Optional(), NumberRange(min=1)], default=None)
    tag_ids = HiddenField('Метки')
    subtasks_json = HiddenField('Подзадачи')
    submit = SubmitField('Сохранить')


class CommentForm(FlaskForm):
    content = TextAreaField('Комментарий', validators=[DataRequired(), Length(1, 2000)])
    submit = SubmitField('Отправить')


class TagForm(FlaskForm):
    name = StringField('Название метки', validators=[DataRequired(), Length(1, 50)])
    color = StringField('Цвет', validators=[DataRequired(), Length(7, 7)], default='#6366f1')
    submit = SubmitField('Создать')
