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


from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (QSizePolicy, QSplitter, QTreeWidget,
        QTreeWidgetItem, QTreeWidgetItemIterator, QVBoxLayout, QWidget)

from ..platforms import Architecture
from ..sysroot import Sysroot

from .better_form import BetterForm
from .filename_editor import FilenameEditor


class PackagesPage(QWidget):
    """ The GUI for the packages page of a project. """

    # The page's label.
    label = "Packages"

    @property
    def project(self):
        """ The project property getter. """

        return self._project

    @project.setter
    def project(self, value):
        """ The project property setter. """

        if self._project != value:
            self._project = value

            self._stdlib_edit.clear()
            self._others_edit.clear()

            self._toml_edit.set_project(value)
            self._dir_edit.set_project(value)

            self._project.sysroot_loaded.connect(self._update_page)
            self._update_page()

    def __init__(self):
        """ Initialise the page. """

        super().__init__()

        self._project = None
        self._module_items = {}
        self._has_openssl = False

        # Create the page's GUI.
        layout = QVBoxLayout()

        self._stdlib_edit = StdlibEditor()
        self._others_edit = OthersEditor()

        splitter = QSplitter()
        splitter.setSizePolicy(
                QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding))
        splitter.addWidget(self._stdlib_edit)
        splitter.addWidget(self._others_edit)
        layout.addWidget(splitter)

        form = BetterForm()

        self._toml_edit = FilenameEditor("Sysroot specification file",
                placeholderText="Specification file name",
                whatsThis="The name of the sysroot specification file.",
                textEdited=self._toml_changed)
        form.addRow("Sysroot specification file", self._toml_edit)

        self._dir_edit = FilenameEditor("Sysroot Directory",
                placeholderText="Sysroot directory name",
                whatsThis="The name of the sysroot directory.",
                textEdited=self._dir_changed, directory=True)
        form.addRow("Sysroot directory", self._dir_edit)

        layout.addLayout(form)

        self.setLayout(layout)

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

    def _update_page(self):
        """ Update the page using the current project. """

        project = self._project

        self._toml_edit.setText(project.sysroot_toml)
        self._dir_edit.setText(project.sysroot_dir)

        # Create a non-verified sysroot for each target architecture and
        # determine the availability of each module.
        self._module_items.clear()
        host = Architecture.architecture()

        self._stdlib_edit.blockSignals(True)
        self._others_edit.blockSignals(True)

        self._has_openssl = False

        for target in Architecture.all_architectures:
            sysroot = Sysroot(project.sysroot_specification, host, target)

            for component in sysroot.components:
                if component.name == 'OpenSSL':
                    self._has_openssl = True

                stdlib = (component.name == 'Python')

                modules = component.modules

                for module_name in modules:
                    module_item = self._get_module_item(module_name, modules,
                            stdlib)
                    if module_item is not None:
                        module_item.target_count += 1

        # Ensure that any modules explcitly used by the project have an item
        # even if they are not provided by the sysroot.
        for module_name in project.standard_library:
            self._add_project_module(module_name, stdlib=True)

        for module_name in project.other_packages:
            self._add_project_module(module_name, stdlib=False)

        # Set the availability of each module.
        for module_item in self._module_items.values():
            module_item.set_availability()

        # Sort module items in each editor.
        self._stdlib_edit.sortItems(0, Qt.AscendingOrder)
        self._others_edit.sortItems(0, Qt.AscendingOrder)

        # Update the dependencies.
        self._update_dependencies()

        self._stdlib_edit.blockSignals(False)
        self._others_edit.blockSignals(False)

    def _get_module_item(self, module_name, modules, stdlib):
        """ Return a ModuleItem object for a module or None if the module is
        internal.
        """

        # TODO: is the modules attribute of a module (ie. the list of
        # sub-modules) used any more?

        # Ignore internal modules.
        module = modules.get(module_name)
        if module is not None and module.internal:
            return None

        # Make sure any parent module items exist.
        if '.' in module_name:
            parent_name = '.'.join(module_name.split('.')[:-1])
            parent = self._get_module_item(parent_name, modules, stdlib)
        else:
            parent = (self._stdlib_edit if stdlib else self._others_edit)

        return self._add_module(parent, module_name, module=module)

    def _add_module(self, parent, module_name, module=None):
        """ Make sure a module appears in the dict of all modules. """

        try:
            module_item = self._module_items[module_name]

            # Update the module if it is currently just a place holder.
            if module_item.module is None:
                module_item.module = module
        except KeyError:
            module_item = ModuleItem(parent, module_name, module)
            self._module_items[module_name] = module_item

        return module_item

    def _add_project_module(self, module_name, stdlib, checked=True):
        """ Make sure a module is in the dict of all modules. """

        # Make sure any parent module items exist.
        if '.' in module_name:
            parent_name = '.'.join(module_name.split('.')[:-1])
            parent = self._add_project_module(parent_name, stdlib,
                    checked=False)
            parent.setExpanded(True)
        else:
            parent = (self._stdlib_edit if stdlib else self._others_edit)

        module_item = self._add_module(parent, module_name)

        if checked:
            module_item.setCheckState(0, Qt.Checked)

        return module_item

    def _update_dependencies(self):
        """ Update the inter-module dependencies. """

        # The first pass is to clear any implicit modules.
        for module_item in self._module_items.values():
            if module_item.checkState(0) == Qt.PartiallyChecked:
                module_item.setCheckState(0, Qt.Unchecked)

        # The second pass is to set the state of any implicit modules.
        for module_item in self._module_items.values():
            if module_item.module is not None and module_item.module.core:
                self._set_implicit(module_item)
            elif module_item.checkState(0) == Qt.Checked:
                self._set_implicit(module_item.parent())
                self._set_implicit_deps(module_item)
            else:
                module_item.setCheckState(0, Qt.Unchecked)

    def _set_implicit(self, module_item):
        """ Set a module's state (and that of all it's parents) to be partially
        checked (unless it is already checked).
        """

        while module_item is not None:
            if module_item.checkState(0) == Qt.Unchecked:
                module_item.setCheckState(0, Qt.PartiallyChecked)

            module_item = module_item.parent()

    def _set_implicit_deps(self, module_item):
        """ Set a module's state (and that of all it's dependents) to be
        partially checked (unless it is already checked).
        """

        if module_item.module is None:
            return

        for dep in module_item.module.deps:
            if dep.startswith('?'):
                dep = dep[1:]
            elif dep.startswith('!'):
                if self._has_openssl:
                    continue

                dep = dep[1:]

            # We have a global pool of all modules so the component doesn't
            # matter.
            if ':' in dep:
                _, dep = dep.split(':', maxsplit=1)

            dep_module_item = self._module_items.get(dep)
            if dep_module_item is not None and dep_module_item.checkState(0) == Qt.Unchecked:
                self._set_implicit(dep_module_item)
                self._set_implicit_deps(dep_module_item)


class ModulesEditor(QTreeWidget):
    """ An editor for selecting a number of interdependent modules and
    packages.
    """

    def __init__(self, title, whats_this):
        """ Initialise the editor. """

        super().__init__(whatsThis=whats_this)

        self.setHeaderLabels([title])
        #self.itemChanged.connect(self.module_changed)

    def module_changed(self, itm, col):
        """ Invoked when a module changes. """


class OthersEditor(ModulesEditor):
    """ An editor for selecting a number of other modules and packages
    specified in the sysroot.
    """

    def __init__(self):
        """ Initialise the editor. """

        super().__init__("Other Packages",
                "This shows the packages and modules that are "
                "available in the sysroot. Check those packages and modules "
                "that are explicitly imported by the application. A module "
                "will be partially checked (and automatically included) if "
                "another module requires it.")

    def module_changed(self, itm, col):
        """ Invoked when a module changes. """


class StdlibEditor(ModulesEditor):
    """ An editor for selecting a number of standard library modules and
    packages.
    """

    def __init__(self):
        """ Initialise the editor. """

        super().__init__("Standard Library",
                "This shows the packages and modules in the target Python "
                "version's standard library. Check those packages and modules "
                "that are explicitly imported by the application. A module "
                "will be partially checked (and automatically included) if "
                "another module requires it.")

    def module_changed(self, itm, col):
        """ Invoked when a module changes. """

        project = self.page.project

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


class ModuleItem(QTreeWidgetItem):
    """ An item in a QTreeWidget that encapsulates a public module. """

    # The colour to use for modules that aren't available for any target.
    _NO_TARGETS = QColor('#f00000')

    # The colour to use for modules that are only available for some targets.
    _SOME_TARGETS = QColor('#f08000')

    def __init__(self, parent, module_name, module):
        """ Initialise the item. """

        super().__init__(parent, module_name.split('.')[-1:])

        self.setFlags(Qt.ItemIsEnabled|Qt.ItemIsUserCheckable)

        self.module = module
        self.target_count = 0

    def set_availability(self):
        """ Set the availability of the module. """

        if self.target_count == 0:
            self.setForeground(0, self._NO_TARGETS)
        elif self.target_count != len(Architecture.all_architectures):
            self.setForeground(0, self._SOME_TARGETS)
