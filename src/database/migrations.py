"""
Database migration utilities for schema changes.
"""
from typing import List, Callable
from sqlalchemy import text
from database.connection import get_db, engine


class Migration:
    """Represents a database migration."""
    
    def __init__(self, version: str, description: str, up_func: Callable, down_func: Callable = None):
        self.version = version
        self.description = description
        self.up_func = up_func
        self.down_func = down_func


class MigrationManager:
    """Manages database migrations."""
    
    def __init__(self):
        self.migrations: List[Migration] = []
        self._register_migrations()
    
    def _register_migrations(self):
        """Register all available migrations."""
        # Migration 001: Initial schema
        self.migrations.append(Migration(
            version="001",
            description="Initial database schema",
            up_func=self._migration_001_up,
            down_func=self._migration_001_down
        ))
    
    def _migration_001_up(self):
        """Create initial database schema."""
        from database.models import Base
        Base.metadata.create_all(bind=engine)
        print("Created initial database schema")
    
    def _migration_001_down(self):
        """Drop initial database schema."""
        from database.models import Base
        Base.metadata.drop_all(bind=engine)
        print("Dropped database schema")
    
    def _create_migration_table(self):
        """Create migration tracking table."""
        with get_db() as db:
            db.execute(text("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version VARCHAR(10) PRIMARY KEY,
                    description TEXT,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
    
    def _is_migration_applied(self, version: str) -> bool:
        """Check if a migration has been applied."""
        with get_db() as db:
            result = db.execute(text(
                "SELECT COUNT(*) FROM schema_migrations WHERE version = :version"
            ), {"version": version}).scalar()
            return result > 0
    
    def _mark_migration_applied(self, migration: Migration):
        """Mark a migration as applied."""
        with get_db() as db:
            db.execute(text("""
                INSERT INTO schema_migrations (version, description)
                VALUES (:version, :description)
            """), {
                "version": migration.version,
                "description": migration.description
            })
    
    def _mark_migration_reverted(self, version: str):
        """Mark a migration as reverted."""
        with get_db() as db:
            db.execute(text(
                "DELETE FROM schema_migrations WHERE version = :version"
            ), {"version": version})
    
    def migrate(self, target_version: str = None):
        """Apply migrations up to target version."""
        self._create_migration_table()
        
        for migration in self.migrations:
            if target_version and migration.version > target_version:
                break
                
            if not self._is_migration_applied(migration.version):
                print(f"Applying migration {migration.version}: {migration.description}")
                try:
                    migration.up_func()
                    self._mark_migration_applied(migration)
                    print(f"Migration {migration.version} applied successfully")
                except Exception as e:
                    print(f"Error applying migration {migration.version}: {e}")
                    raise
    
    def rollback(self, target_version: str):
        """Rollback migrations to target version."""
        self._create_migration_table()
        
        # Apply rollbacks in reverse order
        for migration in reversed(self.migrations):
            if migration.version <= target_version:
                break
                
            if self._is_migration_applied(migration.version):
                if migration.down_func:
                    print(f"Rolling back migration {migration.version}: {migration.description}")
                    try:
                        migration.down_func()
                        self._mark_migration_reverted(migration.version)
                        print(f"Migration {migration.version} rolled back successfully")
                    except Exception as e:
                        print(f"Error rolling back migration {migration.version}: {e}")
                        raise
                else:
                    print(f"No rollback function for migration {migration.version}")
    
    def status(self):
        """Show migration status."""
        self._create_migration_table()
        
        print("Migration Status:")
        print("-" * 50)
        
        for migration in self.migrations:
            status = "Applied" if self._is_migration_applied(migration.version) else "Pending"
            print(f"{migration.version}: {migration.description} [{status}]")


# Convenience functions
def migrate_database(target_version: str = None):
    """Apply database migrations."""
    manager = MigrationManager()
    manager.migrate(target_version)


def rollback_database(target_version: str):
    """Rollback database migrations."""
    manager = MigrationManager()
    manager.rollback(target_version)


def migration_status():
    """Show migration status."""
    manager = MigrationManager()
    manager.status()