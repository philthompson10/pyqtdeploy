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

from ... import AbstractSIPComponent, ComponentOption, ExtensionModule


class SIPComponent(AbstractSIPComponent):
    """ The SIP component. """

    # The list of components that, if specified, should be installed before
    # this one.
    preinstalls = ['Python', 'Qt']

    def get_archive_name(self):
        """ Return the filename of the source archive. """

        return 'sip-{}.tar.gz'.format(self.version)

    def get_archive_urls(self):
        """ Return the list of URLs where the source archive might be
        downloaded from.
        """

        return ['https://www.riverbankcomputing.com/static/Downloads/sip/{}/'.format(self.version)]

    def get_options(self):
        """ Return a list of ComponentOption objects that define the components
        configurable options.
        """

        options = super().get_options()

        options.append(
                ComponentOption('module_name',
                        help="The qualified name of the sip module."))

        return options

    @property
    def host_sip(self):
        """ The name of the host sip executable. """

        return os.path.join(self.host_dir, 'bin', self.host_exe('sip'))

    def install(self):
        """ Install for the target. """

        archive = self.get_archive()

        build_generator = os.path.join(os.getcwd(), 'sip-generator')
        build_module = os.path.join(os.getcwd(), 'sip-module')

        os.mkdir(build_generator)
        os.chdir(build_generator)
        self._install_code_generator(archive)

        os.mkdir(build_module)
        os.chdir(build_module)
        self._install_module(archive)

    @property
    def provides(self):
        """ The dict of parts provided by the component. """

        lib_dir = self.get_component('Python').target_sitepackages_dir

        parts = self.module_name.split('.')
        if len(parts) > 1:
            lib_dir = os.path.join(lib_dir, os.path.join(*parts[:-1]))

        # Note that there is no dependency on the containing package because we
        # don't know the name of the component that provides it.
        return {
            self.module_name: ExtensionModule(
                    deps=('Python:atexit', 'Python:enum', 'Python:gc'),
                    libs=('-L' + lib_dir, '-lsip'))
        }

    @property
    def target_sip_dir(self):
        """ The name of the directory containing the target .sip files. """

        return os.path.join(self.sysroot_dir, 'share', 'sip')

    def verify(self):
        """ Verify the component. """

        # v4.19.14 is the minimum version required by the earliest supported
        # version of PyQt.
        if self.version < (4, 19, 14):
            self.unsupported()

        # v5 is not yet supported.
        if self.version >= 5:
            self.unsupported()

        if self.target_platform_name == 'android':
            if self.version <= (4, 19, 23) and self.get_component('Qt').version > (5, 14):
                self.unsupported("with Qt v5.14 or later on Android")

    def _install_code_generator(self, archive):
        """ Install the code generator for the host. """

        self.building_for_target = False

        self.unpack_archive(archive)
        python = self.get_component('Python')

        args = [python.host_python, 'configure.py', '--bindir',
                os.path.join(self.host_dir, 'bin')]

        if self.version >= (4, 19, 12):
            # From v4.19.12 sip.h is considered part of the tools.
            args.extend(['--incdir', python.target_py_include_dir,
                    '--no-module'])

        self.run(*args)
        os.chdir('sipgen')
        self.run(self.host_make)
        self.run(self.host_make, 'install')

        self.building_for_target = True

    def _install_module(self, archive):
        """ Install the static module for the target. """

        self.unpack_archive(archive)
        python = self.get_component('Python')
        qt = self.get_component('Qt')

        # Create a configuration file.
        cfg = '''py_inc_dir = {0}
py_pylib_dir = {1}
sip_module_dir = {2}
'''.format(python.target_py_include_dir, self.target_lib_dir,
                python.target_sitepackages_dir)

        if self.target_platform_name == 'android':
            cfg += 'android_abi = {}\n'.format(self.android_abi)

        cfg_name = 'sip.cfg'

        with open(cfg_name, 'wt') as cfg_file:
            cfg_file.write(cfg)

        # Configure, build and install.
        args = [python.host_python, 'configure.py', '--static', '--sysroot',
                self.sysroot_dir, '--no-pyi', '--no-tools', '--use-qmake',
                '--configuration', cfg_name]

        if self.version >= (4, 19, 9):
            args.append('--no-dist-info')

        if self.module_name:
            args.extend(['--sip-module', self.module_name])

        self.run(*args)
        self.run(qt.host_qmake)
        self.run(self.host_make)
        self.run(self.host_make, 'install')
