"""
qBittorrent API integration module.

Handles connection, torrent lookup and category changes for processed torrents.
"""

from pathlib import Path
from typing import Optional, List, Dict, Any
import logging

try:
    from qbittorrentapi import Client, LoginFailed
except ImportError:
    Client = None
    LoginFailed = Exception

from .config import Config

logger = logging.getLogger(__name__)


class QBittorrentClient:
    """Wrapper for qBittorrent API client."""
    
    def __init__(
        self,
        url: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        api_key: Optional[str] = None,
        api_key_header: Optional[str] = None,
    ):
        """
        Initialize qBittorrent client.
        
        Args:
            url: qBittorrent WebUI URL (defaults to Config.QBITTORRENT_URL)
            username: Optional username for authentication
            password: Optional password for authentication
        """
        if Client is None:
            raise ImportError(
                "qbittorrent-api is not installed. "
                "Install it with: pip install qbittorrent-api"
            )
        
        self.url = url or Config.QBITTORRENT_URL
        self.username = username or Config.QBITTORRENT_USERNAME
        self.password = password or Config.QBITTORRENT_PASSWORD
        self.api_key = api_key or Config.QBITTORRENT_API_KEY
        self.api_key_header = api_key_header or Config.QBITTORRENT_API_KEY_HEADER
        self.client: Optional[Client] = None
        self.connected = False
    
    def connect(self) -> bool:
        """
        Connect to qBittorrent WebUI.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            extra_headers = None
            if self.api_key:
                extra_headers = {self.api_key_header: self.api_key}
            self.client = Client(
                host=self.url,
                username=self.username if self.username else None,
                password=self.password if self.password else None,
                EXTRA_HEADERS=extra_headers,
            )
            
            # Test connection
            self.client.app_version()
            self.connected = True
            logger.info(f"Connected to qBittorrent at {self.url}")
            return True
        
        except LoginFailed:
            logger.error("qBittorrent authentication failed")
            self.connected = False
            return False
        except Exception as e:
            logger.error(f"Failed to connect to qBittorrent: {str(e)}")
            self.connected = False
            return False
    
    def is_connected(self) -> bool:
        """Check if client is connected."""
        if not self.connected or self.client is None:
            return False
        
        try:
            self.client.app_version()
            return True
        except:
            self.connected = False
            return False
    
    def ensure_connected(self) -> bool:
        """Ensure client is connected, reconnect if needed."""
        if not self.is_connected():
            return self.connect()
        return True

    def test_connection(self) -> Dict[str, Any]:
        """Return diagnostic information for the current qBittorrent connection."""
        if not self.connect():
            return {
                "success": False,
                "url": self.url,
                "error": "Unable to connect to qBittorrent",
            }
        try:
            version = self.client.app_version()
            api_version = self.client.app_web_api_version()
            categories = self.client.torrents_categories()
            return {
                "success": True,
                "url": self.url,
                "version": version,
                "api_version": api_version,
                "categories_count": len(categories),
                "categories": list(categories.keys())[:20],
                "auth_mode": "api_key" if self.api_key else "username_password_or_bypass",
            }
        except Exception as e:
            return {
                "success": False,
                "url": self.url,
                "error": str(e),
            }
    
    def set_category(
        self,
        torrent_hash: str,
        category: str
    ) -> bool:
        """
        Set category for a torrent.
        
        Args:
            torrent_hash: Torrent hash (info_hash)
            category: Category name to set
        
        Returns:
            True if successful, False otherwise
        """
        if not self.ensure_connected():
            return False
        
        try:
            self.client.torrents_set_category(
                torrent_hashes=torrent_hash,
                category=category
            )
            logger.info(f"Set category '{category}' for torrent {torrent_hash[:8]}...")
            return True
        except Exception as e:
            logger.error(f"Failed to set category: {str(e)}")
            return False

    def find_torrent_for_media(
        self,
        media_name: str,
        category: str,
    ) -> Optional[Dict[str, Any]]:
        """Find the best matching torrent for a processed media file."""
        if not self.ensure_connected():
            return None

        source_category = Config.TORRENT_CATEGORIES.get(category, category)
        media_basename = Path(media_name).name.lower()
        media_stem = Path(media_name).stem.lower()

        try:
            torrents = self.client.torrents_info(
                category=source_category,
                include_files=True,
            )
        except Exception as e:
            logger.error(f"Failed to query torrents for category {source_category}: {e}")
            return None

        candidates: List[Dict[str, Any]] = []
        for torrent in torrents:
            t_hash = str(getattr(torrent, "hash", "") or torrent.get("hash", ""))
            t_name = str(getattr(torrent, "name", "") or torrent.get("name", ""))
            t_category = str(getattr(torrent, "category", "") or torrent.get("category", ""))
            t_state = str(getattr(torrent, "state", "") or torrent.get("state", ""))
            content_path = str(
                getattr(torrent, "content_path", "") or torrent.get("content_path", "")
            )
            score = 0

            if media_basename == t_name.lower():
                score += 5
            if media_stem and media_stem in t_name.lower():
                score += 3
            if media_stem and media_stem in content_path.lower():
                score += 2

            files = getattr(torrent, "files", None) or torrent.get("files", [])
            for file_info in files:
                file_name = str(getattr(file_info, "name", "") or file_info.get("name", "")).lower()
                if file_name.endswith(media_basename):
                    score += 10
                    break
                if media_stem and media_stem in file_name:
                    score += 6

            if score > 0 and t_hash:
                candidates.append(
                    {
                        "hash": t_hash,
                        "name": t_name,
                        "category": t_category,
                        "state": t_state,
                        "score": score,
                    }
                )

        if not candidates:
            return None

        candidates.sort(key=lambda item: item["score"], reverse=True)
        return candidates[0]

    def mark_processed_media(
        self,
        media_name: str,
        category: str,
        target_category: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Find the torrent for a media file and move it to the processed category."""
        target = target_category or Config.PROCESSED_CATEGORY
        match = self.find_torrent_for_media(media_name=media_name, category=category)
        if match is None:
            return {
                "success": False,
                "media_name": media_name,
                "source_category": Config.TORRENT_CATEGORIES.get(category, category),
                "target_category": target,
                "error": "No matching torrent found",
            }

        changed = self.set_category(match["hash"], target)
        return {
            "success": changed,
            "media_name": media_name,
            "torrent_name": match["name"],
            "torrent_hash": match["hash"],
            "source_category": match["category"],
            "target_category": target,
            "state": match["state"],
            "error": "" if changed else "Failed to change torrent category",
        }
    
    def set_processed_category(self, torrent_hash: str) -> bool:
        """
        Set the 'processat' category for a processed torrent.
        
        Args:
            torrent_hash: Torrent hash
        
        Returns:
            True if successful, False otherwise
        """
        return self.set_category(torrent_hash, Config.PROCESSED_CATEGORY)
    
    def find_torrent_by_path(
        self,
        file_path: str
    ) -> Optional[Dict[str, Any]]:
        """
        Find a torrent by file path.
        
        Args:
            file_path: Path to search for
        
        Returns:
            Torrent info dict or None if not found
        """
        if not self.ensure_connected():
            return None
        
        try:
            torrents = self.client.torrents_info()
            
            for torrent in torrents:
                # Check if file path matches any content path
                for content_file in torrent.get('files', []):
                    if file_path in content_file.get('name', ''):
                        return {
                            'hash': torrent.get('hash'),
                            'name': torrent.get('name'),
                            'category': torrent.get('category', ''),
                            'state': torrent.get('state', '')
                        }
            
            return None
        except Exception as e:
            logger.error(f"Failed to find torrent: {str(e)}")
            return None
    
    def get_torrents_by_category(
        self,
        category: str
    ) -> List[Dict[str, Any]]:
        """
        Get all torrents in a specific category.
        
        Args:
            category: Category name
        
        Returns:
            List of torrent info dicts
        """
        if not self.ensure_connected():
            return []
        
        try:
            torrents = self.client.torrents_info(category=category)
            return [
                {
                    'hash': t.get('hash'),
                    'name': t.get('name'),
                    'category': t.get('category', ''),
                    'state': t.get('state', ''),
                    'ratio': t.get('ratio', 0.0)
                }
                for t in torrents
            ]
        except Exception as e:
            logger.error(f"Failed to get torrents by category: {str(e)}")
            return []
