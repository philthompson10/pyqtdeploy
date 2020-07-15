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


import csv
import glob
import os
import shlex
import shutil
import tempfile

from ..file_utilities import create_file, open_file
from ..project import Project
from ..platforms import Architecture, Platform
from ..sysroot import Sysroot
from ..user_exception import UserException
from ..version import PYQTDEPLOY_HEXVERSION
from ..version_number import VersionNumber


class Builder:
    """ The builder for a project. """

    def __init__(self, project_name, target_arch_name, message_handler, python,
            qmake):
        """ Initialise the builder for a project. """

        self._message_handler = message_handler

        self._project = Project.load(project_name)
        self._host = Architecture.architecture()
        self._target = Architecture.architecture(target_arch_name)

        self._sysroot = Sysroot(self._project.sysroot_specification,
                self._host, self._target, self._project.sysroots_dir,
                message_handler=self._message_handler, python=python,
                qmake=qmake)

    def build(self, opt, nr_resources, clean, build_dir):
        """ Build the project in a given directory.  Raise a UserException if
        there is an error.
        """

        project = self._project
        python = self._sysroot.get_component('Python')

        # Check the sysroot directory exists.
        if not os.path.isdir(self._sysroot.sysroot_dir):
            raise UserException(
                    "The sysroot directory '{0}' does not exist.".format(
                            self._sysroot.sysroot_dir))

        # Get the names of the required Python modules, extension modules and
        # libraries.
        # TODO
        modules = {}
        #metadata = get_python_metadata(python_target_version)
        #required_modules, required_libraries = project.get_stdlib_requirements(
        #        include_hidden=True)

        #required_py = {}
        #required_ext = {}
        #for name in required_modules.keys():
        #    module = metadata[name]

        #    if module.target and not self._target.is_targeted(module.target):
        #        continue

        #    if module.source is None:
        #        required_py[name] = module
        #    elif not module.core:
        #        required_ext[name] = module

        # Initialise and check we have the information we need.
        #if len(required_ext) != 0:
        #    if source_dir is None:
        #        if project.python_source_dir == '':
        #            raise UserException(
        #                    "The name of the Python source directory has not "
        #                    "been specified")

        #        source_dir = project.path_from_user(project.python_source_dir)

        # Determine the application name.
        if project.application_name:
            application_name = project.application_name
        elif project.application_script:
            application_name = os.path.basename(project.application_script).split('.', maxsplit=1)[0]
        elif project.application_package.name:
            application_name = project.application_package.name
        else:
            application_name = os.path.basename(project.name).split('.', maxsplit=1)[0]

        # Check there is an entry point or a script.
        if project.application_script == '':
            if project.application_entry_point == '':
                raise UserException("Either the application script name or "
                        "the entry point must be specified")
            elif len(project.application_entry_point.split(':')) != 2:
                raise UserException("An entry point must be a module name and "
                        "a callable separated by a colon.")
        elif project.application_entry_point != '':
            raise UserException("Either the application script name or the "
                    "entry point must be specified but not both")

        # Get other directories from the project that may be overridden.
        #if include_dir is None:
        #    include_dir = project.path_from_user(
        #            project.python_target_include_dir)

        #if python_library is None:
        #    python_library = project.path_from_user(
        #            project.python_target_library)

        #if standard_library_dir is None:
        #    standard_library_dir = project.path_from_user(
        #            project.python_target_stdlib_dir)

        # Set the name of the build directory.
        if not build_dir:
            build_dir = 'build-' + self._target.name

        self._build_dir = os.path.abspath(build_dir)

        # Remove any build directory if required.
        if clean:
            self._message_handler.progress_message(
                    "Cleaning {0}".format(self._build_dir))
            shutil.rmtree(self._build_dir, ignore_errors=True)

        # Now start the build.
        self._create_directory(self._build_dir)

        # Create the job file and writer.
        job_dir = tempfile.TemporaryDirectory()
        job_filename = os.path.join(job_dir.name, 'jobs.csv')
        job_file = open(job_filename, 'w', newline='')
        job_writer = csv.writer(job_file)

        # Freeze the bootstrap.  Note that from Python v3.5 the modified part
        # is in _bootstrap_external.py and _bootstrap.py is unchanged from the
        # original source.  We continue to use a local copy of _bootstrap.py
        # as it still needs to be frozen and we don't want to depend on an
        # external source.
        self._freeze_bootstrap('bootstrap', self._build_dir, job_writer,
                python)
        self._freeze_bootstrap('bootstrap_external', self._build_dir,
                job_writer, python)

        # Freeze any main application script.
        if project.application_script != '':
            self._freeze(job_writer,
                    os.path.join(self._build_dir, 'frozen_main.h'),
                    project.project_path(project.application_script),
                    'pyqtdeploy_main', as_c=True)

        # Create the pyqtdeploy module version file.
        with create_file(os.path.join(self._build_dir, 'pyqtdeploy_version.h')) as f:
            f.write(
                    '#define PYQTDEPLOY_HEXVERSION %s\n' % hex(
                            PYQTDEPLOY_HEXVERSION))

        # Generate the application resources.
        resource_names = self._generate_resources(modules, job_writer,
                nr_resources)

        # Write the .pro file.
        self._write_qmake(application_name, modules, job_writer, opt,
                resource_names, python)

        # Run the freeze jobs.
        job_file.close()

        self._run_freeze(python, job_filename, opt)

    def _create_directory(self, dir_name):
        """ Create a directory which may already exist. """

        self._message_handler.verbose_message(
                "Creating directory {0}".format(dir_name))

        try:
            os.makedirs(dir_name, exist_ok=True)
        except Exception as e:
            raise UserException(
                    "Unable to create the '{0}' directory".format(dir_name),
                    str(e))

    @staticmethod
    def _freeze(job_writer, out_file, in_file, name, as_c=False):
        """ Freeze a Python source file to a C header file or a data file. """

        if as_c:
            conversion = 'C'
        else:
            name = ':/' + name
            conversion = 'data'

        job_writer.writerow([out_file, in_file, name, conversion])

    def _freeze_bootstrap(self, name, build_dir, job_writer, python):
        """ Freeze a version dependent bootstrap script. """

        # Find the bootstrap script appropriate for this version of Python.
        bootstrap_dir = self._get_lib_path(name)
        bootstrap = None
        bootstrap_version = None

        for fn in os.listdir(bootstrap_dir):
            version = fn.split('-')[-1]
            if version.endswith('.py'):
                version = version[:-3]

            try:
                version = VersionNumber.parse_version_number(version)
            except UserException:
                continue

            if version > python.version:
                # This is for a later version so we can ignore it.
                continue

            if bootstrap is None or bootstrap_version < version:
                # This is a better candidate than we have so far.
                bootstrap = fn
                bootstrap_version = version

        assert bootstrap is not None

        bootstrap_path = os.path.join(bootstrap_dir, bootstrap)
        self._freeze(job_writer,
                os.path.join(build_dir, 'frozen_' + name + '.h'),
                bootstrap_path, 'pyqtdeploy_' + name, as_c=True)

    def _generate_resources(self, modules, job_writer, nr_resources):
        """ Generate the application resource files and return the names of
        the files relatve to the build directory.
        """

        project = self._project

        resources_contents = []

        # Handle any application package.
        if project.application_package.name is not None:
            self._write_python_modules(project.application_package.modules,
                    os.path.dirname(
                            project.project_path(
                                    project.application_package.name)),
                    resources_contents, job_writer)

        # Handle the standard library and other packages.
        # TODO

        # Write the .qrc files.
        if nr_resources == 1:
            resource_names = [self._write_resource(resources_contents)]
        else:
            resource_names = []

            nr_files = len(resources_contents)

            if nr_resources > nr_files:
                nr_resources = nr_files

            per_resource = (nr_files + nr_resources - 1) // nr_resources
            start = 0

            for r in range(nr_resources):
                end = start + per_resource
                if end > nr_files:
                    end = nr_files

                resource_names.append(
                        self._write_resource(resources_contents[start:end], r))
                start += per_resource

        return resource_names

    @staticmethod
    def _get_lib_path(name):
        """ Get the pathname of a file or directory in the 'lib' sub-directory.
        """

        return os.path.join(os.path.dirname(__file__), 'lib', name)

    def _run_freeze(self, python, job_filename, opt):
        """ Run the accumlated freeze jobs. """

        args = [python.host_python]

        if opt == 2:
            args.append('-OO')
        elif opt == 1:
            args.append('-O')

        args.append(self._get_lib_path('freeze.py'))
        args.append(job_filename)

        self._host.platform.run(*args, message_handler=self._message_handler)

    def _write_python_module(self, name, module, modules, module_root_dir,
            resources_contents, job_writer):
        """ Write a Python module as a resource. """

        # Discard anything other than non-core pure Python modules.
        if module.core or module.builtin or module.source:
            return

        # Determine the full path of the file and whether or not it needs
        # freezing.
        src_name = name.replace('.', os.sep)
        src_path = os.path.join(module_root_dir, src_name)

        if module.data_ext is None:
            if os.path.isdir(src_path):
                src_name = os.path.join(src_name, '__init__')

            dst_name = src_name + '.pyo'
            src_name = src_name + '.py'

            src_path = os.path.join(module_root_dir, src_name)

            # This can happen legitimately if the name corresponds to a simple
            # directory rather than a Python package.
            if not os.path.isfile(src_path):
                return

            freeze = True
        else:
            src_name += module.data_ext
            src_path += module.data_ext

            dst_name = src_name

            freeze = False

        # Determine where the resource is to be created.
        dst_path = os.path.join(self._build_dir, 'resources', dst_name)
        os.makedirs(os.path.dirname(dst_path), exist_ok=True)

        if freeze:
            self._freeze(job_writer, dst_path, src_path,
                    dst_name.replace(os.sep, '/'))
        else:
            shutil.copy2(src_path, dst_path)

        resources_contents.append(dst_name)

    def _write_python_modules(self, modules, module_root_dir,
            resources_contents, job_writer):
        """ Write a collection of Python modules as resources. """

        for name, module in modules.items():
            self._write_python_module(name, module, modules, module_root_dir,
                    resources_contents, job_writer)

    def _write_resource(self, resources_contents, nr=-1):
        """ Write a single resource file and return its basename. """

        suffix = '' if nr < 0 else str(nr)
        basename = 'pyqtdeploy{0}.qrc'.format(suffix)

        with create_file(os.path.join(self._build_dir, 'resources', basename)) as f:
            f.write('''<!DOCTYPE RCC>
<RCC version="1.0">
    <qresource>
''')

            for content in resources_contents:
                f.write('        <file>{}</file>\n'.format(content))

            f.write('''    </qresource>
</RCC>
''')

        return basename

    # The map of non-C/C++ source extensions to qmake variable.
    _source_extensions = (
        ('.asm',    'MASMSOURCES'),
        ('.h',      'HEADERS'),
        ('.java',   'JAVASOURCES'),
        ('.l',      'LEXSOURCES'),
        ('.pyx',    'CYTHONSOURCES'),
        ('.y',      'YACCSOURCES')
    )

    def _write_qmake(self, application_name, modules, job_writer, opt,
            resource_names, python):
        """ Create the .pro file for qmake. """

        project = self._project
        target_platform = self._target.platform.name

        f = create_file(
                os.path.join(self._build_dir, application_name + '.pro'))

        f.write('# Generated for {0} and Python v{1}.\n\n'.format(
                self._target.name, python.version))

        f.write('TEMPLATE = app\n')
        f.write('\n')

        # Configure the CONFIG and QT values that are project dependent.
        needs_cpp11 = False
        needs_gui = False
        qmake_qt5 = set()
        qmake_config5 = set()

        for pyqt_m in project.pyqt_modules:
            metadata = self._get_pyqt_module_metadata(pyqt_m)

            if metadata.cpp11:
                needs_cpp11 = True

            if metadata.gui:
                needs_gui = True

            if self._target.is_targeted(metadata.targets):
                qmake_qt5.update(metadata.qt5)
                qmake_config5.update(metadata.config5)

        # Extract QT and CONFIG values that not version-specific.
        qmake_qt45 = qmake_qt4 & qmake_qt5
        qmake_qt4 -= qmake_qt45
        qmake_qt5 -= qmake_qt45

        qmake_config45 = qmake_config4 & qmake_config5
        qmake_config4 -= qmake_config45
        qmake_config5 -= qmake_config45

        # Generate QT.
        self._write_qt_config(f, 'QT', None, qmake_qt45)
        self._write_qt_config(f, 'QT', 4, qmake_qt4)
        self._write_qt_config(f, 'QT', 5, qmake_qt5)

        if not needs_gui:
            f.write('QT -= gui\n')

        # Generate CONFIG.
        config = ['warn_off']

        if target_platform == 'win':
            if project.application_is_console or not needs_gui:
                config.append('console')

        if needs_cpp11:
            config.append('c++11')

        f.write('CONFIG += {0}\n'.format(' '.join(config)))

        if target_platform == 'macos':
            if not project.application_is_bundle:
                f.write('CONFIG -= app_bundle\n')

        self._write_qt_config(f, 'CONFIG', None, qmake_config45)
        self._write_qt_config(f, 'CONFIG', 4, qmake_config4)
        self._write_qt_config(f, 'CONFIG', 5, qmake_config5)

        # Modules can share sources so we need to make sure we don't include
        # them more than once.  We might as well handle the other things in the
        # same way.
        used_qt = set()
        used_config = set()
        used_sources = set()
        used_defines = set()
        used_includepath = set()
        used_libs = set()
        used_inittab = set()
        used_dlls = set()

        # Handle any static PyQt modules.
        site_packages = standard_library_dir + '/site-packages'
        pyqt_package = self._get_pyqt_package_name()

        for module in self._get_all_pyqt_modules():
            # The uic module is pure Python.
            if module == 'uic':
                continue

            metadata = self._get_pyqt_module_metadata(module)

            if not self._target.is_targeted(metadata.targets):
                continue

            # The sip module is always needed (implicitly or explicitly) if we
            # have got this far.  We handle it separately when it is in a
            # different directory.
            if module == 'sip' and not private_sip:
                used_inittab.add(module)
                used_libs.add('-L' + site_packages)
            else:
                used_inittab.add(pyqt_package + '.' + module)
                used_libs.add('-L' + site_packages + '/' + pyqt_package)

            lib_name = '-l' + module
            if metadata.needs_suffix:
                # Qt4's qmake thinks -lQtCore etc. always refer to the Qt
                # libraries so PyQt4 creates static libraries with a suffix.
                lib_name += '_s'

            used_libs.add(lib_name)

        # Handle any other extension modules.
        for other_em in project.other_extension_modules:
            # If the name is scoped then the targets are the outer scopes for
            # the remaining values.
            value = self._get_scoped_value(other_em.name)
            if value is None:
                continue

            used_inittab.add(value)

            if other_em.qt != '':
                self._add_compound_scoped_values(used_qt, other_em.qt, False)

            if other_em.config != '':
                self._add_compound_scoped_values(used_config, other_em.config,
                        False)

            if other_em.sources != '':
                self._add_compound_scoped_values(used_sources,
                        other_em.sources, True)

            if other_em.defines != '':
                self._add_compound_scoped_values(used_defines,
                        other_em.defines, False)

            if other_em.includepath != '':
                self._add_compound_scoped_values(used_includepath,
                        other_em.includepath, True)

            if other_em.libs != '':
                self._add_compound_scoped_values(used_libs, other_em.libs,
                        False)

        # Configure the target Python interpreter.
        if include_dir != '':
            used_includepath.add(include_dir)

        if python_library != '':
            fi = QFileInfo(python_library)

            py_lib_dir = fi.absolutePath()
            lib = fi.completeBaseName()

            # This is smart enough to translate the Python library as a UNIX .a
            # file to what Windows needs.
            if lib.startswith('lib'):
                lib = lib[3:]

            if '.' in lib and target_platform == 'win':
                lib = lib.replace('.', '')

            used_libs.add('-l' + lib)
            used_libs.add('-L' + py_lib_dir)
        else:
            py_lib_dir = None

        # Handle any standard library extension modules.
        if target_platform not in project.python_use_platform:
            self._add_stdlib_extension_modules(project, target_platform,
                    source_dir, required_ext, used_inittab, used_sources,
                    used_includepath, used_defines, used_libs, used_dlls)

        # Handle any required external libraries.
        android_extra_libs = []

        external_libs = project.external_libraries.get(target_platform, ())

        for required_lib in required_libraries:
            # Skip any external libraries that are not for the current target.
            required_lib = self._get_scoped_value(required_lib)
            if required_lib is None:
                continue

            defines = includepath = libs = ''

            for xlib in external_libs:
                if xlib.name == required_lib:
                    defines = xlib.defines
                    includepath = xlib.includepath
                    libs = xlib.libs
                    break
            else:
                # Use the defaults.
                for xlib in external_libraries_metadata:
                    if xlib.name == required_lib:
                        if target_platform not in project.python_use_platform:
                            defines = xlib.defines
                            includepath = xlib.includepath
                            libs = xlib.get_libs(target_platform)

                        break

            # Check the library is not disabled for this target.
            enabled = False

            if defines != '':
                self._add_compound_scoped_values(used_defines, defines, False)
                enabled = True

            if includepath != '':
                self._add_compound_scoped_values(used_includepath, includepath,
                        True)
                enabled = True

            if libs != '':
                self._add_compound_scoped_values(used_libs, libs, False)
                enabled = True

            if enabled and target_platform == 'android':
                self._add_android_extra_libs(libs, android_extra_libs)

        # Specify any project-specific configuration.
        if used_qt:
            f.write('\n')
            self._write_used_values(f, used_qt, 'QT')

        if used_config:
            f.write('\n')
            self._write_used_values(f, used_config, 'CONFIG')

        # Python v3.6.0 requires C99 at least.  Note that specifying 'c++11' in
        # 'CONFIG' doesn't affect 'CFLAGS'.
        if python_target_version >= (3, 6) and target_platform != 'win':
            f.write('\n')
            f.write('QMAKE_CFLAGS += -std=c99\n')

        # Specify the resource files.
        f.write('\n')
        f.write('RESOURCES = \\\n')
        f.write(' \\\n'.join(['    resources/{0}'.format(n) for n in resource_names]))
        f.write('\n')

        # Specify the defines.
        defines = []
        headers = ['pyqtdeploy_version.h', 'frozen_bootstrap.h',
                'frozen_bootstrap_external.h']

        if project.application_script != '':
            defines.append('PYQTDEPLOY_FROZEN_MAIN')
            headers.append('frozen_main.h')

        if opt:
            defines.append('PYQTDEPLOY_OPTIMIZED')

        if defines or used_defines:
            f.write('\n')

            if defines:
                f.write('DEFINES += {0}\n'.format(' '.join(defines)))

            self._write_used_values(f, used_defines, 'DEFINES')

        # Specify the include paths.
        if used_includepath:
            f.write('\n')
            self._write_used_values(f, used_includepath, 'INCLUDEPATH')

        # Specify the source files and header files.
        f.write('\n')
        f.write('SOURCES = pyqtdeploy_main.cpp pyqtdeploy_start.cpp pdytools_module.cpp\n')
        self._write_used_values(f, used_sources, 'SOURCES')
        self._write_main(used_inittab, used_defines)
        shutil.copy2(self._get_lib_path('pyqtdeploy_start.cpp'),
                self._build_dir)
        shutil.copy2(self._get_lib_path('pdytools_module.cpp'),
                self._build_dir)

        f.write('\n')
        f.write('HEADERS = {0}\n'.format(' '.join(headers)))

        # Specify the libraries.
        if used_libs:
            f.write('\n')
            self._write_used_values(f, used_libs, 'LIBS')

        # Add the library files to be added to an Android APK.
        if android_extra_libs and target_platform == 'android':
            f.write('\n')
            f.write('ANDROID_EXTRA_LIBS += %s\n' % ' '.join(android_extra_libs))

        # If we are using the platform Python on Windows then copy in the
        # required DLLs if they can be found.
        if 'win' in project.python_use_platform and used_dlls and py_lib_dir is not None:
            self._copy_windows_dlls(py_lib_dir, used_dlls, f)

        # Add the project independent post-configuration stuff.
        with open_file(self._get_lib_path('post_configuration.pro')) as pro_f:
            f.write(pro_f.read())

        # Add any application specific stuff.
        qmake_configuration = project.qmake_configuration.strip()

        if qmake_configuration != '':
            f.write('\n' + qmake_configuration + '\n')

        # All done.
        f.close()

    @classmethod
    def _write_qt_config(cls, f, name, qt_major, values):
        """ Write the values of QT or CONFIG which may be Qt version specific.
        """

        if values:
            if qt_major is None:
                indent = ''
            else:
                indent = '    '

                if qt_major == 5:
                    f.write('greaterThan(QT_MAJOR_VERSION, 4) {\n')
                else:
                    f.write('lessThan(QT_MAJOR_VERSION, 5) {\n')

            f.write('%s%s += %s\n' % (indent, name, ' '.join(values)))

            if indent:
                f.write('}\n')

    @classmethod
    def _write_used_values(cls, f, used_values, name):
        """ Write a set of used values to a .pro file. """

        # Sort them for reproduceable output.
        for value in sorted(used_values):
            qmake_var = name

            if qmake_var == 'SOURCES':
                for ext, var in cls._source_extensions:
                    if value.endswith(ext):
                        qmake_var = var
                        break

            elif qmake_var == 'LIBS':
                # A (strictly unnecessary) bit of pretty printing.
                if value.startswith('"-framework') and value.endswith('"'):
                    value = value[1:-1]

            f.write('{0} += {1}\n'.format(qmake_var, value))

    def _copy_windows_dlls(self, py_lib_dir, modules, f):
        """ Generate additional qmake commands to install additional Windows
        DLLs so that the application will be able to run.
        """

        python_target_version = self._project.python_target_version

        dlls = ['python{}{}.dll'.format(python_target_version._major,
                python_target_version._minor)]

        # TODO: MSVC2019 DLLs?
        dlls.append('vcruntime140.dll')

        for module in modules:
            dlls.append(module.pyd)

            if module.dlls is not None:
                dlls.extend(module.dlls)

        for name in dlls:
            f.write('''
PDY_DLL = %s/DLLs%d.%d/%s
exists($$PDY_DLL) {
    CONFIG(debug, debug|release) {
        QMAKE_POST_LINK += $(COPY_FILE) $$shell_path($$PDY_DLL) $$shell_path($$OUT_PWD/debug) &
    } else {
        QMAKE_POST_LINK += $(COPY_FILE) $$shell_path($$PDY_DLL) $$shell_path($$OUT_PWD/release) &
    }
}
''' % (py_lib_dir, py_major, py_minor, name))

    @staticmethod
    def _python_source_file(py_source_dir, rel_path):
        """ Return the absolute name of a file in the Python source tree
        relative to the Modules directory.
        """

        file_path = py_source_dir + '/Modules/' + rel_path

        return QFileInfo(file_path).absoluteFilePath()

    def _add_compound_scoped_values(self, used_values, raw, isfilename):
        """ Parse a string of space separated possible scoped values and add
        them to a set of used values.  The values are optionally treated as
        filenames where they are converted to absolute filenames with UNIX
        separators and have environment variables expanded.
        """

        project = self._project

        for scoped_value in self._split_quotes(raw):
            value = self._get_scoped_value(scoped_value)
            if value is None:
                continue

            # Convert potential filenames.
            if isfilename:
                value = project.path_from_user(value)
            elif value.startswith('-L'):
                value = '-L' + project.path_from_user(value[2:])

            used_values.add(value)

    def _add_android_extra_libs(self, libs, android_extra_libs):
        """ Add the shared library files for Android. """

        project = self._project

        lib_dir = ''
        lib_so = []

        for scoped_value in self._split_quotes(libs):
            # We support the use of scoped values (to be consistent) but it
            # actually makes no sense in this context.
            value = self._get_scoped_value(scoped_value)
            if value is None:
                continue

            if value.startswith('-L'):
                lib_dir = project.path_from_user(value[2:])
            elif value.startswith('-l'):
                lib_so.append('lib' + value[2:] + '.so')

        if lib_dir != '':
            for lib in lib_so:
                android_extra_libs.append(lib_dir + '/' + lib)

    @staticmethod
    def _split_quotes(s):
        """ A generator for a splitting a string allowing for quoted spaces.
        """

        s = s.lstrip()

        while s != '':
            quote_stack = []
            i = 0

            for ch in s:
                if ch in '\'"':
                    if len(quote_stack) == 0 or quote_stack[-1] != ch:
                        quote_stack.append(ch)
                    else:
                        quote_stack.pop()
                elif ch == ' ':
                    if len(quote_stack) == 0:
                        break

                i += 1

            yield s[:i]

            s = s[i:].lstrip()

    def _get_scoped_value(self, scoped_value):
        """ Return the value from a (possibly) scoped value or None if the
        value isn't valid for the target.
        """

        parts = scoped_value.split('#', maxsplit=1)
        if len(parts) == 2:
            scope, value = parts

            if not self._target.is_targeted(scope):
                value = None
        else:
            value = scoped_value

        return value

    def _write_main(self, inittab, defines):
        """ Create the application specific pyqtdeploy_main.cpp file. """

        project = self._project

        f = create_file(os.path.join(self._build_dir, 'pyqtdeploy_main.cpp'))

        # Compilation fails when using GCC 5 when both Py_BUILD_CORE and
        # HAVE_STD_ATOMIC are defined.  Py_BUILD_CORE gets defined when certain
        # Python modukes are used.  We simply make sure HAVE_STD_ATOMIC is not
        # defined.
        if 'Py_BUILD_CORE' in defines:
            f.write('''// Py_BUILD_CORE/HAVE_STD_ATOMIC conflict workaround.
#include <pyconfig.h>
#undef HAVE_STD_ATOMIC

''')

        f.write('''#include <Python.h>
#include <QtGlobal>


''')

        if len(inittab) > 0:
            c_inittab = 'extension_modules'

            self._write_inittab(f, inittab, c_inittab)
        else:
            c_inittab = 'NULL'

        sys_path = project.sys_path

        if sys_path != '':
            f.write('static const char *path_dirs[] = {\n')

            for dir_name in shlex.split(sys_path):
                f.write('    "{0}",\n'.format(dir_name.replace('"','\\"')))

            f.write('''    NULL
};

''')

        if project.application_script != '':
            main_module = '__main__'
            entry_point = 'NULL'
        else:
            main_module, entry_point = project.application_entry_point.split(
                    ':')
            entry_point = '"' + entry_point + '"'

        path_dirs = 'path_dirs' if sys_path != '' else 'NULL'

        if self._target.platform.name == 'win':
            f.write('''

#include <windows.h>

extern int pyqtdeploy_start(int argc, wchar_t **w_argv,
        struct _inittab *extension_modules, const char *main_module,
        const char *entry_point, const char **path_dirs);

int main(int argc, char **)
{
    LPWSTR *w_argv = CommandLineToArgvW(GetCommandLineW(), &argc);

    return pyqtdeploy_start(argc, w_argv, %s, "%s", %s, %s);
}
''' % (c_inittab, main_module, entry_point, path_dirs))
        else:
            f.write('''

extern int pyqtdeploy_start(int argc, char **argv,
        struct _inittab *extension_modules, const char *main_module,
        const char *entry_point, const char **path_dirs);

int main(int argc, char **argv)
{
    return pyqtdeploy_start(argc, argv, %s, "%s", %s, %s);
}
''' % (c_inittab, main_module, entry_point, path_dirs))

        f.close()

    def _write_inittab(self, f, inittab, c_inittab):
        """ Write the Python version specific extension module inittab. """

        # We want reproduceable output.
        sorted_inittab = sorted(inittab)

        for name in sorted_inittab:
            base_name = name.split('.')[-1]

            f.write('extern "C" PyObject *PyInit_%s(void);\n' % (base_name))

        f.write('''
static struct _inittab %s[] = {
''' % c_inittab)

        for name in sorted_inittab:
            base_name = name.split('.')[-1]

            f.write('    {"%s", PyInit_%s},\n' % (name, base_name))

        f.write('''    {NULL, NULL}
};
''')
