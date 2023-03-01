"""
This module contains all the functions for konsave.
"""
import re
import shutil
import traceback
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional
from zipfile import ZipFile, is_zipfile

from config import Config, StripEntry
from consts import (
    CONFIG_FILE,
    EXPORT_EXTENSION,
    HOME,
    KONSAVE_DIR,
    PROFILES_DIR,
    length_of_lop,
    list_of_profiles,
)
from typer import Option, Typer

app = Typer(
    no_args_is_help=True,
    help="Konsave is a tool to save and restore Linux desktop settings with support for KDE Plasma out of the box.",
    epilog="Please report bugs at https://www.github.com/prayag2/konsave",
)


def exception_handler(func: Callable):
    """Handles errors and prints nicely."""

    def inner_func(*args, **kwargs) -> Callable:
        try:
            function: Callable = func(*args, **kwargs)
        except Exception as err:
            dateandtime = datetime.now().strftime("[%d/%m/%Y %H:%M:%S]")
            log_file = HOME / ".cache/konsave_log.txt"
            log_str = f"{dateandtime}\n{traceback.format_exc()}\n"
            log_file.write_text(log_str, encoding="utf-8")

            print(
                f"Konsave: {err}\nPlease check the log at {log_file} for more details."
            )
            return None
        else:
            return function

    return inner_func


def log(msg: str, *args, **kwargs) -> None:
    """Logs text.

    Args:
        msg: the text to be printed
        *args: any arguments for the function print()
        **kwargs: any keyword arguments for the function print()
    """
    print(f"Konsave: {msg}", *args, **kwargs)


@exception_handler
@app.command(name="list")
def list_profiles():
    """List all the created profiles."""

    profiles_list = list_of_profiles

    assert PROFILES_DIR.exists() and length_of_lop != 0, "No profile found."

    # sort n alphabetical order
    profiles_list.sort()

    print("Konsave profiles:")
    print("ID\tNAME")
    for i, item in enumerate(profiles_list):
        print(f"{i + 1}\t{item}")


@exception_handler
@app.command(no_args_is_help=True, name="save")
def save_profile(name: str, force: bool = False):
    """Save necessary config files in ~/.config/konsave/profiles/<name>."""

    assert (
        name not in list_of_profiles or force
    ), "Profile with this name already exists"

    log("saving profile...")
    profile_dir = PROFILES_DIR / name
    profile_dir.mkdir()

    konsave_config = Config(CONFIG_FILE).save

    for entry_name, conf_entry in konsave_config.entries.items():
        folder = profile_dir / entry_name
        folder.mkdir()
        for file in conf_entry.entries:
            source = conf_entry.location / file
            dest = folder / file
            if source.exists():
                if source.is_dir():
                    shutil.copytree(source, dest)
                else:
                    dest.write_bytes(source.read_bytes())

                if file in conf_entry.strips.keys():
                    strip_content(Path(dest), conf_entry.strips[file])

    (profile_dir / CONFIG_FILE.name).write_text(CONFIG_FILE.read_text())

    log("Profile saved successfully!")


def strip_content(file_path: Path, strip_entry: StripEntry) -> None:
    """
    strip entire groups or individual keys from all groups in a file
    group names are in the plasma config format
    https://userbase.kde.org/KDE_System_Administration/Configuration_Files

    Args:
        file_path: path to the file
        strip_args: dict with keys "groups" and "keys"
    """

    def strip_groups(file_content: List[str], groups: List[str], ph: str) -> List[str]:
        for group in groups:
            group_lines = [line for line in file_content if f"[{group}]" in line]
            if group_lines:
                for group_line in group_lines:
                    group_idx = file_content.index(group_line)

                    # remove group header line
                    file_content[group_idx] = ph

                    # remove lines from group_index until next section start
                    for line in range(group_idx, len(file_content)):
                        exp = re.compile(r"^\[.*\].*")
                        if exp.match(file_content[line]):
                            break
                        file_content[line] = ph

        return file_content

    def strip_keys(file_content: List[str], keys: List[str], ph: str) -> List[str]:
        for key in keys:
            key_lines = [line for line in file_content if f"{key}=" in line]
            if key_lines:
                for key_line in key_lines:
                    key_idx = file_content.index(key_line)
                    file_content[key_idx] = ph

        return file_content

    groups = strip_entry.groups
    keys = strip_entry.keys
    file_content = file_path.read_text().splitlines()
    placeholder = "# stripped by konsave"

    file_content = strip_groups(file_content, groups, placeholder)
    file_content = strip_keys(file_content, keys, placeholder)

    # remove lines with placeholder
    file_content = list(filter(lambda x: x != placeholder, file_content))

    file_path.write_text("\n".join(file_content))


@exception_handler
@app.command(no_args_is_help=True, name="apply")
def apply_profile(profile_name: str):
    """Apply profile of the given name."""

    # assert
    assert length_of_lop != 0, "No profile saved yet."
    assert profile_name in list_of_profiles, "Profile not found :("

    # run
    profile_dir = PROFILES_DIR / profile_name

    log("copying files...")

    config_location = profile_dir / "conf.yaml"
    profile_config = Config(config_location).save
    for entry_name, conf_entry in profile_config.entries.items():
        shutil.copytree(
            profile_dir / entry_name, conf_entry.location, dirs_exist_ok=True
        )

    log(
        "Profile applied successfully! Please log-out and log-in to see the changes completely!"
    )


@exception_handler
@app.command(no_args_is_help=True, name="remove")
def remove_profile(profile_name: str):
    """Remove profile with the given name."""

    # assert
    assert length_of_lop != 0, "No profile saved yet."
    assert profile_name in list_of_profiles, "Profile not found."

    # run
    log("removing profile...")
    shutil.rmtree(PROFILES_DIR / profile_name)
    log("removed profile successfully")


@exception_handler
@app.command(no_args_is_help=True)
def export(
    profile_name: str,
    archive_dir: Optional[Path] = None,
    archive_name: Optional[str] = None,
    force: bool = False,
):
    """Export profile to a zip file in the given directory."""

    # assert
    assert length_of_lop != 0, "No profile saved yet."
    assert profile_name in list_of_profiles, "Profile not found."

    # run
    profile_dir = PROFILES_DIR / profile_name

    if archive_name:
        profile_name = archive_name

    if archive_dir:
        export_path = archive_dir / profile_name
    else:
        export_path = Path.cwd() / profile_name

    # Only continue if export_path, export_path.ksnv and export_path.zip don't exist
    # Appends date and time to create a unique file name
    if not force:
        while True:
            paths = [f"{export_path}", f"{export_path}.knsv", f"{export_path}.zip"]
            if any([Path(path).exists() for path in paths]):
                time = "f{:%d-%m-%Y:%H-%M-%S}".format(datetime.now())
                export_path = Path(f"{export_path}_{time}")
            else:
                break

    # compressing the files as zip
    log("Exporting profile. It might take a minute or two...")

    profile_config_file = profile_dir / "conf.yaml"
    conf = Config(profile_config_file)

    export_path_save = export_path / "save"
    export_path_save.mkdir(parents=True)

    for entry_name, conf_entry in conf.save.entries.items():
        log(f'Exporting "{entry_name}"...')
        shutil.copytree(profile_dir / entry_name, export_path_save / entry_name)

    konsave_config_export = conf.export
    export_path_export = export_path / "export"

    for entry_name, conf_entry in konsave_config_export.entries.items():
        for entry in conf_entry.entries:
            source = Path(conf_entry.location) / entry
            dest = export_path_export / entry
            log(f'Exporting "{entry}"...')
            if source.exists():
                if source.is_dir():
                    shutil.copytree(source, dest, symlinks=True)
                else:
                    dest.write_bytes(source.read_bytes())

    shutil.copy(CONFIG_FILE, export_path)

    log("Creating archive")
    shutil.make_archive(export_path, "zip", export_path)

    shutil.rmtree(export_path)
    shutil.move(
        export_path.with_suffix(".zip"), export_path.with_suffix(EXPORT_EXTENSION)
    )

    log(f"Successfully exported to {export_path}{EXPORT_EXTENSION}")


@exception_handler
@app.command(no_args_is_help=True, name="import")
def import_profile(zip_path: Path):
    """Import an exported profile in .knsv format."""

    # assert
    assert (
        is_zipfile(zip_path) and zip_path.suffix == EXPORT_EXTENSION
    ), "Not a valid konsave file"
    profile_name = zip_path.stem
    assert not Path(
        PROFILES_DIR / profile_name
    ).exists(), "A profile with this name already exists"

    # run
    log("Importing profile. It might take a minute or two...")

    temp_path = KONSAVE_DIR / "temp" / profile_name

    with ZipFile(zip_path, "r") as zip_file:
        zip_file.extractall(temp_path)

    config_file_location = temp_path / "conf.yaml"
    conf = Config(config_file_location)
    profile_conf = temp_path / "conf.yaml"

    profile_dir = PROFILES_DIR / profile_name
    shutil.copytree(temp_path / "save", profile_dir)

    (profile_dir / "conf.yaml").write_text(profile_conf.read_text())

    for entry_name, conf_entry in conf.export.entries.items():
        path = temp_path / "export" / entry_name
        for entry_name in conf_entry.entries:
            source = path / entry_name
            dest = Path(conf_entry.location) / entry_name
            log(f'Importing "{entry_name}"...')
            if source.exists():
                if source.is_dir():
                    shutil.copytree(source, dest)
                else:
                    dest.write_bytes(source.read_bytes())

    shutil.rmtree(temp_path)

    log("Profile successfully imported!")


@exception_handler
@app.command()
def wipe(force: bool = Option(..., prompt="Are you sure you want to delete the user?")):
    """Wipe all profiles."""
    if force:
        shutil.rmtree(PROFILES_DIR)
        log("Removed all profiles!")
    else:
        log("Aborting...")


if __name__ == "__main__":
    app()
