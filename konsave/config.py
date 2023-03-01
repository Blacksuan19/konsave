import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Union

import yaml

from konsave.parse import TOKEN_SYMBOL, tokens


@dataclass
class StripEntry:
    """An entry in the strip list"""

    file_name: str
    keys: List[str]
    groups: List[str]

    @classmethod
    def from_dict(cls, name: str, data: dict):
        """Create a StripEntry from a dict"""
        return cls(file_name=name, groups=data["groups"], keys=data["keys"])

    def to_dict(self):
        """Convert a StripEntry to a dict (json representation)"""
        return {self.file_name: {"groups": self.groups, "keys": self.keys}}


@dataclass
class ConfEntry:
    """An entry in the config file inside a section"""

    name: str
    location: str
    entries: List[str]
    strips: List[StripEntry]

    def __post_init__(self):
        # set strips as class attributes
        for strip in self.strips:
            setattr(self, strip.file_name, strip)

        # keep a copy of the original location for to_dict()
        self.localtion_original = self.location

        self.parse_keywords()
        self.parse_functions()

    def parse_keywords(self):
        """
        Replace location keywords with values in conf.yaml. For example, it will replace,
        $HOME with /home/username/
        """
        # expand vriables in location
        for key, value in tokens["keywords"]["dict"].items():
            word = TOKEN_SYMBOL + key
            if word in self.location:
                self.location = self.location.replace(word, value)

    def parse_functions(self):
        """
        Replace location functions with values in conf.yaml. For example, it will replace,
        ${ENDS_WITH='text'} with a folder whose name ends with "text"
        """
        functions = tokens["functions"]
        raw_regex = f"\\{TOKEN_SYMBOL}{functions['raw_regex']}"
        grouped_regex = f"\\{TOKEN_SYMBOL}{functions['grouped_regex']}"

        matches = re.findall(raw_regex, self.location)
        for match in matches:
            func = re.search(grouped_regex, match).group(1)
            if func in functions["dict"]:
                self.location = functions["dict"][func](grouped_regex, self.location)

    @classmethod
    def from_dict(cls, name: str, data: dict):
        """Create a ConfEntry from a dict"""
        subs = []
        if "strip" in data:
            sub_keys = list(data["strip"].keys())
            subs = [
                StripEntry.from_dict(name=sub_keys[i], data=data["strip"][sub_keys[i]])
                for i in range(len(sub_keys))
            ]

        return cls(
            name=name,
            location=data["location"],
            entries=data["entries"],
            strips=subs,
        )

    def to_dict(self):
        """Convert a ConfEntry to a dict (json representation)"""
        to_dict = {
            self.name: {
                "location": self.localtion_original,
                "entries": self.entries,
            }
        }

        strips = {}
        for strip in self.strips:
            strips.update(strip.to_dict())

        # remove empty strips
        if not strips:
            return to_dict

        to_dict[self.name]["strip"] = strips

        return to_dict


@dataclass
class Section:
    """A top level section in config (only save and export)"""

    name: str
    entries: List[ConfEntry]

    def __post_init__(self):
        """Set each entry as a class attribute"""
        for entry in self.entries:
            setattr(self, entry.name, entry)

    @classmethod
    def from_dict(cls, name: str, data: dict):
        """Create a section from a dict"""
        sub_keys = list(data.keys())
        subs = [
            ConfEntry.from_dict(name=sub_keys[i], data=data[sub_keys[i]])
            for i in range(len(sub_keys))
        ]
        return cls(name=name, entries=subs)

    def to_dict(self):
        """Convert a Section to a dict (json representation)"""
        entries = {}
        for entry in self.entries:
            entries.update(entry.to_dict())
        return {self.name: entries}


class Config:
    """The config file"""

    def __init__(self, config_file: Path):
        self.config_file = config_file
        data = yaml.safe_load(self.config_file.read_text())

        # in some cases conf.yaml may contain nothing in "entries"
        # yaml parses these as NoneType which are not iterable which throws an exception
        # we can convert all None-Entries into empty lists recursively so they are simply skipped in loops later on
        def convert_none_to_empty_list(data: Union[List, Dict, None]):
            if isinstance(data, list):
                data[:] = [convert_none_to_empty_list(i) for i in data]
            elif isinstance(data, dict):
                for k, v in data.items():
                    data[k] = convert_none_to_empty_list(v)
            return [] if data is None else data

        data = convert_none_to_empty_list(data)
        keys = list(data.keys())
        self.sections = {
            keys[i]: Section.from_dict(name=keys[i], data=data[keys[i]])
            for i in range(len(keys))
        }
        self.save = self.sections.get("save")
        self.export = self.sections.get("export")

    def __repr__(self) -> str:
        return f"Config({self.__dict__})"

    def __str__(self) -> str:
        return self.__repr__()

    def to_dict(self):
        """Convert a Config to a dict (json representation)"""
        return {
            **self.save.to_dict(),
            **self.export.to_dict(),
        }


# testing code
if __name__ == "__main__":
    conf_file = Path("konsave/conf_kde.yaml")
    data = yaml.safe_load(conf_file.read_text())

    print(data == Config(config_file=conf_file).to_dict())
