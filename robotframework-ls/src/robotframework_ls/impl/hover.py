from robotframework_ls.impl.protocols import ICompletionContext, IKeywordFound
from typing import Optional
from robot.parsing.lexer.tokens import Token
from robocorp_ls_core.robotframework_log import get_logger

log = get_logger(__name__)


def hover(completion_context: ICompletionContext) -> Optional[dict]:

    t = completion_context.get_current_token()
    if t and t.token and t.token.type == Token.KEYWORD:
        keyword_definition = completion_context.get_current_keyword_definition()
        if keyword_definition is not None:

            from robocorp_ls_core.lsp import Hover

            keyword_found: IKeywordFound = keyword_definition.keyword_found

            return Hover(keyword_found.docs).to_dict()

    return None
