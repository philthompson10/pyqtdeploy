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

    # A sequence of ComponentOption instances describing the options that can
    # be specified for the component in the specification file.  These are made
    # available as attributes of the plugin instance.
    options = [
        ComponentOption('version', help="The version number of the component.")
    ]

    def __init__(self, name, sysroot):
        """ Initialise the component. """

        self.name = name
        self._sysroot = sysroot

    def error(self, message):
        """ Issue an error message.  This method will not return. """

        self._sysroot.error("{0}: {1}".format(self.name, message))

    def find_exe(self, name):
        """ Return the absolute pathname of an executable located on PATH. """

        host_exe = self.host_exe(name)

        for d in os.environ.get('PATH', '').split(os.pathsep):
            exe_path = os.path.join(d, host_exe)

            if os.access(exe_path, os.X_OK):
                return exe_path

        self.error("'{0}' must be installed on PATH".format(name))

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
        version number was specified explicitly.  This default implementation
        raises an exception.
        """

        self.error("the version number has not been set")

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

    @property
    def target_platform_name(self):
        """ The name of the target platform. """

        return self._sysroot.target.platform.name

    def verify(self):
        """ Verify the component.  This will be called after the options have
        been parsed and after the version number has been set.
        """

    def verify_host_tools(self, tools):
        """ Verify that a sequence of host tools is available. """

        for tool in tools:
            self.find_exe(tool)

    def warning(self, message):
        """ Issue a warning message. """

        self._sysroot.warning("{0}: {1}".format(self.name, message))


class SourceComponent(ComponentBase):
    """ The base class for the implemenation of component plugins that install
    from a source package.
    """

    # The options.
    options = [
        ComponentOption('source', required=True,
                help="The archive containing the source code.")
    ]

    _ARCHIVE_EXTENSIONS = ('.tar.bz2', '.tar.gz', '.tar.xz', 'tgz', '.zip')

    def get_implied_version(self):
        """ Return the VersionNumber object corresponding to the version number
        implied by the component source.
        """

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
