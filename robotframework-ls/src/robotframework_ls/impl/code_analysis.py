from robocorp_ls_core.lsp import Error
from robocorp_ls_core.robotframework_log import get_logger
from robot.parsing.model.blocks import FirstStatementFinder, LastStatementFinder
from robotframework_ls.impl.ast_utils import MAX_ERRORS, create_error_from_node
import robot.parsing.model.blocks as blocks
import robot.parsing.model.statements as statements
import robot.parsing.lexer.tokens as tokens
from robot.variables import is_scalar_assign
from typing import Any, Union
from robotframework_ls.impl.protocols import ICompletionContext

log = get_logger(__name__)


class _KeywordContainer(object):
    def __init__(self):
        self._name_to_keyword = {}
        self._names_with_variables = set()
        self._multiple_keywords = {}

    def add_keyword(self, keyword_found):
        from robotframework_ls.impl.text_utilities import normalize_robot_name

        normalized_name = normalize_robot_name(keyword_found.keyword_name)
        if normalized_name in self._name_to_keyword:
            if (self._name_to_keyword[normalized_name].library_name == keyword_found.library_name or self._name_to_keyword[normalized_name].resource_name == keyword_found.resource_name) \
                    and self._name_to_keyword[normalized_name].library_alias == keyword_found.library_alias:
                return

            if normalized_name not in self._multiple_keywords:
                self._multiple_keywords[normalized_name] = [
                    self._name_to_keyword[normalized_name]]
            self._multiple_keywords[normalized_name].append(keyword_found)
        else:
            self._name_to_keyword[normalized_name] = keyword_found

        if "{" in normalized_name:
            self._names_with_variables.add(normalized_name)

    def contains_keyword(self, normalized_keyword_name):
        from robotframework_ls.impl.text_utilities import matches_robot_keyword

        if normalized_keyword_name in self._name_to_keyword:
            return True

        # We do not have an exact match, still, we need to check if we may
        # have a match in keywords that accept variables.
        for name in self._names_with_variables:
            if matches_robot_keyword(normalized_keyword_name, name):
                return True

        return False

    def check_multiple_keyword_definitions(self, normalized_keyword_name):
        if normalized_keyword_name in self._multiple_keywords:
            return self._multiple_keywords[normalized_keyword_name]

        return None


class _KeywordsCollector(object):
    def __init__(self):
        self._keywords_container = _KeywordContainer()
        self._resource_name_to_keywords_container = {}
        self._library_name_to_keywords_container = {}

    def accepts(self, keyword_name):
        return True

    def on_keyword(self, keyword_found):
        """
        :param IKeywordFound keyword_found:
        """
        from robotframework_ls.impl.text_utilities import normalize_robot_name

        self._keywords_container.add_keyword(keyword_found)
        library_name = keyword_found.library_name
        library_alias = keyword_found.library_alias
        resource_name = keyword_found.resource_name

        if library_name:
            if library_alias:
                name = normalize_robot_name(library_alias)
            else:
                name = normalize_robot_name(library_name)
            dct = self._library_name_to_keywords_container
        elif resource_name:
            name = normalize_robot_name(resource_name)
            dct = self._resource_name_to_keywords_container
        else:
            log.info(
                "No library name nor resource name for keyword: %s"
                % (keyword_found.name,)
            )
            return

        keyword_container = dct.get(name)
        if keyword_container is None:
            keyword_container = dct[name] = _KeywordContainer()

        keyword_container.add_keyword(keyword_found)

    def contains_keyword(self, normalized_keyword_name):
        from robotframework_ls.impl import text_utilities

        if self._keywords_container.contains_keyword(normalized_keyword_name):
            return True

        for name, remainder in text_utilities.iter_dotted_names(normalized_keyword_name):
            if not name or not remainder:
                continue

            containers = []
            keywords_container = self._resource_name_to_keywords_container.get(
                name)
            if keywords_container:
                containers.append(keywords_container)
            keywords_container = self._library_name_to_keywords_container.get(
                name)
            if keywords_container:
                containers.append(keywords_container)

            for keywords_container in containers:
                if keywords_container.contains_keyword(remainder):
                    return True

        return False

    def check_multiple_keyword_definitions(self, normalized_keyword_name):
        from robotframework_ls.impl import text_utilities

        multi = self._keywords_container.check_multiple_keyword_definitions(
            normalized_keyword_name)
        if multi is not None:
            return multi

        multi = []

        for name, remainder in text_utilities.iter_dotted_names(
            normalized_keyword_name
        ):
            if not name or not remainder:
                continue
            containers = []
            keywords_container = self._resource_name_to_keywords_container.get(
                name)
            if keywords_container:
                containers.append(keywords_container)
            keywords_container = self._library_name_to_keywords_container.get(
                name)
            if keywords_container:
                containers.append(keywords_container)

            for keywords_container in containers:
                m = keywords_container.check_multiple_keyword_definitions(
                    remainder)
                if m is not None:
                    multi.extend(m)

        if len(multi) == 0:
            return None

        return multi


def create_error_from_tokens(start_token: tokens.Token, end_token: tokens.Token, message: str):
    if not end_token:
        end_token = start_token

    return Error(message,
                 start=(start_token.lineno-1,
                        start_token.col_offset) if start_token else (-1, -1),
                 end=(end_token.lineno-1,
                      end_token.end_col_offset) if end_token else (-1, -1))


def create_error_from_statements(start_statement: statements.Statement, end_statement: statements.Statement, message: str):
    start = next((t for t in start_statement.tokens if t.type not in tokens.Token.NON_DATA_TOKENS),
                 start_statement.tokens[0]) if start_statement is not None else None

    end = next((t for t in reversed(end_statement.tokens)
                if t.type not in tokens.Token.NON_DATA_TOKENS), end_statement.tokens[-1]) if end_statement is not None else None

    return create_error_from_tokens(start, end, message)


def create_error(block_statement_token: Union[blocks.Block, statements.Statement, tokens.Token], message: str):
    if isinstance(block_statement_token, tokens.Token):
        return create_error_from_tokens(block_statement_token, block_statement_token, message)

    if isinstance(block_statement_token, blocks.Block):
        first_statement = FirstStatementFinder.find_from(
            block_statement_token)
        last_statement = LastStatementFinder.find_from(
            block_statement_token)

        return create_error_from_statements(first_statement, last_statement, message)

    return create_error_from_statements(block_statement_token, block_statement_token, message)


class CompletionContextModelVisitor(blocks.ModelVisitor):
    def __init__(self, completion_context: ICompletionContext):
        super().__init__()
        self.completion_context = completion_context

    def visit(self, node):
        if self.completion_context is not None:
            self.completion_context.check_cancelled()
        super().visit(node)


class FindEmptyIfBlocksVisitor(blocks.ModelVisitor):

    def __init__(self, model):
        super().__init__()
        self.result = []
        self.model = model
        self.current_branch = None
        self.current_branch_name = "IF"
        self.is_empty = True
        self.else_has_seen = False

    @classmethod
    def find_from(cls, model):
        finder = cls(model.body)
        finder.current_branch = model
        finder.visit(model.body)
        finder.check_is_empty()
        return finder.result

    def visit_EmptyLine(self, node):
        pass

    def visit_Comment(self, node):
        pass

    def check_is_empty(self):
        if self.is_empty:
            self.result.append(
                (self.current_branch, f"{self.current_branch_name} has empty branch."))
        self.is_empty = True

    def visit_ElseIfStatement(self, node):
        self.check_is_empty()
        self.current_branch = node
        self.current_branch_name = "ELSE IF"
        if self.else_has_seen:
            self.result.append(
                (self.current_branch, f"'ELSE IF' after 'ELSE'."))

    def visit_Else(self, node):
        self.check_is_empty()
        self.current_branch = node
        self.current_branch_name = "ELSE"
        if self.else_has_seen:
            self.result.append(
                (self.current_branch, f"Multiple 'ELSE' branches."))
        self.else_has_seen = True

    def visit_list(self, node) -> Any:
        if self.model == node:
            for n in node:
                self.visit(n)

    def generic_visit(self, node) -> Any:
        if self.model == node:
            super().generic_visit(node)
        else:
            self.is_empty = False


class IsEmptyVisitor(blocks.ModelVisitor):

    def __init__(self, model):
        super().__init__()
        self.result = True
        self.model = model

    @classmethod
    def find_from(cls, model):
        finder = cls(model)
        finder.visit(model)
        return finder.result

    def visit_EmptyLine(self, node):
        pass

    def visit_Comment(self, node):
        pass

    def visit_list(self, node) -> Any:
        if self.model == node:
            for n in node:
                self.visit(n)

    def generic_visit(self, node) -> Any:
        if self.model == node:
            super().generic_visit(node)
        else:
            self.result = False


class CodeAnalysisVisitor(CompletionContextModelVisitor):
    def __init__(self, completion_context: ICompletionContext):
        super().__init__(completion_context)
        self.errors = []
        self.completion_context = completion_context

    @classmethod
    def find_from(cls, completion_context: ICompletionContext):
        finder = cls(completion_context)
        finder.visit(completion_context.get_ast())
        return finder.errors

    def append_error(self, node: Union[blocks.Block, statements.Statement, tokens.Token], message: str):
        self.errors.append(create_error(node, message))

    def visit_ForLoopHeader(self, node):
        if not node.variables:
            self.append_error(node, 'FOR loop has no loop variables.')
        else:
            for var in [t for t in node.tokens if t.type in tokens.Token.VARIABLE]:
                if not is_scalar_assign(var.value):
                    self.append_error(
                        var, f"Invalid loop variable {var.value}.")

        if not node.flavor:
            self.append_error(
                node, "FOR loop has no 'IN' or other valid separator.")
        else:

            if not node.values:
                self.append_error(node, 'FOR loop has no loop values.')

        self.generic_visit(node)

    def visit_ForLoop(self, node):
        if not node.body or IsEmptyVisitor.find_from(node.body):
            self.append_error(node.header or node, 'FOR loop has empty body.')
        if not node.end:
            self.append_error(node.header or node,
                              "FOR loop has no closing 'END'.")

        self.generic_visit(node)

    def visit_IfStatement(self, node):
        if not node.value:
            self.append_error(node, 'IF has no expression.')

        self.generic_visit(node)

    def visit_ElseIfStatement(self, node):
        if not node.value:
            self.append_error(node, 'ELSE IF has no expression.')

        self.generic_visit(node)

    def visit_IfBlock(self, node):
        if not node.body:
            self.append_error(node.header or node, 'IF has empty branch.')

        for n, msg in FindEmptyIfBlocksVisitor.find_from(node):
            self.append_error(n or node.header or node, msg)

        if not node.end:
            self.append_error(node.header or node, "IF has no closing 'END'.")

        self.generic_visit(node)

    def visit_LibraryImport(self, node: statements.LibraryImport):
        if node.name is not None:
            lib_info = self.completion_context.workspace.libspec_manager.get_library_info(
                node.name, False, self.completion_context.doc.uri, arguments=node.args, alias=node.alias)
            if lib_info is None:
                self.append_error(node.get_token(tokens.Token.NAME) or node, f"Importing test library '{node.name}' failed.")
        else:
            self.append_error(node, f"Library setting requires value.")
            
        self.generic_visit(node)


class ErrorVisitor(blocks.ModelVisitor):
    def __init__(self):
        super().__init__()
        self.errors = []

    @classmethod
    def find_from(cls, model):
        finder = cls()
        finder.visit(model)
        return finder.errors

    def generic_visit(self, node) -> Any:
        if hasattr(node, "error") and node.error is not None:
            self.errors.append(create_error(node, node.error))

        super().generic_visit(node)


def collect_analysis_errors(completion_context: ICompletionContext):
    from robotframework_ls.impl import ast_utils
    from robotframework_ls.impl.ast_utils import create_error_from_node
    from robotframework_ls.impl.collect_keywords import collect_keywords
    from robotframework_ls.impl.text_utilities import normalize_robot_name

    errors = []
    collector = _KeywordsCollector()
    collect_keywords(completion_context, collector)

    ast = completion_context.get_ast()
    for keyword_usage_info in ast_utils.iter_keyword_usage_tokens(ast):
        completion_context.check_cancelled()
        normalized_name = normalize_robot_name(keyword_usage_info.name)
        if not collector.contains_keyword(normalized_name):

            # There's not a direct match, but the library name may be builtin
            # into the keyword name, so, check if we have a match that way.

            node = keyword_usage_info.node
            error = create_error_from_node(
                node,
                "Undefined keyword: %s." % (keyword_usage_info.name,),
                tokens=[keyword_usage_info.token],
            )

            errors.append(error)
        else:
            multi = collector.check_multiple_keyword_definitions(
                normalized_name)
            if multi is not None:

                node = keyword_usage_info.node
                error = create_error_from_node(
                    node,
                    "Multiple keywords with name '%s' found. Give the full name of the keyword you want to use:\n%s"
                    % (keyword_usage_info.name, "\n".join([f"    {m.library_alias}.{m.keyword_name}" for m in multi])),
                    tokens=[keyword_usage_info.token],
                )
                errors.append(error)

        if len(errors) >= MAX_ERRORS:
            # i.e.: Collect at most 100 errors
            break

    #errors += ErrorVisitor.find_from(ast)
    errors += CodeAnalysisVisitor.find_from(completion_context)

    return errors
