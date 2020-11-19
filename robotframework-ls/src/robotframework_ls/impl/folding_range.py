from typing import Optional

from robot.parsing.model.blocks import *

from robotframework_ls.impl.completion_context import CompletionContext
from robocorp_ls_core.lsp import FoldingRange


class FoldingVisitor(ModelVisitor):
    def __init__(self):
        super().__init__()
        self.foldings = []

    @classmethod
    def find_from(cls, model):
        finder = cls()
        finder.visit(model)
        return finder.foldings

    def visit_ForLoop(self, node: ForLoop):
        self.foldings.append(FoldingRange(node.lineno-1, node.end_lineno-1,
                                          node.col_offset, node.end_col_offset, "for_loop"))
        self.generic_visit(node)

    def visit_Keyword(self, node: Keyword):
        self.foldings.append(FoldingRange(node.lineno-1, node.end_lineno-1,
                                          node.col_offset, node.end_col_offset, "keyword"))
        self.generic_visit(node)

    def visit_TestCase(self, node: TestCase):
        self.foldings.append(FoldingRange(node.lineno-1, node.end_lineno-1,
                                          node.col_offset, node.end_col_offset, "testcase"))
        self.generic_visit(node)

    def visit_CommentSection(self, node: CommentSection):
        self.foldings.append(FoldingRange(node.lineno-1, node.end_lineno-1,
                                          node.col_offset, node.end_col_offset, "comment"))
        self.generic_visit(node)

    def visit_Section(self, node: Section):
        self.foldings.append(FoldingRange(node.lineno-1, node.end_lineno-1,
                                          node.col_offset, node.end_col_offset, "section"))
        self.generic_visit(node)


def folding_range(completion_context: CompletionContext) -> Optional[list[dict]]:
    
    return list([x.to_dict() for x in FoldingVisitor.find_from(completion_context.get_ast())])
