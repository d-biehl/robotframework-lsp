import ast

from robotframework_ls.impl.protocols import ICompletionContext

__all__ = ["CompletionContextModelVisitor", "IsEmptyVisitor"]


class VisitorFinder(object):

    def _find_visitor(self, cls):
        if cls is ast.AST:
            return None
        method = 'visit_' + cls.__name__
        if hasattr(self, method):
            return getattr(self, method)
        for base in cls.__bases__:
            visitor = self._find_visitor(base)
            if visitor:
                return visitor
        return None


class ModelVisitor(ast.NodeVisitor, VisitorFinder):
    """NodeVisitor that supports matching nodes based on their base classes.

    Otherwise identical to the standard `ast.NodeVisitor
    <https://docs.python.org/library/ast.html#ast.NodeVisitor>`__,
    but allows creating ``visit_ClassName`` methods so that the ``ClassName``
    is one of the base classes of the node. For example, this visitor method
    matches all section headers::

        def visit_SectionHeader(self, node):
            # ...

    If all visitor methods match node classes directly, it is better to use
    the standard ``ast.NodeVisitor`` instead.
    """

    def visit(self, node):
        visitor = self._find_visitor(type(node)) or self.generic_visit
        visitor(node)


class CompletionContextModelVisitor(ModelVisitor):
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


class FirstStatementFinder(ModelVisitor):

    def __init__(self):
        self.statement = None

    @classmethod
    def find_from(cls, model):
        finder = cls()
        finder.visit(model)
        return finder.statement

    def visit_Statement(self, statement):
        if self.statement is None:
            self.statement = statement

    def generic_visit(self, node):
        if self.statement is None:
            ModelVisitor.generic_visit(self, node)


class LastStatementFinder(ModelVisitor):

    def __init__(self):
        self.statement = None

    @classmethod
    def find_from(cls, model):
        finder = cls()
        finder.visit(model)
        return finder.statement

    def visit_Statement(self, statement):
        self.statement = statement
