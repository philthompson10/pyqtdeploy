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
import shutil

from ..file_utilities import (create_file as fu_create_file,
        open_file as fu_open_file)
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

    # The list of components that, if specified, should be installed before
    # this one.
    preinstalls = []

    # The dict of VersionedModule objects provided by the component.
    provides = {}

    # The installation status.
    _IS_NOT_INSTALLED, _IS_IN_PROGRESS, _IS_INSTALLED = range(3)

    def __init__(self, name, configuration, sysroot):
        """ Initialise the component. """

        self._install_status = self._IS_NOT_INSTALLED

        self.name = name
        self._sysroot = sysroot
        self._modules = None

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

        return self._sysroot.apple_sdk

    @property
    def building_for_target(self):
        """ This is set if building (ie. compiling and linking) for the target
        architecture.  Otherwise build for the host.  The default is True.
        """

        return self._sysroot.building_for_target

    @building_for_target.setter
    def building_for_target(self, value):
        """ Set to build (ie. compile and link) for the target architecture.
        Otherwise build for the host.
        """

        self._sysroot.building_for_target = value

    def copy_file(self, src, dst, macros=None):
        """ Copy a file while expanding an optional dict of macros. """

        self.verbose("Copying {0} to {1}".format(src, os.path.abspath(dst)))

        if macros is None:
            try:
                shutil.copy(src, dst)
            except Exception as e:
                self.error("unable to copy {0}".format(src), detail=str(e))
        else:
            try:
                with open(src) as f:
                    contents = f.read()
            except Exception as e:
                self.error("unable to open {0} for reading".format(src),
                        detail=str(e))

            for key, value in macros.items():
                contents = contents.replace(key, value)

            try:
                with open(dst, 'w') as f:
                    f.write(contents)
            except Exception as e:
                self.error("unable to create {0} for writing".format(dst),
                        detail=str(e))

    def create_dir(self, name, empty=False):
        """ Ensure a directory exists and optionally delete its contents. """

        self._sysroot.create_dir(name, empty=empty, component=self)

    @staticmethod
    def create_file(name):
        """ Create a text file and return the file object.  A UserException is
        raised if there was an error.
        """

        return fu_create_file(name)

    def ensure_installed(self):
        """ Ensure the component is installed. """

        if self._install_status == self._IS_NOT_INSTALLED:
            self._install_status = self._IS_IN_PROGRESS

            # Make sure any optional pre-installs are done.
            for preinstall in self.preinstalls:
                component = self.get_component(preinstall, required=False)
                if component is not None:
                    component.ensure_installed()

            self.progress("Installing component...")
            self.install()

            self._install_status = self._IS_INSTALLED

        elif self._install_status == self._IS_IN_PROGRESS:
            self.error("the component is part of a circular dependency")

    def error(self, message, detail=''):
        """ Issue an error message.  This method will not return. """

        self._sysroot.error(message, detail=detail, component=self)

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

    def get_modules(self):
        """ Return a map of Module instances, keyed by the name of the module,
        of the modules provided by a particular version of the component.
        """

        # Return any cached value.
        if self._modules is not None:
            return self._modules

        self._modules = {}

        for name, versions in self.provides.items():
            if not isinstance(versions, tuple):
                versions = (versions, )

            for versioned_module in versions:
                if versioned_module.applies_to(self.version):
                    self._modules[name] = versioned_module.module
                    break

        return self._modules

    def get_modules_availability(self, component_availability):
        """ Return a map of the availability of each module provided by the
        component.  The key is the module name and the value is the
        availability (a value between 0 and 2).
        """

        modules_availability = {}

        for name in self.get_modules().keys():
            self._get_a_modules_availability(name, modules_availability,
                    component_availability)

        return modules_availability

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

    @property
    def host_dir(self):
        """ The directory containing any host installations. """

        return self._sysroot.host_dir

    def host_exe(self, name):
        """ Convert a generic executable name to a host-specific version. """

        return self._sysroot.host_exe(name)

    @property
    def host_make(self):
        """ The name of the host make executable. """

        return self._sysroot.host_make

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

    @host_qmake.setter
    def host_qmake(self, value):
        """ Set the full pathname of the host qmake executable. """

        self._sysroot.host_qmake = value

    @abstractmethod
    def install(self):
        """ Install the component. """

    @staticmethod
    def open_file(name):
        """ Open an existing text file and return the file object.  A
        UserException is raised if there was an error.
        """

        return fu_open_file(name)

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
    def sysroot_dir(self):
        """ The name of the sysroot directory. """

        return self._sysroot.sysroot_dir

    @property
    def target_arch_name(self):
        """ The name of the target architecture. """

        return self._sysroot.target.name

    @property
    def target_include_dir(self):
        """ The name of the directory containing target header files. """

        return self._sysroot.target_include_dir

    @property
    def target_lib_dir(self):
        """ The name of the directory containing target libraries. """

        return self._sysroot.target_lib_dir

    @property
    def target_platform_name(self):
        """ The name of the target platform. """

        return self._sysroot.target.platform.name

    @property
    def target_src_dir(self):
        """ The name of the directory containing target sources. """

        return self._sysroot.target_src_dir

    @property
    def target_py_include_dir(self):
        """ The name of the directory containing target Python header files.
        """

        return self._sysroot.target_py_include_dir

    @property
    def target_sitepackages_dir(self):
        """ The name of the target Python site-packages directory. """

        return self._sysroot.target_sitepackages_dir

    def verify(self):
        """ Verify the component.  This will be called after the options have
        been parsed and the version number resolved.
        """

    def verbose(self, message):
        """ Issue a verbose progress message. """

        self._sysroot.verbose(message, component=self)

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

    def _get_a_modules_availability(self, name, modules_availability,
            component_availability):
        """ Return the availability of a particular module. """

        availability = modules_availability.get(name)
        if availability is None:
            module = self._modules[name]

            if module.xdep is None:
                availability = 2
            else:
                availability = component_availability.get(module.xdep, 0)

            # Modules can have circular dependencies so set this now to prevent
            # infinite recursion.
            modules_availability[name] = availability

            for dep in module.deps:
                if dep.startswith('?'):
                    # The dependency is optional so its availability has no
                    # impact.
                    continue
                elif dep.startswith('!'):
                    dep = dep[1:]

                dep_availability = self._get_a_modules_availability(dep,
                        modules_availability, component_availability)

                if availability > dep_availability:
                    availability = dep_availability

            for dep in module.hidden_deps:
                if dep[0] in '?!':
                    dep = dep[1:]

                dep_availability = self._get_a_modules_availability(dep,
                        modules_availability, component_availability)

                if availability > dep_availability:
                    availability = dep_availability

            modules_availability[name] = availability

        return availability


class SourceComponent(ComponentBase):
    """ The base class for the implemenation of component plugins that can be
    installed from a source package.
    """

    def get_archive(self):
        """ Return the pathname of a local copy of a source archive.  The
        source directories specified by the --source-dir command line option
        are searched first.  If the archive was not found then it is downloaded
        from the optional URL.
        """

        archive_name = self.get_archive_name()

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

        # Search the download cache.
        cache_dir = os.path.join(os.path.expanduser('~'), '.pyqtdeploy',
                'cache')

        archive = os.path.join(cache_dir, archive_name)
        if os.path.isfile(archive):
            self.verbose("Found '{0}' in download cache".format(archive_name))
            return archive

        # Try and download the archive into the cache.
        urls = self.get_archive_urls()
        if urls:
            from urllib.request import urlopen

            self.create_dir(cache_dir)

            for url in urls:
                archive_url = url + archive_name

                self.verbose("Trying to download '{0}' from {1}".format(
                        archive_name, url))

                try:
                    with urlopen(archive_url) as response, open(archive, 'wb') as f:
                        shutil.copyfileobj(response, f)
                except Exception as e:
                    continue

                self.verbose("Downloaded '{0}'".format(archive_url))

                return archive

        self.error("unable to find '{0}'".format(archive))

    @abstractmethod
    def get_archive_name(self):
        """ Return the filename of the source archive. """

    def get_archive_urls(self):
        """ Return the list of URLs where the source archive might be
        downloaded from.
        """

        # This default implementation does not support downloads.
        return []

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

    def unpack_archive(self, archive, chdir=True):
        """ An archive is unpacked in the current directory.  If requested its
        top level directory becomes the current directory.  The name of the
        directory (not its pathname) is returned.
        """

        # Windows has a problem extracting the Qt source archive (probably the
        # long pathnames).  As a work around we copy it to the current
        # directory and extract it from there.
        self.copy_file(archive, '.')
        archive_name = os.path.basename(archive)

        # Unpack the archive.
        self.verbose("Unpacking '{}'".format(archive_name))

        try:
            shutil.unpack_archive(archive_name)
        except Exception as e:
            self.error("unable to unpack {0}".format(archive_name),
                    detail=str(e))

        # Assume that the name of the extracted directory is the same as the
        # archive without the extension.
        archive_root = None
        for _, extensions, _ in shutil.get_unpack_formats():
            for ext in extensions:
                if archive_name.endswith(ext):
                    archive_root = archive_name[:-len(ext)]
                    break

            if archive_root:
                break
        else:
            # This should never happen if we have got this far.
            self.error("'{0}' has an unknown extension".format(archive))

        # Validate the assumption by checking the expected directory exists.
        if not os.path.isdir(archive_root):
            self.error(
                    "unpacking {0} did not create a directory called '{1}' as "
                            "expected".format(archive_name, archive_root))

        # Delete the copied archive.
        os.remove(archive_name)

        # Change to the extracted directory if required.
        if chdir:
            os.chdir(archive_root)

        return archive_root
