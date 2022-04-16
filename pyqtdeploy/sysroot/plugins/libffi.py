# Copyright (c) 2022, Riverbank Computing Limited
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

from ... import Component, ComponentLibrary, ComponentOption


class libffiComponent(Component):
    """ The libffi component. """

    # Add the 'install_from_source' option.
    option_install_from_source = True

    # The version will be determined dynamically if the system provided version
    # is being used.
    version_is_optional = True

    def get_archive_name(self):
        """ Return the filename of the source archive. """

        return 'libffi-{}.tar.gz'.format(self.version)

    def get_archive_urls(self):
        """ Return the list of URLs where the source archive might be
        downloaded from.
        """

        return ['https://github.com/libffi/libffi/releases/download/v{}/'.format(self.version)]

    def install(self):
        """ Install for the target. """

        if not self.install_from_source:
            return

        # Unpack the source.
        self.unpack_archive(self.get_archive())

        if self.target_platform_name == 'win':
            make_args = [self.host_make, '-f', 'win32\\Makefile.msc',
                    'zlib.lib']

            if self.static_msvc_runtime:
                make_args.append('LOC=-MT')

            self.run(*make_args)

            self.copy_file('zconf.h', self.target_include_dir)
            self.copy_file('zlib.h', self.target_include_dir)
            self.copy_file('zlib.lib', self.target_lib_dir)

        elif self.target_platform_name == 'android':
            # Configure the environment.
            original_path = self.add_to_path(self.android_toolchain_bin)
            os.environ['CROSS_PREFIX'] = self.android_toolchain_prefix
            os.environ['CC'] = self.android_toolchain_cc

            # It isn't clear why this is needed, possibly a clang bug.
            if self.target_arch_name == 'android-32':
                os.environ['CFLAGS'] = '-fPIC'

            self.run('./configure', '--static', '--prefix=' + self.sysroot_dir)
            self.run(self.host_make,
                    'AR=' + self.android_toolchain_prefix + 'ar cqs',
                    'install')

            if self.target_arch_name == 'android-32':
                del os.environ['CFLAGS']

            del os.environ['CROSS_PREFIX']
            del os.environ['CC']
            os.environ['PATH'] = original_path

        else:
            if self.target_platform_name == 'ios':
                # Note that this doesn't create a library that can be used with
                # an x86-based simulator.
                os.environ['CFLAGS'] = '-fembed-bitcode -O3 -arch arm64 -isysroot ' + self.apple_sdk

            self.run('./configure', '--static', '--prefix=' + self.sysroot_dir)
            self.run(self.host_make)
            self.run(self.host_make, 'install')

            if self.target_platform_name == 'ios':
                del os.environ['CFLAGS']

    @property
    def provides(self):
        """ The dict of parts provided by the component. """

        dll_version = '7' if self.version == (3, 3) else '8'

        return {
                'libffi': ComponentLibrary(
                        libs=('win#-llibffi-{}'.format(dll_version),
                                '!win#-lffi'))
        }

    def verify(self):
        """ Verify the component. """

        if self.target_platform_name in ('android', 'ios'):
            self.error(
                    "'{0}' is not a supported target platform".format(
                            self.target_platform_name))

        if self.install_from_source:
            if self.version is None:
                self.error(
                        "'version' must be specified when installing from "
                        "source")

            # TODO: check tool availability.
        else:
            installed_version = self._get_installed_version()

            if self.version is None:
                self.version = installed_version
            elif self.version != installed_version:
                self.error(
                        "v{0} is specified but the host installation is "
                                "v{1}".format(self.version, installed_version))

        if (3, 3) > self.version >= (3, 5):
            self.unsupported("use v3.3 or v3.4")

    def _get_installed_version(self):
        """ Get the installed version. """

        if self.target_platform_name == 'win':
            self.error(
                    "using an existing installation is not supported for "
                    "Windows targets")

        if self.target_platform_name == 'macos':
            ffi_h_dir = self.apple_sdk + '/usr/include/ffi'
        elif self.target_platform_name == 'linux':
            ffi_h_dir = '/usr/include/x86_64-linux-gnu'

        version_file = ffi_h_dir + '/ffi.h'
        version_line = self.get_version_from_file('libffi', version_file)

        # The version number seems to be the second 'word' of the line.
        version_str = version_line.split()[1]

        return self.parse_version_number(version_str)
