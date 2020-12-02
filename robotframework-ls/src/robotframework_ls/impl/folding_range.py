from typing import Optional, List, Dict

from robotframework_ls.impl.protocols import ICompletionContext
from robotframework_ls.impl.robot_visitors import CompletionContextModelVisitor

from robocorp_ls_core.lsp import FoldingRange


class FoldingVisitor(CompletionContextModelVisitor):
    def __init__(self, completion_context: ICompletionContext = None):
        super().__init__()
        self.foldings: List[FoldingRange] = []

    @classmethod
    def find_from(cls, model, completion_context: ICompletionContext = None):
        finder = cls(completion_context)
        finder.visit(model)
        return finder.foldings

    def visit_ForLoop(self, node):
        self.foldings.append(FoldingRange(node.lineno - 1, node.end_lineno - 1,
                                          node.col_offset, node.end_col_offset, "for_loop"))
        self.generic_visit(node)

    def visit_Keyword(self, node):
        self.foldings.append(FoldingRange(node.lineno - 1, node.end_lineno - 1,
                                          node.col_offset, node.end_col_offset, "keyword"))
        self.generic_visit(node)

    def visit_TestCase(self, node):
        self.foldings.append(FoldingRange(node.lineno - 1, node.end_lineno - 1,
                                          node.col_offset, node.end_col_offset, "testcase"))
        self.generic_visit(node)

    def visit_CommentSection(self, node):
        self.foldings.append(FoldingRange(node.lineno - 1, node.end_lineno - 1,
                                          node.col_offset, node.end_col_offset, "comment"))
        self.generic_visit(node)

    def visit_Section(self, node):
        self.foldings.append(FoldingRange(node.lineno - 1, node.end_lineno - 1,
                                          node.col_offset, node.end_col_offset, "section"))
        self.generic_visit(node)


def folding_range(completion_context: ICompletionContext) -> Optional[List[Dict]]:

    return list([x.to_dict() for x in FoldingVisitor.find_from(completion_context.get_ast(), completion_context)])
