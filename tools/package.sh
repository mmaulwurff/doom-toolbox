#!/usr/bin/env sh
#
# SPDX-FileCopyrightText: © 2024 Alexander Kromm <mmaulwurff@gmail.com>
# SPDX-License-Identifier: CC0-1.0
#
# Builds a .pk3 package from an .org file.
# Meant to be run from the root project directory, like:
# ./tools/package.sh DoomDoctor.org
#
# ! Warning: this script removes project-related directories inside build directory.

title=$(grep --max-count=1 "#+title: " "$1" | sed "s/#+title: //" | sed "s/ /-/")
name=$(basename "$1" ".org")

rm --recursive --force "build/$name"

emacs "$1" --quick --batch --eval "(progn (require 'ob-tangle) (setq org-confirm-babel-evaluate nil) (org-babel-tangle))"

rm --recursive --force "build/$title"
rm --recursive --force "build/$title.pk3"

mkdir --parents "build/$title"
cp --recursive "build/$name/"* "build/$title"
cp --recursive LICENSES "build/$title"
cp --recursive documentation "build/$title"
cp "$1" "build/$title/Readme.org"

cd "build/$title" || exit
7z a -tzip "../$title.pk3" ./*
