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

from .... import ComponentOption, SourceComponent

from .configure_python import configure_python


class PythonComponent(SourceComponent):
    """ The host and target Python component. """

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
                        help="Install the host Python from a source package "
                                "rather than an existing installation."))

        return options

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

    def verify(self):
        """ Verify the component. """

        if self.version < (3, 5):
            self.error("versions earlier than v3.5 are not supported")

        if self.version >= (3, 8):
            self.error("v{0} is not yet supported".format(self.version))

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

            if self.version != host_version:
                self.error(
                        "v{0} is specified but the host installation is "
                                "v{1}".format(self.version, host_version))

        if not self.install_from_source and self.host_platform_name != 'win':
            self.error(
                    "using an existing Python installation for the target is "
                    "not supported on {0}".format(self.target_platform_name))

        if self.target_platform_name == 'android':
            if self.version < (3, 6):
                self.error(
                        "v{0} is not supported on Android".format(
                                self.version))

            if self.android_api < 21:
                self.error("Android API level 21 or greater is required")

        # Check the OpenSSL support.
        if self.install_from_source:
            openssl = self.get_component('OpenSSL', required=False)
            if openssl is None:
                self._has_openssl = False
            else:
                if self.version < (3, 5, 3) and openssl.version >= (1, 1, 0):
                    self.error(
                            "v{0} requires OpenSSL v1.0".format(self.version))
                elif self.version >= (3, 6) and openssl.version < (1, 0, 2):
                    self.error(
                            "v{0} requires OpenSSL v1.0.2 or later".format(
                                    self.version))

                self._has_openssl = True
        else:
            # The standard Python builds support OpenSSL.
            self._has_openssl = True

    def _install_host_from_source(self):
        """ Install the host Python from source. """

        sysroot.building_for_target = False

        # Unpack the source.
        archive = sysroot.find_file(self.source)
        sysroot.unpack_archive(archive)

        sysroot.run('./configure', '--prefix', sysroot.host_dir,
                '--with-ensurepip=no')

        # For reasons not fully understood, the presence of this environment
        # variable breaks the build (probably only on macOS).
        launcher = os.environ.get('__PYVENV_LAUNCHER__')
        if launcher is not None:
            del os.environ['__PYVENV_LAUNCHER__']

        sysroot.run(sysroot.host_make)
        sysroot.run(sysroot.host_make, 'install')

        if launcher is not None:
            os.environ['__PYVENV_LAUNCHER__'] = launcher

        sysroot.building_for_target = True

        # TODO: host_bin_dir?
        self.host_python = os.path.join(sysroot.host_bin_dir,
                'python{}.{}'.format(self.version.major, self.version.minor))

    def _build_target_from_source(self, sysroot):
        """ Build the target Python from source. """

        # Unpack the source for any separately compiled internal extension
        # modules.
        archive = sysroot.find_file(self.source)

        old_wd = os.getcwd()
        os.chdir(sysroot.target_src_dir)
        sysroot.unpack_archive(archive)
        self._patch_source_for_target(sysroot)
        os.chdir(old_wd)

        # Unpack the source to build from.
        sysroot.unpack_archive(archive)
        self._patch_source_for_target(sysroot)

        # Configure for the target.
        configure_python(self.dynamic_loading, sysroot)

        # Do the build.
        sysroot.run(sysroot.host_qmake, 'SYSROOT=' + sysroot.sysroot_dir)
        sysroot.run(sysroot.host_make)
        sysroot.run(sysroot.host_make, 'install')

        # Create a platform-specific dummy _sysconfigdata module.  This allows
        # the sysconfig module to work.  If necessary we can populate it with
        # genuinely useful information if people ask for it.
        if sysroot.target_platform_name != 'win':
            self._create_sysconfigdata(sysroot)

    def _create_sysconfigdata(self, sysroot):
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

        scd_name = '_sysconfigdata_m_{0}.py'.format(
                scd_names[sysroot.target_platform_name])
        scd_path = os.path.join(sysroot.target_py_stdlib_dir, scd_name)
        scd = sysroot.create_file(scd_path)
        scd.write('''# Automatically generated.

build_time_vars = {
}
''')
        scd.close()

    def _install_target_from_existing_windows_version(self, sysroot):
        """ Install the target Python from an existing installation on Windows.
        """ 

        install_path = sysroot.get_python_install_path()

        major, minor = self._major_minor(sysroot)

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

    def _patch_source_for_target(self, sysroot):
        """ Patch the source code as necessary for the target. """

        if sysroot.target_platform_name == 'ios':
           self._patch_source(sysroot,
                os.path.join('Modules', 'posixmodule.c'),
                self._patch_for_ios_system)

        elif sysroot.target_platform_name == 'win':
           self._patch_source(sysroot,
                os.path.join('Modules', '_io', '_iomodule.c'),
                self._patch_for_win_iomodule)

           self._patch_source(sysroot,
                os.path.join('Modules', 'expat', 'loadlibrary.c'),
                self._patch_for_win_loadlibrary)

           self._patch_source(sysroot,
                os.path.join('Modules', '_winapi.c'),
                self._patch_for_win_winapi)

    def _patch_source(self, sysroot, source, patcher):
        """ Invoke a patcher callable to patch a source file. """

        # Ignore if the source file doesn't exist.
        if not os.path.isfile(source):
            return

        orig = source + '.orig'
        os.rename(source, orig)

        orig_file = sysroot.open_file(orig)
        patch_file = sysroot.create_file(source)

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

    @staticmethod
    def _major_minor(sysroot):
        """ Return the Python major.minor as a tuple. """

        return (sysroot.target_py_version.major,
                sysroot.target_py_version.minor)

    @classmethod
    def _major_minor_as_string(cls, sysroot):
        """ Return the Python major.minor as a string. """

        major, minor = cls._major_minor(sysroot)

        return str(major) + '.' + str(minor)
