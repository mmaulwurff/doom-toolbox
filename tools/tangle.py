#!/usr/bin/env python3

# SPDX-FileCopyrightText: © 2025 Alexander Kromm <mmaulwurff@gmail.com>
# SPDX-License-Identifier: CC0-1.0

# Written for Python >=3.11.

from subprocess import run
from sys import argv


def tangle(project_file_name):
    run(["emacs",
         project_file_name,
         "--quick",
         "--batch",
         "--eval",
         "(progn "
             "(require 'ob-tangle)"
             "(setq org-confirm-babel-evaluate nil)"
             "(org-babel-tangle))"])

if __name__ == "__main__":
    assert len(argv) == 2, "Usage: ./tools/tangle.py Project.org"
    tangle(argv[1])
