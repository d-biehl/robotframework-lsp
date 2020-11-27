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
            
            signature_args = ""
            for a in keyword_found.keyword_args:
                if signature_args:
                    signature_args +=", "

                if a.is_keyword_arg:
                    signature_args += "**"
                if a.is_star_arg:
                    signature_args += "*"

                signature_args += a.arg_name

                if a.arg_type:
                    signature_args += f": {a.arg_type}"

                if a.default_value:
                    signature_args += f"={a.default_value}"

            signature = f"{keyword_found.keyword_name}({signature_args})"

            hover_text = "```python\n"
            
            hover_text += signature

            hover_text += "\n```"

            hover_text += "\n"
            hover_text += keyword_found.docs 
            
            return Hover(hover_text).to_dict()

    return None
