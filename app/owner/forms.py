from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, DateTimeLocalField, SubmitField
from wtforms.validators import DataRequired, Length, Optional
from app.models import Task


class AssignTaskForm(FlaskForm):
    title = StringField('Название', validators=[DataRequired(), Length(1, 200)])
    description = TextAreaField('Описание', validators=[Optional(), Length(max=2000)])
    priority = SelectField('Приоритет', choices=[
        (Task.PRIORITY_LOW, 'Низкий'),
        (Task.PRIORITY_MEDIUM, 'Средний'),
        (Task.PRIORITY_HIGH, 'Высокий'),
        (Task.PRIORITY_CRITICAL, 'Критический'),
    ], default=Task.PRIORITY_MEDIUM)
    deadline = DateTimeLocalField('Срок', format='%Y-%m-%dT%H:%M', validators=[Optional()])
    assigned_to_id = SelectField('Исполнитель', validators=[DataRequired()], coerce=int)
    submit = SubmitField('Поручить')
