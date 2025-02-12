#!/usr/bin/env sh
#
# SPDX-FileCopyrightText: © 2024 Alexander Kromm <mmaulwurff@gmail.com>
# SPDX-License-Identifier: CC0-1.0
#
# Builds a .pk3 package from an .org file.

title=$(grep --max-count=1 "#+title: " "$1" | sed "s/#+title: //" | sed "s/ /-/")
name=$(basename "$1" ".org")

emacs "$1" --quick --batch --eval "(progn (require 'ob-tangle) (setq org-confirm-babel-evaluate nil) (org-babel-tangle))"

rm -rf "build/$title"
rm -rf "build/$title.pk3"

mkdir -p "build/$title"
cp -r "build/$name/"* "build/$title"
cp -r LICENSES "build/$title"
cp "$1" "build/$title"

cd "build/$title"
7z a -tzip "../$title.pk3" ./*
