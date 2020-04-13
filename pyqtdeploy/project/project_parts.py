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


class QrcPackage():
    """ The encapsulation of a memory-filesystem package. """

    def __init__(self):
        """ Initialise the package. """

        self.name = None
        self.contents = []
        self.exclusions = ['*.pyc', '*.pyd', '*.pyo', '*.pyx', '*.pxi',
                '__pycache__', '*-info', 'EGG_INFO', '*.so']

    def copy(self):
        """ Return a copy of the package. """

        copy = type(self)()

        copy.name = self.name
        copy.contents = [content.copy() for content in self.contents]
        copy.exclusions = list(self.exclusions)

        return copy


class QrcFile():
    """ The encapsulation of a memory-filesystem file. """

    def __init__(self, name, included=True):
        """ Initialise the file. """

        self.name = name
        self.included = included

    def copy(self):
        """ Return a copy of the file. """

        return type(self)(self.name, self.included)


class QrcDirectory(QrcFile):
    """ The encapsulation of a memory-filesystem directory. """

    def __init__(self, name, included=True):
        """ Initialise the directory. """

        super().__init__(name, included)

        self.contents = []

    def copy(self):
        """ Return a copy of the directory. """

        copy = super().copy()

        copy.contents = [content.copy() for content in self.contents]

        return copy


class ExternalLibrary():
    """ The encapsulation of an external library. """

    def __init__(self, name, defines, includepath, libs):
        """ Initialise the external library. """

        self.name = name
        self.defines = defines
        self.includepath = includepath
        self.libs = libs


class ExtensionModule():
    """ The encapsulation of an extension module. """

    def __init__(self, name, qt, config, sources, defines, includepath, libs):
        """ Initialise the extension module. """

        self.name = name
        self.qt = qt
        self.config = config
        self.sources = sources
        self.defines = defines
        self.includepath = includepath
        self.libs = libs
