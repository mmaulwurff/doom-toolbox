#!/usr/bin/env python3

# SPDX-FileCopyrightText: © 2025 Alexander Kromm <mmaulwurff@gmail.com>
# SPDX-License-Identifier: CC0-1.0

# Requirements for environment variables:
# - package, tangle: PATH: has Emacs.
# - test: PATH: has Emacs and GZDoom.
#
# Written for Python >=3.13.
#
# Results are written to `build` directory.
#
# ! Warning: this script may remove files and directories in `build` directory.

from os import chdir, makedirs, path
from pathlib import Path
from re import search, MULTILINE
from shutil import copy, copytree, make_archive, move, rmtree, which
from subprocess import run, PIPE, STDOUT
from sys import argv, exit


def help():
    print("Usage: ./tools/org.py COMMAND ORG_FILE\n\n"
          "Commands:\n"
          "- package    build .pk3 package from ORG_FILE.\n"
          "- test       run tests for ORG_FILE.\n"
          "- tangle     convert ORG_FILE to a conventional GZDoom mod directory.\n"
          "- export     export ORG_FILE module to a ZScript file with namespace.\n"
          "\n"
          "Export usage: ./tools/org.py export ORG_FILE NAMESPACE EXPORT_FILE\n")

def is_ignored(line, ignored_lines):
    for ignored_line in ignored_lines:
        if search(ignored_line, line) != None:
            return True
    return False

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

def test(project_file_name):
    assert which("gzdoom") != None, "GZDoom not in PATH environment variable"

    chdir(Path(path.dirname(__file__)) / "..")

    assert Path(project_file_name).exists(),\
        "file {} not found".format(path.abspath(project_file_name))

    build_directory_path = tangle(project_file_name)
    test_directory_path = Path(str(build_directory_path) + "Test")

    if not Path("build/config.ini").exists():
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
                         "tools/ClematisM-v2.1.0.pk3",
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

def package(project_file_name):
    assert Path(project_file_name).exists(),\
        "file {} not found".format(path.abspath(project_file_name))

    with open(project_file_name) as project_file:
        project_content = project_file.read()

    found = search(r'"^#+title: (.*)$', project_content, flags=MULTILINE)
    assert found != None, "no title found"

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

def export_module(module_file_name, namespace, export_file_name):
    assert Path(module_file_name).exists(),\
        "file {} not found".format(path.abspath(module_file_name))

    build_directory_path = tangle(module_file_name)
    module_file_base_name = path.splitext(path.basename(module_file_name))[0]
    zscript_file_name = (build_directory_path / module_file_base_name)\
        .with_suffix(".zs")

    with open(zscript_file_name) as module_file:
        original_contents = module_file.read()

    replaced_contents = original_contents.replace("NAMESPACE_", namespace)

    export_directory = path.dirname(export_file_name)
    if not path.exists(export_directory):
        makedirs(export_directory)

    with open(export_file_name, "w") as export_file:
        export_file.write(replaced_contents)


if __name__ == "__main__":
    command = argv[1] if len(argv) > 1 else None
    match command:
        case "help":
            action = help
            parametersCount = 0
        case "package":
            action = package
            parametersCount = 1
        case "test":
            action = test
            parametersCount = 1
        case "tangle":
            action = tangle
            parametersCount = 1
        case "export":
            action = export_module
            parametersCount = 3
        case _:
            action = None
            parametersCount = None

    if len(argv) - 2 == parametersCount:
        match parametersCount:
            case 0:
                action()
            case 1:
                action(argv[2])
            case 2:
                action(argv[2], argv[3])
            case 3:
                action(argv[2], argv[3], argv[4])
        exit()

    if action == None:
        help()
    else:
        if parametersCount == 1:
            print("Usage: ./tools/org.py {} ORG_FILE".format(command));
        elif command == "export":
            print("Usage: ./tools/org.py {} ORG_FILE NAMESPACE EXPORT_FILE"\
                .format(command));
        else:
            assert false, "missing help for command {}".format(command)

    exit(-1)
