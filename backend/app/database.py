from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = "sqlite:///./split_piggybank.db"

engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def run_migrations():
    """Lightweight ad-hoc migrations for columns added after the initial release.

    Base.metadata.create_all() only creates missing tables, it never alters
    existing ones, so a new nullable-with-default column on an existing table
    needs to be added by hand for databases created before it existed.
    """
    with engine.connect() as conn:
        existing_cols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(groups)")}
        if "currency" not in existing_cols:
            conn.exec_driver_sql("ALTER TABLE groups ADD COLUMN currency VARCHAR(3) NOT NULL DEFAULT 'RUB'")
            conn.commit()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
