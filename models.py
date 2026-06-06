from sqlalchemy import create_engine, Column, Integer, String, Float, Date, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from datetime import datetime, date
from config import DB_PATH

engine = create_engine(f'sqlite:///{DB_PATH}', echo=False)
Base = declarative_base()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Supplier(Base):
    __tablename__ = 'suppliers'

    id = Column(Integer, primary_key=True)
    supplier_code = Column(String(50), unique=True, nullable=False)
    supplier_name = Column(String(200), nullable=False)
    contact_person = Column(String(100))
    contact_phone = Column(String(50))
    contact_email = Column(String(100))
    address = Column(Text)
    industry = Column(String(100))
    registered_capital = Column(Float)
    establishment_date = Column(Date)
    status = Column(String(20), default='pending')
    level = Column(String(10))
    total_score = Column(Float)
    quality_score = Column(Float)
    environmental_score = Column(Float)
    financial_score = Column(Float)
    admission_date = Column(Date)
    last_review_date = Column(Date)
    next_review_date = Column(Date)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    is_active = Column(Boolean, default=True)

    qualifications = relationship('Qualification', back_populates='supplier', cascade='all, delete-orphan')
    performance_records = relationship('PerformanceRecord', back_populates='supplier', cascade='all, delete-orphan')
    quality_issues = relationship('QualityIssue', back_populates='supplier', cascade='all, delete-orphan')
    tasks = relationship('Task', back_populates='supplier', cascade='all, delete-orphan')
    level_changes = relationship('LevelChange', back_populates='supplier', cascade='all, delete-orphan')
    transactions = relationship('Transaction', back_populates='supplier', cascade='all, delete-orphan')


class Qualification(Base):
    __tablename__ = 'qualifications'

    id = Column(Integer, primary_key=True)
    supplier_id = Column(Integer, ForeignKey('suppliers.id'), nullable=False)
    qual_type = Column(String(100), nullable=False)
    cert_number = Column(String(100))
    issue_date = Column(Date)
    expiry_date = Column(Date)
    issuing_authority = Column(String(200))
    file_path = Column(String(500))
    ocr_result = Column(Text)
    is_verified = Column(Boolean, default=False)
    verification_note = Column(Text)
    created_at = Column(DateTime, default=datetime.now)

    supplier = relationship('Supplier', back_populates='qualifications')


class PerformanceRecord(Base):
    __tablename__ = 'performance_records'

    id = Column(Integer, primary_key=True)
    supplier_id = Column(Integer, ForeignKey('suppliers.id'), nullable=False)
    record_year = Column(Integer, nullable=False)
    record_month = Column(Integer, nullable=False)
    on_time_rate = Column(Float)
    quality_pass_rate = Column(Float)
    response_time_hours = Column(Float)
    total_orders = Column(Integer)
    total_amount = Column(Float)
    complaint_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.now)

    supplier = relationship('Supplier', back_populates='performance_records')


class QualityIssue(Base):
    __tablename__ = 'quality_issues'

    id = Column(Integer, primary_key=True)
    supplier_id = Column(Integer, ForeignKey('suppliers.id'), nullable=False)
    issue_date = Column(Date, nullable=False)
    issue_type = Column(String(50))
    severity = Column(String(20), default='normal')
    description = Column(Text)
    affected_orders = Column(String(500))
    is_resolved = Column(Boolean, default=False)
    resolution_date = Column(Date)
    created_at = Column(DateTime, default=datetime.now)

    supplier = relationship('Supplier', back_populates='quality_issues')


class Task(Base):
    __tablename__ = 'tasks'

    id = Column(Integer, primary_key=True)
    supplier_id = Column(Integer, ForeignKey('suppliers.id'), nullable=False)
    task_type = Column(String(50), nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    status = Column(String(20), default='pending')
    priority = Column(String(20), default='normal')
    created_at = Column(DateTime, default=datetime.now)
    due_date = Column(Date)
    last_reminder_date = Column(Date)
    reminder_count = Column(Integer, default=0)
    assigned_to = Column(String(100))
    completed_at = Column(DateTime)

    supplier = relationship('Supplier', back_populates='tasks')


class LevelChange(Base):
    __tablename__ = 'level_changes'

    id = Column(Integer, primary_key=True)
    supplier_id = Column(Integer, ForeignKey('suppliers.id'), nullable=False)
    old_level = Column(String(10))
    new_level = Column(String(10))
    change_type = Column(String(20))
    reason = Column(Text)
    score_before = Column(Float)
    score_after = Column(Float)
    status = Column(String(20), default='pending')
    approver = Column(String(100))
    approval_date = Column(Date)
    created_at = Column(DateTime, default=datetime.now)

    supplier = relationship('Supplier', back_populates='level_changes')


class Transaction(Base):
    __tablename__ = 'transactions'

    id = Column(Integer, primary_key=True)
    supplier_id = Column(Integer, ForeignKey('suppliers.id'), nullable=False)
    transaction_date = Column(Date, nullable=False)
    order_number = Column(String(100))
    product_name = Column(String(200))
    quantity = Column(Float)
    unit_price = Column(Float)
    total_amount = Column(Float)
    is_on_time = Column(Boolean)
    quality_grade = Column(String(20))
    created_at = Column(DateTime, default=datetime.now)

    supplier = relationship('Supplier', back_populates='transactions')


class OperationLog(Base):
    __tablename__ = 'operation_logs'

    id = Column(Integer, primary_key=True)
    operator = Column(String(100))
    operation_type = Column(String(50), nullable=False)
    target_type = Column(String(50))
    target_id = Column(Integer)
    description = Column(Text)
    old_value = Column(Text)
    new_value = Column(Text)
    ip_address = Column(String(50))
    created_at = Column(DateTime, default=datetime.now)


class SupplierAlternative(Base):
    __tablename__ = 'supplier_alternatives'

    id = Column(Integer, primary_key=True)
    original_supplier_id = Column(Integer, ForeignKey('suppliers.id'), nullable=False)
    alternative_supplier_id = Column(Integer, ForeignKey('suppliers.id'), nullable=False)
    match_score = Column(Float)
    recommendation_reason = Column(Text)
    created_at = Column(DateTime, default=datetime.now)


def init_db():
    Base.metadata.create_all(bind=engine)


def get_session():
    return SessionLocal()


if __name__ == '__main__':
    init_db()
    print('数据库初始化完成')
