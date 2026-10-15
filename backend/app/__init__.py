# backend/app/models/__init__.py
from sqlalchemy.orm import DeclarativeBase

# from app.db.base import Base
# from app.models.candidate import CandidateProfile


class Base(DeclarativeBase):
    pass