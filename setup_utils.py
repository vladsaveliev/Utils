#!/usr/bin/env python
import os
import subprocess
import sys
from genericpath import isdir
from os.path import join, isfile, abspath, dirname, relpath
from sys import platform as sys_platform
import platform

import shutil
from pip.req import parse_requirements


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
        print('Cleaning up binary, build and dist...')
        if isdir('build'):
            shutil.rmtree('build')
        if isdir('dist'):
            shutil.rmtree('dist')
        if isdir(package_name + '.egg-info'):
            shutil.rmtree(package_name + '.egg-info')
        print('Done.')
        sys.exit()

    if is_installing():
        version = write_version_py(package_name)
        print('''-----------------------------------
 Installing {} version {}
-----------------------------------
'''.format(name, version))
        return version


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


def compile_tool(tool_name, dirpath, requirements):
    if not all(isfile(join(dirpath, req)) for req in requirements):
        print('Compiling ' + tool_name)
        return_code = subprocess.call(['make', '-C', dirpath])
        if return_code != 0 or not all(isfile(join(dirpath, req)) for req in requirements):
            sys.stderr.write('Failed to compile ' + tool_name + ' (' + dirpath + ')\n')
            return False
    return True


def which(program):
    """
    returns the path to an executable or None if it can't be found
    """
    def is_exe(_fpath):
        return os.path.isfile(_fpath) and os.access(_fpath, os.X_OK)

    fpath, fname = os.path.split(program)
    if fpath:
        if is_exe(program):
            return program
    else:
        for path in os.environ["PATH"].split(os.pathsep):
            exe_file = os.path.join(path, program)
            if is_exe(exe_file):
                return exe_file
    return None


utils_package_name = 'Utils'

def get_sambamba_executable():
    sambamba_dirpath = join(utils_package_name, 'sambamba_binaries')
    if 'darwin' in sys_platform:
        path = join(sambamba_dirpath, 'sambamba_osx')
    elif 'redhat' in platform.dist():
        path = join(sambamba_dirpath, 'sambamba_centos')
    else:
        path = join(sambamba_dirpath, 'sambamba_lnx')
    if isfile(path):
        return path
    elif isfile(path + '.gz'):
        print('gunzipping sambamba ' + path + '.gz')
        os.system('gunzip ' + path + '.gz')
        return path
    else:
        sys.stderr.write('Error: could not find sambamba ' + path + '(.gz)')

def get_utils_package_files():
    return [
        relpath(get_sambamba_executable(), utils_package_name),
        'bedtools/bedtools2/bin/*',
    ] + find_package_files('reporting', utils_package_name, skip_exts=['.sass', '.coffee', '.map'])\
      + find_package_files('reference_data', utils_package_name)
