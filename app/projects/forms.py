from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, Length, Optional


class ProjectForm(FlaskForm):
    name = StringField('Название', validators=[DataRequired(), Length(1, 100)])
    description = TextAreaField('Описание', validators=[Optional(), Length(max=1000)])
    color = StringField('Цвет', validators=[DataRequired(), Length(7, 7)], default='#6366f1')
    submit = SubmitField('Сохранить')
