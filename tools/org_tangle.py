#!/usr/bin/env python3

# SPDX-FileCopyrightText: © 2025 Alexander Kromm <mmaulwurff@gmail.com>
# SPDX-License-Identifier: CC0-1.0

# Requirements for environment variables:
# - PATH: has Emacs.
#
# Written for Python >=3.11.
#
# ! Warning: this script removes build directory before tangling.

from os import chdir, path
from pathlib import Path
from shutil import which, rmtree
from subprocess import run
from sys import argv


def tangle(project_file_name):
    assert which("emacs") != None, "Emacs not in PATH environment variable"

    chdir(Path(path.dirname(__file__)) / "..")

    assert Path(project_file_name).exists(),\
        "file {} not found".format(path.abspath(project_file_name))

    project_file_base_name = path.splitext(path.basename(project_file_name))[0]
    build_directory_path = Path("build/" + project_file_base_name)
    rmtree(build_directory_path, True)

    run(["emacs",
         project_file_name,
         "--quick",
         "--batch",
         "--eval",
         "(progn "
             "(require 'ob-tangle)"
             "(setq org-confirm-babel-evaluate nil)"
             "(org-babel-tangle))"])

    return build_directory_path

if __name__ == "__main__":
    assert len(argv) == 2, "Usage: ./tools/org_tangle.py Project.org"
    tangle(argv[1])
