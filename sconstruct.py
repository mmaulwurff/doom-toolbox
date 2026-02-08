# SPDX-FileCopyrightText: © 2025 Alexander Kromm <mmaulwurff@gmail.com>
# SPDX-License-Identifier: CC0-1.0

# This is build definitions for DoomToolbox.
# See https://scons.github.io/docs/scons-user.html for details.

# TODO: test on Windows.

# TODO: move autoadvance to config.ini?
#+wi_autoadvance 1\

# TODO: add targets to build all packages and to run all tests.

# TODO: Instead of copying all LICENSES, copy only needed. Use Reuse?

# TODO: fix parallel builds (-j 4). Check with moules of Typist.pk3.
# May be a problem with cleaning, if main target is built after a module.

from os import environ, makedirs, path
from pathlib import Path
from re import search, MULTILINE
from shutil import copy, copytree, make_archive, move, rmtree, which
from subprocess import run, PIPE, STDOUT

import hashlib


# General setup
Decider('timestamp-match')
Default(None)
DefaultEnvironment(ENV=environ.copy())

emacs = which('emacs-nox') or which('emacs')
assert emacs != None

# Common functions
def noop(target, source, env):
  pass

def make_project_name(org_file):
  return path.splitext(path.basename(org_file))[0]

def make_export(source):
  htmlize_path = path.abspath('tools/htmlize.el')
  rel = '' if len(path.normpath(source).split(path.sep)) == 1 else '../'
  css_path = rel + 'tools/org-adwaita.css'
  css_link = f'<link rel=\\\\\\"stylesheet\\\\\\" type=\\\\\\"text/css\\\\\\" href=\\\\\\"{css_path}\\\\\\"/>'
  return f'{emacs} {source} --quick --batch --load {htmlize_path} --eval "\
    (progn (require \'htmlize)\
           (setq org-confirm-babel-evaluate nil)\
           (setq org-html-htmlize-output-type \'css)\
           (setq org-html-validation-link nil)\
           (setq org-html-head-extra \\"{css_link}\\")\
           (org-html-export-to-html))"'


# Target setup functions
def add_main_target(org_file, target_format):
  name = make_project_name(org_file)
  zscript_name = target_format.format(name)

  tangle = f'{emacs} $SOURCE --quick --batch --eval "\
    (progn (require \'ob-tangle)\
           (setq org-confirm-babel-evaluate nil)\
           (org-babel-tangle))"'

  def clean(target, source, env):
    rmtree(f'build/{name}', True)

  return Alias(name, Command(target=zscript_name, source=org_file, action=[clean, tangle]))

def add_html_target(org_file, main_target):
  name = make_project_name(org_file)
  html_name = f'{name}Html'

  def putHtml(target, source, env):
    move(f'{name}.html', f'build/{name}/{name}.html')
    makedirs(f'build/{name}/tools/', exist_ok=True)
    copy('tools/org-adwaita.css', f'build/{name}/tools/org-adwaita.css')

  return AlwaysBuild(Alias(html_name, main_target, [make_export(org_file), putHtml]))

def add_test_target(org_file, main_target):
  name = make_project_name(org_file)
  test_name = f'{name}Test'

  def run_test(target, source, env):
    args = ['gzdoom',
            '-noautoload',
            '-nosound',
            '-config', 'build/config.ini',
            '-iwad', 'tools/miniwad.wad',
            '-file',
              'tools/ClematisM-v2.1.0.pk3',
              f'build/{name}',
              f'build/{name}Test',
            f'+exec build/{name}Test/commands.txt']

    if not Path("build/config.ini").exists():
      copy("tools/config.ini", "build/config.ini")

    result = run(stdout=PIPE, stderr=STDOUT, text=True, args=args)

    with open('tools/IgnoredEngineOutput.txt') as lines_to_skip_file:
      lines_to_skip = [line.rstrip() for line in lines_to_skip_file]

    def printable(line):
      return not any([search(to_skip, line) for to_skip in lines_to_skip])

    for line in filter(printable, result.stdout.splitlines()):
      # TODO: sed 's/Script error, \"\(.*\)\/:\(.*\)\" line \(.*\)/\1\/\2:\3/')"
      print(line)

  return AlwaysBuild(Alias(test_name, main_target, run_test))

def add_pack_target(org_file, main_target):
  name = make_project_name(org_file)
  pack_name = f'{name}.pk3'
  build_path = Path(f'build/{name}')

  def pack(target, source, env):
    with open(org_file) as project_file:
      project_content = project_file.read()

    def make_short_hash():
      h = hashlib.new('sha1')
      h.update(project_content.encode('utf-8'))
      return h.hexdigest()[:8]

    foundVersion = search('^#[+]version: *(.*)$', project_content, flags=MULTILINE)
    version = foundVersion.group(1) if foundVersion != None else make_short_hash()

    copytree('LICENSES', build_path/'LICENSES', dirs_exist_ok=True)
    copytree('documentation', build_path/'documentation', dirs_exist_ok=True)
    copy(org_file, build_path/org_file)

    archive = make_archive(Path(str(build_path) + '-' + version), 'zip', build_path)
    move(archive, Path(archive).with_suffix('.pk3'))

  return AlwaysBuild(Alias(pack_name, main_target, pack))

def make_index(target, source, env):
  copy('README.html', 'index.html')


# Targets
pk3_all = Alias("Pk3All", None, noop)

module_targets = []
for org_file in Glob('modules/*.org'):
  main_target = add_main_target(org_file, 'build/{0}/{0}.zs')
  test_target = add_test_target(org_file, main_target)
  module_targets.append(f'{main_target[0]}, {test_target[0]}')

project_targets = []
for org_file in Glob('*.org'):
  if str(org_file) != 'README.org':
    main_target = add_main_target(org_file, 'build/{0}/zscript.zs')
    html_target = add_html_target(org_file, main_target)
    test_target = add_test_target(org_file, main_target)
    pack_target = add_pack_target(org_file, html_target)
    Depends(pk3_all, pack_target)
    project_targets.append(
      f'{main_target[0]}, {html_target[0]}, {test_target[0]}, {pack_target[0]}')

html_all = Alias("HtmlAll", None, make_index)
for org_file in Glob('*/*.org') + Glob('*.org'):
  html_name = f'{path.splitext(org_file)[0]}.html'
  Depends(html_all, Command(target=html_name,
                            source=org_file,
                            action=make_export(org_file)))

AlwaysBuild(Alias("LintAll", None,
                  [f'{emacs} {org_file} --quick --batch --eval "(print (org-lint))"'
                   for org_file in Glob('*/*.org') + Glob('*.org')]))


# Dependencies
def add_dependency(project, module, namespace):
  def export_module(target, source, env):
    with open(target[0], 'w') as target_file:
      with open(source[0]) as module_file:
        target_file.write(module_file.read().replace('NAMESPACE_', namespace))

  Depends(project, Command(target=f'build/{project}/zscript/{namespace}{module}.zs',
                           source=f'build/{module}/{module}.zs',
                           action=export_module))

add_dependency('DoomDoctor', 'StringUtils', 'dd_')
add_dependency('FinalCustomDoom', 'PlainTranslator', 'cd_')

add_dependency('Typist.pk3', 'libeye', 'tt_le_')
add_dependency('Typist.pk3', 'LazyPoints', 'tt_lp_')
add_dependency('Typist.pk3', 'StringUtils', 'tt_su_')


# Help
Help(f"""
Modules:

- {'\n- '.join(module_targets)}

Projects:

- {'\n- '.join(project_targets)}

General targets:

- Pk3All: build packages for all mods
- LintAll: run org-lint for all Org files

Type 'scons <target>' to build a target.
""", append=False)
