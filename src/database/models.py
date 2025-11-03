"""
Database models for the Content Virality Platform.
"""
import uuid
from datetime import datetime
from typing import List, Optional
from sqlalchemy import (
    Column, String, Boolean, DateTime, Text, JSON, 
    ForeignKey, Table, UniqueConstraint, Numeric
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, Session
from sqlalchemy.sql import func
from sqlalchemy.types import TypeDecorator, CHAR
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID

Base = declarative_base()


class GUID(TypeDecorator):
    """Platform-independent GUID type.
    
    Uses PostgreSQL's UUID type when available, otherwise uses CHAR(36).
    """
    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(PostgresUUID())
        else:
            return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == 'postgresql':
            return str(value)
        else:
            if not isinstance(value, uuid.UUID):
                return str(uuid.UUID(value))
            else:
                return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        else:
            if not isinstance(value, uuid.UUID):
                return uuid.UUID(value)
            return value

# Association table for user roles (many-to-many)
user_roles = Table(
    'user_roles',
    Base.metadata,
    Column('user_id', GUID(), ForeignKey('users.id'), primary_key=True),
    Column('role_id', GUID(), ForeignKey('roles.id'), primary_key=True),
    Column('assigned_at', DateTime, default=datetime.utcnow)
)


class User(Base):
    """User model for authentication and profile management."""
    __tablename__ = 'users'
    
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    first_name = Column(String(50))
    last_name = Column(String(50))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    roles = relationship("Role", secondary=user_roles, back_populates="users")
    created_data_sources = relationship("DataSource", back_populates="created_by_user")
    trained_models = relationship("MLModel", back_populates="trained_by_user")
    custom_reports = relationship("CustomReport", back_populates="created_by_user")
    activity_logs = relationship("ActivityLog", back_populates="user")
    
    def __repr__(self):
        return f"<User(username='{self.username}', email='{self.email}')>"
    
    @property
    def full_name(self):
        """Get user's full name."""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.username
    
    def has_role(self, role_name: str) -> bool:
        """Check if user has a specific role."""
        return any(role.name == role_name for role in self.roles)
    
    def has_permission(self, permission: str) -> bool:
        """Check if user has a specific permission."""
        for role in self.roles:
            if role.permissions and permission in role.permissions:
                return True
        return False


class Role(Base):
    """Role model for role-based access control."""
    __tablename__ = 'roles'
    
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    name = Column(String(50), unique=True, nullable=False)
    description = Column(Text)
    permissions = Column(JSON)  # List of permission strings
    
    # Relationships
    users = relationship("User", secondary=user_roles, back_populates="roles")
    
    def __repr__(self):
        return f"<Role(name='{self.name}')>"


class DataSource(Base):
    """Data source model for managing external content sources."""
    __tablename__ = 'data_sources'
    
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    type = Column(String(50), nullable=False)  # 'reddit', 'twitter', 'rss'
    config = Column(JSON, nullable=False)  # Source-specific configuration
    is_active = Column(Boolean, default=True)
    created_by = Column(GUID(), ForeignKey('users.id'))
    created_at = Column(DateTime, default=datetime.utcnow)
    last_scraped_at = Column(DateTime)
    
    # Relationships
    created_by_user = relationship("User", back_populates="created_data_sources")
    scraping_jobs = relationship("ScrapingJob", back_populates="data_source")
    
    def __repr__(self):
        return f"<DataSource(name='{self.name}', type='{self.type}')>"


class ScrapingJob(Base):
    """Scraping job model for scheduled data collection."""
    __tablename__ = 'scraping_jobs'
    
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    data_source_id = Column(GUID(), ForeignKey('data_sources.id'), nullable=False)
    schedule_cron = Column(String(100))  # Cron expression for scheduling
    is_active = Column(Boolean, default=True)
    last_run_at = Column(DateTime)
    next_run_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    data_source = relationship("DataSource", back_populates="scraping_jobs")
    
    def __repr__(self):
        return f"<ScrapingJob(data_source_id='{self.data_source_id}', schedule='{self.schedule_cron}')>"


class MLModel(Base):
    """ML model management for versioning and performance tracking."""
    __tablename__ = 'ml_models'
    
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    type = Column(String(50), nullable=False)  # 'virality', 'topic', 'sentiment'
    version = Column(String(20), nullable=False)
    model_path = Column(String(255))
    metrics = Column(JSON)  # Performance metrics
    is_active = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    trained_by = Column(GUID(), ForeignKey('users.id'))
    
    # Relationships
    trained_by_user = relationship("User", back_populates="trained_models")
    performance_records = relationship("ModelPerformance", back_populates="model")
    
    # Unique constraint on name and version
    __table_args__ = (UniqueConstraint('name', 'version', name='_model_name_version_uc'),)
    
    def __repr__(self):
        return f"<MLModel(name='{self.name}', version='{self.version}', type='{self.type}')>"


class ModelPerformance(Base):
    """Model performance tracking over time."""
    __tablename__ = 'model_performance'
    
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    model_id = Column(GUID(), ForeignKey('ml_models.id'), nullable=False)
    metric_name = Column(String(50), nullable=False)
    metric_value = Column(Numeric(10, 4), nullable=False)
    recorded_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    model = relationship("MLModel", back_populates="performance_records")
    
    def __repr__(self):
        return f"<ModelPerformance(model_id='{self.model_id}', metric='{self.metric_name}', value={self.metric_value})>"


class CustomReport(Base):
    """Custom report configurations and saved analyses."""
    __tablename__ = 'custom_reports'
    
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    config = Column(JSON, nullable=False)  # Report configuration and parameters
    created_by = Column(GUID(), ForeignKey('users.id'), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    created_by_user = relationship("User", back_populates="custom_reports")
    
    def __repr__(self):
        return f"<CustomReport(name='{self.name}', created_by='{self.created_by}')>"


class ActivityLog(Base):
    """System activity logging for audit trails."""
    __tablename__ = 'activity_logs'
    
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id = Column(GUID(), ForeignKey('users.id'))
    action = Column(String(100), nullable=False)
    resource_type = Column(String(50))
    resource_id = Column(String(100))
    details = Column(JSON)  # Additional action details
    ip_address = Column(String(45))  # IPv4 or IPv6
    user_agent = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="activity_logs")
    
    def __repr__(self):
        return f"<ActivityLog(user_id='{self.user_id}', action='{self.action}')>"