import robot.parsing.model.blocks as blocks
from robotframework_ls.impl.protocols import ICompletionContext

__all__ = ["CompletionContextModelVisitor", "IsEmptyVisitor"]


class CompletionContextModelVisitor(blocks.ModelVisitor):
    def __init__(self, completion_context: ICompletionContext = None):
        super().__init__()
        self.completion_context = completion_context

    def visit(self, node):
        if self.completion_context is not None:
            self.completion_context.check_cancelled()
        super().visit(node)


class IsEmptyVisitor(CompletionContextModelVisitor):

    def __init__(self, model, completion_context: ICompletionContext = None):
        super().__init__(completion_context)
        self.result = True
        self.model = model

    @classmethod
    def find_from(cls, model, completion_context: ICompletionContext = None):
        finder = cls(model, completion_context)
        finder.visit(model)
        return finder.result

    def visit_EmptyLine(self, node):
        pass

    def visit_Comment(self, node):
        pass

    def visit_list(self, node):
        if self.model == node:
            for n in node:
                self.visit(n)

    def generic_visit(self, node):
        if self.model == node:
            super().generic_visit(node)
        else:
            self.result = False
