"""
qBittorrent API integration module.

Handles connection and category management for processed torrents.
"""

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
        password: Optional[str] = None
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
        self.client: Optional[Client] = None
        self.connected = False
    
    def connect(self) -> bool:
        """
        Connect to qBittorrent WebUI.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            self.client = Client(
                host=self.url,
                username=self.username if self.username else None,
                password=self.password if self.password else None
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
