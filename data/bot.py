import sqlalchemy
from data.db_session import *
import datetime
from sqlalchemy import orm


class BotToken(SqlAlchemyBase):
    __tablename__ = 'bots'
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True, autoincrement=True)
    token = sqlalchemy.Column(sqlalchemy.VARCHAR(250), unique=True)