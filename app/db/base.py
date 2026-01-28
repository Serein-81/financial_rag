# app/db/base.py
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    """
    SQLAlchemy ORM 的基类。
    所有的数据模型（Model）都要继承这个类，
    这样 SQLAlchemy 才能知道哪些类是数据库表。
    """
    pass