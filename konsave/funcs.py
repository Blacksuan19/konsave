"""
This module contains all the functions for konsave.
"""

import os
import re
import shutil
import traceback
from datetime import datetime
from pathlib import Path
from random import shuffle
from typing import Dict, List
from zipfile import ZipFile, is_zipfile

from konsave.consts import (
    CONFIG_FILE,
    EXPORT_EXTENSION,
    HOME,
    KONSAVE_DIR,
    PROFILES_DIR,
)
from konsave.parse import TOKEN_SYMBOL, parse_functions, parse_keywords, tokens

try:
    import yaml
except ModuleNotFoundError as error:
    raise ModuleNotFoundError(
        "Please install the module PyYAML using pip: \n" "pip install PyYAML"
    ) from error


def exception_handler(func):
    """Handles errors and prints nicely.

    Args:
        func: any function

    Returns:
        Returns function
    """

    def inner_func(*args, **kwargs):
        try:
            function = func(*args, **kwargs)
        except Exception as err:
            dateandtime = datetime.now().strftime("[%d/%m/%Y %H:%M:%S]")
            log_file = os.path.join(HOME, ".cache/konsave_log.txt")

            with open(log_file, "a") as file:
                file.write(dateandtime + "\n")
                traceback.print_exc(file=file)
                file.write("\n")

            print(
                f"Konsave: {err}\nPlease check the log at {log_file} for more details."
            )
            return None
        else:
            return function

    return inner_func


def mkdir(path):
    """Creates directory if it doesn't exist.

    Args:
        path: path to the new directory

    Returns:
        path: the same path
    """
    if not os.path.exists(path):
        os.makedirs(path)
    return path


def log(msg, *args, **kwargs):
    """Logs text.

    Args:
        msg: the text to be printed
        *args: any arguments for the function print()
        **kwargs: any keyword arguments for the function print()
    """
    print(f"Konsave: {msg}", *args, **kwargs)


@exception_handler
def copy(source, dest):
    """
    This function was created because shutil.copytree gives error if the destination folder
    exists and the argument "dirs_exist_ok" was introduced only after python 3.8.
    This restricts people with python 3.7 or less from using Konsave.
    This function will let people with python 3.7 or less use Konsave without any issues.
    It uses recursion to copy files and folders from "source" to "dest"

    Args:
        source: the source destination
        dest: the destination to copy the file/folder to
    """
    assert isinstance(source, str) and isinstance(dest, str), "Invalid path"
    assert source != dest, "Source and destination can't be same"
    assert os.path.exists(source), "Source path doesn't exist"

    if not os.path.exists(dest):
        os.mkdir(dest)

    for item in os.listdir(source):
        source_path = os.path.join(source, item)
        dest_path = os.path.join(dest, item)

        if os.path.isdir(source_path):
            copy(source_path, dest_path)
        else:
            if os.path.exists(dest_path):
                os.remove(dest_path)
            if os.path.exists(source_path):
                shutil.copy(source_path, dest)


@exception_handler
def read_konsave_config(config_file) -> dict:
    """Reads "conf.yaml" and parses it.

    Args:
        config_file: path to the config file
    """
    with open(config_file, "r") as text:
        konsave_config = yaml.load(text.read(), Loader=yaml.SafeLoader)
    parse_keywords(tokens, TOKEN_SYMBOL, konsave_config)
    parse_functions(tokens, TOKEN_SYMBOL, konsave_config)

    # in some cases conf.yaml may contain nothing in "entries"
    # yaml parses these as NoneType which are not iterable which throws an exception
    # we can convert all None-Entries into empty lists recursively so they are simply skipped in loops later on
    def convert_none_to_empty_list(data):
        if isinstance(data, list):
            data[:] = [convert_none_to_empty_list(i) for i in data]
        elif isinstance(data, dict):
            for k, v in data.items():
                data[k] = convert_none_to_empty_list(v)
        return [] if data is None else data

    return convert_none_to_empty_list(konsave_config)


@exception_handler
def list_profiles(profile_list, profile_count):
    """Lists all the created profiles.

    Args:
        profile_list: the list of all created profiles
        profile_count: number of profiles created
    """

    # assert
    assert os.path.exists(PROFILES_DIR) and profile_count != 0, "No profile found."

    # sort in alphabetical order
    profile_list.sort()

    # run
    print("Konsave profiles:")
    print("ID\tNAME")
    for i, item in enumerate(profile_list):
        print(f"{i + 1}\t{item}")


@exception_handler
def save_profile(name, profile_list, force=False):
    """Saves necessary config files in ~/.config/konsave/profiles/<name>.

    Args:
        name: name of the profile
        profile_list: the list of all created profiles
        force: force overwrite already created profile, optional
    """

    # assert
    assert name not in profile_list or force, "Profile with this name already exists"

    # run
    log("saving profile...")
    profile_dir = os.path.join(PROFILES_DIR, name)
    mkdir(profile_dir)

    konsave_config = read_konsave_config(CONFIG_FILE)["save"]

    for section in konsave_config:
        location = konsave_config[section]["location"]
        strip = konsave_config[section].get("strip", {})
        folder = os.path.join(profile_dir, section)
        mkdir(folder)
        for entry in konsave_config[section]["entries"]:
            source = os.path.join(location, entry)
            dest = os.path.join(folder, entry)
            if os.path.exists(source):
                if os.path.isdir(source):
                    copy(source, dest)
                else:
                    shutil.copy(source, dest)

                if entry in strip:
                    strip_content(Path(dest), strip[entry])

    shutil.copy(CONFIG_FILE, profile_dir)

    log("Profile saved successfully!")


def strip_content(file_path: Path, strip_args: Dict[str, List[str]]) -> None:
    """
    strip entire groups or individual keys from all groups in a file
    group names are in the plasma config format
    https://userbase.kde.org/KDE_System_Administration/Configuration_Files

    Args:
        file_path: path to the file
        strip_args: dict with keys "groups" and "keys"
    """
    groups = strip_args.get("groups", [])
    keys = strip_args.get("keys", [])
    file_content = file_path.read_text().splitlines()
    placeholder = "# stripped by konsave"

    def strip_groups(file_content: List[str], groups: List[str]) -> List[str]:
        for group in groups:
            group_lines = [line for line in file_content if f"[{group}]" in line]
            if group_lines:
                for group_line in group_lines:
                    group_idx = file_content.index(group_line)

                    # remove group header line
                    file_content[group_idx] = placeholder

                    # remove lines from group_index until next section start
                    for line in range(group_idx, len(file_content)):
                        exp = re.compile(r"^\[.*\].*")
                        if exp.match(file_content[line]):
                            break
                        file_content[line] = placeholder

        return file_content

    def strip_keys(file_content: List[str], keys: List[str]) -> List[str]:
        for key in keys:
            key_lines = [line for line in file_content if f"{key}=" in line]
            if key_lines:
                for key_line in key_lines:
                    key_idx = file_content.index(key_line)
                    file_content[key_idx] = placeholder

        return file_content

    file_content = strip_groups(file_content, groups)
    file_content = strip_keys(file_content, keys)

    # remove empty lines
    file_content = list(filter(lambda x: x != placeholder, file_content))

    file_path.write_text("\n".join(file_content))


@exception_handler
def apply_profile(profile_name, profile_list, profile_count):
    """Applies profile of the given id.

    Args:
        profile_name: name of the profile to be applied
        profile_list: the list of all created profiles
        profile_count: number of profiles created
    """

    # assert
    assert profile_count != 0, "No profile saved yet."
    assert profile_name in profile_list, "Profile not found :("

    # run
    profile_dir = os.path.join(PROFILES_DIR, profile_name)

    log("copying files...")

    config_location = os.path.join(profile_dir, "conf.yaml")
    profile_config = read_konsave_config(config_location)["save"]
    for name in profile_config:
        location = os.path.join(profile_dir, name)
        copy(location, profile_config[name]["location"])

    log(
        "Profile applied successfully! Please log-out and log-in to see the changes completely!"
    )


@exception_handler
def remove_profile(profile_name, profile_list, profile_count):
    """Removes the specified profile.

    Args:
        profile_name: name of the profile to be removed
        profile_list: the list of all created profiles
        profile_count: number of profiles created
    """

    # assert
    assert profile_count != 0, "No profile saved yet."
    assert profile_name in profile_list, "Profile not found."

    # run
    log("removing profile...")
    shutil.rmtree(os.path.join(PROFILES_DIR, profile_name))
    log("removed profile successfully")


@exception_handler
def export(profile_name, profile_list, profile_count, archive_dir, archive_name, force):
    """It will export the specified profile as a ".knsv" to the specified directory.
       If there is no specified directory, the directory is set to the current working directory.

    Args:
        profile_name: name of the profile to be exported
        profile_list: the list of all created profiles
        profile_count: number of profiles created
        directory: output directory for the export
        force: force the overwrite of existing export file
        name: the name of the resulting archive
    """

    # assert
    assert profile_count != 0, "No profile saved yet."
    assert profile_name in profile_list, "Profile not found."

    # run
    profile_dir = os.path.join(PROFILES_DIR, profile_name)

    if archive_name:
        profile_name = archive_name

    if archive_dir:
        export_path = os.path.join(archive_dir, profile_name)
    else:
        export_path = os.path.join(os.getcwd(), profile_name)

    # Only continue if export_path, export_path.ksnv and export_path.zip don't exist
    # Appends date and time to create a unique file name
    if not force:
        while True:
            paths = [f"{export_path}", f"{export_path}.knsv", f"{export_path}.zip"]
            if any([os.path.exists(path) for path in paths]):
                time = "f{:%d-%m-%Y:%H-%M-%S}".format(datetime.now())
                export_path = f"{export_path}_{time}"
            else:
                break

    # compressing the files as zip
    log("Exporting profile. It might take a minute or two...")

    profile_config_file = os.path.join(profile_dir, "conf.yaml")
    konsave_config = read_konsave_config(profile_config_file)

    export_path_save = mkdir(os.path.join(export_path, "save"))
    for name in konsave_config["save"]:
        location = os.path.join(profile_dir, name)
        log(f'Exporting "{name}"...')
        copy(location, os.path.join(export_path_save, name))

    konsave_config_export = konsave_config["export"]
    export_path_export = mkdir(os.path.join(export_path, "export"))
    for name in konsave_config_export:
        location = konsave_config_export[name]["location"]
        path = mkdir(os.path.join(export_path_export, name))
        for entry in konsave_config_export[name]["entries"]:
            source = os.path.join(location, entry)
            dest = os.path.join(path, entry)
            log(f'Exporting "{entry}"...')
            if os.path.exists(source):
                if os.path.isdir(source):
                    copy(source, dest)
                else:
                    shutil.copy(source, dest)

    shutil.copy(CONFIG_FILE, export_path)

    log("Creating archive")
    shutil.make_archive(export_path, "zip", export_path)

    shutil.rmtree(export_path)
    shutil.move(export_path + ".zip", export_path + EXPORT_EXTENSION)

    log(f"Successfully exported to {export_path}{EXPORT_EXTENSION}")


@exception_handler
def import_profile(path):
    """This will import an exported profile.

    Args:
        path: path of the `.knsv` file
    """

    # assert
    assert (
        is_zipfile(path) and path[-5:] == EXPORT_EXTENSION
    ), "Not a valid konsave file"
    item = os.path.basename(path)[:-5]
    assert not os.path.exists(
        os.path.join(PROFILES_DIR, item)
    ), "A profile with this name already exists"

    # run
    log("Importing profile. It might take a minute or two...")

    item = os.path.basename(path).replace(EXPORT_EXTENSION, "")

    temp_path = os.path.join(KONSAVE_DIR, "temp", item)

    with ZipFile(path, "r") as zip_file:
        zip_file.extractall(temp_path)

    config_file_location = os.path.join(temp_path, "conf.yaml")
    konsave_config = read_konsave_config(config_file_location)

    profile_dir = os.path.join(PROFILES_DIR, item)
    copy(os.path.join(temp_path, "save"), profile_dir)
    shutil.copy(os.path.join(temp_path, "conf.yaml"), profile_dir)

    for section in konsave_config["export"]:
        location = konsave_config["export"][section]["location"]
        path = os.path.join(temp_path, "export", section)
        mkdir(path)
        for entry in konsave_config["export"][section]["entries"]:
            source = os.path.join(path, entry)
            dest = os.path.join(location, entry)
            log(f'Importing "{entry}"...')
            if os.path.exists(source):
                if os.path.isdir(source):
                    copy(source, dest)
                else:
                    shutil.copy(source, dest)

    shutil.rmtree(temp_path)

    log("Profile successfully imported!")


@exception_handler
def wipe():
    """Wipes all profiles."""
    confirm = input('This will wipe all your profiles. Enter "WIPE" To continue: ')
    if confirm == "WIPE":
        shutil.rmtree(PROFILES_DIR)
        log("Removed all profiles!")
    else:
        log("Aborting...")
