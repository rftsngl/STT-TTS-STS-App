"""
SQLite database module for API key management with encryption.
"""
from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from cryptography.fernet import Fernet
from loguru import logger

from app.config import get_settings


class DatabaseError(Exception):
    """Base exception for database operations."""
    pass


class EncryptionError(Exception):
    """Exception for encryption/decryption errors."""
    pass


class Database:
    """SQLite database manager with connection pooling and encryption."""
    
    def __init__(self, db_path: str, encryption_key: Optional[str] = None):
        """
        Initialize database connection.
        
        Args:
            db_path: Path to SQLite database file
            encryption_key: Base64-encoded Fernet key for API key encryption
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize encryption
        if encryption_key:
            try:
                self._cipher = Fernet(encryption_key.encode())
            except Exception as exc:
                raise EncryptionError(f"Invalid encryption key: {exc}") from exc
        else:
            # Generate a new key if none provided
            self._cipher = Fernet(Fernet.generate_key())
            logger.warning("No encryption key provided, generated new key (not persisted)")
        
        self._local = threading.local()
        self._lock = threading.Lock()
        
        # Initialize database schema
        self._init_schema()
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local database connection."""
        if not hasattr(self._local, 'connection'):
            self._local.connection = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False,
                timeout=30.0
            )
            self._local.connection.row_factory = sqlite3.Row
        return self._local.connection
    
    @contextmanager
    def _transaction(self):
        """Context manager for database transactions."""
        conn = self._get_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    
    def _init_schema(self) -> None:
        """Initialize database schema."""
        with self._transaction() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS api_keys (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    provider VARCHAR(50) NOT NULL,
                    key_name VARCHAR(100) NOT NULL,
                    encrypted_key TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active BOOLEAN DEFAULT 1,
                    UNIQUE(provider, key_name)
                )
            """)
            
            # Create index for faster lookups
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_provider_active 
                ON api_keys(provider, is_active)
            """)
            
            logger.info("Database schema initialized at {}", self.db_path)
    
    def _encrypt_key(self, api_key: str) -> str:
        """Encrypt API key using Fernet."""
        try:
            encrypted = self._cipher.encrypt(api_key.encode())
            return encrypted.decode()
        except Exception as exc:
            raise EncryptionError(f"Failed to encrypt API key: {exc}") from exc
    
    def _decrypt_key(self, encrypted_key: str) -> str:
        """Decrypt API key using Fernet."""
        try:
            decrypted = self._cipher.decrypt(encrypted_key.encode())
            return decrypted.decode()
        except Exception as exc:
            raise EncryptionError(f"Failed to decrypt API key: {exc}") from exc
    
    def add_api_key(
        self,
        provider: str,
        key_name: str,
        api_key: str,
        is_active: bool = True
    ) -> int:
        """
        Add or update an API key.
        
        Args:
            provider: Provider name (e.g., 'elevenlabs', 'openai')
            key_name: Descriptive name for the key
            api_key: The actual API key to encrypt and store
            is_active: Whether the key is active
            
        Returns:
            ID of the inserted/updated key
        """
        encrypted = self._encrypt_key(api_key)
        
        with self._transaction() as conn:
            cursor = conn.execute("""
                INSERT INTO api_keys (provider, key_name, encrypted_key, is_active)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(provider, key_name) DO UPDATE SET
                    encrypted_key = excluded.encrypted_key,
                    updated_at = CURRENT_TIMESTAMP,
                    is_active = excluded.is_active
            """, (provider, key_name, encrypted, is_active))
            
            key_id = cursor.lastrowid
            logger.info("API key stored: provider={}, key_name={}, id={}", provider, key_name, key_id)
            return key_id
    
    def get_api_key(self, provider: str, key_name: Optional[str] = None) -> Optional[str]:
        """
        Get decrypted API key for a provider.
        
        Args:
            provider: Provider name
            key_name: Optional specific key name. If None, returns first active key.
            
        Returns:
            Decrypted API key or None if not found
        """
        conn = self._get_connection()
        
        if key_name:
            cursor = conn.execute("""
                SELECT encrypted_key FROM api_keys
                WHERE provider = ? AND key_name = ? AND is_active = 1
            """, (provider, key_name))
        else:
            cursor = conn.execute("""
                SELECT encrypted_key FROM api_keys
                WHERE provider = ? AND is_active = 1
                ORDER BY updated_at DESC
                LIMIT 1
            """, (provider,))
        
        row = cursor.fetchone()
        if row:
            return self._decrypt_key(row['encrypted_key'])
        return None
    
    def list_api_keys(self, provider: Optional[str] = None) -> List[Dict[str, object]]:
        """
        List all API keys (without decrypting them).
        
        Args:
            provider: Optional provider filter
            
        Returns:
            List of key metadata dictionaries
        """
        conn = self._get_connection()
        
        if provider:
            cursor = conn.execute("""
                SELECT id, provider, key_name, created_at, updated_at, is_active
                FROM api_keys
                WHERE provider = ?
                ORDER BY updated_at DESC
            """, (provider,))
        else:
            cursor = conn.execute("""
                SELECT id, provider, key_name, created_at, updated_at, is_active
                FROM api_keys
                ORDER BY provider, updated_at DESC
            """)
        
        return [dict(row) for row in cursor.fetchall()]
    
    def delete_api_key(self, provider: str, key_name: str) -> bool:
        """
        Delete an API key.
        
        Args:
            provider: Provider name
            key_name: Key name
            
        Returns:
            True if deleted, False if not found
        """
        with self._transaction() as conn:
            cursor = conn.execute("""
                DELETE FROM api_keys
                WHERE provider = ? AND key_name = ?
            """, (provider, key_name))
            
            deleted = cursor.rowcount > 0
            if deleted:
                logger.info("API key deleted: provider={}, key_name={}", provider, key_name)
            return deleted
    
    def deactivate_api_key(self, provider: str, key_name: str) -> bool:
        """
        Deactivate an API key without deleting it.
        
        Args:
            provider: Provider name
            key_name: Key name
            
        Returns:
            True if deactivated, False if not found
        """
        with self._transaction() as conn:
            cursor = conn.execute("""
                UPDATE api_keys
                SET is_active = 0, updated_at = CURRENT_TIMESTAMP
                WHERE provider = ? AND key_name = ?
            """, (provider, key_name))
            
            updated = cursor.rowcount > 0
            if updated:
                logger.info("API key deactivated: provider={}, key_name={}", provider, key_name)
            return updated
    
    def close(self) -> None:
        """Close database connection."""
        if hasattr(self._local, 'connection'):
            self._local.connection.close()
            delattr(self._local, 'connection')


# Global database instance
_db_instance: Optional[Database] = None
_db_lock = threading.Lock()


def get_database() -> Database:
    """Get or create global database instance."""
    global _db_instance

    if _db_instance is not None:
        return _db_instance

    with _db_lock:
        if _db_instance is not None:
            return _db_instance

        settings = get_settings()
        db_path = getattr(settings, 'database_path', './data/speech_app.db')
        encryption_key = getattr(settings, 'encryption_key', None)

        # Generate encryption key if not provided
        if not encryption_key:
            encryption_key = Fernet.generate_key().decode()
            logger.warning(
                "No encryption key configured. Generated temporary key. "
                "Set ENCRYPTION_KEY in .env to persist keys across restarts."
            )

        _db_instance = Database(db_path, encryption_key)
        return _db_instance

