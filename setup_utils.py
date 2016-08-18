#!/usr/bin/env python
import os
import subprocess
import sys
from genericpath import isdir, exists
from os.path import join, isfile, abspath, dirname, relpath

import shutil
from pip.req import parse_requirements

import Utils
from Utils.call_process import run
from Utils.file_utils import which
from Utils.logger import critical, err, info
import Utils.logger
Utils.logger.is_debug = True


def init(name, package_name, setup_py_fpath):
    if abspath(dirname(setup_py_fpath)) != abspath(os.getcwd()):
        sys.stderr.write('Please, change to ' + dirname(setup_py_fpath) + ' before running setup.py\n')
        sys.exit()

    if sys.argv[-1] == 'tag':
        version = write_version_py(package_name)
        run_cmdl('git tag -a %s -m "Version %s"' % (version, version))
        run_cmdl('git push --tags')
        sys.exit()

    if sys.argv[-1] == 'publish':
        run_cmdl('python setup.py sdist upload')
        # _run('python setup.py bdist_wheel upload')
        sys.exit()

    if sys.argv[-1] == 'up':
        run_cmdl('git pull --recurse-submodules --rebase')
        # if first time: $ git submodule update --init --recursive
        run_cmdl('git submodule foreach "(git checkout master; git pull --rebase)"')
        sys.exit()

    if sys.argv[-1] == 'clean':
        clean_package(package_name, '.')
        sys.exit()

    if is_installing():
        version = write_version_py(package_name)
        print('''-----------------------------------
 Installing {name} version {version}
-----------------------------------
'''.format(name=name, version=version))

        info('Installing BEDtools')
        bedtools_fpath = install_bedtools()
        info('Using BedTools at ' + bedtools_fpath)

        info('Installing Sambamba')
        sambamba_fpath = install_sambamba()
        info('Using Sambamba at ' + sambamba_fpath)

        return version
    else:
        info('Running setup command: ' + sys.argv[-1])


def clean_package(package_name, dirpath='.'):
    print('Cleaning up binary, build and dist for ' + package_name + ' in ' + dirpath + '...')
    if isdir(join(dirpath, 'build')):
        shutil.rmtree(join(dirpath, 'build'))
    if isdir(join(dirpath, 'dist')):
        shutil.rmtree(join(dirpath, 'dist'))
    if isdir(join(dirpath, package_name + '.egg-info')):
        shutil.rmtree(join(dirpath, package_name + '.egg-info'))
    print('Done.')


def get_reqs():
    try:
        from pip.download import PipSession
    except ImportError:  # newer setuptools
        install_reqs = parse_requirements('requirements.txt')
    else:
        install_reqs = parse_requirements('requirements.txt', session=PipSession())
    reqs = [str(ir.req) for ir in install_reqs]
    return reqs


def find_package_files(dirpath, package, skip_exts=None):
    paths = []
    for (path, dirs, fnames) in os.walk(join(package, dirpath)):
        for fname in fnames:
            if skip_exts and any(fname.endswith(ext) for ext in skip_exts):
                continue
            fpath = join(path, fname)
            paths.append(relpath(fpath, package))
    return paths


''' Versioning:
1. Write each version to VERSION.txt
2. If the changes are significant, tag the release and push the new tag:
   $ python setup.py tag '''
def write_version_py(package_name):
    version_txt = 'VERSION.txt'
    with open(version_txt) as f:
        v = f.read().strip().split('\n')[0]

    try:
        import subprocess
        git_revision = subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD']).rstrip()
    except:
        git_revision = ''
        pass

    version_py = os.path.join(package_name, 'version.py')
    with open(version_py, 'w') as f:
        f.write((
            '# Do not edit this file, pipeline versioning is governed by git tags\n' +
            '__version__ = \'' + v + '\'\n' +
            '__git_revision__ = \'' + git_revision + '\''))
    return v


def run_cmdl(_cmd):
    print('$ ' + _cmd)
    os.system(_cmd)


def is_installing():
    return sys.argv[-1] in ['install', 'develop', 'build', 'build_ext']


def is_cleaning():
    return sys.argv[-1] in ['clean']


def compile_tool(tool_name, dirpath, requirements):
    if not all(isfile(join(dirpath, req)) for req in requirements):
        info('Compiling ' + tool_name)
        run('make -C ' + dirpath)
        if not all(isfile(join(dirpath, req)) for req in requirements):
            err('Failed to compile ' + tool_name + ' (' + dirpath + ')\n')
            return False
    return True


utils_package_name = 'Utils'


def get_utils_package_files():
    return [
        relpath(Utils.bedtools_execuable_fpath, utils_package_name),
        relpath(Utils.sambamba_executable_path, utils_package_name),
        'bedtools/*.py',
        'sambamba/*.py',
    ] + find_package_files('reporting', utils_package_name, skip_exts=['.sass', '.coffee', '.map'])\
      + find_package_files('reference_data', utils_package_name, skip_exts=['ga4gh_tricky_regions.zip'])


def install_sambamba():
    path = Utils.sambamba_executable_path
    if exists(path):
        return path
    elif exists(path + '.gz'):
        info('Gunzipping sambamba ' + path + '.gz')
        os.system('gunzip ' + path + '.gz')
        return path

    err('Could not find sambamba ' + path + '(.gz): the ' + dirname(path) +
        ' contents is ' + str(os.listdir(path)))
    sys_fpath = which('sambamba')
    if sys_fpath:
        err('Using sambamba found in $PATH: ' + sys_fpath)
        return sys_fpath
    else:
        critical('Error: sambamba was not found in ' + Utils.sambamba_bin_dirpath +
                 ' or in $PATH')


def install_bedtools():
    success_compilation = compile_tool('BEDtools', Utils.bedtools_dirpath, [Utils.bedtools_execuable_fpath])
    if success_compilation:
        return Utils.bedtools_execuable_fpath
    sys_bedtools_fpath = which('bedtools')
    if sys_bedtools_fpath:
        err('Compilation failed, using bedtools in $PATH: ' + sys_bedtools_fpath)
        return sys_bedtools_fpath
    else:
        critical('Compilation of BEDtools at ' + Utils.bedtools_dirpath +
                 ' failed, and no bedtools found in $PATH')