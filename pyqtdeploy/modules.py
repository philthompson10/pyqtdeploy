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


from .version_number import VersionNumber


class Module:
    """ Encapsulate the meta-data for a module. """

    def __init__(self, internal=False, target='', deps=(), hidden_deps=(),
            core=False, builtin=False, defines=None, xdep=None, modules=None,
            source=None, libs=None, includepath=None, pyd=None, dlls=None,
            data_ext=None):
        """ Initialise the object. """

        # Set if the module is internal.
        self.internal = internal

        # The target platform(s) of the module.
        self.target = target

        # The sequence of modules that this one is dependent on.
        self.deps = (deps, ) if isinstance(deps, str) else deps

        # The sequence of additional modules that this one is dependent on.
        # These dependencies are hidden from the user and (most importantly)
        # further sub-dependencies are ignored.  The use case is the warnings
        # module in Python v3 which is a dependency of the core (for a simple
        # function that should never be called) but drags in a lot of other
        # stuff.
        self.hidden_deps = (hidden_deps, ) if isinstance(hidden_deps, str) else hidden_deps

        # Set if the module is always compiled in to the interpreter library
        # (if it is an extension module) or if it is required (if it is a
        # Python module).
        self.core = core

        # Set if the module is a core Python module that is embedded as a
        # builtin.
        self.builtin = builtin

        # The sequence of (possibly scoped) DEFINES to add to the .pro file.
        self.defines = (defines, ) if isinstance(defines, str) else defines

        # The name of a required external component.
        self.xdep = xdep

        # The sequence of modules or sub-packages if this is a package,
        # otherwise None.
        self.modules = (modules, ) if isinstance(modules, str) else modules

        # The sequence of (possibly scoped) source files relative to the
        # Modules directory if this is an extension module, otherwise None.
        self.source = (source, ) if isinstance(source, str) else source

        # The sequence of (possibly scoped) LIBS to add to the .pro file.
        self.libs = (libs, ) if isinstance(libs, str) else libs

        # The sequence of (possibly scoped) directories relative to the Modules
        # directory to add to INCLUDEPATH.
        self.includepath = (includepath, ) if isinstance(includepath, str) else includepath

        # The name of the extension module if it is implemented as a .pyd file
        # included in the Windows installer from python.org.
        self.pyd = pyd

        # The sequence of additional DLLs needed by the extension module and
        # included in the Windows installer from python.org.
        self.dlls = (dlls, ) if isinstance(dlls, str) else dlls

        # The file extension if the module is actually a data file.  Note that
        # None and '' have different meanings.
        self.data_ext = data_ext


class VersionedModule:
    """ Encapsulate the meta-data common to all types of module. """

    def __init__(self, min_version=None, version=None, max_version=None,
            internal=False, target='', deps=(), hidden_deps=(), core=False,
            builtin=False, defines=None, xdep=None, modules=None, source=None,
            libs=None, includepath=None, pyd=None, dlls=None):
        """ Initialise the object. """

        self._min_version = min_version
        self._max_version = max_version
        self._version = version

        self.module = Module(internal, target, deps, hidden_deps, core,
                builtin, defines, xdep, modules, source, libs, includepath,
                pyd, dlls)

    def applies_to(self, version):
        """ Returns True if the given version applies to this versioned module.
        """

        if self._version is not None:
            return version == self._version

        if self._min_version is not None:
            if version < self._min_version:
                return False

        if self._max_version is not None:
            if version > self._max_version:
                return False

        return True


class ExtensionModule(VersionedModule):
    """ Encapsulate the meta-data for a single extension module. """

    def __init__(self, source, libs=None, includepath=None, min_version=None,
            version=None, max_version=None, internal=False, target='', deps=(),
            hidden_deps=(), core=False, defines=None, xdep=None, pyd=None,
            dlls=None):
        """ Initialise the object. """

        super().__init__(min_version=min_version, version=version,
                max_version=max_version, internal=internal, target=target,
                deps=deps, hidden_deps=hidden_deps, core=core, defines=defines,
                xdep=xdep, source=source, libs=libs, includepath=includepath,
                pyd=pyd, dlls=dlls)


class PythonModule(VersionedModule):
    """ Encapsulate the meta-data for a single Python module. """

    def __init__(self, min_version=None, version=None, max_version=None,
            internal=False, target='', deps=(), hidden_deps=(), core=False,
            builtin=False, modules=None):
        """ Initialise the object. """

        super().__init__(min_version=min_version, version=version,
                max_version=max_version, internal=internal, target=target,
                deps=deps, hidden_deps=hidden_deps, core=core, builtin=builtin,
                modules=modules)
