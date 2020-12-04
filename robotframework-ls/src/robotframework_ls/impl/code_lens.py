from typing import Optional, List, Dict

from robot.parsing.model.blocks import TestCase, TestCaseSection

from robocorp_ls_core.lsp import CodeLens, Command, Range, Position

from robotframework_ls.impl.protocols import ICompletionContext

from robotframework_ls.impl.robot_visitors import CompletionContextModelVisitor


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
        self.code_lens.append(CodeLens(Range(Position(node.header.lineno - 1, node.header.col_offset),
                                             Position(node.header.lineno - 1, node.header.col_offset)), Command("Run Test", "robot.runTestcase", [self.doc_uri, node.name])))
        self.code_lens.append(CodeLens(Range(Position(node.header.lineno - 1, node.header.col_offset),
                                             Position(node.header.lineno - 1, node.header.col_offset)), Command("Debug Test", "robot.debugTestcase", [self.doc_uri, node.name])))

    def visit_TestCaseSection(self, node: TestCaseSection):
        self.generic_visit(node)


def code_lens(completion_context: ICompletionContext, doc_uri: str) -> Optional[List[Dict]]:
    result = []

    result.append(CodeLens(Range(Position(0, 0), Position(0, 0)),
                           Command("Run Suite", "robot.runTestsuite", [doc_uri])))
    result.append(CodeLens(Range(Position(0, 0), Position(0, 0)),
                           Command("Debug Suite", "robot.debugTestsuite", [doc_uri])))

    result += CodeLensVisitor.find_from(completion_context.get_ast(),
                                        doc_uri, completion_context)

    return list([x.to_dict() for x in result])
