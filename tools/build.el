;;; build.el --- Description -*- lexical-binding: t; -*-
;;
;; SPDX-FileCopyrightText: © 2026 Alexander Kromm <mmaulwurff@gmail.com>
;; SPDX-License-Identifier: BSD-3-Clause
;;
;; Author: m8f
;; Maintainer: m8f
;; Created: April 04, 2026
;; Modified: April 04, 2026
;; Version: 0.0.1
;; Keywords: games
;; Homepage: https://github.com/mmaulwurff/doom-toolbox/
;; Package-Requires: ((emacs "30.1"))
;;
;; This file is not part of GNU Emacs.
;;
;;; Commentary:
;;
;;  This file contains functions to build DoomToolbox projects.
;;
;;; Code:

(defun dt-tangle ()
  (require 'ob-tangle)
  (setq org-confirm-babel-evaluate nil)
  (set-language-environment "UTF-8")
  (org-babel-tangle))

(defun dt-export (htmlize-el-path relative-part)
  (load htmlize-el-path)
  (require 'htmlize)
  (setq org-confirm-babel-evaluate nil)
  (set-language-environment "UTF-8")
  (setq org-html-htmlize-output-type 'css)
  (setq org-html-validation-link nil)
  (setq css-path (concat relative-part "tools/org-adwaita.css"))
  (setq org-html-head-extra
    (format "<link rel=\"stylesheet\" type=\"text/css\" href=\"%s\"/>" css-path))
  (org-html-export-to-html))

;;; build.el ends here
