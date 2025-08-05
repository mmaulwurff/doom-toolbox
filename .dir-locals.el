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
                  (let ((d (dir-locals-find-file "./"))) (if (stringp d) d (car d)))))))
  (ispell-local-dictionary . "american")))

(org-mode . (
  (org-html-doctype . "html5")
  (org-html-html5-fancy . t)
  ;; See https://emacs.stackexchange.com/questions/3374/set-the-background-of-org-exported-code-blocks-according-to-theme
  (eval . (progn
            (defun my/org-inline-css-hook (exporter)
              "Insert custom inline CSS to set the code colors code according to the current theme"
              (when (eq exporter 'html)
                (let* ((my-pre-bg (face-background 'default))
                       (my-pre-fg (face-foreground 'default)))
                  (setq
                   org-html-head-extra
                   (concat
                    org-html-head-extra
                    (format "<style type=\"text/css\">\n pre.src {background-color: %s; color: %s;}</style>\n"
                            my-pre-bg my-pre-fg))))))
            (add-hook 'org-export-before-processing-hook 'my/org-inline-css-hook))))))
