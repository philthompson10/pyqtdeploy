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

        # Configure the component.
        for option in self.get_options():
            value = configuration.get(option.name)

            if value is None:
                if option.required:
                    self.error(
                            "'{0}' has not been specified".format(option.name))

                # Create a default value.
                if option.default is None:
                    value = option.type()
                else:
                    value = option.default
            elif not isinstance(value, option.type):
                self.error(
                        "value of '{0}' has an unexpected type".format(
                                option.name))
            elif option.values:
                if value not in option.values:
                    self.error(
                            "'{0}' must have be one of these values: {1}".format(option.name, ','.join(option.values)))

            setattr(self, option.name, value)

            try:
                del configuration[option.name]
            except KeyError:
                pass

        unused = configuration.keys()
        if unused:
            self.error("unknown option(s): {0}".format(', '.join(unused)))

        # Allow the version number to be defined by an environment variable.
        self.version = self.parse_version_number(
                os.path.expandvars(self.version))

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

        self._sysroot.error(message, component=self)

    def find_exe(self, name, required=True):
        """ Return the absolute pathname of an executable located on PATH. """

        return self._sysroot.find_exe(name, required=required, component=self)

    def get_options(self):
        """ Return a list of ComponentOption objects that define the components
        configurable options.
        """

        return [ComponentOption('version', required=True,
                help="The version number of the component.")]

    def get_component(self, name, required=True):
        """ Return the component object for the given name or None if the
        component hasn't been specified.  If it has not been specified and it
        is required then raise an exception.
        """

        return self._sysroot.get_component(name, required=required,
                component=self)

    def get_version_from_file(self, identifier, filename):
        """ Return the stripped line from a file containing an identifier
        (typically a pre-processor macro defining a version number).
        """

        self.verbose(
                "Determining installed version from '{0}'".format(filename))

        if os.path.isfile(filename):
            with open(filename) as f:
                for line in f:
                    if identifier in line:
                        version_line = line.strip()
                        break
                else:
                    self.error(
                            "Unable to find '{0}' in {1}.".format(identifier,
                                    filename))

        return version_line

    def host_exe(self, name):
        """ Convert a generic executable name to a host-specific version. """

        return self._sysroot.host_exe(name)

    @property
    def host_platform_name(self):
        """ The name of the host platform. """

        return self._sysroot.host.platform.name

    @property
    def host_python(self):
        """ The full pathname of the host Python executable. """

        return self._sysroot.host_python

    @host_python.setter
    def host_python(self, value):
        """ Set the full pathname of the host Python executable. """

        self._sysroot.host_python = value

    @property
    def host_qmake(self):
        """ The full pathname of the host qmake executable. """

        return self._sysroot.host_qmake

    @abstractmethod
    def install(self):
        """ Install the component. """

    @staticmethod
    def parse_version_number(version_str):
        """ Return the VersionNumber object corresponding to a version number
        as a string.  UserException is raised if it couldn't be parsed.

        The version number format is M[.m[.p]][suffix] where M is the int major
        version, m is the int minor version, p is the int patch version and
        suffix is a str suffix.
        """

        from ..version_number import VersionNumber

        return VersionNumber.parse_version_number(version_str)

    def progress(self, message):
        """ Issue a progress message. """

        self._sysroot.progress(message, component=self)

    def run(self, *args, capture=False):
        """ Run a command, optionally capturing stdout. """

        return self._sysroot.run(*args, capture=capture)

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

        self._sysroot.warning(message, component=self)

    def _android_only(self, attr_name):
        """ Issue an error message about an Android-only attribute. """

        self.error(
                "the '{0}' attribute is only supported for Android targets".format(attr_name))

    def _apple_only(self, attr_name):
        """ Issue an error message about an Apple-only attribute. """

        self.error(
                "the '{0}' attribute is only supported for Apple targets".format(
                        attr_name))


class SourceComponent(ComponentBase):
    """ The base class for the implemenation of component plugins that can be
    installed from a source package.
    """

    def get_options(self):
        """ Return a list of ComponentOption objects that define the components
        configurable options.
        """

        options = super().get_options()

        options.append(
                ComponentOption('install_from_source', type=bool, default=True,
                        help="Install from a source package rather an "
                                "existing installation."))

        return options

    def get_source_archive(self, archive_name, url=None):
        """ Return the pathname of a local copy of a source archive.  The
        source directories specified by the --source-dir command line option
        are searched first.  If the archive was not found then it is downloaded
        from the optional URL.
        """

        # Search any source directories.
        for source_dir in self._sysroot.source_dirs:
            self.verbose(
                    "Looking for '{0}' in {1}".format(archive_name,
                            source_dir))

            archive = os.path.join(source_dir, archive_name)
            if os.path.isfile(archive):
                self.verbose(
                        "Found '{0}' in {1}".format(archive_name, source_dir))
                return archive

        if url is None:
            self.error("unable to find '{0}'".format(archive))

        # Search the URL cache.
        cache_dir = os.path.join(os.path.expanduser('~'), '.pyqtdeploy',
                'cache')

        archive = os.path.join(cache_dir, archive_name)
        if os.path.isfile(archive):
            self.verbose("Found '{0}' in download cache".format(archive_name))
            return archive

        # Download the archive into the cache.
        from shutil import copyfileobj
        from urllib.request import urlopen

        os.makedirs(cache_dir, exist_ok=True)

        archive_url = url + archive_name

        self.progress("Downloading '{0}'".format(archive_url))

        try:
            with urlopen(archive_url) as response, open(archive, 'wb') as f:
                copyfileobj(response, f)
        except Exception as e:
            self._sysroot.error("unable to download '{0}'".format(archive_url),
                    detail=str(e), component=self)

        self.verbose("Downloaded '{0}'".format(archive_url))
