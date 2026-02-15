import json
from . import util

JS_ACTIONS = (
    "open_url",
    "add_trigger_words",
    "use_preview_prompt",
    "dl_model_new_version",
    "rename_card",
    "remove_card"
)

PY_ACTIONS = (
    "open_url",
    "rename_card",
    "remove_card"
)


def parse_js_msg(msg):

    util.printD("Start parse js msg")
    msg_dict = json.loads(msg)

    if isinstance(msg_dict, str):
        msg_dict = json.loads(msg_dict)

    action = msg_dict.get("action", "")
    if not action:
        util.printD("No action from js request")
        return None

    if action not in JS_ACTIONS:
        util.printD(f"Unknown action: {action}")
        return None

    util.printD("End parse js msg")

    return msg_dict


def build_py_msg(action:str, content:dict):

    util.printD("Start build_msg")
    if not (content and action and action in PY_ACTIONS):
        util.indented_msg(
            f"""
            Could not run action on content:
            {action=}
            {content=}
            """
        )
        return None

    msg = {
        "action" : action,
        "content": content
    }

    util.printD("End build_msg")
    return json.dumps(msg)
