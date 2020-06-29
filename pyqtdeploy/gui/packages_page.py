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
from PyQt5.QtWidgets import (QSplitter, QTreeWidget, QTreeWidgetItem,
        QTreeWidgetItemIterator, QVBoxLayout, QWidget)

from ..platforms import Architecture
from ..sysroot import Sysroot


class PackagesPage(QSplitter):
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

            self._project.sysroot_loaded.connect(self._sysroot_loaded)
            self._sysroot_loaded()

    def __init__(self):
        """ Initialise the page. """

        super().__init__()

        self._project = None

        # Create the page's GUI.
        self._stdlib_edit = StdlibEditor(self)
        self._others_edit = OthersEditor(self)

    def _sysroot_loaded(self):
        """ Invoked when a sysroot specification has been loaded. """

        project = self._project

        # Create a non-verified sysroot for each target architecture and
        # determine the availability of each module.
        module_items = {}
        host = Architecture.architecture()

        self._stdlib_edit.blockSignals(True)
        self._others_edit.blockSignals(True)

        for target in Architecture.all_architectures:
            sysroot = Sysroot(project.sysroot_specification, host, target)

            for component in sysroot.components:
                editor = (self._stdlib_edit if component.name == 'Python' else self._others_edit)

                modules = component.get_modules()

                for module_name, module in modules.items():
                    # TODO: this doesn't work for components that provide
                    # sub-packages (eg. PyQt5.sip).
                    if module.internal or '.' in module_name:
                        continue

                    self._add_component_module_item(module_items, module_name,
                            modules, editor)

        # Ensure that any modules explcitly used by the project have an item
        # even if they are not provided by the sysroot.
        for module_name in project.standard_library:
            self._add_project_module(module_items, module_name, stdlib=True)

        for module_name in project.other_packages:
            self._add_project_module(module_items, module_name, stdlib=False)

        # Sort module items in each editor.
        self._stdlib_edit.sortItems(0, Qt.AscendingOrder)
        self._others_edit.sortItems(0, Qt.AscendingOrder)

        self._stdlib_edit.blockSignals(False)
        self._others_edit.blockSignals(False)

        self._update_dependencies()

    def _add_component_module_item(self, module_items, module_name, modules,
            parent):
        """ Add a module provided by a component. """

        module = modules[module_name]

        try:
            module_item = module_items[module_name]
        except KeyError:
            module_item = ModuleItem(parent, module_name, module)
            module_items[module_name] = module_item

        module_item.target_count += 1

        if module.modules is not None:
            for submodule in module.modules:
                self._add_component_module_item(module_items, submodule,
                        modules, module_item)

    def _add_project_module(self, module_items, module_name, stdlib,
            checked=True):
        """ Make sure a module is in the dict of all modules. """

        # Make sure any parent module items exist.
        if '.' in module_name:
            parent_name = '.'.join(module_name.split('.')[:-1])
            parent = self._add_project_module(module_items, parent_name,
                    stdlib, checked=False)
            parent.setExpanded(True)
        else:
            parent = (self._stdlib_edit if stdlib else self._others_edit)

        try:
            module_item = module_items[module_name]
        except KeyError:
            module_item = ModuleItem(parent, module_name)
            module_items[module_name] = module_item

        if checked:
            module_item.setCheckState(0, Qt.Checked)

        return module_item

    def _update_dependencies(self):
        """ Update the implicit state of each module. """

        #self._stdlib_edit.update()
        #self._others_edit.update()


class ModulesEditor(QTreeWidget):
    """ An editor for selecting a number of interdependent modules and
    packages.
    """

    def __init__(self, page, title, whats_this):
        """ Initialise the editor. """

        super().__init__(whatsThis=whats_this)

        self.setHeaderLabels([title])
        #self.itemChanged.connect(self.module_changed)

        pane = QWidget()
        layout = QVBoxLayout()
        layout.addWidget(self)
        pane.setLayout(layout)
        page.addWidget(pane)

        self.page = page

    def module_changed(self, itm, col):
        """ Invoked when a module changes. """

    def populate(self):
        """ Populate the editor. """

    def update(self):
        """ Update the contents of the editor. """

        blocked = self.blockSignals(True)
        self.clear()

        if self.page.project.python_component is None:
            self.setEnabled(False)
        else:
            self.setEnabled(True)
            self.populate()

        self.blockSignals(blocked)


class OthersEditor(ModulesEditor):
    """ An editor for selecting a number of other modules and packages
    specified in the sysroot.
    """

    def __init__(self, page):
        """ Initialise the editor. """

        super().__init__(page, "Other Packages",
                "This shows the packages and modules that are "
                "available in the sysroot. Check those packages and modules "
                "that are explicitly imported by the application. A module "
                "will be partially checked (and automatically included) if "
                "another module requires it.")

    def module_changed(self, itm, col):
        """ Invoked when a module changes. """

    def populate(self):
        """ Populate the editor. """


class StdlibEditor(ModulesEditor):
    """ An editor for selecting a number of standard library modules and
    packages.
    """

    def __init__(self, page):
        """ Initialise the editor. """

        super().__init__(page, "Standard Library",
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

    def populate(self):
        """ Populate the editor. """

        project = self.page.project
        python = project.python_component

        modules = python.get_modules()
        modules_availability = python.get_modules_availability(
                project.component_availability)

        def add_module(name, module, parent):
            itm = QTreeWidgetItem(parent, name.split('.')[-1:])
            itm.setFlags(Qt.ItemIsEnabled|Qt.ItemIsUserCheckable)
            itm._name = name

            # Change the appearence of the item according to its availability.
            availability = modules_availability[name]

            if availability == 0:
                itm.setDisabled(True)
            elif availability == 1:
                font = itm.font(0)
                font.setItalic(True)
                itm.setFont(0, font)

            # Handle any sub-modules.
            if module.modules is not None:
                for submodule_name in module.modules:
                    # We assume that a missing sub-module is because it is not
                    # in the current version rather than bad meta-data.
                    submodule = modules.get(submodule_name)
                    if submodule is not None and not submodule.internal:
                        add_module(submodule_name, submodule, itm)

        for name, module in modules.items():
            if not module.internal and '.' not in name:
                add_module(name, module, self)

        self.sortItems(0, Qt.AscendingOrder)

        self._set_dependencies()

    def _set_dependencies(self):
        """ Set the dependency information. """

        project = self.page.project

        required_modules, _ = project.get_stdlib_requirements()

        blocked = self.blockSignals(True)

        it = QTreeWidgetItemIterator(self)
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

        self.blockSignals(blocked)


class ModuleItem(QTreeWidgetItem):
    """ An item in a QTreeWidget that encapsulates a public module. """

    def __init__(self, parent, module_name, module=None):
        """ Initialise the item. """

        super().__init__(parent, module_name.split('.')[-1:])

        self.setFlags(Qt.ItemIsEnabled|Qt.ItemIsUserCheckable)
        self.setCheckState(0, Qt.Unchecked)

        self.module = module
        self.target_count = 0

    def set_availability(self):
        """ Set the availability of the module. """

        if self.target_count == 0:
            self.setBackground(0, Qt.red)
        elif self.target_count != len(Architecture.all_architectures):
            self.setBackground(0, Qt.darkYellow)
