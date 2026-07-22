# SPDX-FileCopyrightText: © 2025 Alexander Kromm <mmaulwurff@gmail.com>
# SPDX-License-Identifier: CC0-1.0

# This is build definitions for DoomToolbox.
# See https://scons.github.io/docs/scons-user.html for details.


import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import git
import reuse.project
import reuse.report
import SCons.Script
from SCons.Script import Alias, AlwaysBuild, Command, Depends, Glob

# General setup
SCons.Script.Decider('timestamp-match')
SCons.Script.Default(None)
SCons.Script.DefaultEnvironment(ENV=os.environ.copy())

emacs = (
  shutil.which('emacs-nox')
  or shutil.which('emacs')
  or Path('c:/tools/emacs/bin/emacs.exe')
)
uzdoom = (
  os.path.expanduser(os.environ['DT_ENGINE'])
  if 'DT_ENGINE' in os.environ
  else shutil.which('uzdoom')
)


# Common functions
def make_project_name(org_file):
  return os.path.splitext(os.path.basename(org_file))[0]


def make_export(source, prefix):
  build_el_path = os.path.abspath('tools/build.el')
  return f'{emacs} {source} --quick --batch \
    --load {build_el_path} \
    --eval "(dt-export \\"{prefix}\\")"'


# Target setup functions
def add_main_target(org_file, target_format):
  name = make_project_name(org_file)
  zscript_name = target_format.format(name)
  build_el_path = os.path.abspath('tools/build.el')
  tangle = f'{emacs} $SOURCE --quick --batch \
    --load {build_el_path} \
    --eval "(dt-tangle)"'

  return Alias(name, Command(target=zscript_name, source=org_file, action=tangle))


def add_test_target(org_file, main_target):
  name = make_project_name(org_file)
  test_name = f'{name}Test'

  def run_test(target, source, env):
    print('------------------------------------------------------------')

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
      shutil.copy('tools/config.ini', 'build/config.ini')

    # Script errors cause an error window to appear,
    # and execution waits for user to press the button.
    # To not bother with closing this window programmatically, just time out.
    try:
      result = subprocess.run(
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        args=args,
        timeout=60 * 3,
        check=True,
      )
    except subprocess.TimeoutExpired:
      print('timeout')
      return 1

    with open(
      'tools/IgnoredEngineOutput.txt', encoding='utf-8'
    ) as lines_to_skip_file:
      lines_to_skip = [line.rstrip() for line in lines_to_skip_file]

    def printable(line):
      return not any(re.search(to_skip, line) for to_skip in lines_to_skip)

    has_errors = False
    for line in filter(printable, result.stdout.splitlines()):
      line = re.sub(r'(.*)/:(.*), line (.*)', r'\1/\2:\3', line)
      line = re.sub(
        r'Script error, \"(.*)/:(.*)\" line (.*)', r'ERROR: \1/\2:\3', line
      )
      line = re.sub(
        r'Script warning, \"(.*)/:(.*)\" line (.*)', r'WARNING: \1/\2:\3', line
      )
      has_errors = has_errors or 'ERROR' in line or 'WARNING' in line
      print(line)

    return 1 if has_errors else 0

  return AlwaysBuild(Alias(test_name, main_target, run_test))


def read_meta(content):
  pattern = '^#[+]name: meta\n#[+]begin_src.*\n((?s:.)*?)#[+]end_src'
  meta_block = re.search(pattern, content, flags=re.MULTILINE)
  return json.loads(meta_block.group(1)) if meta_block else None


def extract_meta(org_file):
  with open(org_file, encoding='utf-8') as project_file:

    def read_whole():
      project_file.seek(0)
      return read_meta(project_file.read())

    meta = read_meta(project_file.read(512))
    return meta or read_whole()


def add_pack_target(org_file, main_target):
  name = make_project_name(org_file)
  pack_name = f'{name}.pk3'
  build_path = Path(f'build/{name}')

  def extract_version():
    meta = extract_meta(org_file)
    if meta and 'version' in meta:
      return f'v{meta["version"]}'
    else:
      return git.Repo().head.object.hexsha[:10]

  def pack(target, source, env):
    shutil.copytree(
      'documentation', build_path / 'documentation', dirs_exist_ok=True
    )
    shutil.copy(org_file, build_path / 'README.org')

    licenses_path = build_path / 'LICENSES'
    os.makedirs(licenses_path, exist_ok=True)
    project = reuse.project.Project.from_directory(build_path)
    report = reuse.report.ProjectReport.generate(project)
    for license in report.used_licenses:
      shutil.copy('LICENSES/' + license + '.txt', licenses_path)

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

    version = extract_version()
    archive = shutil.make_archive(
      Path(str(build_path) + '-' + version), 'zip', build_path
    )
    result_path = Path(archive).with_suffix('.pk3')
    shutil.move(archive, result_path)
    print(f'Created {result_path}')

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
      shutil.copy('tools/config.ini', 'build/config.ini')

    # Script errors cause an error window to appear,
    # and execution waits for user to press the button.
    # To not bother with closing this window programmatically, just time out.
    try:
      result = subprocess.run(
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        args=args,
        timeout=60 * 3,
        check=True,
      )
    except subprocess.TimeoutExpired:
      print('timeout')
      return 1

    with open(
      'tools/IgnoredEngineOutput.txt', encoding='utf-8'
    ) as lines_to_skip_file:
      lines_to_skip = [line.rstrip() for line in lines_to_skip_file]

    def printable(line):
      return not any(re.search(to_skip, line) for to_skip in lines_to_skip)

    for line in filter(printable, result.stdout.splitlines()):
      print(line)

    return 0

  return check_compatibility


def make_index(target, source, env):
  shutil.copy('README.html', 'index.html')


def pack_module(target, source, env):
  os.makedirs('build/modules', exist_ok=True)
  for one_source in source:
    shutil.copy(one_source.sources[0], 'build/modules')


def add_dependency(project, module, namespace):
  target_directory = f'build/{project}/zscript'
  destination = f'{target_directory}/{namespace}{module}.zs'

  def export_module(target, source, env):
    os.makedirs(target_directory, exist_ok=True)
    with (
      open(destination, 'w', encoding='utf-8') as target_file,
      open(source[0], encoding='utf-8') as module_file,
    ):
      target_file.write(module_file.read().replace('NAMESPACE_', namespace))

  Depends(
    project,
    Command(
      target=destination,
      source=f'build/{module}/{module}.zs',
      action=export_module,
    ),
  )


def setup_dependencies(org_file):
  meta = extract_meta(org_file)
  if meta and 'depends' in meta:
    for module, namespace in meta['depends'].items():
      add_dependency(make_project_name(org_file), module, namespace)


# Targets
compatibility_target = AlwaysBuild(
  Alias('CheckCompatibility', None, make_check_compatibility_target())
)
clematis_target = add_main_target('add-ons/ClematisM.org', 'build/{0}/zscript.zs')

test_targets = []
module_targets = []
module_targets_names = []
for org_file in Glob('modules/*.org'):
  main_target = add_main_target(org_file, 'build/{0}/{0}.zs')
  test_target = add_test_target(org_file, main_target)
  setup_dependencies(org_file)
  Depends(test_target, clematis_target)
  test_targets.append(test_target)
  module_targets_names.append(f'{main_target[0]}, {test_target[0]}')
  module_targets.append(main_target)

addon_targets_names = []
pack_targets = []
for org_file in Glob('add-ons/*.org'):
  main_target = add_main_target(org_file, 'build/{0}/zscript.zs')
  test_target = add_test_target(org_file, main_target)
  pack_target = add_pack_target(org_file, main_target)

  setup_dependencies(org_file)

  if org_file != 'ClematisM.org':
    Depends(test_target, clematis_target)

  test_targets.append(test_target)
  pack_targets.append(pack_target)
  addon_targets_names.append(f'{main_target[0]}, {test_target[0]}, {pack_target[0]}')
  Depends(compatibility_target, main_target)

html_targets = []
for org_file in Glob('*.org'):
  html_name = f'{os.path.splitext(org_file)[0]}.html'
  html_targets.append(
    Command(target=html_name, source=org_file, action=make_export(org_file, ''))
  )
for org_file in Glob('*/*.org'):
  html_name = f'{os.path.splitext(org_file)[0]}.html'
  html_targets.append(
    Command(target=html_name, source=org_file, action=make_export(org_file, '../'))
  )

AlwaysBuild(Alias('PackModules', module_targets, pack_module))
Alias('Pk3All', pack_targets, None)
Alias('TestAll', test_targets, None)
Alias('HtmlAll', html_targets, make_index)

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


SCons.Script.Help(
  f"""
Modules:

- {'\n- '.join(module_targets_names)}

Add-ons:

- {'\n- '.join(addon_targets_names)}

General targets:

- Pk3All: build packages for all add-ons
- TestAll: test all add-ons and modules
- LintAll: run org-lint for all Org files
- CheckCompatibility: check that all add-ons can be loaded together
- PackModules: pack all modules to build/modules directory

Type 'scons <target>' to build a target.
""",
  append=False,
)
