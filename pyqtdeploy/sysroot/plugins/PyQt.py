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

from ... import Component, ComponentOption, VersionedModule


# TODO
# The VersionedModule objects for all modules that can be provided by the
# component.
_ALL_MODULES = {
    'PyQt5': VersionedModule(),
    'PyQt5.QtAndroidExtras':
        VersionedModule(target='android', deps='PyQt5.QtCore'),
    'PyQt5.QtBluetooth': VersionedModule(deps='PyQt5.QtCore'),
    'PyQt5.QtCore': VersionedModule(deps='SIP:PyQt5.sip'),
    'PyQt5.QtDBus': VersionedModule(deps='PyQt5.QtCore'),
    'PyQt5.QtGui': VersionedModule(deps='PyQt5.QtCore'),
    'PyQt5.QtHelp': VersionedModule(deps='PyQt5.QtWidgets'),
    'PyQt5.QtLocation': VersionedModule(deps='PyQt5.QtPositioning'),
    'PyQt5.QtMacExtras':
        VersionedModule(target='ios|macos', deps='PyQt5.QtGui'),
    'PyQt5.QtMultimedia':
        VersionedModule(deps=('PyQt5.QtGui', 'PyQt5.QtNetwork')),
    'PyQt5.QtMultimediaWidgets':
        VersionedModule(deps=('PyQt5.QtMultimedia', 'PyQt5.QtWidgets')),
    'PyQt5.QtNetwork': VersionedModule(deps='PyQt5.QtCore'),
    'PyQt5.QtNetworkAuth': VersionedModule(deps='PyQt5.QtNetwork'),
    'PyQt5.QtNfc': VersionedModule(deps='PyQt5.QtCore'),
    'PyQt5.QtOpenGL': VersionedModule(deps='PyQt5.QtWidgets'),
    'PyQt5.QtPositioning': VersionedModule(deps='PyQt5.QtCore'),
    'PyQt5.QtPrintSupport': VersionedModule(deps='PyQt5.QtWidgets'),
    'PyQt5.QtQml': VersionedModule(deps='PyQt5.QtNetwork'),
    'PyQt5.QtQuick': VersionedModule(deps=('PyQt5.QtGui', 'PyQt5.QtQml')),
    'PyQt5.QtQuick3D':
        VersionedModule(min_version=(5, 15),
                deps=('PyQt5.QtGui', 'PyQt5.QtQml')),
    'PyQt5.QtQuickWidgets':
        VersionedModule(deps=('PyQt5.QtQuick', 'PyQt5.QtWidgets')),
    'PyQt5.QtRemoteObjects': VersionedModule(deps='PyQt5.QtCore'),
    'PyQt5.QtSensors': VersionedModule(deps='PyQt5.QtCore'),
    'PyQt5.QtSerialPort': VersionedModule(deps='PyQt5.QtCore'),
    'PyQt5.QtSql': VersionedModule(deps='PyQt5.QtWidgets'),
    'PyQt5.QtSvg': VersionedModule(deps='PyQt5.QtWidgets'),
    'PyQt5.QtTest': VersionedModule(deps='PyQt5.QtWidgets'),
    'PyQt5.QtTextToSpeech':
        VersionedModule(min_version=(5, 15, 1), deps='PyQt5.QtCore'),
    'PyQt5.QtWebChannel': VersionedModule(deps='PyQt5.QtCore'),
    'PyQt5.QtWebSockets': VersionedModule(deps='PyQt5.QtNetwork'),
    'PyQt5.QtWidgets': VersionedModule(deps='PyQt5.QtGui'),
    'PyQt5.QtWinExtras': VersionedModule(target='win', deps='PyQt5.QtWidgets'),
    'PyQt5.QtX11Extras': VersionedModule(target='linux', deps='PyQt5.QtCore'),
    'PyQt5.QtXml': VersionedModule(deps='PyQt5.QtCore'),
    'PyQt5.QtXmlPatterns': VersionedModule(deps='PyQt5.QtNetwork'),
    'PyQt5._QOpenGLFunctions_2_0': VersionedModule(deps='PyQt5.QtGui'),
    'PyQt5._QOpenGLFunctions_2_1': VersionedModule(deps='PyQt5.QtGui'),
    'PyQt5._QOpenGLFunctions_4_1_Core': VersionedModule(deps='PyQt5.QtGui'),
    'PyQt5._QOpenGLFunctions_ES2': VersionedModule(deps='PyQt5.QtGui'),
}


class PyQtComponent(Component):
    """ The PyQt component. """

    # The component must be installed from source.
    must_install_from_source = True

    # The list of components that, if specified, should be installed before
    # this one.
    preinstalls = ['Python', 'Qt', 'SIP']

    def get_archive_name(self):
        """ Return the filename of the source archive. """

        if self._license_file is not None:
            return 'PyQt5_commercial-{}.tar.gz'.format(self.version)

        if self.version <= (5, 13, 1):
            return 'PyQt5_gpl-{}.tar.gz'.format(self.version)

        return 'PyQt5-{}.tar.gz'.format(self.version)

    def get_archive_urls(self):
        """ Return the list of URLs where the source archive might be
        downloaded from.
        """

        if self._license_file is not None:
            return super().get_archive_urls()

        if self.version <= (5, 14):
            return ['https://www.riverbankcomputing.com/static/Downloads/PyQt5/{}/'.format(self.version)]

        return self.get_pypi_urls('PyQt5')

    def get_options(self):
        """ Return a list of ComponentOption objects that define the components
        configurable options.
        """

        options = super().get_options()

        options.append(
                ComponentOption('disabled_features', type=list,
                        help="The features that are disabled."))

        valid_modules = sorted(
                [name[len('PyQt5.'):]
                        for name in _ALL_MODULES if name != 'PyQt5'])

        options.append(
                ComponentOption('installed_modules', type=list, required=True,
                        values=valid_modules,
                        help="The extension modules to be installed."))

        return options

    def install(self):
        """ Install for the target. """

        # See if there is a license file.
        self._license_file = self.get_file('pyqt-commercial.sip')

        # Unpack the source.
        self.unpack_archive(self.get_archive())

        # Copy any license file.
        if self._license_file is not None:
            self.copy_file(self._license_file, 'sip')

        # Map the target name onto the names used by configure.py.
        pyqt_platform = self.target_platform_name

        if pyqt_platform == 'android':
            pyqt_platform = 'linux'
        elif pyqt_platform in ('ios', 'macos'):
            pyqt_platform = 'darwin'
        elif pyqt_platform == 'win':
            pyqt_platform = 'win32'

        # Create a configuration file.
        python = self.get_component('Python')
        qt = self.get_component('Qt')
        sip = self.get_component('SIP')

        cfg = '''py_platform = {0}
py_inc_dir = {1}
py_pylib_dir = {2}
py_pylib_lib = {3}
pyqt_module_dir = {4}
pyqt_sip_dir = {5}
[Qt 5.0]
pyqt_modules = {6}
'''.format(pyqt_platform, python.target_py_include_dir, self.target_lib_dir,
                python.target_py_lib, python.target_sitepackages_dir,
                os.path.join(sip.target_sip_dir, 'PyQt5'),
                ' '.join(self.installed_modules))

        if self.disabled_features:
            cfg += 'pyqt_disabled_features = {0}\n'.format(
                    ' '.join(self.disabled_features))

        cfg_name = 'pyqt5-' + self.target_arch_name + '.cfg'

        with self.create_file(cfg_name) as cfg_file:
            cfg_file.write(cfg)

        # Configure, build and install.
        args = [python.host_python, 'configure.py', '--static', '--qmake',
            qt.host_qmake, '--sysroot', self.sysroot_dir, '--no-tools',
            '--no-qsci-api', '--no-designer-plugin', '--no-python-dbus',
            '--no-qml-plugin', '--no-stubs', '--configuration', cfg_name,
            '--sip', sip.host_sip, '--confirm-license', '-c', '-j2',
            '--no-dist-info']

        if self.verbose_enabled:
            args.append('--verbose')

        self.run(*args)
        self.run(self.host_make)
        self.run(self.host_make, 'install')

    @property
    def provides(self):
        """ The dict of VersionedModule objects provided by the component. """

        modules = {'PyQt5': _ALL_MODULES['PyQt5']}

        for name in self.installed_modules:
            name = 'PyQt5.' + name
            modules[name] = _ALL_MODULES[name]

        return modules

    def verify(self):
        """ Verify the component. """

        # v5.11.0-2 have too many problems so it's easier to blacklist them.
        if self.version < (5, 12):
            self.unsupported()

        if self.version >= (5, 13):
            self.untested()

        # Check the corresponding SIP version.
        sip_version = self.get_component('SIP').version

        if sip_version < (4, 19, 19):
            if self.version >= (5, 13, 1):
                self.error("SIP v4.19.19 or later is required")
        elif sip_version < (4, 19, 20):
            if self.version >= (5, 14):
                self.error("SIP v4.19.20 or later is required")
        elif sip_version < (4, 19, 23):
            if self.version >= (5, 15):
                self.error("SIP v4.19.23 or later is required")

        if self.version >= (5, 13, 1) and sip_version < (4, 19, 19):
            self.error("SIP v4.19.19 or later is required")
        elif self.version >= (5, 15) and sip_version < (4, 19, 23):
            self.error("SIP v4.19.23 or later is required")

        # This is needed by dependent components.
        if not self.get_component('Qt').ssl:
            self.disabled_features.append('PyQt_SSL')
