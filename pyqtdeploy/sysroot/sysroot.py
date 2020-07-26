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

from ..file_utilities import (create_file as fu_create_file,
        open_file as fu_open_file)
from ..platforms import Architecture, Platform
from ..user_exception import UserException
from ..version_number import VersionNumber

from .specification import SysrootSpecification


class Sysroot:
    """ Encapsulate a target-specific system root directory. """

    def __init__(self, specification, host, target, sysroots_dir,
            message_handler=None, python=None, qmake=None):
        """ Initialise the object. """

        self._specification = specification
        self.host = host
        self.target = target
        self._message_handler = message_handler

        if not sysroots_dir:
            sysroots_dir = os.path.dirname(
                    self._specification.specification_file)

        self.sysroot_dir = os.path.join(sysroots_dir,
                'sysroot-' + self.target.name)

        self._building_for_target = True

        self.components = specification.create_components_for_target(target,
                self)

        # Set any externally specified qmake.
        if python is not None:
            python_component = self.get_component('Python', required=False)
            if python_component is not None:
                python_component.host_python = python

        if qmake is not None:
            qt_component = self.get_component('Qt', required=False)
            if qt_component is not None:
                qt_component.host_qmake = qmake

    @staticmethod
    def error(message, detail='', exception=None, component=None):
        """ Raise an exception that will report an error is a user friendly
        manner.
        """

        if component is not None:
            message = "{0}: {1}".format(component.name, message)

        raise UserException(message, detail=detail) from exception

    def find_exe(self, name, required=True, component=None):
        """ Return the absolute pathname of an executable located on PATH. """

        host_exe = self.host_exe(name)

        for d in os.get_exec_path():
            exe_path = os.path.join(d, host_exe)

            if os.access(exe_path, os.X_OK):
                return exe_path

        if required:
            self.error("'{0}' could not be found on PATH".format(name),
                    component=component)

        return None

    def get_component(self, name, required=True, component=None):
        """ Return the component object for the given name or None if the
        component hasn't been specified.  If it has not been specified and it
        is required then raise an exception.
        """

        for comp in self.components:
            if comp.name == name:
                return comp

        if required:
            self.error(
                    "'{0}' must be specified as a component of the "
                            "sysroot".format(name),
                    component=component)

        return None

    def host_exe(self, name):
        """ Convert a generic executable name to a host-specific version. """

        return self.host.platform.exe(name)

    def install_components(self, component_names, source_dirs, no_clean):
        """ Install a sequence of components.  If no names are given then
        create the system image root directory and install everything.  Raise a
        UserException if there is an error.
        """

        # Verify the configuration.
        self.verify()

        # Normalise the list of source directories to search.
        if source_dirs:
            self.source_dirs = [os.path.abspath(s) for s in source_dirs]
        else:
            self.source_dirs = [
                    os.path.dirname(self._specification.specification_file)]

        self.target.configure()

        if component_names:
            components = self._components_from_names(component_names)
            all_components = False
        else:
            components = self.components
            all_components = True

        self.create_dir(self.sysroot_dir, empty=all_components)
        os.makedirs(self.host_dir, exist_ok=True)
        os.makedirs(self.target_include_dir, exist_ok=True)
        os.makedirs(self.target_lib_dir, exist_ok=True)
        os.makedirs(self.target_src_dir, exist_ok=True)

        # Create a new build directory.
        build_dir = os.path.join(self.sysroot_dir, 'build')
        self.create_dir(build_dir, empty=True)
        cwd = os.getcwd()

        # Install the components.
        self.building_for_target = True

        for component in components:
            component.ensure_installed(build_dir, all_components)

        # Remove the build directory if requested.
        os.chdir(cwd)

        if not no_clean:
            # This can fail on Windows (complaining about non-empty
            # directories).  Therefore we just warn that we couldn't do it.
            try:
                self.delete_dir(build_dir)
            except UserException as e:
                self.verbose("Warning: " + e.text)

    def show_options(self, component_names):
        """ Show the options for a sequence of components.  If no names are
        given then show the options of all components.  Raise a UserException
        if there is an error.
        """

        if component_names:
            components = self._components_from_names(component_names)
        else:
            components = self.components

        assert self._message_handler is not None
        self._specification.show_options(components, self._message_handler)

    def verify(self):
        """ Verify the configuration.  Raise a UserException if there is an
        error.
        """

        assert self._message_handler is not None

        # Verify the host and target.
        self.progress(
                "Verifying host architecture '{0}'...".format(self.host.name))
        self.host.verify_as_host(self.target, self._message_handler)

        self.progress(
                "Verifying target architecture '{0}'...".format(
                        self.target.name))
        self.target.verify_as_target(self._message_handler)

        # Verify the components.
        for component in self.components:
            self.progress(
                    "Verifying {0} v{1}...".format(component.name,
                            component.version))

            component.verify()

    def warning(self, message, component=None):
        """ Issue a warning message. """

        if component is not None:
            message = "{0}: {1}".format(component.name, message)

        assert self._message_handler is not None
        self._message_handler.warning(message)

    def _components_from_names(self, component_names):
        """ Return a sequence of components from a sequence of names. """

        components = []

        for name in component_names:
            for component in self.components:
                if component.name == name:
                    components.append(component)
                    break
            else:
                self.error("unkown component '{0}'".format(name))

        return components

    @property
    def android_ndk_root(self):
        """ The path of the root of the Android NDK. """

        return self.target.platform.android_ndk_root

    @property
    def android_ndk_sysroot(self):
        """ The path of the Android NDK's sysroot directory. """

        return self.target.platform.android_ndk_sysroot

    @property
    def android_ndk_version(self):
        """ The VersionNumber object representing the version number of the
        Android NDK.
        """

        ndk_version = self.target.platform.android_ndk_version

        if ndk_version is None:
            self.error("unable to determine the NDK version number")

        return ndk_version

    @property
    def android_sdk_version(self):
        """ The VersionNumber object representing the version number of the
        Android SDK.
        """

        sdk_version = self.target.platform.android_sdk_version

        if sdk_version is None:
            self.error("unable to determine the SDK version number")

        return sdk_version

    @property
    def android_toolchain_bin(self):
        """ The path of the Android toolchain's bin directory. """

        return self.target.android_toolchain_bin

    @property
    def android_toolchain_cc(self):
        """ The name of the Android toolchain's C compiler. """

        return self.target.android_toolchain_cc

    @property
    def android_toolchain_prefix(self):
        """ The name of the Android toolchain's prefix. """

        return self.target.android_toolchain_prefix

    @property
    def apple_sdk(self):
        """ The Apple SDK to use. """

        arch = self.target if self._building_for_target else self.host

        return arch.platform.apple_sdk

    @property
    def building_for_target(self):
        """ This is set if building (ie. compiling and linking) for the target
        architecture.  Otherwise build for the host.  The default is True.
        """

        return self._building_for_target

    @building_for_target.setter
    def building_for_target(self, value):
        """ Set to build (ie. compile and link) for the target architecture.
        Otherwise build for the host.
        """

        if value:
            for component in self.components:
                component.sdk_deconfigure(self.host.platform.name)

            self.host.deconfigure()

            self.target.configure()

            for component in self.components:
                component.sdk_configure(self.target.platform.name)
        else:
            for component in self.components:
                component.sdk_deconfigure(self.target.platform.name)

            self.target.deconfigure()

            self.host.configure()

            for component in self.components:
                component.sdk_configure(self.host.platform.name)

        self._building_for_target = value

    def copy_dir(self, src, dst, ignore=None):
        """ Copy a directory and its contents optionally ignoring a sequence of
        patterns.  If the destination directory already exists its contents
        will be first deleted.
        """

        # Make sure the destination does not exist but can be created.
        self.delete_dir(dst)
        self.create_dir(os.path.dirname(dst))

        self.verbose("Copying {0} to {1}".format(src, os.path.abspath(dst)))

        if ignore is not None:
            ignore = shutil.ignore_patterns(*ignore)

        try:
            shutil.copytree(src, dst, ignore=ignore)
        except Exception as e:
            self.error("unable to copy directory {0}".format(src),
                    detail=str(e))

    def create_dir(self, name, empty=False, component=None):
        """ Ensure a directory exists and optionally delete its contents. """

        if empty:
            self.delete_dir(name)

        if os.path.exists(name):
            if not os.path.isdir(name):
                self.error("{0} exists but is not a directory".format(name),
                        component=component)
        else:
            self.verbose("Creating {0}".format(name), component=component)

            try:
                os.makedirs(name, exist_ok=True)
            except Exception as e:
                self.error("unable to create directory {0}".format(name),
                        detail=str(e), component=component)

    def create_file(self, name, component=None):
        """ Create a text file and return the file object. """

        try:
            return fu_create_file(name)
        except UserException as e:
            self.error(str(e), component=component)

    def delete_dir(self, name):
        """ Delete a directory and its contents. """

        if os.path.exists(name):
            if not os.path.isdir(name):
                self.error("{0} exists but is not a directory".format(name))

            self.verbose("Deleting {0}".format(name))

            # 32 bit applications on Windows have a 256 character limit on file
            # names which we can hit.  The Microsoft work around is to prepend
            # a magic string.
            name_hack = '\\\\?\\' + name if sys.platform == 'win32' else name

            try:
                shutil.rmtree(name_hack)
            except Exception as e:
                self.error("unable to remove directory {0}.".format(name),
                        detail=str(e))

    @property
    def host_arch_name(self):
        """ The name of the host architecture. """

        return self.host.arch_name

    @property
    def host_dir(self):
        """ The directory containing the host installations. """

        return os.path.join(self.sysroot_dir, 'host')

    @property
    def host_make(self):
        """ The name of the host make executable. """

        return self.host.platform.make

    @property
    def host_pip(self):
        """ The pathname of the host pip executable. """

        self._check_python_component()

        return os.path.join(self.host_bin_dir, self.host_exe('pip'))

    def open_file(self, name, component=None):
        """ Open an existing text file and return the file object. """

        try:
            return fu_open_file(name)
        except UserException as e:
            self.error(str(e), component=component)

    # TODO
    def pip_install(self, package):
        """ Use pip to install a package in the sysroot site-packages
        directory.
        """

        self.run(self.host_pip, 'install', '--target',
                self.target_sitepackages_dir, package)

    def progress(self, message, component=None):
        """ Issue a progress message. """

        if component is not None:
            message = "{0}: {1}".format(component.name, message)

        assert self._message_handler is not None
        self._message_handler.progress_message(message)

    def run(self, *args, capture=False):
        """ Run a command, optionally capturing stdout. """

        assert self._message_handler is not None
        return Platform.run(*args, message_handler=self._message_handler,
                capture=capture)

    @property
    def target_include_dir(self):
        """ The name of the directory containing target header files. """

        return os.path.join(self.sysroot_dir, 'include')

    @property
    def target_lib_dir(self):
        """ The name of the directory containing target libraries. """

        return os.path.join(self.sysroot_dir, 'lib')

    @property
    def target_src_dir(self):
        """ The name of the directory containing target sources. """

        return os.path.join(self.sysroot_dir, 'src')

    def verbose(self, message, component=None):
        """ Issue a verbose progress message. """

        if component is not None:
            message = "{0}: {1}".format(component.name, message)

        assert self._message_handler is not None
        self._message_handler.verbose_message(message)

    @property
    def verbose_enabled(self):
        """ True if verbose messages are being displayed. """

        assert self._message_handler is not None
        return self._message_handler.verbose
