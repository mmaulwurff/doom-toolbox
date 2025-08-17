#!/usr/bin/env python3

# SPDX-FileCopyrightText: © 2025 Alexander Kromm <mmaulwurff@gmail.com>
# SPDX-License-Identifier: CC0-1.0

# Requirements for environment variables:
# - PATH: has Emacs and GZDoom,
# - CLEMATIS_PATH: path to Clematis directory, example: "/home/user/src/clematis/src"
#
# TODO: add descriptions for Clematis an Miniwad.
#
# Written for Python >=3.11.

from org_tangle import tangle
from os import environ, chdir, path
from pathlib import Path
from re import search
from shutil import which, copy
from subprocess import run, PIPE, STDOUT
from sys import argv


def is_ignored(line, ignored_lines):
    for ignored_line in ignored_lines:
        if search(ignored_line, line) != None:
            return True
    return False

def test(project_file_name):
    assert which("gzdoom") != None, "GZDoom not in PATH environment variable"
    assert "CLEMATIS_PATH" in environ, "CLEMATIS_PATH environment variable not set"

    chdir(Path(path.dirname(__file__)) / "..")

    build_directory_path = tangle(project_file_name)
    test_directory_path = Path(str(build_directory_path) + "Test")

    copy("tools/config.ini", "build/config.ini")

    commands_file_path = Path(str(build_directory_path) + "TestCommands.txt")
    with open(commands_file_path) as commands_file:
        commands = commands_file.read()

    result = run(stdout = PIPE,
                 stderr = STDOUT,
                 text = True,
                 args = ["gzdoom",
                         "-noautoload",
                         "-nosound",
                         "-config",
                         "build/config.ini",
                         "-iwad",
                         "tools/miniwad.wad",
                         "-file",
                         environ["CLEMATIS_PATH"],
                         build_directory_path,
                         test_directory_path if test_directory_path.exists() else "",
                         "+wi_autoadvance 1",
                         "+" + commands])

    with open("tools/IgnoredGzdoomOutput.txt") as ignored_lines_file:
        ignored_lines = [line.rstrip() for line in ignored_lines_file]

    for line in result.stdout.splitlines():
        if not is_ignored(line, ignored_lines):
            print(line)

    # TODO: ~sed 's/Script error, \"\(.*\)\/:\(.*\)\" line \(.*\)/\1\/\2:\3/')"~

if __name__ == "__main__":
    assert len(argv) == 2, "Usage: ./tools/test.py Project.org"
    test(argv[1])
