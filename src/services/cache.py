import os
import json
import hashlib
import time
import gzip
import pickle
from pathlib import Path
from functools import wraps, lru_cache
from typing import Any, Callable, Dict, Optional, TypeVar, Union, Type, List, Tuple
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

T = TypeVar('T')
CACHE_VERSION = "1.0"

class CacheMissError(Exception):
    """Raised when a cache key is not found."""
    pass

class CacheExpiredError(Exception):
    """Raised when a cached item has expired."""
    pass

class Cache:
    """A hybrid cache with both in-memory and persistent storage."""
    
    def __init__(self, cache_dir: str = ".cache", ttl: int = 86400, max_size_mb: int = 100):
        """Initialize the cache.
        
        Args:
            cache_dir: Directory to store cached items
            ttl: Time-to-live in seconds (default: 1 day)
            max_size_mb: Maximum cache size in MB (default: 100MB)
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl = ttl
        self.max_size = max_size_mb * 1024 * 1024  # Convert MB to bytes
        self._ensure_cleanup()
    
    def _get_key_path(self, key: str) -> Path:
        """Get the filesystem path for a cache key."""
        key_hash = hashlib.md5(key.encode('utf-8')).hexdigest()
        return self.cache_dir / f"{key_hash}.pkl.gz"
    
    def _get_metadata_path(self) -> Path:
        """Get the path to the metadata file."""
        return self.cache_dir / "metadata.json"
    
    def _load_metadata(self) -> Dict[str, Dict[str, Any]]:
        """Load cache metadata."""
        metadata_path = self._get_metadata_path()
        if not metadata_path.exists():
            return {}
        try:
            with open(metadata_path, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to load cache metadata: {e}")
            return {}
    
    def _save_metadata(self, metadata: Dict[str, Dict[str, Any]]) -> None:
        """Save cache metadata."""
        metadata_path = self._get_metadata_path()
        try:
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
        except IOError as e:
            logger.error(f"Failed to save cache metadata: {e}")
    
    def _update_metadata(self, key: str, size: int) -> None:
        """Update metadata for a cache key."""
        metadata = self._load_metadata()
        metadata[key] = {
            'size': size,
            'last_accessed': time.time(),
            'created_at': metadata.get(key, {}).get('created_at', time.time()),
            'version': CACHE_VERSION
        }
        self._save_metadata(metadata)
    
    def _cleanup(self) -> None:
        """Clean up expired and least recently used items."""
        metadata = self._load_metadata()
        if not metadata:
            return
        
        # Remove expired items
        now = time.time()
        total_size = 0
        items = []
        
        for key, meta in list(metadata.items()):
            key_path = self._get_key_path(key)
            
            # Remove if file is missing or metadata is invalid
            if not key_path.exists() or 'size' not in meta:
                metadata.pop(key, None)
                continue
                
            # Check if expired
            if now - meta.get('created_at', 0) > self.ttl:
                try:
                    key_path.unlink()
                    metadata.pop(key, None)
                except OSError as e:
                    logger.warning(f"Failed to remove expired cache item {key}: {e}")
                continue
                
            # Add to cleanup list
            size = meta['size']
            total_size += size
            items.append((key, meta, size))
        
        # Remove LRU items if over size limit
        if total_size > self.max_size:
            # Sort by last accessed time (oldest first)
            items.sort(key=lambda x: x[1].get('last_accessed', 0))
            
            for key, meta, size in items:
                if total_size <= self.max_size * 0.9:  # Stop at 90% of max size
                    break
                    
                try:
                    key_path = self._get_key_path(key)
                    key_path.unlink()
                    metadata.pop(key, None)
                    total_size -= size
                except OSError as e:
                    logger.warning(f"Failed to remove LRU cache item {key}: {e}")
        
        self._save_metadata(metadata)
    
    def _ensure_cleanup(self) -> None:
        """Ensure cleanup runs periodically."""
        self._cleanup()
        # Schedule next cleanup in 1 hour
        import threading
        timer = threading.Timer(3600, self._ensure_cleanup)
        timer.daemon = True
        timer.start()
    
    def set(self, key: str, value: Any) -> None:
        """Set a value in the cache."""
        key_path = self._get_key_path(key)
        
        try:
            # Serialize and compress the value
            serialized = pickle.dumps(value)
            compressed = gzip.compress(serialized)
            
            # Write to file atomically
            temp_path = key_path.with_suffix('.tmp')
            with open(temp_path, 'wb') as f:
                f.write(compressed)
            temp_path.replace(key_path)  # Atomic rename
            
            # Update metadata
            self._update_metadata(key, len(compressed))
            
        except (IOError, pickle.PickleError, OSError) as e:
            logger.error(f"Failed to cache item {key}: {e}")
            try:
                key_path.unlink(missing_ok=True)
            except OSError:
                pass
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a value from the cache."""
        key_path = self._get_key_path(key)
        
        try:
            # Check if file exists and is not expired
            if not key_path.exists():
                raise CacheMissError(f"Cache miss for key: {key}")
                
            # Load metadata
            metadata = self._load_metadata().get(key, {})
            if time.time() - metadata.get('created_at', 0) > self.ttl:
                key_path.unlink()
                raise CacheExpiredError(f"Cache expired for key: {key}")
            
            # Read and decompress the value
            with gzip.open(key_path, 'rb') as f:
                compressed = f.read()
            serialized = gzip.decompress(compressed)
            value = pickle.loads(serialized)
            
            # Update last accessed time
            self._update_metadata(key, len(compressed))
            
            return value
            
        except (IOError, gzip.BadGzipFile, pickle.UnpicklingError) as e:
            logger.warning(f"Failed to load cached item {key}: {e}")
            try:
                key_path.unlink(missing_ok=True)
            except OSError:
                pass
            if default is not None:
                return default
            raise CacheMissError(f"Cache error for key {key}: {e}")
    
    def delete(self, key: str) -> None:
        """Delete a key from the cache."""
        key_path = self._get_key_path(key)
        try:
            key_path.unlink(missing_ok=True)
            
            # Update metadata
            metadata = self._load_metadata()
            if key in metadata:
                metadata.pop(key)
                self._save_metadata(metadata)
                
        except OSError as e:
            logger.warning(f"Failed to delete cache item {key}: {e}")
    
    def clear(self) -> None:
        """Clear the entire cache."""
        try:
            # Remove all cache files
            for path in self.cache_dir.glob("*.pkl.gz"):
                try:
                    path.unlink()
                except OSError as e:
                    logger.warning(f"Failed to delete cache file {path}: {e}")
            
            # Clear metadata
            metadata_path = self._get_metadata_path()
            if metadata_path.exists():
                metadata_path.unlink()
                
        except OSError as e:
            logger.error(f"Failed to clear cache: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        metadata = self._load_metadata()
        total_size = sum(meta.get('size', 0) for meta in metadata.values())
        
        return {
            'total_items': len(metadata),
            'total_size_mb': total_size / (1024 * 1024),
            'max_size_mb': self.max_size / (1024 * 1024),
            'hit_rate': 0.0,  # Would need request tracking for this
            'oldest_item': min((meta.get('created_at', 0) for meta in metadata.values()), default=None),
            'newest_item': max((meta.get('created_at', 0) for meta in metadata.values()), default=None)
        }

# Global cache instance
cache = Cache()

def cached(ttl: int = 3600, maxsize: int = 128, key_prefix: str = ""):
    """Decorator for caching function results.
    
    Args:
        ttl: Time-to-live in seconds
        maxsize: Maximum number of items to cache in memory
        key_prefix: Optional prefix for cache keys
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        # Use LRU cache for in-memory caching
        func_cached = lru_cache(maxsize=maxsize)(func)
        
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            # Generate a cache key
            cache_key = f"{key_prefix}:{func.__module__}:{func.__name__}:{args}:{frozenset(kwargs.items())}"
            
            try:
                # Try to get from in-memory cache first
                return func_cached(*args, **kwargs)
                
            except KeyError:
                try:
                    # Fall back to disk cache
                    return cache.get(cache_key)
                    
                except (CacheMissError, CacheExpiredError):
                    # Compute and cache the result
                    result = func(*args, **kwargs)
                    
                    # Update caches
                    try:
                        cache.set(cache_key, result)
                        # Also update the in-memory cache
                        func_cached.cache_clear()  # Clear to force update
                        _ = func_cached(*args, **kwargs)
                    except Exception as e:
                        logger.warning(f"Failed to update cache: {e}")
                    
                    return result
                
        return wrapper
    
    return decorator

def async_cached(ttl: int = 3600, maxsize: int = 128, key_prefix: str = ""):
    """Decorator for caching async function results."""
    def decorator(func):
        # Use LRU cache for in-memory caching
        func_cached = lru_cache(maxsize=maxsize)(lambda *a, **kw: None)
        
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate a cache key
            cache_key = f"{key_prefix}:{func.__module__}:{func.__name__}:{args}:{frozenset(kwargs.items())}"
            
            try:
                # Try to get from in-memory cache first
                cached_result = func_cached(*args, **kwargs)
                if cached_result is not None:
                    return cached_result
                    
            except KeyError:
                pass
                
            try:
                # Fall back to disk cache
                return cache.get(cache_key)
                
            except (CacheMissError, CacheExpiredError):
                # Compute and cache the result
                result = await func(*args, **kwargs)
                
                # Update caches
                try:
                    cache.set(cache_key, result)
                    # Also update the in-memory cache
                    func_cached.cache_clear()
                    _ = func_cached(*args, **kwargs)
                except Exception as e:
                    logger.warning(f"Failed to update cache: {e}")
                
                return result
            
        return wrapper
    
    return decorator
