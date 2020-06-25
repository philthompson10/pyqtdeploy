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
import sys

from ... import ComponentOption, SourceComponent


class QtComponent(SourceComponent):
    """ The Qt component. """

    # The list of components that, if specified, should be installed before
    # this one.
    preinstalls = ['OpenSSL', 'zlib']

    def get_options(self):
        """ Return a list of ComponentOption objects that define the components
        configurable options.
        """

        options = super().get_options()

        options.append(
                ComponentOption('configure_options', type=list,
                        help="The additional options to be passed to "
                                "'configure' when building from source."))

        options.append(
                ComponentOption('disabled_features', type=list,
                        help="The features that are disabled when building "
                                "from source."))

        options.append(
                ComponentOption('edition', values=['commercial', 'opensource'],
                        help="The Qt edition being used when building from "
                                "source."))

        options.append(
                ComponentOption('ssl',
                        values=['openssl-linked', 'openssl-runtime',
                                'securetransport'],
                        help="Enable SSL support."))

        options.append(
                ComponentOption('skip', type=list,
                        help="The Qt modules to skip when building from "
                                "source."))

        options.append(
                ComponentOption('static_msvc_runtime', type=bool,
                        help="Set if the MSVC runtime should be statically "
                                "linked."))

        return options

    def install(self):
        """ Install for the target. """

        if self.install_from_source:
            self._install_from_source()

    def verify(self):
        """ Verify the component. """

        # Do some basic version checks.
        if self.version >= 6:
            self.error("Qt v6 is not supported")

        if self.version < (5, 12):
            self.error("Qt v5.12 or later is required")

        if self.version >= (5, 13):
            self.warning("Qt v5.13 and later is untested")

        # Make sure any installed version is the one specified.
        if not self.install_from_source:
            self._verify_installed_version()

        # If we are linking against OpenSSL then get its version number.
        if self.ssl == 'openssl-linked':
            openssl = self.get_component('OpenSSL')
            self._openssl_version = openssl.version
        else:
            self._openssl_version = None

        # Android-specific checks.
        if self.target_platform_name == 'android':
            # Issue warnings about untested SDK and NDK versions.
            if sysroot.android_sdk_version < (26, 1, 1):
                self.warning(
                        "versions of the SDK earlier than v26.1.1 are untested")

            if sysroot.android_sdk_version > (26, 1, 1):
                self.warning(
                        "versions of the SDK later than v26.1.1 are untested")

            if sysroot.android_ndk_version < 19:
                self.warning(
                        "versions of the NDK earlier than r19 are untested")

            if sysroot.android_ndk_version > 19:
                self.warning(
                        "versions of the NDK later than r19 are untested")

            if self._openssl_version is not None:
                # The standard Qt build for Android uses OpenSSL v1.0.* so we
                # must use the same.
                # TODO: Check if Qt v5.13 is built against OpenSSL v1.1.*.
                if self._openssl_version >= (1, 1):
                    self.error("OpenSSL v1.0.* is required for Android")

        # Additional checks for when we are installing from source.
        if self.install_from_source:
            # We don't support cross-compiling Qt.
            if self.host_platform_name != self.target_platform_name:
                self.error("cross compiling Qt is not supported")

            if not self.edition:
                self.error(
                        "the 'edition' option must be specified when building "
                        "from source")

            # Make sure we have a Python v2.7 installation.
            if self.host_platform_name == 'win':
                self._py_27 = self.get_python_install_path(2, 7)

    def _install_from_source(self):
        """ Install Qt from source. """

        archive = self.get_archive(
                'qt-everywhere-src-{}.tar.xz'.format(self.version),
                url='https://download.qt.io/archive/qt/{}.{}/{}/single/'.format(
                        self.version.major, self.version.minor, self.version))
        self.unpack_archive(archive)

        if self.host_platform_name == 'win':
            configure = 'configure.bat'

            dx_setenv = os.path.expandvars(
                    '%DXSDK_DIR%\\Utilities\\bin\\dx_setenv.cmd')

            if os.path.exists(dx_setenv):
                sysroot.run(dx_setenv)

            original_path = os.environ['PATH']
            new_path = [original_path]

            new_path.insert(0, os.path.abspath('gnuwin32\\bin'))
            new_path.insert(0, self._py_27)

            os.environ['PATH'] = ';'.join(new_path)
        else:
            configure = './configure'
            original_path = None

        target_qt_dir = os.path.join(self.sysroot_dir, 'Qt')

        args = [configure, '-prefix', target_qt_dir, '-' + self.edition,
                '-confirm-license', '-static', '-release', '-nomake',
                'examples', '-nomake', 'tools',
                '-I', self.target_include_dir,
                '-L', self.target_lib_dir]

        if sys.platform == 'win32' and self.static_msvc_runtime:
            args.append('-static-runtime')

        if self.ssl:
            args.append('-ssl')

            if self.ssl == 'securetransport':
                args.append('-securetransport')

            elif self.ssl == 'openssl-linked':
                args.append('-openssl-linked')

                if sys.platform == 'win32':
                    if self._openssl_version >= (1, 1):
                        openssl_libs = '-llibssl -llibcrypto'
                    else:
                        openssl_libs = '-lssleay32 -llibeay32'

                    args.append('OPENSSL_LIBS=' + openssl_libs + ' -lws2_32 -lgdi32 -ladvapi32 -lcrypt32 -luser32')

            elif self.ssl == 'openssl-runtime':
                args.append('-openssl-runtime')

        else:
            args.append('-no-ssl')

        if self.configure_options:
            args.extend(self.configure_options)

        xcb_enabled = True
        if self.disabled_features:
            for feature in self.disabled_features:
                args.append('-no-feature-' + feature)

                if feature == 'xcb':
                    xcb_enabled = False

        if self.skip:
            for module in self.skip:
                args.append('-skip')
                args.append(module)

        if sys.platform == 'win32':
            # These cause compilation failures (although maybe only with static
            # builds).
            args.append('-skip')
            args.append('qtimageformats')
        elif sys.platform == 'linux' and xcb_enabled:
            args.append('-qt-xcb')

        self.run(*args)
        self.run(self.host_make)
        self.run(self.host_make, 'install')

        if original_path is not None:
            os.environ['PATH'] = original_path

        self.host_qmake = os.path.join(target_qt_dir, 'bin', 'qmake')

    def _verify_installed_version(self):
        """ Verify that the installed version is compatible with the specified
        version.
        """

        for line in self.run(self.host_qmake, '-query', capture=True).split():
            parts = line.split(':')
            if len(parts) == 2 and parts[0] == 'QT_VERSION':
                host_version = self.parse_version_number(parts[1])
                break
        else:
            self.error(
                    "unable to determine Qt version number from {0}".format(
                            self.host_qmake))

        if self.version != host_version:
            self.error(
                    "v{0} is specified but the host installation is "
                    "v{1}".format(self.version, host_version))
