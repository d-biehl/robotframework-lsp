from robotframework_ls.impl.protocols import ICompletionContext, IKeywordFound
from typing import Optional


def hover(completion_context: ICompletionContext) -> Optional[dict]:
    keyword_definition = completion_context.get_current_keyword_definition()
    if keyword_definition is not None:

        from robocorp_ls_core.lsp import Hover        

        keyword_found: IKeywordFound = keyword_definition.keyword_found

        return Hover(keyword_found.docs).to_dict()

    return None
