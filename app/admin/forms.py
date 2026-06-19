from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SelectField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Length, Email, Optional, EqualTo, ValidationError
from app.models import User

ROLE_CHOICES = [('user', 'Пользователь'), ('admin', 'Администратор')]


class CreateUserForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(3, 64)])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=120)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=8)])
    confirm_password = PasswordField('Confirm Password', validators=[
        DataRequired(), EqualTo('password', message='Passwords must match.')
    ])
    role = SelectField('Роль', choices=ROLE_CHOICES, default='user')
    submit = SubmitField('Создать пользователя')

    def validate_username(self, field):
        if User.query.filter_by(username=field.data.strip()).first():
            raise ValidationError('Username already taken.')

    def validate_email(self, field):
        if User.query.filter_by(email=field.data.strip().lower()).first():
            raise ValidationError('Email already registered.')


class EditUserForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=120)])
    role = SelectField('Роль', choices=ROLE_CHOICES)
    is_active = BooleanField('Активен')
    new_password = PasswordField('Новый пароль (оставьте пустым, чтобы не менять)',
                                 validators=[Optional(), Length(min=8)])
    submit = SubmitField('Сохранить')
