# SPDX-FileCopyrightText: © 2025 Alexander Kromm <mmaulwurff@gmail.com>
# SPDX-License-Identifier: CC0-1.0

# Build definitions for DoomToolbox.
# See https://scons.github.io/docs/scons-user.html for details.


import csv
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import git
import pyttsx3
import reuse.project
import reuse.report
import SCons.Script
from ffmpeg import FFmpeg
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
engine = (
  Path(os.environ['DT_ENGINE']).expanduser()
  if 'DT_ENGINE' in os.environ
  else shutil.which('uzdoom')
)
build_el_path = Path('tools/build.el').resolve()


# Common functions
def make_project_name(org_file):
  return Path(org_file).stem


def make_export(source, prefix):
  return f'{emacs} {source} --quick --batch \
    --load {build_el_path} \
    --eval "(dt-export \\"{prefix}\\")"'


# Target setup functions
def add_main_target(org_file, target_format):
  zscript_name = target_format.format(make_project_name(org_file))
  tangle = f'{emacs} $SOURCE --quick --batch \
    --load {build_el_path} \
    --eval "(dt-tangle)"'

  return Command(target=zscript_name, source=org_file, action=tangle)


def add_test_target(org_file, main_target):
  name = make_project_name(org_file)
  test_name = f'{name}Test'

  def run_test(target, source, env):
    print('------------------------------------------------------------')

    args = [
      engine,
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
        check=False,
      )
    except subprocess.TimeoutExpired:
      print('timeout')
      return 1

    with Path.open(
      'tools/IgnoredEngineOutput.txt',
      encoding='utf-8',
    ) as lines_to_skip_file:
      lines_to_skip = [line.rstrip() for line in lines_to_skip_file]

    def printable(line):
      return not any(re.search(to_skip, line) for to_skip in lines_to_skip)

    has_errors = False
    for line in filter(printable, result.stdout.splitlines()):
      line = re.sub(r'(.*)/:(.*), line (.*)', r'\1/\2:\3', line)
      line = re.sub(
        r'Script error, \"(.*)/:(.*)\" line (.*)',
        r'ERROR: \1/\2:\3',
        line,
      )
      line = re.sub(
        r'Script warning, \"(.*)/:(.*)\" line (.*)',
        r'WARNING: \1/\2:\3',
        line,
      )
      has_errors = has_errors or 'ERROR' in line or 'WARNING' in line
      print(line)

    return 1 if has_errors else 0

  return AlwaysBuild(Alias(test_name, main_target, run_test))


def read_org_block(block_name, content):
  pattern = f'^#[+]name: {block_name}\n#[+]begin_src.*\n((?s:.)*?)#[+]end_src'
  meta_block = re.search(pattern, content, flags=re.MULTILINE)
  return json.loads(meta_block.group(1)) if meta_block else None


def extract_meta(org_file):
  with Path.open(org_file, encoding='utf-8') as project_file:

    def read_whole():
      project_file.seek(0)
      return read_org_block('meta', project_file.read())

    meta = read_org_block('meta', project_file.read(512))
    return meta or read_whole()


def add_pack_target(org_file, main_target):
  name = make_project_name(org_file)
  pack_name = f'{name}.pk3'
  build_path = Path(f'build/{name}')

  def extract_version():
    meta = extract_meta(org_file)
    if meta and 'version' in meta:
      return f'v{meta["version"]}'
    return git.Repo().head.object.hexsha[:10]

  def pack(target, source, env):
    shutil.copytree(
      'documentation',
      build_path / 'documentation',
      dirs_exist_ok=True,
    )
    shutil.copy(org_file, build_path / 'README.org')

    licenses_path = build_path / 'LICENSES'
    Path(licenses_path).mkdir(parents=True, exist_ok=True)
    project = reuse.project.Project.from_directory(build_path)
    report = reuse.report.ProjectReport.generate(project)
    for used_license in report.used_licenses:
      shutil.copy('LICENSES/' + used_license + '.txt', licenses_path)

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
        ],
      )

    version = extract_version()
    archive = shutil.make_archive(
      Path(str(build_path) + '-' + version),
      'zip',
      build_path,
    )
    result_path = Path(archive).with_suffix('.pk3')
    shutil.move(archive, result_path)
    print(f'Created {result_path}')

  return AlwaysBuild(Alias(pack_name, main_target, pack))


def make_check_compatibility_target():
  names = [make_project_name(org_file) for org_file in Glob('add-ons/*.org')]
  projects = ['./build/' + name for name in names]

  def check_compatibility(target, source, env):
    args = [
      engine,
      '-noautoload',
      '-nosound',
      '-config',
      './build/config.ini',
      '-iwad',
      './tools/miniwad.wad',
      (
        '+wait 2; map map01;'
        ' wait 2; summon doomimp;'
        ' wait 2; save test;'
        ' wait 2; load test;'
        ' wait 2; quit'
      ),
      '-file',
      *projects,
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
        check=False,
      )
    except subprocess.TimeoutExpired:
      print('timeout')
      return 1

    with Path.open(
      'tools/IgnoredEngineOutput.txt',
      encoding='utf-8',
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
  Path('build/modules').mkdir(parents=True, exist_ok=True)
  for one_source in source:
    shutil.copy(one_source.sources[0], 'build/modules')


def add_dependency(main_target, project, module, namespace):
  target_directory = f'build/{project}/zscript'
  destination = f'{target_directory}/{namespace}{module}.zs'

  def export_module(target, source, env):
    Path(target_directory).mkdir(parents=True, exist_ok=True)
    with (
      Path.open(destination, 'w', encoding='utf-8') as target_file,
      Path.open(source[0], encoding='utf-8') as module_file,
    ):
      target_file.write(module_file.read().replace('NAMESPACE_', namespace))

  Depends(
    main_target,
    Command(
      target=destination,
      source=f'build/{module}/{module}.zs',
      action=export_module,
    ),
  )


def setup_dependencies(main_target, org_file):
  meta = extract_meta(org_file)
  if meta and 'depends' in meta:
    for module, namespace in meta['depends'].items():
      add_dependency(main_target, make_project_name(org_file), module, namespace)


def add_autoautosave_generate_sounds_target():
  sound_directory = 'build/Autoautosave/sounds'

  def generate(target, source, env):
    sound_engine = pyttsx3.init()
    Path(sound_directory).mkdir(parents=True, exist_ok=True)

    sound_engine.setProperty('rate', 140)
    sound_engine.setProperty('pitch', 0)
    sound_engine.setProperty('voice', 'storm')

    with Path.open(
      'build/Autoautosave/events.json',
      encoding='utf-8',
    ) as events_file:
      events = json.load(events_file)

    for index, text in events.items():
      wav_name = f'build/Autoautosave/sounds/aas{index}.wav'
      ogg_name = f'build/Autoautosave/sounds/aas{index}.ogg'

      sound_engine.save_to_file(text, wav_name)
      sound_engine.runAndWait()
      Path(ogg_name).unlink(missing_ok=True)
      print(f'Converting to {ogg_name}...')
      FFmpeg().input(wav_name).output(ogg_name).execute()
      Path(wav_name).unlink()

    sound_engine.stop()

  return Command(sound_directory, 'add-ons/Autoautosave.org', generate)


def make_translations_target(org_file):
  name = make_project_name(org_file)
  source_language_paths = Glob(f'translations/{name}/*.csv')

  if len(source_language_paths) == 0:
    return None

  language_map = {
    'cs_CZ': 'cs',  # Czech
    'de_DE': 'de',  # German
    'en_GB': 'eng',  # English (UK)
    'en_US': 'default',  # English (US)
    'eo': 'eo',  # Esperanto
    'es_419': 'esm',  # Latin American Spanish
    'es_ES': 'es',  # Castilian Spanish
    'fi_FI': 'fi',  # Finnish
    'fr_FR': 'fr',  # French
    'hu_HU': 'hu',  # Hungarian
    'it_IT': 'it',  # Italian
    'ja_JP': 'jp',  # Japanese
    'ko_KR': 'ko',  # Korean
    'nl_NL': 'nl',  # Dutch
    'pl_PL': 'pl',  # Polish
    'pt_BR': 'pt',  # Brazilian Portuguese
    'pt_PT': 'ptg',  # European Portuguese
    'ro_RO': 'ro',  # Romanian
    'ru_RU': 'ru',  # Russian
    'sr_RS': 'sr',  # Serbian
    'uk_UA': 'uk',  # Ukrainian
  }
  target_language_path = Path(f'build/{name}/language.csv')
  target_field_names = [
    'default',
    'Identifier',
    'Remarks',
    *[language_map[Path(path).stem] for path in source_language_paths],
  ]
  del target_field_names[target_field_names.index('default', 1)]

  def generate(target, source, env):
    authors = set()
    licenses = set()
    rows = {}

    for source_language_path in source_language_paths:
      with Path.open(
        source_language_path, 'r', newline='', encoding='utf-8'
      ) as source_language_file:
        csv_reader = csv.DictReader(source_language_file)
        for row in csv_reader:
          string_id = row['context']
          string = row['target']
          if re.match('c[0-9]*', string_id):
            authors.add(string)
          elif string_id == 'i':
            licenses.add(string)
          else:
            rows[string_id] = rows.get(string_id, {})
            rows[string_id]['Identifier'] = string_id
            rows[string_id][language_map[Path(source_language_path).stem]] = string

    with Path.open(
      target_language_path, 'w', newline='', encoding='utf-8'
    ) as target_language_file:
      csv_writer = csv.DictWriter(target_language_file, target_field_names)
      csv_writer.writeheader()
      # Hack: CSV doesn't have comments. REUSE wants \n after SPDX lines.
      # Put SPDX in the last column.
      for author in authors:
        csv_writer.writerow({target_field_names[-1]: author})
      for a_license in licenses:
        csv_writer.writerow({target_field_names[-1]: a_license})
      for row in rows.values():
        csv_writer.writerow(row)

  return Command(target_language_path, [org_file, *source_language_paths], generate)


# Targets
compatibility_target = AlwaysBuild(
  Alias('CheckCompatibility', None, make_check_compatibility_target()),
)
clematis_target = Alias(
  'ClematisM',
  add_main_target('add-ons/ClematisM.org', 'build/{0}/zscript.zs'),
)

test_targets = []
module_targets = []
module_targets_names = []
for org_file in Glob('modules/*.org'):
  name = make_project_name(org_file)
  main_target = Alias(name, add_main_target(org_file, 'build/{0}/{0}.zs'))
  test_target = add_test_target(org_file, main_target)
  setup_dependencies(main_target, org_file)
  Depends(test_target, clematis_target)
  test_targets.append(test_target)
  module_targets_names.append(f'{main_target[0]}, {test_target[0]}')
  module_targets.append(main_target)

addon_targets_names = []
pack_targets = []
for org_file in Glob('add-ons/*.org'):
  name = make_project_name(org_file)
  main_target = add_main_target(org_file, 'build/{0}/zscript.zs')

  if str(org_file) == 'add-ons/Autoautosave.org':
    generate_sounds_target = add_autoautosave_generate_sounds_target()
    Depends(generate_sounds_target, main_target)
    Alias('Autoautosave', generate_sounds_target)
    main_target = generate_sounds_target
  else:
    Alias(name, main_target)

  test_target = add_test_target(org_file, main_target)
  pack_target = add_pack_target(org_file, main_target)

  setup_dependencies(main_target, org_file)

  if str(org_file) != 'add-ons/ClematisM.org':
    Depends(test_target, clematis_target)

  test_targets.append(test_target)
  pack_targets.append(pack_target)
  addon_targets_names.append(f'{name}, {test_target[0]}, {pack_target[0]}')
  Depends(compatibility_target, main_target)

  Depends(main_target, make_translations_target(org_file))

html_targets = []
for org_file in Glob('*.org'):
  path = Path(org_file)
  html_name = f'{path.parent}{path.stem}.html'
  html_targets.append(
    Command(target=html_name, source=org_file, action=make_export(org_file, '')),
  )
for org_file in Glob('*/*.org'):
  path = Path(org_file)
  html_name = f'{path.parent}{path.stem}.html'
  html_targets.append(
    Command(target=html_name, source=org_file, action=make_export(org_file, '../')),
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
  ),
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
