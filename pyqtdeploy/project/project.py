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

from ..sysroot import SysrootSpecification
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

    # Emitted when the sysroot has been loaded.
    sysroot_loaded = pyqtSignal()

    def __init__(self, name=''):
        """ Initialise the project. """

        super().__init__()

        self._modified = False
        self._name = QFileInfo(name) if name != '' else None

        self.sysroot_specification = None

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

        self.sysroot_specification = SysrootSpecification(self.sysroot_toml,
                file_path)

        self.sysroot_loaded.emit()

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
