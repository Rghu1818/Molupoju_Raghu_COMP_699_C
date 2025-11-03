"""
Database utility functions.
"""
import uuid
from typing import Union


def ensure_uuid(value: Union[str, uuid.UUID]) -> uuid.UUID:
    """
    Ensure a value is a UUID object.
    
    Args:
        value: String UUID or UUID object
        
    Returns:
        UUID object
        
    Raises:
        ValueError: If the value cannot be converted to UUID
    """
    if isinstance(value, uuid.UUID):
        return value
    elif isinstance(value, str):
        if not value:
            raise ValueError("Empty string cannot be converted to UUID")
        return uuid.UUID(value)
    else:
        raise ValueError(f"Cannot convert {type(value)} to UUID")


def safe_uuid_filter(model_field, value: Union[str, uuid.UUID]):
    """
    Create a safe UUID filter for SQLAlchemy queries.
    
    Args:
        model_field: The SQLAlchemy model field (e.g., User.id)
        value: String UUID or UUID object
        
    Returns:
        SQLAlchemy filter condition
    """
    try:
        uuid_obj = ensure_uuid(value)
        return model_field == uuid_obj
    except (ValueError, TypeError):
        # Return a condition that will never match
        return model_field == None