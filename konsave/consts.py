"""
This module contains all the variables for konsave
"""
import os
from pathlib import Path

from konsave import __version__

HOME: Path = Path.home()
CONFIG_DIR = HOME / ".config"
SHARE_DIR = HOME / ".local/share"
BIN_DIR = HOME / ".local/bin"
KONSAVE_DIR = CONFIG_DIR / "konsave"
PROFILES_DIR = KONSAVE_DIR / "profiles"
CONFIG_FILE = KONSAVE_DIR / "conf.yaml"

EXPORT_EXTENSION = ".knsv"

# Create PROFILES_DIR if it doesn't exist
if not PROFILES_DIR.exists():
    os.makedirs(PROFILES_DIR)

list_of_profiles = [x.name for x in PROFILES_DIR.iterdir() if x.is_dir()]
length_of_lop = len(list_of_profiles)

VERSION = __version__
