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
import toml

from PyQt5.QtCore import QDir, QFileInfo, QObject, pyqtSignal

from ..platforms import Architecture, Platform
from ..sysroot import Sysroot, SysrootSpecification
from ..user_exception import UserException

from .project_parts import QrcDirectory, QrcFile, QrcPackage


class Project(QObject):
    """ The encapsulation of a project. """

    # The minimum supported project version.  At the moment a project will be
    # automatically updated to the current version when saved.
    min_version = 0

    # The current project version.
    version = 0

    # Emitted when the modification state of the project changes.
    modified_changed = pyqtSignal(bool)

    @property
    def modified(self):
        """ The modified property getter. """

        return self._modified

    @modified.setter
    def modified(self, value):
        """ The modified property setter. """

        if self._modified != value:
            self._modified = value
            self.modified_changed.emit(value)

    # Emitted when the name of the project changes.
    name_changed = pyqtSignal(str)

    @property
    def name(self):
        """ The name property getter. """

        # Use absoluteFilePath() because the file might not exist.
        return self._name.absoluteFilePath() if self._name is not None else ''

    @name.setter
    def name(self, value):
        """ The name property setter. """

        if self._name is None or self._name.absoluteFilePath() != value:
            self._name = QFileInfo(value)
            self.name_changed.emit(value)

    # Emitted when the version number of Python being targeted changes.
    python_target_version_changed = pyqtSignal()

    def __init__(self, name=''):
        """ Initialise the project. """

        super().__init__()

        self._modified = False
        self._name = QFileInfo(name) if name != '' else None

        self.external_components_availability = {}
        self.python_component = None

        # Initialise the project data.
        self.application_name = ''
        self.application_is_console = False
        self.application_is_bundle = True
        self.application_package = QrcPackage()
        self.application_script = ''
        self.application_entry_point = ''
        self.sys_path = ''
        self.standard_library = []
        self.other_packages = []
        self.sysroot_dir = ''
        self.sysroot_toml = ''
        self.qmake_configuration = ''

    def path_to_user(self, path):
        """ Convert a file name to one that is relative to the project file if
        possible and uses native separators.
        """

        if self._name is not None:
            rel = self._name.dir().relativeFilePath(path)
            if not rel.startswith('..'):
                path = rel

        return QDir.toNativeSeparators(path)

    def path_from_user(self, user_path):
        """ Convert the name of a file or directory specified by the user to
        the standard Qt format (ie. an absolute path using UNIX separators).  A
        user path may be relative to the name of the project and may contain
        environment variables.
        """

        fi = self._fileinfo_from_user(user_path)

        # Use the canonical name if possible (ie. when the file exists) and
        # fall back to the absolute name.
        path = fi.canonicalFilePath()
        if path == '':
            path = fi.absoluteFilePath()

        return path

    def get_executable_basename(self):
        """ Return the basename of the application executable (i.e. with no
        path or extension.
        """

        if self.application_name != '':
            return self.application_name

        name = self.application_script
        if name == '':
            name = self.application_package.name
            if name == '':
                return ''

        return self._fileinfo_from_user(name).completeBaseName()

    def _fileinfo_from_user(self, user_path):
        """ Convert the name of a file or directory specified by the user to a
        QFileInfo instance.  A user path may be relative to the name of the
        project file and may contain environment variables.
        """

        # TODO: review need to allow environment variables.
        fi = QFileInfo(os.path.expandvars(user_path.strip()))

        if fi.isRelative() and self._name is not None:
            fi = QFileInfo(self._name.canonicalPath() + '/' + fi.filePath())

        return fi

    def get_stdlib_requirements(self, include_hidden=False):
        """ Return a 2-tuple of the required Python standard library modules
        and the required external libraries.  The modules are a dict with the
        module name as the key and a bool as the value.  The bool is True if
        the module is explicitly required and False if it is implicitly
        required.  The libraries are a set of well known library names.
        """

        # Work out the dependencies.
        metadata = self.python_component.get_modules()
        all_modules = {name: _DepState(module)
                for name, module in metadata.items()}

        visit = 0
        for name in all_modules.keys():
            self._set_dependency_state(all_modules, name, visit)
            visit += 1

        # Extract the required modules and libraries.
        required_modules = {}
        required_libraries = set()

        for name, dep_state in all_modules.items():
            if dep_state.explicit:
                explicit = True
            elif dep_state.implicit:
                explicit = False
            else:
                continue

            # Handle any hidden dependencies if required.
            if include_hidden:
                for hidden_dep in dep_state.module.hidden_deps:
                    if hidden_dep not in required_modules:
                        required_modules[hidden_dep] = False

            required_modules[name] = explicit

            if dep_state.module.xdep is not None:
                required_libraries.add(dep_state.module.xdep)

        return required_modules, required_libraries

    def _set_dependency_state(self, all_modules, name, visit, is_dep=False):
        """ Set a module's dependency state. """

        dep_state = all_modules[name]

        if dep_state.visit == visit:
            return

        dep_state.visit = visit

        if dep_state.module.builtin:
            # This will mean that the explicit and implicit states will remain
            # None and so the module will be omitted from the list.
            return

        dep_state.explicit = (name in self.standard_library)

        if dep_state.module.core or is_dep:
            dep_state.implicit = True

        for dep in dep_state.module.deps:
            # If the first character of the module is '?' then it should be
            # excluded if SSL support is disabled.  If the first character is
            # '!' then it should be excluded if SSL support is enabled.
            if dep[0] == '?':
                if 'ssl' not in self.standard_library:
                    continue

                dep = dep[1:]
            elif dep[0] == '!':
                if 'ssl' in self.standard_library:
                    continue

                dep = dep[1:]

            self._set_dependency_state(all_modules, dep, visit,
                    (dep_state.explicit or dep_state.implicit))

    @classmethod
    def load(cls, file_name, target=None):
        """ Return a new project loaded from the given file.  Raise a
        UserException if there was an error.
        """

        # Get the loader for the project.
        fi = QFileInfo(file_name)
        file_path = QDir.toNativeSeparators(fi.canonicalFilePath())

        if file_path.endswith('.pdy'):
            from .legacy import load_xml as loader

            # Save the file using the current format.
            fi.setFile(file_path.replace('.pdy', '.pdt'))
        else:
            loader = cls._load_toml

        # Create the project and load it.
        project = cls()
        project._name = fi
        loader(project, file_path)
        project.load_sysroot(target)

        return project

    def load_sysroot(self, target=None):
        """ Load the project's sysroot specification file. """

        # Get the pathname of the project file.
        file_path = QDir.toNativeSeparators(self._name.canonicalFilePath())

        # Unless a specific target was specified, create a non-verified sysroot
        # for each supported target architecture that define Python and Qt
        # components.
        host = Architecture.architecture()
        specification = SysrootSpecification(self.sysroot_toml, file_path)

        self.python_component = None
        sysroots = []
        targets = Architecture.all_architectures if target is None else [target]

        for target in targets:
            sysroot = Sysroot(specification, host, target)

            # Make sure the same version of Python and Qt is specified for each
            # one.  For the moment ignore targets that don't specify Python and
            # Qt components.
            python = sysroot.get_component('Python', required=False)
            if python is not None:
                if self.python_component is None:
                    self.python_component = python
                elif self.python_component.version != python.version:
                    raise UserException(
                            "The sysroot specification file defines more than "
                                    "one version of Python.")

                if sysroot.get_component('Qt', required=False) is not None:
                    sysroots.append(sysroot)

        # Make sure at least one target specified Python and Qt components.
        if len(sysroots) == 0:
            raise UserException(
                    "The sysroot specification file does not define 'Python' "
                    "and 'Qt' components for any target architecture.")

        # The availability is 0 if a component isn't available in any sysroot,
        # 1 if it is available for at least one sysroot architecture and 2 if
        # it is available for all sysroots.
        self.external_components_availability = {}

        for name in self.python_component.external_component_names:
            nr_sysroots = 0

            for sysroot in sysroots:
                if sysroot.get_component(name, required=False) is not None:
                    nr_sysroots += 1

            if nr_sysroots == 0:
                availability = 0
            elif nr_sysroots == len(sysroots):
                availability = 2
            else:
                availability = 1

            self.external_components_availability[name] = availability

        self.python_target_version_changed.emit()

    def save(self):
        """ Save the project.  Raise a UserException if there was an error. """

        self._save_project(self.name)

    def save_as(self, file_name):
        """ Save the project to the given file and make the file the
        destination of subsequent saves.  Raise a UserException if there was an
        error.
        """

        self._save_project(file_name)

        # Only do this after the project has been successfully saved.
        self.name = file_name

    @staticmethod
    def _get_dict(container, name):
        """ Return a container value assuming it is a dict. """

        try:
            return container[name]
        except KeyError:
            return {}

    @staticmethod
    def _get_list(container, name):
        """ Return a container value assuming it is a list. """

        try:
            return container[name]
        except KeyError:
            return []

    @classmethod
    def _load_package(cls, container):
        """ Return a populated QrcPackage instance. """

        package = QrcPackage()

        package.name = container.get('name', '')
        package.contents = cls._load_mfs_contents(container)
        package.exclusions = cls._get_list(container, 'exclude')

        return package

    @classmethod
    def _load_mfs_contents(cls, container):
        """ Return a list of contents for a memory-filesystem container. """

        contents = []

        for content_element in cls._get_list(container, 'Content'):
            name = content_element.get('name', '')
            included = content_element.get('included', False)
            isdir = content_element.get('is_directory', False)

            content = QrcDirectory(name, included) if isdir else QrcFile(name, included)

            if isdir:
                content.contents = cls._load_mfs_contents(content_element)

            contents.append(content)

        return contents

    @classmethod
    def _load_toml(cls, project, file_path):
        """ Load a TOML format project file. """

        try:
            with open(file_path) as f:
                root = toml.load(f)
        except Exception as e:
            raise UserException(
                "There was an error reading the project file.", str(e))

        # Check the project version number.
        version = root.get('version')
        if version is None:
            raise UserException("Missing 'version' attribute.")

        if version < cls.min_version:
            raise UserException("The project's format is no longer supported.")

        if version > cls.version:
            raise UserException(
                    "The project's format is version {0} but only version {1} is supported.".format(version, cls.version))

        project.sysroot_toml = root.get('sysroot', '')
        project.sysroot_dir = root.get('sysroot_dir', '')
        project.standard_library = cls._get_list(root, 'standard_library')
        project.other_packages = cls._get_list(root, 'other_packages')

        # The application specific configuration.
        application = cls._get_dict(root, 'Application')

        project.application_entry_point = application.get('entry_point', '')
        project.application_is_console = application.get('is_console', False)
        project.application_is_bundle = application.get('is_bundle', False)
        project.application_name = application.get('name', '')
        project.application_script = application.get('script', '')
        project.qmake_configuration = application.get('qmake_configuration',
                '')
        project.sys_path = application.get('syspath', '')

        # Any application package.
        app_package = application.get('Package')

        if app_package is not None:
            project.application_package = cls._load_package(app_package)
        else:
            project.application_package = QrcPackage()

    def _save_project(self, file_name):
        """ Save the project to the given file.  Raise a UserException if there
        was an error.
        """

        root = {
            'version': self.version,
            'sysroot': self.sysroot_toml,
            'sysroot_dir': self.sysroot_dir,
            'standard_library': self.standard_library,
            'other_packages': self.other_packages
        }

        application = {
            'entry_point': self.application_entry_point,
            'is_console': self.application_is_console,
            'is_bundle': self.application_is_bundle,
            'name': self.application_name,
            'qmake_configuration': self.qmake_configuration,
            'script': self.application_script,
            'syspath': self.sys_path
        }

        if self.application_package.name is not None:
            application['Package'] = self._save_package(
                    self.application_package)

        root['Application'] = application

        try:
            with open(file_name, 'w') as f:
                toml.dump(root, f)
        except Exception as e:
            raise UserException(
                    "There was an error writing the project file.", str(e))

        self.modified = False

    @classmethod
    def _save_package(cls, qrc_package):
        """ Return a container containing a QrcPackage. """

        container = {
            'name': qrc_package.name,
            'exclude': qrc_package.exclusions
        }

        cls._save_mfs_contents(container, qrc_package.contents)

        return container

    @classmethod
    def _save_mfs_contents(cls, container, contents):
        """ Save the contents of a memory-filesystem container. """

        subcontainers = []

        for content in contents:
            isdir = isinstance(content, QrcDirectory)

            subcontainer = {
                'name': content.name,
                'included': content.included,
                'is_directory': isdir
            }

            if isdir:
                cls._save_mfs_contents(subcontainer, content.contents)

            subcontainers.append(subcontainer)

        container['Content'] = subcontainers


class _DepState:
    """ Encapsulate the state information required when working out module
    dependencies.
    """

    def __init__(self, module):
        """ Initialise the object. """

        self.module = module
        self.explicit = False
        self.implicit = False
        self.visit = -1
