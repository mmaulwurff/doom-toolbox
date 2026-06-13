# SPDX-FileCopyrightText: © 2025 Alexander Kromm <mmaulwurff@gmail.com>
# SPDX-License-Identifier: CC0-1.0

# This is build definitions for DoomToolbox.
# See https://scons.github.io/docs/scons-user.html for details.


from os import environ, makedirs, path
from pathlib import Path
from re import MULTILINE, search, sub
from shutil import copy, copytree, make_archive, move, rmtree, which
from subprocess import PIPE, STDOUT, TimeoutExpired, run

import git
import reuse.project
import reuse.report
from SCons.Script import (
  Alias,
  AlwaysBuild,
  Command,
  Decider,
  Default,
  DefaultEnvironment,
  Depends,
  Glob,
  Help,
)

# General setup
Decider('timestamp-match')
Default(None)
DefaultEnvironment(ENV=environ.copy())

emacs = which('emacs-nox') or which('emacs') or Path('c:/tools/emacs/bin/emacs.exe')
uzdoom = (
  path.expanduser(environ['DT_ENGINE'])
  if 'DT_ENGINE' in environ
  else which('uzdoom')
)


# Common functions
def make_project_name(org_file):
  return path.splitext(path.basename(org_file))[0]


def make_export(source):
  build_el_path = path.abspath('tools/build.el')
  return f'{emacs} {source} --quick --batch \
    --load {build_el_path} \
    --eval "(dt-export)"'


# Target setup functions
def add_main_target(org_file, target_format):
  name = make_project_name(org_file)
  zscript_name = target_format.format(name)
  build_el_path = path.abspath('tools/build.el')
  tangle = f'{emacs} $SOURCE --quick --batch \
    --load {build_el_path} \
    --eval "(dt-tangle)"'

  def clean(target, source, env):
    rmtree(f'build/{name}', True)

  return Alias(
    name, Command(target=zscript_name, source=org_file, action=[clean, tangle])
  )


def add_test_target(org_file, main_target):
  name = make_project_name(org_file)
  test_name = f'{name}Test'

  def run_test(target, source, env):
    args = [
      uzdoom,
      '-noautoload',
      '-nosound',
      '-config',
      './build/config.ini',
      '-iwad',
      './tools/miniwad.wad',
      '-file',
      './build/ClematisM',
      f'./build/{name}',
      f'./build/{name}Test',
      f'+exec {f"./build/{name}Test/commands.txt"}',
    ]

    if not Path('build/config.ini').exists():
      copy('tools/config.ini', 'build/config.ini')

    # Script errors cause an error window to appear,
    # and execution waits for user to press the button.
    # To not bother with closing this window programmatically, just time out.
    try:
      result = run(stdout=PIPE, stderr=STDOUT, text=True, args=args, timeout=60 * 3)
    except TimeoutExpired:
      print('timeout')
      return 1

    with open(
      'tools/IgnoredEngineOutput.txt', encoding='utf-8'
    ) as lines_to_skip_file:
      lines_to_skip = [line.rstrip() for line in lines_to_skip_file]

    def printable(line):
      return not any([search(to_skip, line) for to_skip in lines_to_skip])

    has_errors = False
    for line in filter(printable, result.stdout.splitlines()):
      line = sub(r'(.*)/:(.*), line (.*)', r'\1/\2:\3', line)
      line = sub(r'Script error, \"(.*)/:(.*)\" line (.*)', r'ERROR: \1/\2:\3', line)
      line = sub(
        r'Script warning, \"(.*)/:(.*)\" line (.*)', r'WARNING: \1/\2:\3', line
      )
      has_errors = has_errors or 'ERROR' in line or 'WARNING' in line
      print(line)

    return 1 if has_errors else 0

  return AlwaysBuild(Alias(test_name, main_target, run_test))


def add_pack_target(org_file, main_target):
  name = make_project_name(org_file)
  pack_name = f'{name}.pk3'
  build_path = Path(f'build/{name}')

  def pack(target, source, env):
    with open(org_file, encoding='utf-8') as project_file:
      project_content = project_file.read()

    commit_sha = git.Repo().head.object.hexsha[:10]
    foundVersion = search('^#[+]version: *(.*)$', project_content, flags=MULTILINE)
    version = foundVersion.group(1) if foundVersion is not None else commit_sha

    copytree('documentation', build_path / 'documentation', dirs_exist_ok=True)
    copy(org_file, build_path / 'README.org')

    licenses_path = build_path / 'LICENSES'
    makedirs(licenses_path, exist_ok=True)
    project = reuse.project.Project.from_directory(build_path)
    report = reuse.report.ProjectReport.generate(project)
    for license in report.used_licenses:
      copy('LICENSES/' + license + '.txt', licenses_path)

    # Note: project and report are duplicated intentionally
    # to re-read the directory after copying licenses.
    project = reuse.project.Project.from_directory(build_path)
    report = reuse.report.ProjectReport.generate(project)
    if not report.is_compliant:
      print(
        [
          'ERROR',
          name,
          ' '.join(report.recommendations),
          'bad licenses',
          report.bad_licenses,
          'deprecated licenses',
          report.deprecated_licenses,
          'unused licenses',
          report.unused_licenses,
          'missing licenses',
          report.missing_licenses,
          'invalid SPDX expressions',
          report.invalid_spdx_expressions,
          'files without licenses',
          report.files_without_licenses,
          'files without copyright',
          report.files_without_copyright,
        ]
      )

    archive = make_archive(Path(str(build_path) + '-' + version), 'zip', build_path)
    move(archive, Path(archive).with_suffix('.pk3'))

  return AlwaysBuild(Alias(pack_name, main_target, pack))


def make_check_compatibility_target():
  names = []
  for org_file in Glob('add-ons/*.org'):
    names.append(make_project_name(org_file))

  projects = ['./build/' + name for name in names]

  def check_compatibility(target, source, env):
    args = [
      uzdoom,
      '-noautoload',
      '-nosound',
      '-config',
      './build/config.ini',
      '-iwad',
      './tools/miniwad.wad',
      '+wait 2; map map01; wait 2; save test; wait 2; load test; wait 2; quit',
      '-file',
    ] + projects

    if not Path('build/config.ini').exists():
      copy('tools/config.ini', 'build/config.ini')

    # Script errors cause an error window to appear,
    # and execution waits for user to press the button.
    # To not bother with closing this window programmatically, just time out.
    try:
      result = run(stdout=PIPE, stderr=STDOUT, text=True, args=args, timeout=60 * 3)
    except TimeoutExpired:
      print('timeout')
      return 1

    with open(
      'tools/IgnoredEngineOutput.txt', encoding='utf-8'
    ) as lines_to_skip_file:
      lines_to_skip = [line.rstrip() for line in lines_to_skip_file]

    def printable(line):
      return not any([search(to_skip, line) for to_skip in lines_to_skip])

    for line in filter(printable, result.stdout.splitlines()):
      print(line)

    return 0

  return check_compatibility


def make_index(target, source, env):
  copy('README.html', 'index.html')


# Targets
pk3_all = Alias('Pk3All', None, None)
test_all = Alias('TestAll', None, None)
clematis_target = add_main_target('add-ons/ClematisM.org', 'build/{0}/zscript.zs')

module_targets = []
for org_file in Glob('modules/*.org'):
  main_target = add_main_target(org_file, 'build/{0}/{0}.zs')
  test_target = add_test_target(org_file, main_target)
  Depends(test_target, clematis_target)
  Depends(test_all, test_target)
  module_targets.append(f'{main_target[0]}, {test_target[0]}')

project_targets = []
for org_file in Glob('add-ons/*.org'):
  main_target = add_main_target(org_file, 'build/{0}/zscript.zs')
  test_target = add_test_target(org_file, main_target)
  pack_target = add_pack_target(org_file, main_target)

  if org_file != 'ClematisM.org':
    Depends(test_target, clematis_target)
  Depends(test_all, test_target)
  Depends(pk3_all, pack_target)
  project_targets.append(f'{main_target[0]}, {test_target[0]}, {pack_target[0]}')

html_all = Alias('HtmlAll', None, make_index)
for org_file in Glob('*/*.org') + Glob('*.org'):
  html_name = f'{path.splitext(org_file)[0]}.html'
  Depends(
    html_all,
    Command(target=html_name, source=org_file, action=make_export(org_file)),
  )

AlwaysBuild(
  Alias(
    'LintAll',
    None,
    [
      f'{emacs} {org_file} --quick --batch --eval "(print (org-lint))"'
      for org_file in Glob('*/*.org') + Glob('*.org')
    ],
  )
)

AlwaysBuild(Alias('CheckCompatibility', None, make_check_compatibility_target()))
for org_file in Glob('add-ons/*.org'):
  Depends('CheckCompatibility', make_project_name(org_file))


# Dependencies
def add_dependency(project, module, namespace):
  target_directory = f'build/{project}/zscript'

  def export_module(target, source, env):
    makedirs(target_directory, exist_ok=True)
    destination = f'{target_directory}/{namespace}{module}.zs'
    with open(destination, 'w', encoding='utf-8') as target_file:
      with open(source[0], encoding='utf-8') as module_file:
        target_file.write(module_file.read().replace('NAMESPACE_', namespace))

  Depends(
    project,
    Command(
      target=project + module,
      source=f'build/{module}/{module}.zs',
      action=export_module,
    ),
  )


add_dependency('VmAbortReporter', 'StringUtils', 'NAMESPACE_')
add_dependency('LispOnZscript', 'StringUtils', 'tl_')

add_dependency('DoomDoctor', 'StringUtils', 'dd_')
add_dependency('DoomDoctor', 'VmAbortReporter', 'dd_')

add_dependency('FinalCustomDoom', 'PlainTranslator', 'cd_')

add_dependency('SoundToScreen', 'PlainTranslator', 'st_')

for dependency in ['StringUtils', 'libeye', 'PlainTranslator']:
  add_dependency('TargetSpy', dependency, 'ts_')

add_dependency('Typist.pk3', 'libeye', 'tt_le_')
add_dependency('Typist.pk3', 'LazyPoints', 'tt_lp_')
add_dependency('Typist.pk3', 'StringUtils', 'tt_su_')
add_dependency('Typist.pk3', 'PlainTranslator', 'tt_')

add_dependency('Gearbox', 'MD5', 'gb_')
add_dependency('Gearbox', 'PreviousWeapon', 'gb_')
add_dependency('Gearbox', 'StringUtils', 'gb_')
add_dependency('Gearbox', 'VmAbortReporter', 'gb_')
add_dependency('Gearbox', 'PlainTranslator', 'gb_')

# Help
Help(
  f"""
Modules:

- {'\n- '.join(module_targets)}

Projects:

- {'\n- '.join(project_targets)}

General targets:

- Pk3All: build packages for all mods
- TestAll: test all packages and modules
- LintAll: run org-lint for all Org files
- CheckCompatibility: check that all projects can be loaded together

Type 'scons <target>' to build a target.
""",
  append=False,
)
