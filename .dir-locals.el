;; SPDX-FileCopyrightText: © 2025 Alexander Kromm <mmaulwurff@gmail.com>
;; SPDX-License-Identifier: CC0-1.0

;; This is directory local variables file for Emacs.

((nil . (
         ;; Set the path to the dictionary file so it works in files in subdirectories too.
         ;; See https://stackoverflow.com/questions/4012321/how-can-i-access-the-path-to-the-current-directory-in-an-emacs-directory-variabl
         (eval . (setq ispell-personal-dictionary
                       (expand-file-name
                        "./tools/aspell.en.pws"
                        (file-name-directory
                         (let ((d (dir-locals-find-file "./")))
                           (if (stringp d) d (car d)))))))
         (ispell-local-dictionary . "american"))))
