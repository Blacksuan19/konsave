"""
This module parses conf.yaml
"""
import os
import re

from konsave.consts import BIN_DIR, CONFIG_DIR, HOME, SHARE_DIR


def ends_with(grouped_regex, path) -> str:
    """Finds folder with name ending with the provided string.

    Args:
        grouped_regex: regex of the function
        path: path
    """
    occurence = re.search(grouped_regex, path).group()
    dirs = os.listdir(path[0 : path.find(occurence)])
    ends_with_text = re.search(grouped_regex, occurence).group(2)
    for directory in dirs:
        if directory.endswith(ends_with_text):
            return path.replace(occurence, directory)
    return occurence


def begins_with(grouped_regex, path) -> str:
    """Finds folder with name beginning with the provided string.

    Args:
        grouped_regex: regex of the function
        path: path
    """
    occurence = re.search(grouped_regex, path).group()
    dirs = os.listdir(path[0 : path.find(occurence)])
    ends_with_text = re.search(grouped_regex, occurence).group(2)
    for directory in dirs:
        if directory.startswith(ends_with_text):
            return path.replace(occurence, directory)
    return occurence


TOKEN_SYMBOL = "$"
tokens = {
    "keywords": {
        "dict": {
            "HOME": HOME,
            "CONFIG_DIR": CONFIG_DIR,
            "SHARE_DIR": SHARE_DIR,
            "BIN_DIR": BIN_DIR,
        }
    },
    "functions": {
        "raw_regex": r"\{\w+\=(?:\"|')\S+(?:\"|')\}",
        "grouped_regex": r"\{(\w+)\=(?:\"|')(\S+)(?:\"|')\}",
        "dict": {"ENDS_WITH": ends_with, "BEGINS_WITH": begins_with},
    },
}
