import sys
import os
from typing import Dict, List, Optional, Tuple

from robot.variables import Variables
from robot.errors import DataError
from robot.running.testlibraries import TestLibrary
from robot.utils import get_error_message

from robot.libdocpkg.builder import JavaDocBuilder, RESOURCE_EXTENSIONS, SPEC_EXTENSIONS

from robot.libdocpkg.model import LibraryDoc

from robot.libdocpkg.robotbuilder import KeywordDocBuilder, LibraryDocBuilder, ResourceDocBuilder
from robot.libdocpkg.specbuilder import SpecDocBuilder
from robot.utils.error import get_error_details

    
def get_robot_version():
    try:
        import robot

        v = str(robot.get_version())
    except BaseException:        
        v = "unknown"
    return v

def get_robot_major_version():
    robot_version = get_robot_version()

    major_version = 3
    try:
        if "." in robot_version:
            major_version = int(robot_version.split(".")[0])
    except BaseException:
        pass

    return major_version

def _LibraryDocumentation(library_or_resource, name=None, version=None,
                          doc_format=None, variables=None):
    builder = _DocumentationBuilder(library_or_resource, variables)
    try:
        libdoc = builder.build(library_or_resource)
    except DataError:
        raise
    except BaseException:
        raise DataError("Building library '%s' failed: %s"
                        % (library_or_resource, get_error_message()))
    if name:
        libdoc.name = name
    if version:
        libdoc.version = version
    if doc_format:
        libdoc.doc_format = doc_format
    return libdoc


def _DocumentationBuilder(library_or_resource, variables):
    extension = os.path.splitext(library_or_resource)[1][1:].lower()
    if extension in RESOURCE_EXTENSIONS:
        return ResourceDocBuilder()
    if extension in SPEC_EXTENSIONS:
        return SpecDocBuilder()
    if extension == 'java':
        return JavaDocBuilder()
    return _LibraryDocBuilder(variables)


class _LibraryDocBuilder(LibraryDocBuilder):

    def __init__(self, variables) -> None:
        super().__init__()
        self.variables = variables

    def build(self, library):
        name, args = self._split_library_name_and_args(library)
        lib = TestLibrary(name, args, variables=self.variables)
        libdoc = LibraryDoc(name=lib.name,
                            doc=self._get_doc(lib),
                            version=lib.version,
                            scope=str(lib.scope),
                            doc_format=lib.doc_format,
                            source=lib.source,
                            lineno=lib.lineno)
        libdoc.inits = self._get_initializers(lib)
        libdoc.keywords = KeywordDocBuilder().build_keywords(lib)
        return libdoc


def run_doc(library_name: str, output_filename: str, additional_path: str, additional_pythonpath_entries: List[str], variables: Dict[str, str]) -> Tuple[Optional[LibraryDoc], Optional[str]]:
    old_path = sys.path
    try:
        if additional_pythonpath_entries:
            for p in additional_pythonpath_entries:
                if p:
                    sys.path.insert(0, p)

        if additional_path:
            sys.path.insert(0, additional_path)
        vars = Variables()
        for n, v in variables.items():
            vars[n] = v

        libdoc = _LibraryDocumentation(library_name, variables=vars)

        libdoc.save(output_filename, "XML:HTML" if get_robot_major_version() < 4 else "LIBSPEC")
        
        return (libdoc, None)
    except BaseException:
        msg, trace = get_error_details()
        nl = "\n"
        return None, f"{msg}{(nl+trace) if trace else ''}"
    finally:
        sys.path = old_path
