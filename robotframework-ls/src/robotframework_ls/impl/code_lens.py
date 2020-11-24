from typing import Optional, List, Dict

from robot.parsing.model.blocks import TestCase, TestCaseSection

from robotframework_ls.impl.completion_context import CompletionContext
from robocorp_ls_core.lsp import CodeLens, Command, Range, Position

from robotframework_ls.impl.protocols import ICompletionContext

from .robot_visitors import CompletionContextModelVisitor


class CodeLensVisitor(CompletionContextModelVisitor):
    def __init__(self, doc_uri: str, completion_context: ICompletionContext = None):
        super().__init__(completion_context)
        self.code_lens: List[CodeLens] = []
        self.doc_uri = doc_uri

    @classmethod
    def find_from(cls, model, doc_uri, completion_context: ICompletionContext = None):
        finder = cls(doc_uri, completion_context)
        finder.visit(model)
        return finder.code_lens

    def visit_TestCase(self, node: TestCase):
        self.code_lens.append(CodeLens(Range(Position(node.header.lineno-1, node.header.col_offset),
                                             Position(node.header.lineno-1, node.header.col_offset)), Command("Run", "robot.runTestcase", [self.doc_uri, node.name])))
        self.code_lens.append(CodeLens(Range(Position(node.header.lineno-1, node.header.col_offset),
                                             Position(node.header.lineno-1, node.header.col_offset)), Command("Debug", "robot.debugTestcase", [self.doc_uri, node.name])))

    def visit_TestCaseSection(self, node: TestCaseSection):
        self.code_lens.append(CodeLens(Range(Position(node.header.lineno-1, node.header.col_offset),
                                             Position(node.header.lineno-1, node.header.col_offset)), Command("Run", "robot.runTestsuite", [self.doc_uri])))
        self.code_lens.append(CodeLens(Range(Position(node.header.lineno-1, node.header.col_offset),
                                             Position(node.header.lineno-1, node.header.col_offset)), Command("Debug", "robot.debugTestsuite", [self.doc_uri])))
        self.generic_visit(node)


def code_lens(completion_context: CompletionContext, doc_uri: str) -> Optional[List[Dict]]:
    result = list([x.to_dict() for x in CodeLensVisitor.find_from(
        completion_context.get_ast(), doc_uri, completion_context)])

    return result
