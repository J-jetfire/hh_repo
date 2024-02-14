from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

# engine = create_engine(settings.DATABASE_URL, pool_size=50)


if settings.MODE == 'TEST':
    engine = create_engine(settings.TEST_DATABASE_URL, pool_size=50)
elif settings.MODE == 'DEV':
    engine = create_engine(settings.DATABASE_URL, pool_size=50)
else:
    engine = create_engine(settings.DATABASE_URL, pool_size=50)  # standard env

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
