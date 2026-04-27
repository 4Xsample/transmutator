"""
Main entry point for Transmutator V2.

This is a placeholder for Phase 1 (TUI implementation).
For now, it provides basic validation and testing functionality.
"""

import sys
from pathlib import Path
from .config import Config
from .doctor import render_diagnostics
from .file_detector import FileDetector
from .qbittorrent import QBittorrentClient


def validate_setup():
    """Validate that the system is properly configured."""
    print("🔍 Validating Transmutator V2 setup...\n")
    
    # Check paths
    print("📁 Checking paths:")
    path_results = Config.validate_paths()
    
    for key, exists in path_results.items():
        status = "✅" if exists else "❌"
        print(f"  {status} {key}: {exists}")
    
    # Check tools
    print("\n🛠️  Checking tools:")
    if path_results.get("handbrake_available"):
        print("  ✅ HandBrakeCLI is available")
    else:
        print("  ❌ HandBrakeCLI not found")
    
    if path_results.get("ffmpeg_available"):
        print("  ✅ FFmpeg is available")
    else:
        print("  ❌ FFmpeg not found")
    
    # Test qBittorrent connection
    print("\n🌐 Testing qBittorrent connection:")
    try:
        qbt = QBittorrentClient()
        if qbt.connect():
            print("  ✅ Connected to qBittorrent")
            version = qbt.client.app_version()
            print(f"     Version: {version}")
        else:
            print("  ⚠️  Could not connect to qBittorrent (this is OK if not configured)")
    except ImportError:
        print("  ⚠️  qbittorrent-api not installed")
    except Exception as e:
        print(f"  ⚠️  Connection test failed: {str(e)}")
    
    print("\n" + "="*50)
    print("Setup validation complete!")
    print("="*50)


def test_file_detection():
    """Test file detection on TMP staging directory."""
    print("\n🔍 Testing file detection...\n")
    
    if not Config.TMP_STAGING.exists():
        print(f"⚠️  TMP staging directory does not exist: {Config.TMP_STAGING}")
        print("   Create it or update Config.TMP_STAGING")
        return
    
    files_by_category = FileDetector.scan_all_categories()
    
    if not files_by_category:
        print("📭 No media files found in TMP staging directory")
        return
    
    total_files = sum(len(files) for files in files_by_category.values())
    print(f"📊 Found {total_files} media file(s) across {len(files_by_category)} category/categories:\n")
    
    for category, files in files_by_category.items():
        print(f"  📁 {category}: {len(files)} file(s)")
        for media_file in files[:5]:  # Show first 5
            print(f"     - {media_file.path.name} ({media_file.media_type.value})")
        if len(files) > 5:
            print(f"     ... and {len(files) - 5} more")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ("--tui", "-t"):
        from .app import run_app
        run_app()
    elif len(sys.argv) > 1 and sys.argv[1] in ("doctor", "--doctor"):
        print(render_diagnostics())
    elif len(sys.argv) > 1 and sys.argv[1] in ("web", "--web"):
        from .web_server import run_server
        run_server()
    elif len(sys.argv) > 1 and sys.argv[1] == "test":
        test_file_detection()
    else:
        validate_setup()
