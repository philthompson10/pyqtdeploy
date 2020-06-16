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


from PyQt5.QtCore import pyqtSlot, Qt
from PyQt5.QtWidgets import (QTreeWidget, QTreeWidgetItem,
        QTreeWidgetItemIterator, QVBoxLayout, QWidget)

from ..metadata import get_python_metadata


class StandardLibraryPage(QWidget):
    """ The GUI for the standard library page of a project. """

    # The page's label.
    label = "Standard Library"

    @property
    def project(self):
        """ The project property getter. """

        return self._project

    @project.setter
    def project(self, value):
        """ The project property setter. """

        if self._project != value:
            self._project = value

            self._project.python_target_version_changed.connect(
                    self._update_page)

            self._update_page()

    def __init__(self):
        """ Initialise the page. """

        super().__init__()

        self._project = None

        # Create the page's GUI.
        layout = QVBoxLayout()

        self._stdlib_edit = QTreeWidget(
                whatsThis="This shows the packages and modules in the target "
                        "Python version's standard library. Check those "
                        "packages and modules that are explicitly imported by "
                        "the application. A module will be partially checked "
                        "(and automatically included) if another module "
                        "requires it.")
        self._stdlib_edit.setHeaderLabels(["Package"])
        self._stdlib_edit.itemChanged.connect(self._module_changed)

        layout.addWidget(self._stdlib_edit)

        self.setLayout(layout)

    @pyqtSlot()
    def _update_page(self):
        """ Update the page using the current project. """

        project = self.project

        if project.python_target_version is None:
            return

        editor = self._stdlib_edit

        metadata = get_python_metadata(project.python_target_version)

        blocked = editor.blockSignals(True)

        editor.clear()

        def add_module(name, module, parent):
            itm = QTreeWidgetItem(parent, name.split('.')[-1:])
            itm.setFlags(Qt.ItemIsEnabled|Qt.ItemIsUserCheckable)
            itm._name = name

            # Handle any sub-modules.
            if module.modules is not None:
                for submodule_name in module.modules:
                    # We assume that a missing sub-module is because it is not
                    # in the current version rather than bad meta-data.
                    submodule = metadata.get(submodule_name)
                    if submodule is not None and not submodule.internal:
                        add_module(submodule_name, submodule, itm)

        for name, module in metadata.items():
            if not module.internal and '.' not in name:
                add_module(name, module, editor)

        editor.sortItems(0, Qt.AscendingOrder)

        editor.blockSignals(blocked)

        self._set_dependencies()

    def _set_dependencies(self):
        """ Set the dependency information. """

        project = self.project
        editor = self._stdlib_edit

        required_modules, _ = project.get_stdlib_requirements()

        blocked = editor.blockSignals(True)

        it = QTreeWidgetItemIterator(editor)
        itm = it.value()
        while itm is not None:
            explicit = required_modules.get(itm._name)
            expanded = False
            if explicit is None:
                state = Qt.Unchecked
            elif explicit:
                state = Qt.Checked
                expanded = True
            else:
                state = Qt.PartiallyChecked

            itm.setCheckState(0, state)

            # Make sure every explicitly checked item is visible.
            if expanded:
                parent = itm.parent()
                while parent is not None:
                    parent.setExpanded(True)
                    parent = parent.parent()

            it += 1
            itm = it.value()

        editor.blockSignals(blocked)

    def _module_changed(self, itm, col):
        """ Invoked when a standard library module has changed. """

        project = self._project

        # Get all the names to add or remove.
        names = []

        def add_name(subitm):
            names.append(subitm._name)

            for i in range(subitm.childCount()):
                add_name(subitm.child(i))

        add_name(itm)

        if itm.checkState(col) == Qt.Checked:
            # Add the names if they aren't already present.
            for name in names:
                if name not in project.standard_library:
                    project.standard_library.append(name)
        else:
            # Remove the names if they are present.
            for name in names:
                try:
                    project.standard_library.remove(name)
                except ValueError:
                    pass

            itm.setExpanded(False)

        self._set_dependencies()

        project.modified = True
