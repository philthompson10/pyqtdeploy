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

from ..metadata import get_python_metadata, supported_python_versions
from ..platforms import Platform
from ..user_exception import UserException

from .project_parts import (ExternalLibrary, ExtensionModule, QrcDirectory,
        QrcFile, QrcPackage)


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

    def __init__(self, name=''):
        """ Initialise the project. """

        super().__init__()

        # Initialise the project meta-data.
        self._modified = False
        self._name = QFileInfo(name) if name != '' else None

        # Initialise the project data.
        self.application_name = ''
        self.application_is_pyqt5 = True
        self.application_is_console = False
        self.application_is_bundle = True
        self.application_package = QrcPackage()
        self.application_script = ''
        self.application_entry_point = ''
        self.external_libraries = {}
        self.other_extension_modules = []
        self.other_packages = []
        self.pyqt_modules = []
        self.python_use_platform = ['win']
        self.python_target_version = supported_python_versions[0]
        self.qmake_configuration = ''
        self.standard_library = []
        self.sys_path = ''

        self.set_default_locations()

    def set_default_locations(self):
        """ Set the various locations to their default values. """

        self.python_host_interpreter = '$SYSROOT/host/bin/python'

        self.python_source_dir = '$SYSROOT/src/Python-$PDY_PY_MAJOR.$PDY_PY_MINOR.$PDY_PY_MICRO'
        self.python_target_include_dir = '$SYSROOT/include/python$PDY_PY_MAJOR.$PDY_PY_MINOR'
        self.python_target_library = '$SYSROOT/lib/libpython$PDY_PY_MAJOR.$PDY_PY_MINOR.a'
        self.python_target_stdlib_dir = '$SYSROOT/lib/python$PDY_PY_MAJOR.$PDY_PY_MINOR'

        self.using_default_locations = True

    def path_to_user(self, path):
        """ Convert a file name to one that is relative to the project name if
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

    def expandvars(self, path):
        """ Call os.path.expandvars() after expanding some internal values. """

        major, minor, micro = self.python_target_version
        major = str(major)
        minor = str(minor)
        micro = str(micro)

        path = path.replace('$PDY_PY_MAJOR', major)
        path = path.replace('${PDY_PY_MAJOR}', major)

        path = path.replace('$PDY_PY_MINOR', minor)
        path = path.replace('${PDY_PY_MINOR}', minor)

        path = path.replace('$PDY_PY_MICRO', micro)
        path = path.replace('${PDY_PY_MICRO}', micro)

        return os.path.expandvars(path)

    def _fileinfo_from_user(self, user_path):
        """ Convert the name of a file or directory specified by the user to a
        QFileInfo instance.  A user path may be relative to the name of the
        project and may contain environment variables.
        """

        fi = QFileInfo(self.expandvars(user_path.strip()))

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
        metadata = get_python_metadata(self.python_target_version)
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

            if dep_state.module.xlib is not None:
                required_libraries.add(dep_state.module.xlib)

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
    def load(cls, file_name):
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

        # Check the target Python version is supported.
        if project.python_target_version not in supported_python_versions:
            raise UserException(
                    "Python v{0} is not supported.".format(
                            '.'.join([str(v)
                                    for v in project.python_target_version])))

        # If the default locations are being used then use the current defaults
        # instead of those (possibly out of date) in the project file.
        if project.using_default_locations:
            project.set_default_locations()

        return project

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

        project.pyqt_modules = cls._get_list(root, 'pyqt_modules')
        project.standard_library = cls._get_list(root, 'standard_library')
        project.using_default_locations = root.get('using_default_locations',
                True)

        # The Python configuration.
        python = cls._get_dict(root, 'Python')

        major = python.get('major', 0)
        minor = python.get('minor', 0)
        patch = python.get('patch', 0)
        project.python_target_version = (major, minor, patch)

        project.python_use_platform = cls._get_list(python, 'platform_python')
        project.python_host_interpreter = python.get('host_interpreter', '')
        project.python_source_dir = python.get('source_dir', '')
        project.python_target_include_dir = python.get('target_include_dir',
                '')
        project.python_target_library = python.get('target_library', '')
        project.python_target_stdlib_dir = python.get('target_stdlib_dir', '')

        # The application specific configuration.
        application = cls._get_dict(root, 'Application')

        project.application_entry_point = application.get('entry_point', '')
        project.application_is_pyqt5 = application.get('is_pyqt5', True)
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

        # Any external C libraries.
        project.external_libraries = {}

        for target, xlibs in cls._get_dict(root, 'ExternalLibraries').items():
            target_external_libs = []

            for xlib in xlibs:
                name = xlib.get('name', '')
                defines = xlib.get('defines', '')
                includepath = xlib.get('includepath', '')
                libs = xlib.get('libs', '')

                target_external_libs.append(
                        ExternalLibrary(name, defines, includepath, libs))

            project.external_libraries[target] = target_external_libs

        # Any other Python packages.
        project.other_packages = [cls._load_package(p)
                for p in cls._get_list(root, 'packages')]

        # Any other extension modules.
        project.other_extension_modules = []

        for extension_module in cls._get_list(root, 'extension_modules'):
            name = extension_module.get('name')
            qt = extension_module.get('qt', '')
            config = extension_module.get('config', '')
            sources = extension_module.get('sources', '')
            defines = extension_module.get('defines', '')
            includepath = extension_module.get('includepath', '')
            libs = extension_module.get('libs', '')

            project.other_extension_modules.append(
                    ExtensionModule(name, qt, config, sources, defines,
                            includepath, libs))

    def _save_project(self, file_name):
        """ Save the project to the given file.  Raise a UserException if there
        was an error.
        """

        root = {
            'version': self.version,
            'pyqt_modules': self.pyqt_modules,
            'standard_library': self.standard_library,
            'using_default_locations': self.using_default_locations
        }

        python = {
            'platform_python': self.python_use_platform,
            'major': self.python_target_version[0],
            'minor': self.python_target_version[1],
            'patch': self.python_target_version[2]
        }

        if not self.using_default_locations:
            python['host_interpreter'] = self.python_host_interpreter
            python['source_dir'] = self.python_source_dir
            python['target_include_dir'] = self.python_target_include_dir
            python['target_library'] = self.python_target_library
            python['target_stdlib_dir'] = self.python_target_stdlib_dir

        root['Python'] = python

        application = {
            'entry_point': self.application_entry_point,
            'is_pyqt5': self.application_is_pyqt5,
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

        externals = {}

        for target, external_libs in self.external_libraries.items():
            target_externals = []

            for external_lib in external_libs:
                external = {
                    'name': external_lib.name,
                    'defines': external_lib.defines,
                    'includepath': external_lib.includepath,
                    'libs': external_lib.libs
                }

                target_externals.append(external)

            externals[target] = target_externals

        root['ExternalLibraries'] = externals

        root['packages'] = [self._save_packages(p)
                for p in self.other_packages]

        extensions = []

        for extension_module in self.other_extension_modules:
            extension = {
                'name': extension_module.name,
                'qt': extension_module.qt,
                'config': extension_module.config,
                'sources': extension_module.sources,
                'defines': extension_module.defines,
                'includepath': extension_module.includepath,
                'libs': extension_module.libs
            }

            extensions.append(extension)

        root['extension_modules'] = extensions

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
