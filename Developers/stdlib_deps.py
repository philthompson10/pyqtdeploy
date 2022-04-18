# Copyright (c) 2022, Riverbank Computing Limited
# All rights reserved.


import argparse
import sys

from pyqtdeploy import Architecture
from pyqtdeploy.parts import Part
from pyqtdeploy.version_number import VersionNumber
from pyqtdeploy.sysroot.plugins.Python.standard_library import standard_library


def package_provided(package, target, version, no_libffi, no_openssl, no_zlib,
        show_cached, depth=0, memo=None):
    """ Show the availability of a package and it's dependencies. """

    indent = ' ' * (2 * depth)

    # Manage circular dependencies.
    if memo is None:
        memo = {}
    elif package in memo:
        provided = memo[package]

        if show_cached:
            if provided:
                print(f"{indent}{package}")
            else:
                print(f"{indent}{package}: not provided for target/version")

        return provided

    # Assume for the moment that the package is provided.
    memo[package] = True

    # Get the package's possible parts.
    try:
        parts = standard_library[package]
    except KeyError:
        raise ValueError(f"no such package '{package}'") from None

    # Get any applicable part.
    part = Part.get_applicable_part('Python', package, parts, target, version)

    if part is None:
        print(f"{indent}{package}: not provided for target/version")
        provided = False
    else:
        print(f"{indent}{package}")

        deps = part.deps if isinstance(part.deps, tuple) else (part.deps, )

        if len(deps) == 0:
            provided = True
        else:
            # Assume the dependencies will be satisfied.
            provided = True

            for dep in deps:
                # Handle target-specific dependencies.
                if '#' in dep:
                    dep_target, dep = dep.split('#', maxsplit=1)

                    if not target.is_targeted(dep_target):
                        continue

                # Handle external components.
                if ':' in dep:
                    component, dep = dep.split(':', maxsplit=1)

                    if component not in ('libffi', 'zlib'):
                        raise ValueError(f"unknown component '{component}'")

                    if component == 'libffi' and no_libffi:
                        provided = False

                    if component == 'zlib' and no_zlib:
                        provided = False

                    continue

                # Optional dependencies can be ignored.
                if dep.startswith('?'):
                    continue

                # Handle OpenSSL fallbacks.
                if dep.startswith('!'):
                    if no_openssl:
                        dep = dep[1:]
                    else:
                        # OpenSSL is available so the part isn't needed.
                        continue

                dep_provided = package_provided(dep, target, version,
                        no_libffi, no_openssl, no_zlib, show_cached,
                        depth=depth + 1, memo=memo)

                if not dep_provided:
                    provided = False

            if not provided:
                print(f"{indent}{package}: missing dependency")

    memo[package] = provided

    return provided


# Parse the command line.
parser = argparse.ArgumentParser()

parser.add_argument('--no-libffi', help="assume libffi is not available",
        default=False, action='store_true')
parser.add_argument('--no-openssl', help="assume OpenSSL is not available",
        default=False, action='store_true')
parser.add_argument('--no-zlib', help="assume zlib is not available",
        default=False, action='store_true')
parser.add_argument('--show-cached', help="show cached dependency checks",
        default=False, action='store_true')
parser.add_argument('--target', help="the target architecture")
parser.add_argument('--python-version', help="the version of Python to use")
parser.add_argument('package', help="the name of the Python package")

args = parser.parse_args()

if args.target:
    target = Architecture.architecture(args.target)
else:
    target = Architecture.architecture()

if args.python_version:
    version = VersionNumber.parse_version_number(args.python_version)
else:
    version = VersionNumber.parse_version_number(sys.hexversion >> 8)

# Show the package and it's dependencies.
package_provided(args.package, target, version, args.no_libffi,
        args.no_openssl, args.no_zlib, args.show_cached)
