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

from .component_option import ComponentOption


class AbstractComponent(ABC):
    """ The abstract base class for the implementation of a component plugin.
    """

    ###########################################################################
    # The following make up the public API to be used by component plugins.
    ###########################################################################

    # The list of components that, if specified, should be installed before
    # this one.
    preinstalls = []

    # The dict of VersionedModule objects provided by the component.
    provides = {}

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

    def create_file(name):
        """ Create a text file and return the file object. """

        self._sysroot.create_file(name, component=self)

    def error(self, message, detail=''):
        """ Issue an error message.  This method will not return. """

        self._sysroot.error(message, detail=detail, component=self)

    def find_exe(self, name, required=True):
        """ Return the absolute pathname of an executable located on PATH. """

        return self._sysroot.find_exe(name, required=required, component=self)

    def get_component(self, name, required=True):
        """ Return the component object for the given name or None if the
        component hasn't been specified.  If it has not been specified and it
        is required then raise an exception.
        """

        return self._sysroot.get_component(name, required=required,
                component=self)

    def get_file(self, name):
        """ Return the pathname of a file in one of the directories specified
        by the --source-dir command line option.  None is return if it could
        not be found.
        """

        for source_dir in self._sysroot.source_dirs:
            self.verbose("Looking for '{0}' in {1}".format(name, source_dir))

            pathname = os.path.join(source_dir, name)
            if os.path.isfile(pathname):
                self.verbose("Found '{0}' in {1}".format(name, source_dir))

                return pathname

        return None

    def get_options(self):
        """ Return a list of ComponentOption objects that define the components
        configurable options.
        """

        return [ComponentOption('version', required=True,
                help="The version number of the component.")]

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

    @abstractmethod
    def install(self):
        """ Install the component. """

    def open_file(name):
        """ Open an existing text file and return the file object. """

        return self._sysroot.open_file(name, component=self)

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

    def unsupported(self):
        """ Issue an error message that the version of the component is
        unsupported.
        """

        self.error("v{0} is unsupported".format(self.version))

    def untested(self):
        """ Issue a warning message that the version of the component is
        untested.
        """

        self.warning("v{0} is untested".format(self.version))

    def verify(self):
        """ Verify the component.  This will be called after the options have
        been parsed and the version number resolved.
        """

    def verbose(self, message):
        """ Issue a verbose progress message. """

        self._sysroot.verbose(message, component=self)

    @property
    def verbose_enabled(self):
        """ True if verbose messages are being displayed. """

        return self._sysroot.verbose_enabled

    def verify_host_tools(self, tools):
        """ Verify that a sequence of host tools is available. """

        for tool in tools:
            self.find_exe(tool)

    def warning(self, message):
        """ Issue a warning message. """

        self._sysroot.warning(message, component=self)

    ###########################################################################
    # The following are not part of the public API used by component plugins.
    ###########################################################################

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
                values = value if isinstance(value, list) else [value]

                for v in values:
                    if v not in option.values:
                        self.error(
                                "'{0}' must have one of these values: {1} and "
                                        "not '{2}'".format(option.name,
                                                ', '.join(option.values), v))

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

    @property
    def modules(self):
        """ The map of Module instances, keyed by the name of the module, of
        the modules provided by this version of the component.
        """

        if self._modules is None:
            self._modules = {}
            provides = self.provides
            openssl = self.get_component('OpenSSL', required=False)
            result_cache = {}

            for name in provides:
                module = self._available_version(name, provides, openssl,
                        result_cache)

                if module is not None:
                    self._modules[name] = module

        return self._modules

    def _available_version(self, name, provides, openssl, result_cache):
        """ Return the Module object for a module that is available for this
        version and target and available components or None if it is not
        available.
        """

        # See if we have already determined if the module is available.
        try:
            return result_cache[name]
        except KeyError:
            pass

        # Try each version of the module.
        versions = provides[name]

        if not isinstance(versions, tuple):
            versions = (versions, )

        for versioned_module in versions:
            if versioned_module.applies_to(self.version):
                module = versioned_module.module

                # Circular dependencies are valid (and presumably dealt with in
                # the module implementation) so we assume the module will be
                # available (to prevent recursive calls) and update the result
                # afterwards.
                result_cache[name] = module

                if not self._is_available(module, provides, openssl, result_cache):
                    module = None

                break
        else:
            module = None

        # Cache the result.
        result_cache[name] = module

        return module

    def _is_available(self, module, provides, openssl, result_cache):
        """ Return True if a Module object for a module is available for this
        version and target and available components or None if it is not
        available.
        """

        # Discard modules with missing external dependencies.
        if module.xdep is not None and self.get_component(module.xdep, required=False) is None:
            return False

        # Discard modules not applicable to the target architecture.
        if module.target != '' and not self._sysroot.target.is_targeted(module.target):
            return False

        # Check any dependencies.
        for dep in module.deps:
            if dep.startswith('?'):
                # The dependency is optional so its availability has no impact.
                continue
            elif dep.startswith('!'):
                # This is only provided if OpenSSL is not available.
                if openssl is not None:
                    continue

                dep = dep[1:]

            # Ignore it if it isn't a dependency for this target.
            if '#' in dep:
                target, dep = dep.split('#', maxsplit=1)

                if not self._sysroot.target.is_targeted(target):
                    continue

            # See if it is an inter-component dependency.
            if ':' in dep:
                component_name, dep = dep.split(':', maxsplit=1)
                component = self.get_component(component_name, required=False)
                if component is None:
                    return False

                dep_module = component.modules.get(dep)
            else:
                dep_module = self._available_version(dep, provides, openssl,
                        result_cache)

            if dep_module is None:
                return False

        return True

    def _android_only(self, attr_name):
        """ Issue an error message about an Android-only attribute. """

        self.error(
                "the '{0}' attribute is only supported for Android "
                        "targets".format(attr_name))

    def _apple_only(self, attr_name):
        """ Issue an error message about an Apple-only attribute. """

        self.error(
                "the '{0}' attribute is only supported for Apple "
                        "targets".format(attr_name))
