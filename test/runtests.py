#!/usr/bin/env python3

import os
import shutil
import subprocess
import sys


class UserException(Exception):
    """ An exception used for reporting user-triggered errors. """


def default_target():
    """ Return the default target. """

    if sys.platform.startswith('linux'):
        target = 'linux-64'
    elif sys.platform == 'win32':
        # MSVC2015 is v14, MSVC2017 is v15, MSVC2019 is v16.
        vs_major = os.environ.get('VisualStudioVersion', '0.0').split('.')[0]

        if vs_major == '0':
            # If there is no development environment then use the host
            # platform.
            from distutils.util import get_platform

            is_32 = (get_platform() == 'win32')
        elif vs_major == '14':
            is_32 = (os.environ.get('Platform') != 'X64')
        else:
            is_32 = (os.environ.get('VSCMD_ARG_TGT_ARCH') != 'x64')

        target = 'win-' + ('32' if is_32 else '64')
    elif sys.platform == 'darwin':
        target = 'macos-64'
    else:
        raise UserException("unsupported host platform")

    return target


def find_tests(test, target):
    """ Return a 2-tuple of test files and expected results for a target. """

    tests = []

    if test is None:
        test = os.path.join(os.path.dirname(__file__), 'tests')

    if os.path.isfile(test):
        tests.append((test, False))
    elif os.path.isdir(test):
        for dirpath, _, filenames in os.walk(test):
            # See if there is a file describing the tests expected to fail for
            # a particular platform.
            expected_fails = {}

            expected_fails_file = os.path.join(dirpath, 'ExpectedFails')
            if os.path.isfile(expected_fails_file):
                with open(expected_fails_file) as ef_f:
                    for line in ef_f:
                        line = line.strip()

                        # Ignore comments.
                        if line.startswith('#'):
                            continue

                        # We just ignore bad lines.
                        parts = line.split(':')
                        if len(parts) != 2:
                            continue

                        test_file = parts[0].strip()
                        if test_file == '':
                            continue

                        expected_fails[test_file] = parts[1].strip().split()

            for fn in filenames:
                tests.append(
                        (os.path.join(dirpath, fn),
                                expected_fails.get(fn, False)))
    else:
        raise UserException("unknown test '{0}'".format(test))

    return sorted(tests)


class TestCase:
    """ Encapsulate a test for a particular target. """

    def __init__(self, test, expected_fail, target):
        """ Initialise the object. """

        self.test = test
        self.expected_fail = expected_fail
        self.target = target

    @staticmethod
    def call(args, verbose, failure_message):
        """ Call a sub-process. """

        if verbose:
            print("Running: '{}'".format(' '.join(args)))

        error = False

        try:
            with subprocess.Popen(args, stderr=subprocess.PIPE, stdout=subprocess.PIPE, universal_newlines=True) as process:
                try:
                    line = process.stdout.readline()

                    while line:
                        if verbose:
                            print(line.rstrip())

                        line = process.stdout.readline()

                    stderr = process.stderr.read().rstrip()
                    if stderr:
                        print(stderr)

                    retcode = process.wait()
                    if retcode != 0:
                        if expected_fail:
                            print(failure_message + " as expected")
                        else:
                            print("Returned exit code {}".format(retcode))
                            error = True

                except Exception as e:
                    print(process.stderr.read().rstrip())
                    process.kill()
                    error = True

        except Exception as e:
            print(str(e))
            error = True

        if error:
            raise UserException(failure_message)

    def run(self, python, qmake, no_clean, verbose):
        """ Re-implemented to run a test. """

        raise NotImplementedError


class SysrootTest(TestCase):
    """ Encapsulate a pyqtdeploy-sysroot test for a particular target. """

    # The filename extension of pyqtdeploy-sysroot tests.
    test_extension = '.toml'

    def run(self, python, qmake, no_clean, verbose):
        """ Run a pyqtdeploy-sysroot test. """

        print("Building sysroot from {}".format(self.test))

        # The name of the sysroot directory to be built.
        test_name = os.path.basename(self.test)
        if test_name.endswith(self.test_extension):
            test_name = test_name[:-len(self.test_extension)]

        # Run pyqtdeploy-sysroot.
        args = ['pyqtdeploy-sysroot']

        if no_clean:
            args.append('--no-clean')

        if verbose:
            args.append('--verbose')

        if python is not None:
            args.extend(['--python', python])

        if qmake is not None:
            args.extend(['--qmake', qmake])

        args.extend(['--target', self.target])
        args.extend(['--sysroots-dir', os.path.join('sysroot', test_name)])
        args.append(self.test)

        self.call(args, verbose,
                "Build of sysroot from {} failed".format(self.test))

        if not self.expected_fail:
            print("Build of sysroot from {} successful".format(self.test))


class BuildTest(TestCase):
    """ Encapsulate a pyqtdeploy-build test for a particular target. """

    # The filename extension of pyqtdeploy-build tests.
    test_extension = '.pdt'

    def run(self, python, qmake, no_clean, verbose):
        """ Run a pyqtdeploy-build test. """

        print("Building application from {}".format(self.test))

        # Run pyqtdeploy-build.
        args = ['pyqtdeploy-build']

        if no_clean:
            args.append('--no-clean')

        if verbose:
            args.append('--verbose')

        if python is not None:
            args.extend(['--python', python])

        if qmake is not None:
            args.extend(['--qmake', qmake])

        args.extend(['--target', self.target])
        args.append(self.test)

        self.call(args, verbose,
                "pyqtdeploy-build using {} failed".format(self.test))

        # Change to the build directory and run qmake and make.
        build_dir = 'build-' + self.target
        make = 'nmake' if sys.platform == 'win32' else 'make'

        os.chdir(build_dir)

        self.call([qmake], verbose, "qmake failed")
        self.call([make], verbose, "make failed")

        # Run the test if it is native.
        target = self.target.split('-')[0]

        if target in ('linux', 'macos', 'win'):
            test_name = os.path.basename(self.test)

            executable = os.getcwd()
            if target == 'win':
                executable = os.path.join(executable, 'release')

            if test_name.startswith('stdlib_'):
                executable = os.path.join(executable, 'python_stdlib')

                # Map tests to packages for non-trivial packages.
                test_package_map = {'expat': 'xml.parsers.expat'}

                test_package = self.test.split('_')[1].split('.')[0]
                test_package = test_package_map.get(test_package, test_package)
                args = [executable, test_package]
            else:
                executable = os.path.join(executable, test_name.split('.')[0])
                args = [executable]

            self.call(args, verbose, executable + " failed")

        os.chdir('..')

        if not no_clean:
            shutil.rmtree(build_dir)

        if not self.expected_fail:
            print("Build of application from {} successful".format(self.test))


def run_command(*args):
    """ Run a command and return the output. """

    error = None
    stdout = []

    try:
        with subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True) as process:
            try:
                while process.poll() is None:
                    line = process.stdout.readline()
                    if not line:
                        continue

                    stdout.append(line)

                if process.returncode != 0:
                    error = "returned exit code {}".format(process.returncode)

            except Exception as e:
                process.kill()
    except Exception as e:
        error = str(e)

    if error:
        raise UserException(
                "Execution of '{0}' failed: {1}".format(args[0], error))

    return ''.join(stdout).strip()


if __name__ == '__main__':

    import argparse

    # Parse the command line.
    parser = argparse.ArgumentParser()

    parser.add_argument('--no-clean',
            help="do not remove the temporary build directories",
            action='store_true')
    parser.add_argument('--python',
            help="the python executable when using an existing Python "
                    "installation",
            metavar="FILE")
    parser.add_argument('--qmake',
            help="the qmake executable when using an existing Qt installation",
            metavar="FILE")
    parser.add_argument('--show', help="show the tests that would be run",
            action='store_true')
    parser.add_argument('--test',
            help="a test directory, TOML specification file or project file")
    parser.add_argument('--target', help="the target platform")
    parser.add_argument('--verbose', help="enable verbose progress messages",
            action='store_true')

    args = parser.parse_args()

    # Convert to absolute paths.
    python = os.path.abspath(args.python) if args.python else 'python'
    qmake = os.path.abspath(args.qmake) if args.qmake else None

    # Anchor everything from the directory containing this script.
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    try:
        # Determine the version numbers of any existing Python and Qt
        # installations.
        python_version = run_command(python, '-c',
                'import sys; print(sys.version.split()[0])')

        os.environ['PYTHON_VERSION'] = python_version
        if args.verbose:
            print("Existing Python installation is v{0}".format(python_version))

        if qmake is not None:
            for line in run_command(qmake, '-query').split():
                parts = line.split(':')
                if len(parts) == 2 and parts[0] == 'QT_VERSION':
                    qt_version = parts[1]
                    break
            else:
                raise UserException(
                        "unable to determine Qt version number from {0}".format(
                                qmake))

            os.environ['QT_VERSION'] = qt_version
            if args.verbose:
                print("Existing Qt installation is v{0}".format(qt_version))

        # Run the tests.
        if args.target:
            target = args.target
        else:
            target = default_target()

        tests = find_tests(args.test, target)

        # Any sysroot tests must be run first.
        for test, expected_fail in tests:
            if test.endswith(SysrootTest.test_extension):
                if args.show:
                    print(test + " (expected to fail)" if expected_fail else '')
                else:
                    SysrootTest(test, expected_fail, target).run(python, qmake,
                            args.no_clean, args.verbose)

        for test, expected_fail in tests:
            if test.endswith(BuildTest.test_extension):
                if args.show:
                    print(test + " (expected to fail)" if expected_fail else '')
                else:
                    BuildTest(test, expected_fail, target).run(python, qmake,
                            args.no_clean, args.verbose)

    except UserException as e:
        print(e)
        sys.exit(1)
