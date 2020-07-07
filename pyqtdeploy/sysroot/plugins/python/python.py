# Copyright (c) 2020, Riverbank Computing Limited
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
# 
# 1. Redistributions of source code must retain the above copyright notice,
#    this list of conditions and the following disclaimer.
# 
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
# 
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.


import os
import shutil
import sys

from .... import AbstractPythonComponent, ComponentOption

from .pyconfig import generate_pyconfig_h
from .standard_library import standard_library


# The latest tested patch releases of each minor version.
LATEST_3_5_RELEASE = (3, 5, 9)
LATEST_3_6_RELEASE = (3, 6, 11)
LATEST_3_7_RELEASE = (3, 7, 8)


class PythonComponent(AbstractPythonComponent):
    """ The host and target Python component. """

    # The list of components that, if specified, should be installed before
    # this one.  Note that we don't need to specify things like 'OpenSSL' as
    # these are only used by this component when building the application and
    # not the sysroot.
    preinstalls = ['Qt']

    # The dict of VersionedModule objects provided by the component.
    provides = standard_library

    def __init__(self, *args, **kwargs):
        """ Initialise the component. """

        super().__init__(*args, **kwargs)

        self._host_python = None

    def get_archive_name(self):
        """ Return the filename of the source archive. """

        return 'Python-{}.tgz'.format(self.version)

    def get_archive_urls(self):
        """ Return the list of URLs where the source archive might be
        downloaded from.
        """

        return ['https://www.python.org/ftp/python/{}/'.format(self.version)]

    def get_options(self):
        """ Return a list of ComponentOption objects that define the components
        configurable options.
        """

        options = super().get_options()

        options.append(
                ComponentOption('dynamic_loading', type=bool,
                        help="Set to enable support for the dynamic loading "
                                "of extension modules when building from "
                                "source."))

        options.append(
                ComponentOption('install_host_from_source', type=bool,
                        default=True,
                        help="Install the host Python from a source package "
                                "rather than an existing installation."))

        return options

    @property
    def host_python(self):
        """ The full pathname of the host python executable. """

        if self._host_python is None:
            if self.host_platform_name == 'win':
                self._host_python = self._get_python_install_path()
            else:
                self._host_python = self.find_exe(self._py_subdir)

        return self._host_python

    @host_python.setter
    def host_python(self, value):
        """ Set the full pathname of the host python executable. """

        self._host_python = value

    def install(self):
        """ Install for the host and target. """

        # Install the host installation.
        if self.install_host_from_source:
            interpreter = self._install_host_from_source()

        # Install the target installation.
        if self.install_from_source:
            self._install_target_from_source()
        else:
            self._install_target_from_existing_windows_version()

        self.host_python = os.path.join(self.host_dir, 'bin',
                'python{}.{}'.format(self.version.major, self.version.minor))

    @property
    def target_py_include_dir(self):
        """ The name of the directory containing target Python header files.
        """

        return os.path.join(self.target_include_dir, self._py_subdir)

    @property
    def target_py_lib(self):
        """ The name of the target Python library. """

        lib = self._py_subdir

        if self.version <= (3, 7):
            lib += 'm'

        return lib

    @property
    def target_py_stdlib_dir(self):
        """ The name of the directory containing target Python standard
        library.
        """

        return os.path.join(self.target_lib_dir, self._py_subdir)

    @property
    def target_sitepackages_dir(self):
        """ The name of the target Python site-packages directory. """

        return os.path.join(self.target_lib_dir, self._py_subdir,
                'site-packages')

    def verify(self):
        """ Verify the component. """

        if self.version < (3, 5):
            self.unsupported()

        if self.version == (3, 5):
            if self.version > LATEST_3_5_RELEASE:
                self.untested()
        elif self.version == (3, 6):
            if self.version > LATEST_3_6_RELEASE:
                self.untested()
        elif self.version == (3, 7):
            if self.version > LATEST_3_7_RELEASE:
                self.untested()
        else:
            self.unsupported()

        if self.install_host_from_source:
            if self.host_platform_name == 'win':
                self.error(
                        "installing the host Python from a source package on "
                        "Windows is not supported")
        else:
            # Check that the host installation is the right version.
            host_version_str = self.run(self.host_python, '-c',
                    'import sys; print(sys.version.split()[0])', capture=True)

            host_version = self.parse_version_number(host_version_str)

            # The patch version shouldn't matter.
            if self.version.major != host_version.major or self.version.minor != host_version.minor:
                self.error(
                        "v{0} is specified but the host installation is "
                                "v{1}".format(self.version, host_version))

        if self.install_from_source:
            # Make sure Qt is specified.
            self.get_component('Qt')

            # Check the OpenSSL support.
            openssl = self.get_component('OpenSSL', required=False)
            if openssl is None:
                self._has_openssl = False
            else:
                if self.version >= (3, 8):
                    if openssl.version < (1, 1, 1):
                        self.error(
                                "v{0} requires OpenSSL v1.1.1".format(
                                        self.version))
                elif self.version >= (3, 7, 4):
                    if (1, 1, 0) > openssl.version > (1, 1, 1):
                        self.error(
                                "v{0} requires OpenSSL v1.1.0 or "
                                        "v1.1.1".format(self.version))
                elif self.version == (3, 7):
                    if openssl.version != (1, 1, 0):
                        self.error(
                                "v{0} requires OpenSSL v1.1.0".format(
                                        self.version))
                else:
                    if openssl.version != (1, 0, 2):
                        self.error(
                                "v{0} requires OpenSSL v1.0.2".format(
                                        self.version))

                self._has_openssl = True
        elif self.host_platform_name != 'win':
            self.error(
                    "using an existing Python installation for the target is "
                    "not supported on {0}".format(self.target_platform_name))

            # A standard Python builds support OpenSSL.
            self._has_openssl = True

        if self.target_platform_name == 'android':
            if self.version < (3, 6):
                self.error(
                        "v{0} is not supported on Android".format(
                                self.version))

            if self.android_api < 21:
                self.error("Android API level 21 or greater is required")

    def _configure_python(self):
        """ Configure a Python source directory for a particular target. """

        self.progress(
                "Configuring Python v{0} for {1}".format(self.version,
                        self.target_arch_name))

        py_src_dir = os.getcwd()

        configurations_dir = os.path.join(os.path.dirname(__file__),
                'configurations')

        # Copy the modules config.c file.
        config_c_src_file = 'config_py{0}.c'.format(self.version.major)
        config_c_dst_file = os.path.join(py_src_dir, 'Modules', 'config.c')

        self.progress("Installing {0}".format(config_c_dst_file))

        self.copy_file(os.path.join(configurations_dir, config_c_src_file),
                config_c_dst_file)

        # Generate the pyconfig.h file.  We follow the Python approach of a
        # static version for Windows and a dynamically created version for
        # other platforms.
        pyconfig_h_dst_file = os.path.join(py_src_dir, 'pyconfig.h')

        if self.target_platform_name == 'win':
            self.progress("Installing {0}".format(pyconfig_h_dst_file))

            # Find the pyconfig.h file appropriate for this version of Python.
            pyconfig_dir = os.path.join(configurations_dir, 'pyconfig')
            pyconfig = None
            pyconfig_version = None

            for fn in os.listdir(pyconfig_dir):
                version = fn.split('-')[-1]
                if version.endswith('.h'):
                    version = version[:-2]

                try:
                    version = self.parse_version_number(version)
                except UserException:
                    continue

                if version > self.version:
                    # This is for a later version so we can ignore it.
                    continue

                if pyconfig is None or pyconfig_version < version:
                    # This is a better candidate than any we have so far.
                    pyconfig = fn
                    pyconfig_version = version

            assert pyconfig is not None

            self.copy_file(os.path.join(pyconfig_dir, pyconfig),
                    pyconfig_h_dst_file, macros={
                        '@PY_DYNAMIC_LOADING@': '#define' if self.dynamic_loading else '#undef'})

            # Rename these otherwise MSVC confuses them with the ones we want
            # to use.
            pc_src_dir = os.path.join(py_src_dir, 'PC')

            for name in ('config.c', 'pyconfig.h'):
                try:
                    os.rename(os.path.join(pc_src_dir, name),
                            os.path.join(pc_src_dir, name + '.orig'))
                except FileNotFoundError:
                    pass
        else:
            self.progress("Generating {0}".format(pyconfig_h_dst_file))

            generate_pyconfig_h(pyconfig_h_dst_file, self)

        # Copy the python.pro file.
        python_pro_dst_file = os.path.join(py_src_dir, 'python.pro')

        self.progress("Installing {0}".format(python_pro_dst_file))

        self.copy_file(os.path.join(configurations_dir, 'python.pro'),
                python_pro_dst_file, macros={
                    '@PY_MAJOR_VERSION@': str(self.version.major),
                    '@PY_MINOR_VERSION@': str(self.version.minor),
                    '@PY_PATCH_VERSION@': str(self.version.patch),
                    '@PY_DYNAMIC_LOADING@': 'enabled' if self.dynamic_loading else 'disabled'})

    def _create_sysconfigdata(self):
        """ Create the _sysconfigdata module. """

        # The names must match those used in python.pro.  On macOS and Linux
        # they are chosen to match those used by a default build.  On Android
        # and iOS they are chosen to be unique so that they can have separate
        # entries in the Python meta-data.
        scd_names = {
            'android':  'linux_android',
            'ios':      'darwin_ios',
            'macos':    'darwin_darwin',
            'linux':    'linux_x86_64-linux-gnu',
        }

        scd_path = os.path.join(self.target_lib_dir,
                'python{}.{}'.format(self.version.major, self.version.minor),
                '_sysconfigdata_m_{}.py'.format(
                        scd_names[self.target_platform_name]))

        scd = self.create_file(scd_path)
        scd.write('''# Automatically generated.

build_time_vars = {
}
''')
        scd.close()

    def _get_py_install_path(self):
        """ Return the name of the directory containing the root of the Python
        installation directory.  It must not be called on a non-Windows
        platform.
        """

        from winreg import HKEY_CURRENT_USER, HKEY_LOCAL_MACHINE, QueryValue

        reg_version = '{0}.{1}'.format(self.version.major, self.version.minor)
        if self.target_arch_name.endswith('-32'):
            reg_version += '-32'

        sub_key_user = 'Software\\Python\\PythonCore\\{}\\InstallPath'.format(
                reg_version)
        sub_key_all_users = 'Software\\Wow6432Node\\Python\\PythonCore\\{}\\InstallPath'.format(
                reg_version)

        queries = (
            (HKEY_CURRENT_USER, sub_key_user),
            (HKEY_LOCAL_MACHINE, sub_key_user),
            (HKEY_LOCAL_MACHINE, sub_key_all_users))

        for key, sub_key in queries:
            try:
                install_path = QueryValue(key, sub_key)
            except OSError:
                pass
            else:
                break
        else:
            self.error(
                    "Unable to find an installation of Python v{0}.".format(
                            reg_version))

        return install_path

    def _install_host_from_source(self):
        """ Install the host Python from source. """

        self.building_for_target = False

        # Unpack the source.
        self.unpack_archive(self.get_archive())

        self.run('./configure', '--prefix', self.host_dir,
                '--with-ensurepip=no')

        # For reasons not fully understood, the presence of this environment
        # variable breaks the build (probably only on macOS).
        launcher = os.environ.get('__PYVENV_LAUNCHER__')
        if launcher is not None:
            del os.environ['__PYVENV_LAUNCHER__']

        self.run(self.host_make)
        self.run(self.host_make, 'install')

        if launcher is not None:
            os.environ['__PYVENV_LAUNCHER__'] = launcher

        self.building_for_target = True

    def _install_target_from_source(self):
        """ Install the target Python from source. """

        # Unpack the source for any separately compiled internal extension
        # modules.
        archive = self.get_archive()

        old_wd = os.getcwd()
        os.chdir(self.target_src_dir)
        self.unpack_archive(archive)
        self._patch_source_for_target()
        os.chdir(old_wd)

        # Unpack the source to build from.
        self.unpack_archive(archive)
        self._patch_source_for_target()

        # Configure for the target.
        self._configure_python()

        # Do the build.
        qt = self.get_component('Qt')

        self.run(qt.host_qmake, 'SYSROOT=' + self.sysroot_dir)
        self.run(self.host_make)
        self.run(self.host_make, 'install')

        # Create a platform-specific dummy _sysconfigdata module.  This allows
        # the sysconfig module to work.  If necessary we can populate it with
        # genuinely useful information if people ask for it.
        if self.target_platform_name != 'win':
            self._create_sysconfigdata()

    def _install_target_from_existing_windows_version(self, sysroot):
        """ Install the target Python from an existing installation on Windows.
        """ 

        install_path = sysroot.get_python_install_path()

        major = self.version.major
        minor = self.version.minor

        # The interpreter library.
        lib_name = 'python{0}{1}.lib'.format(major, minor)

        sysroot.copy_file(install_path + 'libs\\' + lib_name,
                os.path.join(sysroot.target_lib_dir, lib_name))

        lib_name = 'python{0}.lib'.format(major)

        sysroot.copy_file(install_path + 'libs\\' + lib_name,
                os.path.join(sysroot.target_lib_dir, lib_name))

        # The DLLs and extension modules.
        sysroot.copy_dir(install_path + 'DLLs',
                os.path.join(sysroot.target_lib_dir,
                        'DLLs{0}.{1}'.format(major, minor)),
                ignore=('*.ico', 'tcl*.dll', 'tk*.dll', '_tkinter.pyd'))

        py_dll = 'python{0}{1}.dll'.format(major, minor)
        py_dll_dir = install_path
        vc_dll = 'vcruntime140.dll'

        sysroot.copy_file(py_dll_dir + vc_dll,
                os.path.join(sysroot.target_lib_dir, vc_dll))

        sysroot.copy_file(py_dll_dir + py_dll,
                os.path.join(sysroot.target_lib_dir, py_dll))

        # The standard library.
        py_subdir = 'python{0}.{1}'.format(major, minor)

        sysroot.copy_dir(install_path + 'Lib',
                os.path.join(sysroot.target_lib_dir, py_subdir),
                ignore=('site-packages', '__pycache__', '*.pyc', '*.pyo'))

        # The header files.
        sysroot.copy_dir(install_path + 'include',
                os.path.join(sysroot.target_include_dir, py_subdir))

    def _patch_source_for_target(self):
        """ Patch the source code as necessary for the target. """

        if self.target_platform_name == 'ios':
           self._patch_source(os.path.join('Modules', 'posixmodule.c'),
                self._patch_for_ios_system)

        elif self.target_platform_name == 'win':
           self._patch_source(os.path.join('Modules', '_io', '_iomodule.c'),
                self._patch_for_win_iomodule)

           self._patch_source(
                os.path.join('Modules', 'expat', 'loadlibrary.c'),
                self._patch_for_win_loadlibrary)

           self._patch_source(os.path.join('Modules', '_winapi.c'),
                self._patch_for_win_winapi)

    def _patch_source(self, source, patcher):
        """ Invoke a patcher callable to patch a source file. """

        # Ignore if the source file doesn't exist.
        if not os.path.isfile(source):
            return

        orig = source + '.orig'
        os.rename(source, orig)

        orig_file = self.open_file(orig)
        patch_file = self.create_file(source)

        patcher(orig_file, patch_file)

        orig_file.close()
        patch_file.close()

    @staticmethod
    def _patch_for_ios_system(orig_file, patch_file):
        """ iOS doesn't have system() and the POSIX module uses hard-coded
        configurations rather than the normal configure by introspection
        process.
        """

        for line in orig_file:
            # Just skip any line that sets HAVE_SYSTEM.
            minimal = line.strip().replace(' ', '')
            if minimal != '#defineHAVE_SYSTEM1':
                patch_file.write(line)

    @staticmethod
    def _patch_for_win_iomodule(orig_file, patch_file):
        """ _iomodule.c in Python v3.6 includes consoleapi.h when it should
        include windows.h (as it does in Python v3.7).
        """

        for line in orig_file:
            patch_file.write(line.replace('consoleapi.h', 'windows.h'))

    @staticmethod
    def _patch_for_win_loadlibrary(orig_file, patch_file):
        """ Compiling loadlibrary.c triggers a missing definition of NMHDR.  A
        regular build from python.orgg doesn't have this problem so it is
        likely that the qmake build system is either not defining soemthing it
        should or defining something it shouldn't.  Including Python.h seems
        to work around the problem.
        """

        for line in orig_file:
            minimal = line.strip().replace(' ', '')
            if minimal == '#include<windows.h>':
                patch_file.write('#include <Python.h>\n\n')

            patch_file.write(line)

    @staticmethod
    def _patch_for_win_winapi(orig_file, patch_file):
        """ Both _winapi.c and overlapped.c define a C structure with the name
        OverlappedType.  We rename the former.
        """

        for line in orig_file:
            patch_file.write(line.replace('OverlappedType', 'OverlappedType_'))

    @property
    def _py_subdir(self):
        """ The name of a version-specific Python sub-directory. """

        return 'python{}.{}'.format(self.version.major, self.version.minor)
