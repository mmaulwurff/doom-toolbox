#!/usr/bin/env sh
#
# SPDX-FileCopyrightText: © 2024 Alexander Kromm <mmaulwurff@gmail.com>
# SPDX-License-Identifier: CC0-1.0
#
# Builds a .pk3 package from an .org file.

title=$(grep --max-count=1 "#+title: " "$1" | sed "s/#+title: //" | sed "s/ /-/")
name=$(basename "$1" ".org")

emacs "$1" --quick --batch --eval "(progn (require 'ob-tangle) (setq org-confirm-babel-evaluate nil) (org-babel-tangle))"

rm -rf "packages/$title"
rm -rf "packages/$title.pk3"

mkdir -p "packages/$title"
cp -r "build/$name/"* "packages/$title"
cp -r LICENSES "packages/$title"
cp "$1" "packages/$title"

cd "packages/$title"
7z a -tzip "../../packages/$title.pk3" ./*
