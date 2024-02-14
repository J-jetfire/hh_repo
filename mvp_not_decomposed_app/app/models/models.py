import uuid
# from sqlalchemy import MetaData
# from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, BOOLEAN, Table, ForeignKey, func, DateTime, Sequence
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, validates

from app.database.database import Base


### APP MODELS ###