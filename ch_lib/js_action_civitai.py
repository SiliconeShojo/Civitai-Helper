import os
from pathlib import Path
import webbrowser
from . import util
from . import model
from . import civitai
from . import msg_handler
from . import downloader


def open_model_url(msg):
    util.printD("Start open_model_url")

    output = ""
    result = msg_handler.parse_js_msg(msg)
    if not result:
        util.printD("Parsing js ms failed")
        return None

    model_type = result["model_type"]
    search_term = result["search_term"]

    model_info = civitai.load_model_info_by_search_term(model_type, search_term)
    if not model_info:
        util.printD(f"Failed to get model info for {model_type} {search_term}")
        return ""

    if "modelId" not in model_info.keys():
        util.printD(f"Failed to get model id from info file for {model_type} {search_term}")
        return ""

    model_id = model_info["modelId"]
    if not model_id:
        util.printD(f"model id from info file of {model_type} {search_term} is None")
        return ""

    url = f'{civitai.URLS["modelPage"]}{model_id}'

    content = {
        "url": ""
    }

    if not util.get_opts("ch_open_url_with_js"):
        util.printD(f"Open Url: {url}")
        webbrowser.open_new_tab(url)
    else:
        util.printD("Send Url to js")
        content["url"] = url
        output = msg_handler.build_py_msg("open_url", content)

    util.printD("End open_model_url")
    return output


def add_trigger_words(msg):
    util.printD("Start add_trigger_words")

    result = msg_handler.parse_js_msg(msg)
    if not result:
        util.printD("Parsing js ms failed")
        return None

    model_type = result["model_type"]
    search_term = result["search_term"]
    prompt = result["prompt"]

    model_info = civitai.load_model_info_by_search_term(model_type, search_term)
    if not model_info:
        util.printD(f"Failed to get model info for {model_type} {search_term}")
        return [prompt, prompt]

    if "trainedWords" not in model_info.keys():
        util.printD(f"Failed to get trainedWords from info file for {model_type} {search_term}")
        return [prompt, prompt]

    trained_words = model_info.get("trainedWords", [])
    if len(trained_words) == 0:
        util.printD(f"trainedWords from info file for {model_type} {search_term} is empty")
        return [prompt, prompt]

    prompt_list = ',' in trained_words[0]

    separator = "\n" if prompt_list else ", "
    trigger_words = separator.join(trained_words)

    new_prompt = f"{prompt} {trigger_words}"

    util.printD(f"trigger_words: {trigger_words}")
    util.printD(f"prompt: {prompt}")
    util.printD(f"new_prompt: {new_prompt}")

    util.printD("End add_trigger_words")

    return [new_prompt, new_prompt]


def use_preview_image_prompt(msg):
    util.printD("Start use_preview_image_prompt")

    result = msg_handler.parse_js_msg(msg)
    if not result:
        util.printD("Parsing js ms failed")
        return None

    model_type = result["model_type"]
    search_term = result["search_term"]
    prompt = result["prompt"]
    neg_prompt = result["neg_prompt"]


    model_info = civitai.load_model_info_by_search_term(model_type, search_term)
    if not model_info:
        util.printD(f"Failed to get model info for {model_type} {search_term}")
        return [prompt, neg_prompt, prompt, neg_prompt]

    images = model_info.get("images", [])
    if len(images) == 0:
        util.printD(f"No images from info file for {model_type} {search_term}")
        return [prompt, neg_prompt, prompt, neg_prompt]

    preview_prompt = ""
    preview_neg_prompt = ""
    for img in images:
        meta = img.get("meta", {})
        preview_prompt = meta.get("prompt", "")
        preview_neg_prompt = meta.get("negativePrompt", "")

        if preview_prompt:
            break

    if not preview_prompt:
        util.printD(f"There is no prompt of {model_type} {search_term} in its preview image")
        return [prompt, neg_prompt, prompt, neg_prompt]

    util.printD("End use_preview_image_prompt")

    return [preview_prompt, preview_neg_prompt, preview_prompt, preview_neg_prompt]


def dl_model_new_version(msg):
    util.printD("Start dl_model_new_version")

    output = ""

    max_size_preview = util.get_opts("ch_max_size_preview")
    nsfw_preview_threshold = util.get_opts("ch_nsfw_threshold")

    result = msg_handler.parse_js_msg(msg)
    if not result:
        output = "Parsing js msg failed"
        util.printD(output)
        yield output
        return

    model_path = result["model_path"]
    version_id = result["version_id"]
    download_url = result["download_url"]
    model_type = result["model_type"]

    if not (model_path and version_id and download_url):
        output = util.indented_msg(f"""
            Missing parameter:
            {model_path=}
            {version_id=}
            {download_url=}
        """)
        util.printD(output)
        yield output
        return

    util.printD(f"model_path: {model_path}")
    util.printD(f"version_id: {version_id}")
    util.printD(f"download_url: {download_url}")

    if not os.path.isfile(model_path):
        output = f"model_path is not a file: {model_path}"
        util.printD(output)
        yield output
        return

    model_folder = os.path.dirname(model_path)

    success = False
    headers = {
        "content-type": "application/json"
    }
    api_key = util.get_opts("ch_civiai_api_key")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    for result in downloader.dl_file(download_url, folder=model_folder, headers=headers):
        if not isinstance(result, str):
            success, output = result
            break

        yield result

    if not success:
        util.printD(output)
        yield "Model download failed. See console for more details."
        return

    version_info = civitai.get_version_info_by_version_id(version_id)

    model.process_model_info(output, version_info, model_type)

    for result in civitai.get_preview_image_by_model_path(
        output,
        max_size_preview,
        nsfw_preview_threshold
    ):
        yield result

    output = f"Done. Model downloaded to: {output}"
    util.printD(output)
    yield output


def get_model_path_from_js_msg(result):
    if not result:
        output = "Parsing js ms failed"
        util.error(output)
        util.printD(output)
        return None

    model_type = result["model_type"]
    search_term = result["search_term"]

    model_path = model.get_model_path_by_search_term(model_type, search_term)
    if not model_path:
        output = f"Fail to get model for {model_type} {search_term}"
        util.error(output)
        util.printD(output)
        return None

    if not os.path.isfile(model_path):
        output = f"Model {model_type} {search_term} does not exist, no need to remove"
        util.error(output)
        util.printD(output)
        return None

    return model_path


def make_new_filename(candidate_file, model_name, new_name):
    path, filename = os.path.split(candidate_file)

    if filename.index(model_name) != 0:
        output = util.indented_msg(f"""
            Could not find model_name in candidate file
            {model_name=}
            {candidate_file=}
            {new_name=}
        """)
        util.error(output)
        util.printD(output)
        return None

    new_filename = filename.replace(model_name, new_name, 1)

    new_path = os.path.join(path, new_filename)

    return new_path


def rename_model_by_path(msg):
    util.printD("Start rename_model_by_path")

    output = ""
    result = msg_handler.parse_js_msg(msg)

    model_path = get_model_path_from_js_msg(result)

    if model_path is None:
        output = "Could not rename model."
        return output

    model_files = model.get_model_files_from_model_path(model_path)
    model_name = Path(model_path).stem
    new_name = util.bash_filename(result["new_name"])

    renamed = []
    for candidate_file in model_files:
        new_path = make_new_filename(candidate_file, model_name, new_name)
        if new_path is None:
            continue

        renamed.append(f"* {candidate_file} to {new_path}")
        util.printD(f"Renaming file {candidate_file} to {new_path}")
        os.rename(candidate_file, new_path)

    renamed = "\n".join(renamed)
    status = f"The following files were renamed: \n{renamed}"
    util.info(status)

    util.printD("End rename_model_by_path")
    return output


def remove_model_by_path(msg):
    output = ""
    util.printD("Start remove_model_by_path")

    result = msg_handler.parse_js_msg(msg)

    model_path = get_model_path_from_js_msg(result)

    if model_path is None:
        output = "Could not remove model."
        return output

    model_files = model.get_model_files_from_model_path(model_path)

    removed = []
    for candidate_file in model_files:
        util.printD(f"* Removing file {candidate_file}")
        removed.append(candidate_file)
        os.remove(candidate_file)

    removed = "\n".join(removed)
    status = f"The following files were removed: \n{removed}"
    util.info(status)

    util.printD("End remove_model_by_path")
    return output
