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


from PyQt5.QtWidgets import QWidget

from .better_form import BetterForm
from .filename_editor import FilenameEditor


class SysrootPage(QWidget):
    """ The GUI for the sysroot page of a project. """

    # The page's label.
    label = "Sysroot"

    @property
    def project(self):
        """ The project property getter. """

        return self._project

    @project.setter
    def project(self, value):
        """ The project property setter. """

        if self._project != value:
            self._project = value
            self._toml_edit.set_project(value)
            self._dir_edit.set_project(value)
            self._update_page()

    def __init__(self):
        """ Initialise the page. """

        super().__init__()

        self._project = None

        # Create the page's GUI.
        form = BetterForm()

        self._toml_edit = FilenameEditor("Sysroot specification file",
                placeholderText="Specification file name",
                whatsThis="The name of the sysroot specification file.",
                textEdited=self._toml_changed)
        form.addRow("Specification file", self._toml_edit)

        self._dir_edit = FilenameEditor("Sysroot Directory",
                placeholderText="Sysroot directory name",
                whatsThis="The name of the sysroot directory.",
                textEdited=self._dir_changed, directory=True)
        form.addRow("Sysroot directory", self._dir_edit)

        self.setLayout(form)

    def _update_page(self):
        """ Update the page using the current project. """

        project = self.project

        self._toml_edit.setText(project.sysroot_toml)
        self._dir_edit.setText(project.sysroot_dir)

    def _toml_changed(self, value):
        """ Invoked when the user edits the specification file name. """

        project = self.project

        project.sysroot_toml = value
        project.modified = True

        project.load_sysroot()

    def _dir_changed(self, value):
        """ Invoked when the user edits the sysroot directory name. """

        project = self.project

        project.sysroot_dir = value
        project.modified = True
