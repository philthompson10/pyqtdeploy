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


from  collections import OrderedDict
import importlib
import os
import shutil
import toml

from ..platforms import Architecture
from ..user_exception import UserException

from .component import ComponentBase


class Specification:
    """ Encapsulate the specification of a system root directory. """

    def __init__(self, specification_file, plugin_dirs, target):
        """ Initialise the object. """

        self._specification_file = specification_file

        self.components = []

        # Load the TOML file.
        with open(specification_file) as f:
            try:
                spec = toml.load(f, _dict=OrderedDict)
            except Exception as e:
                raise UserException(
                        "{0}: {1}".format(specification_file, str(e)))

        # Do a high level parse and import the plugins.
        all_architecture_names = [a.name
                for a in Architecture.all_architectures]

        for name, value in spec.items():
            # At the moment every name is a component name and every value is a
            # component configuration.
            if not isinstance(value, OrderedDict):
                raise UserException("unexpected option '{0}'".format(name))

            # Ignore the component if it is disabled for this target.
            disabled_targets = value.get('disabled_targets')
            if disabled_targets is not None and target in disabled_targets:
                continue

            # Ignore the component if it not explicity enabled.
            enabled_targets = value.get('enabled_targets')
            if enabled_targets is not None and target not in enabled_targets:
                continue

            # Identify the default configuration and any target-specific
            # configuration.
            default_config = OrderedDict()
            target_config = None

            for config_name, config_value in value.items():
                if config_name in all_architecture_names:
                    # Ignore if it isn't for the target.
                    if config_name != target:
                        continue

                    if not isinstance(config_value, OrderedDict):
                        raise UserException(
                                "configuration for '{0}' must be a table".format(config_name))

                    target_config = config_value
                else:
                    default_config[config_name] = config_value

            # Apply any defaults to the target configuration.
            if target_config is not None:
                default_config.update(target_config)

            target_config = default_config

            # Find the component's plugin.
            plugin = None

            # Search any user specified directories.
            if plugin_dirs:
                for plugin_dir in plugin_dirs:
                    plugin = self._plugin_from_file(name, plugin_dir)
                    if plugin is not None:
                        break

            # Search the included plugin packages.
            if plugin is None:
                # The name of the package root.
                package_root = '.'.join(__name__.split('.')[:-1])

                for package in ('.plugins', '.plugins.contrib'):
                    plugin = self._plugin_from_package(name, package,
                            package_root)
                    if plugin is not None:
                        break
                else:
                    raise UserException(
                            "unable to find a plugin for '{0}'".format(name))

            # Create the component plugin.
            component = plugin()
            setattr(component, 'name', name)
            setattr(component, '_options_values', target_config)

            self.components.append(component)

    def parse_options(self):
        """ Parse all the components' options. """

        for component in self.components:
            options_values = component._options_values

            # Parse the component-specific options.
            for cls in type(component).__mro__:
                options = cls.__dict__.get('options')
                if options:
                    self._parse_options(options_values, options, component)

                if cls is ComponentBase:
                    break

            unused = options_values.keys()
            if unused:
                self._parse_error(
                        "unknown option(s): {0}".format(', '.join(unused)),
                        component.name)

            del component._options_values

    def _plugin_from_file(self, name, plugin_dir):
        """ Try and load a component plugin from a file. """

        plugin_file = os.path.join(plugin_dir, name + '.py')
        spec = importlib.util.spec_from_file_location(name, plugin_file)
        plugin_module = importlib.util.module_from_spec(spec)

        try:
            spec.loader.exec_module(plugin_module)
        except FileNotFoundError:
            return None

        return self._plugin_from_module(name, plugin_module)

    def _plugin_from_package(self, name, package, package_root):
        """ Try and load a component plugin from a Python package. """

        rel_name = package + '.' + name

        try:
            plugin_module = importlib.import_module(rel_name,
                    package=package_root)
        except ImportError:
            return None

        return self._plugin_from_module(package_root + rel_name, plugin_module)

    def _plugin_from_module(self, fq_name, plugin_module):
        """ Get any plugin implementation from a module. """

        fq_name_parts = fq_name.split('.')

        for component_type in plugin_module.__dict__.values():
            if isinstance(component_type, type):
                if issubclass(component_type, ComponentBase):
                    # Make sure the type is defined in the plugin and not
                    # imported by it.  Allow for a plugin implemented as a
                    # sub-package.
                    if component_type.__module__.split('.')[:len(fq_name_parts)] == fq_name_parts:
                        return component_type

        return None

    def _parse_options(self, options_values, options, component):
        """ Parse a mapping of values according to a set of options and add the
        corresponding values as attributes of a component object.
        """

        for option in options:
            value = options_values.get(option.name)

            if value is None:
                if option.required:
                    self._parse_error(
                            "'{0}' has not been specified".format(option.name),
                            component.name)

                # Create a default value.
                if option.default is None:
                    value = option.type()
                else:
                    value = option.default
            elif not isinstance(value, option.type):
                self._bad_type(option.name, component.name)
            elif option.values:
                if value not in option.values:
                    self._parse_error(
                            "'{0}' must have be one of these values: {1}".format(option.name, ','.join(option.values)),
                            component.name)

            setattr(component, option.name, value)

            try:
                del options_values[option.name]
            except KeyError:
                pass

    def _bad_type(self, name, component_name=None):
        """ Raise an exception when an option name has the wrong type. """

        self._parse_error("value of '{0}' has an unexpected type".format(name),
                component_name)

    def _parse_error(self, message, component_name):
        """ Raise an exception for by an error in the specification file. """

        if component_name:
            exception = "{0}: Component '{1}': {2}".format(
                    self._specification_file, component_name, message)
        else:
            exception = "{0}: {1}".format(self._specification_file, message)

        raise UserException(exception)

    def show_options(self, components, message_handler):
        """ Show the options for a sequence of components. """

        headings = ("Component", "Option [*=required]", "Type", "Description")
        widths = [len(h) for h in headings]
        options = OrderedDict()

        # Collect the options for each component while working out the required
        # column widths.
        for component in components:
            name_len = len(component.name)
            if widths[0] < name_len:
                widths[0] = name_len

            # Allow sub-classes to override super-classes.
            component_options = OrderedDict()

            for cls in type(component).__mro__:
                for option in cls.__dict__.get('options', []):
                    if option.name not in component_options:
                        component_options[option.name] = option

                        name_len = len(option.name)
                        if option.required:
                            name_len == 1

                        if widths[1] < name_len:
                            widths[1] = name_len

                if cls is ComponentBase:
                    break

            options[component.name] = component_options

        # Display the formatted options.
        self._show_row(headings, widths, message_handler)

        ulines = ['-' * len(h) for h in headings]
        self._show_row(ulines, widths, message_handler)

        # Calculate the room available for the description column.
        avail = shutil.get_terminal_size()[0] - 1

        for w in widths[:-1]:
            avail -= 2 + w

        avail = max(avail, widths[-1])

        for component_name, component_options in options.items():
            component_col = component_name

            for option_name, option in component_options.items():
                if option.required:
                    option_name += '*'

                row = [component_col, option_name]

                if option.type is int:
                    type_name = 'int'
                elif option.type is str:
                    type_name = 'str'
                elif option.type is bool:
                    type_name = 'bool'
                elif option.type is list:
                    type_name = 'list'
                elif option.type is dict:
                    type_name = 'dict'
                else:
                    type_name = "???"

                row.append(type_name)

                row.append('')
                line = ''
                for word in option.help.split():
                    if len(line) + len(word) < avail:
                        # There is room for the word on this line.
                        if line:
                            line += ' ' + word
                        else:
                            line = word
                    else:
                        if line:
                            # Show what we have so far.
                            row[-1] = line
                            line = word
                        else:
                            # The word is too long so truncate it.
                            row[-1] = word[:avail]

                        self._show_row(row, widths, message_handler)

                        # Make the row blank for the next word.
                        row = [''] * len(headings)

                if line:
                    # The last line.
                    row[-1] = line
                    self._show_row(row, widths, message_handler)

                # Don't repeat the component name.
                component_col = ''

    @staticmethod
    def _show_row(columns, widths, message_handler):
        """ Show one row of the options table. """

        row = ['{:{width}}'.format(columns[i], width=w) 
                for i, w in enumerate(widths)]

        message_handler.message('  '.join(row))
