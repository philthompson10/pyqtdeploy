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

from ... import Component, ComponentOption, ExtensionModule


class SIPComponent(Component):
    """ The SIP component (ie. the sip module). """

    # The list of components that, if specified, should be installed before
    # this one.
    preinstalls = ['Python', 'Qt']

    def get_archive_name(self):
        """ Return the filename of the source archive. """

        return '{}-{}.tar.gz'.format(self.module_name.replace('.', '_'),
                self.version)

    def get_archive_urls(self):
        """ Return the list of URLs where the source archive might be
        downloaded from.
        """

        return self.get_pypi_urls(self.module_name.replace('.', '-'))

    def get_options(self):
        """ Return a list of ComponentOption objects that define the components
        configurable options.
        """

        options = super().get_options()

        options.append(
                ComponentOption('module_name', required=True,
                        help="The qualified name of the sip module."))

        return options

    def install(self):
        """ Install for the target. """

        archive = self.get_archive()
        self.unpack_archive(archive)

        # Gather the name of the source and header files
        sources = []
        headers = []

        for fname in os.listdir():
            if fname.endswith('.c') or fname.endswith('.cpp'):
                sources.append(fname)
            elif fname.endswith('.h'):
                headers.append(fname)

        # Create a .pro file to build the module.
        python = self.get_component('Python')

        if self.target_platform_name == 'android':
            android_abi = self.android_abi
        else:
            android_abi = ''

        module_dir = os.sep.join(self.module_name.split('.')[:-1])

        pro = _SIP_PRO.format(android_abis=android_abi,
                includepath=python.target_py_include_dir,
                sitepackages=os.path.join(python.target_sitepackages_dir,
                        module_dir),
                sources=' '.join(sources), headers=' '.join(headers))

        with self.create_file('sip.pro') as f:
            f.write(pro)

        # Run qmake and make to install it.
        self.run(self.get_component('Qt').host_qmake)
        self.run(self.host_make)
        self.run(self.host_make, 'install')

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

    def verify(self):
        """ Verify the component. """

        self.find_exe('sip-install')


# The skeleton .pro file for the sip module.
_SIP_PRO = """TEMPLATE = lib
TARGET = sip
CONFIG -= qt
CONFIG += warn_on exceptions_off staticlib release
ANDROID_ABIS = {android_abis}

INCLUDEPATH += {includepath}

target.path = {sitepackages}
INSTALLS += target

SOURCES = {sources}
HEADERS = {headers}
"""
