#!/usr/bin/env python3

# SPDX-FileCopyrightText: © 2025 Alexander Kromm <mmaulwurff@gmail.com>
# SPDX-License-Identifier: CC0-1.0

# Builds a .pk3 package from an .org file.
# Meant to be run from the root project directory, like:
# ./tools/package.py DoomDoctor.org
#
# Requirements for environment variables:
# - PATH: has Emacs.
#
# Written for Python >=3.11.
#
# ! Warning: this script removes project-related directories inside build
# directory.

from pathlib import Path
from re import search, MULTILINE
from shutil import rmtree, copytree, make_archive, move
from sys import argv
from org_tangle import tangle


def package(project_file_name):
    with open(project_file_name) as project_file:
        project_content = project_file.read()

    found = search("^#\+title: (.*)$", project_content, flags=MULTILINE)
    assert found != None, "No title found."

    title = found.group(1).replace(" ", "-")

    # 1. Tangle the source to build files.
    build_directory_path = tangle(project_file_name)
    # TODO: export to HTML too (through Markdown?).

    # 2. Clean package directory and package.
    package_directory_path = Path("build/" + title)
    rmtree(package_directory_path, True)

    package_path = Path("build/" + title).with_suffix(".pk3")
    package_path.unlink(True)

    # 3. Copy build files, licenses, and documentation to package directory.
    copytree(build_directory_path, package_directory_path)
    copytree("LICENSES",
             package_directory_path / "LICENSES",
             dirs_exist_ok=True)
    copytree("documentation",
             package_directory_path / "documentation",
             dirs_exist_ok=True)

    archive = make_archive(package_directory_path,
                           "zip",
                           package_directory_path)
    move(archive, Path(archive).with_suffix(".pk3"))

if __name__ == "__main__":
    assert len(argv) == 2, "Usage: ./tools/package.py Project.org"
    package(argv[1])
