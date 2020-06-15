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


from abc import ABC, abstractmethod
import os

from ..user_exception import UserException


class ComponentOption:
    """ Encapsulate an option for the component in the specification file. """

    def __init__(self, name, type=str, required=False, default=None,
            values=None, help=''):
        """ Initialise the object. """

        self.name = name
        self.type = type
        self.required = required
        self.default = default
        self.values = values
        self.help = help if help else "None available."

        if values:
            self.help += " The possible values are: {0}.".format(
                    ', '.join([self._format_value(v) for v in values]))

        if default is not None:
            self.help += " The default value is {0}.".format(
                    self._format_value(default))

    def _format_value(self, value):
        """ Format a value according to the type of the option. """

        value = str(value)

        if self.type is not int:
            value = "'" + value + "'"

        return value


class ComponentBase(ABC):
    """ The base class for the implementation of a component plugin. """

    def __init__(self, name, configuration, sysroot):
        """ Initialise the component. """

        self.name = name
        self._sysroot = sysroot

        self.use_native_version = False

        # Configure the component.
        for option in self.get_options():
            value = configuration.get(option.name)

            if value is None:
                if option.required:
                    self._parse_error(
                            "'{0}' has not been specified".format(option.name))

                # Create a default value.
                if option.default is None:
                    value = option.type()
                else:
                    value = option.default
            elif not isinstance(value, option.type):
                self._parse_error(
                        "value of '{0}' has an unexpected type".format(
                                option.name))
            elif option.values:
                if value not in option.values:
                    self._parse_error(
                            "'{0}' must have be one of these values: {1}".format(option.name, ','.join(option.values)))

            setattr(self, option.name, value)

            try:
                del configuration[option.name]
            except KeyError:
                pass

        unused = configuration.keys()
        if unused:
            self._parse_error(
                    "unknown option(s): {0}".format(', '.join(unused)))

    @property
    def android_api(self):
        """ The Android API to use. """

        try:
            return self._sysroot.target.platform.android_api
        except AttributeError:
            self._android_only('android_api')

    @property
    def apple_sdk(self):
        """ The Apple SDK to use. """

        arch = self._sysroot.target if self._sysroot.building_for_target else self._sysroot.host

        try:
            return arch.platform.apple_sdk
        except AttributeError:
            self._apple_only('apple_sdk')

    def error(self, message):
        """ Issue an error message.  This method will not return. """

        self._sysroot.error("{0}: {1}".format(self.name, message))

    def find_exe(self, name, required=True):
        """ Return the absolute pathname of an executable located on PATH. """

        host_exe = self.host_exe(name)

        for d in os.environ.get('PATH', '').split(os.pathsep):
            exe_path = os.path.join(d, host_exe)

            if os.access(exe_path, os.X_OK):
                return exe_path

        if required:
            self.error("'{0}' must be installed on PATH".format(name))

        return None

    def get_options(self):
        """ Return a list of ComponentOption objects that define the components
        configurable options.
        """

        return [ComponentOption('version',
                help="The version number of the component.")]

    def get_component(self, name, required=True):
        """ Return the component object for the given name or None if the
        component hasn't been specified.  If it has not been specified and it
        is required then raise an exception.
        """

        for component in self._sysroot.components:
            if component.name == name:
                return component

        if required:
            self.error(
                    "'{0}' must be specified as a component of the sysroot".format(name))

        return None

    def get_implied_version(self):
        """ Return the VersionNumber object corresponding to the implied
        version number of the component.  This will never be called if the
        version number was specified explicitly.
        """

        # See if a native version (ie. one supplied by the target operating
        # system) is to be used.
        version = self.get_native_version()
        if version is not None:
            self.use_native_version = True
            return version

        self.error("the version number has not been set")

    def get_native_version(self):
        """ Return the VersionNumber object corresponding to the version number
        of the component provided by the target operating system.
        """

        # This default implementation does not support native versions.
        return None

    def get_version_from_file(self, identifier, filename):
        """ Return the stripped line from a file containing an identifier
        (typically a pre-processor macro defining a version number).  None is
        returned if the file doesn't exist or doesn't contain the identifier.
        """

        self.verbose(
                "Determining installed version from '{0}'".format(filename))

        version_line = None

        if os.path.isfile(filename):
            with open(filename) as f:
                for line in f:
                    if identifier in line:
                        version_line = line.strip()
                        break

        return version_line

    def host_exe(self, name):
        """ Convert a generic executable name to a host-specific version. """

        return self._sysroot.host.platform.exe(name)

    @property
    def host_platform_name(self):
        """ The name of the host platform. """

        return self._sysroot.host.platform.name

    @abstractmethod
    def install(self):
        """ Install the component. """

    def parse_version_number(self, version_str):
        """ Parse a version number of the component returning a VersionNumber
        object.  UserException is raised if it couldn't be parsed.

        The version number format supported by the default implementation is
        M[.m[.p]][suffix] where M is the int major version, m is the int minor
        version, p is the int patch version and suffix is a str suffix.
        """

        from ..version_number import VersionNumber

        return VersionNumber.parse_version_number(version_str)

    def progress(self, message):
        """ Issue a progress message. """

        self._sysroot.progress("{0}: {1}".format(self.name, message))

    def resolve_version(self):
        """ Make sure the version attribute is a VersionNumber object. """

        if isinstance(self.version, str):
            if self.version != '':
                # Use an explicitly specified version number.
                self.version = self.parse_version_number(self.version)
            else:
                self.version = self.get_implied_version()

    @property
    def target_platform_name(self):
        """ The name of the target platform. """

        return self._sysroot.target.platform.name

    def verify(self):
        """ Verify the component.  This will be called after the options have
        been parsed and the version number resolved.
        """

    def verbose(self, message):
        """ Issue a verbose progress message. """

        self._sysroot.verbose("{0}: {1}".format(self.name, message))

    def verify_host_tools(self, tools):
        """ Verify that a sequence of host tools is available. """

        for tool in tools:
            self.find_exe(tool)

    def warning(self, message):
        """ Issue a warning message. """

        self._sysroot.warning("{0}: {1}".format(self.name, message))

    def _android_only(self, attr_name):
        """ Issue an error message about an Android-only attribute. """

        self.error(
                "the '{0}' attribute is only supported for Android targets".format(attr_name))

    def _apple_only(self, attr_name):
        """ Issue an error message about an Apple-only attribute. """

        self.error(
                "the '{0}' attribute is only supported for Apple targets".format(
                        attr_name))

    def _parse_error(self, message):
        """ Raise an exception for by an error in the specification file. """

        raise UserException(
                "{0}: Component '{1}': {2}".format(self.specification_file,
                        self.name, message))


class SourceComponent(ComponentBase):
    """ The base class for the implemenation of component plugins that install
    from a source package.
    """

    _ARCHIVE_EXTENSIONS = ('.tar.bz2', '.tar.gz', '.tar.xz', 'tgz', '.zip')

    def get_implied_version(self):
        """ Return the VersionNumber object corresponding to the version number
        implied by the component source.
        """

        # If 'source' hasn't been specified then use the super-class
        # implementation.
        if self.source == '':
            return super().get_implied_version()

        # Get the basename without any standard source archive extensions.
        name = os.path.basename(self.source)

        for ext in self._ARCHIVE_EXTENSIONS:
            if name.endswith(ext):
                name = name[:-len(ext)]
                break

        for version_str in name.split('-'):
            try:
                return self.parse_version_number(version_str)
            except UserException:
                pass

        self.error(
                "unable to extract a version number from '{0}'".format(name))

    def get_options(self):
        """ Return a list of ComponentOption objects that define the components
        configurable options.
        """

        options = super().get_options()

        options.append(
                ComponentOption('source',
                        help="The archive containing the source code."))

        return options
