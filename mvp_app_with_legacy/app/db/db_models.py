import uuid
from enum import Enum
from sqlalchemy import Column, Integer, String, TIMESTAMP, BOOLEAN, ForeignKey, BigInteger, Enum as EnumSQL, FLOAT, \
    DateTime, Sequence, Table, MetaData, Float, func, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship

Base = declarative_base()
metadata = MetaData()

### MODELS ###