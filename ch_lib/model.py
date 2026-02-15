import glob
import os
import json
import re
import urllib.parse
from PIL import Image
import piexif
import piexif.helper
from modules import shared
from modules import paths_internal
from . import civitai
from . import downloader
from . import util


ROOT_PATH = paths_internal.data_path

EXTS = (".bin", ".pt", ".safetensors", ".ckpt", ".gguf", ".zip")
CIVITAI_EXT = ".info"
SDWEBUI_EXT = ".json"

folders = {
    "ti": os.path.join(ROOT_PATH, "embeddings"),
    "hyper": os.path.join(ROOT_PATH, "models", "hypernetworks"),
    "ckp": os.path.join(ROOT_PATH, "models", "Stable-diffusion"),
    "lora": os.path.join(ROOT_PATH, "models", "Lora"),
    "lycoris": os.path.join(ROOT_PATH, "models", "LyCORIS"),
    "vae": os.path.join(ROOT_PATH, "models", "VAE"),
    "controlnet": os.path.join(ROOT_PATH, "models", "Controlnet"),
    "detection": os.path.join(ROOT_PATH, "models", "adetailer"),
}


class VersionMismatchException(Exception):

    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


def get_model_info_paths(model_path):
    base, _ = os.path.splitext(model_path)
    info_file = f"{base}{civitai.SUFFIX}{CIVITAI_EXT}"
    sd15_file = f"{base}{SDWEBUI_EXT}"
    return (info_file, sd15_file)


def local_image(model_info, img):
    if "url" not in img:
        raise ValueError("No URL to fetch the image.")
    if "images" not in model_info:
        return None

    for eimg in model_info["images"]:
        if "url" not in eimg:
            continue
        if img["url"] == eimg["url"]:
            return eimg.get("local_file", None)

    return None


def next_example_image_path(model_path):
    base_path, _ = os.path.splitext(model_path)
    i = 0
    while glob.glob(f"{base_path}.example.{i}.*"):
        i += 1
    return f"{base_path}.example.{i}"


def get_custom_model_folder():


    if hasattr(shared.cmd_opts, "embeddings_dir") and shared.cmd_opts.embeddings_dir and os.path.isdir(shared.cmd_opts.embeddings_dir):
        folders["ti"] = shared.cmd_opts.embeddings_dir

    if hasattr(shared.cmd_opts, "hypernetwork_dir") and shared.cmd_opts.hypernetwork_dir and os.path.isdir(shared.cmd_opts.hypernetwork_dir):
        folders["hyper"] = shared.cmd_opts.hypernetwork_dir

    if hasattr(shared.cmd_opts, "ckpt_dir") and shared.cmd_opts.ckpt_dir and os.path.isdir(shared.cmd_opts.ckpt_dir):
        folders["ckp"] = shared.cmd_opts.ckpt_dir

    if hasattr(shared.cmd_opts, "lora_dir") and shared.cmd_opts.lora_dir and os.path.isdir(shared.cmd_opts.lora_dir):
        folders["lora"] = shared.cmd_opts.lora_dir

    if hasattr(shared.cmd_opts, "vae_dir") and shared.cmd_opts.vae_dir and os.path.isdir(shared.cmd_opts.vae_dir):
        folders["vae"] = shared.cmd_opts.vae_dir

    if util.get_opts("ch_dl_lyco_to_lora"):
        folders["lycoris"] = folders["lora"]
        return

    try:
        if os.path.isdir(shared.cmd_opts.lyco_dir):
            folders["lycoris"] = shared.cmd_opts.lyco_dir

    except AttributeError:
        try:
            if os.path.isdir(shared.cmd_opts.lyco_dir_backcompat):
                folders["lycoris"] = shared.cmd_opts.lyco_dir_backcompat

        except AttributeError:
            return


def locate_model_from_partial(root, model_name):

    util.printD(model_name)

    for ext in EXTS:
        filename = os.path.join(root, f"{model_name}{ext}")
        if os.path.isfile(filename):
            return filename

    return None


def metadata_needed(info_file, sd15_file, refetch_old):

    need_civitai = metadata_needed_for_type(info_file, "civitai", refetch_old)
    need_sdwebui = metadata_needed_for_type(sd15_file, "sdwebui", refetch_old)

    return need_civitai or need_sdwebui


def metadata_needed_for_type(path, meta_type, refetch_old):

    if meta_type == "sdwebui" and not util.get_opts("ch_dl_webui_metadata"):
        return False

    if not os.path.isfile(path):
        return True

    return False


def verify_overwrite_eligibility(path, new_data):
    if not os.path.isfile(path):
        return True

    with open(path, "r") as file:
        old_data = json.load(file)

    if "civitai" in path:
        new_id = new_data.get("id", "")
        old_id = old_data.get("id", "")
        if new_id != old_id:
            if old_id != "":
                raise VersionMismatchException(
                    f"New metadata id ({new_id}) does not match old metadata id ({old_id})"
                )

    new_description = new_data.get("description", "")
    old_description = old_data.get("description", "")
    if new_description == "" and old_description != "":
        util.printD(
            f"New description is blank while old description contains data. Skipping {path}"
        )
        return False

    return True


def write_info(data, path, info_type):
    util.printD(f"Write model {info_type} info to file: {path}")
    with open(os.path.realpath(path), 'w') as info_file:
        info_file.write(json.dumps(data, indent=4))


def process_model_info(model_path, model_info, model_type="ckp", refetch_old=False):

    if model_info is None:
        util.printD("Failed to get model info.")
        return

    info_file, sd15_file = get_model_info_paths(model_path)
    existing_info = {}
    try:
        existing_info = load_model_info(info_file)
    except:
        util.printD("No existing model info.")

    clean_html = util.get_opts("ch_clean_html")

    parent = model_info["model"]

    description = parent.get("description", "")
    if description and clean_html:
        description = util.trim_html(description)
    parent["description"] = description

    version_description = model_info.get("description", "")
    if version_description and clean_html:
        version_description = util.trim_html(version_description)
    model_info["description"] = version_description



    updated = False
    if util.get_opts("ch_download_examples"):
        images = model_info.get("images", [])

        for img in images:
            url = img.get("url", None)


            nsfw_preview_threshold = util.get_opts("ch_nsfw_threshold")
            rating = img.get("nsfwLevel", 32)
            if rating > 1:
                if civitai.NSFW_LEVELS[nsfw_preview_threshold] < rating:
                    continue

            if url:
                existing_dl = local_image(existing_info, img)
                if existing_dl:
                    img["local_file"] = existing_dl

                else:
                    path = urllib.parse.urlparse(url).path
                    _, ext = os.path.splitext(path)
                    outpath = next_example_image_path(model_path) + ext

                    for result in downloader.dl_file(
                            url,
                            folder=os.path.dirname(outpath),
                            filename=os.path.basename(outpath)):
                        if not isinstance(result, str):
                            success, output = result
                            break

                    if not success:
                        downloader.error(url, "Failed to download model image.")
                        continue

                    img["local_file"] = outpath
                    updated = True

    if metadata_needed_for_type(info_file, "civitai", refetch_old) or updated:
        if refetch_old:
            try:
                if verify_overwrite_eligibility(info_file, model_info):
                    write_info(model_info, info_file, "civitai")

            except VersionMismatchException as e:
                util.printD(f"{e}, aborting")
                return

        else:
            write_info(model_info, info_file, "civitai")

    if not util.get_opts("ch_dl_webui_metadata"):
        return

    if not metadata_needed_for_type(sd15_file, "sdwebui", refetch_old):
        util.printD(f"Metadata not needed for: {sd15_file}.")
        return

    process_sd15_info(sd15_file, model_info, parent, model_type, refetch_old)


def process_sd15_info(sd15_file, model_info, parent, model_type, refetch_old):

    sd_data = {}

    sd_data["description"] = parent.get("description", "")

    version_info = model_info.get("description", None)
    if version_info is not None:
        sd_data["notes"] = version_info

    base_model = model_info.get("baseModel", None)
    sd_version = 'Unknown'
    if base_model:
        version = None
        try:
            version = base_model[3]
        except IndexError:
            version = 0

        sd_version = {
            "1": 'SD1',
            "2": 'SD2',
            "L": 'SDXL',
        }.get(version, 'Unknown')

    sd_data["sd version"] = sd_version

    for filedata in model_info["files"]:
        if filedata["type"] == "VAE":
            sd_data["vae"] = filedata["name"]

    activator = model_info.get("trainedWords", [])
    if (activator and activator[0]):
        if "," in activator[0]:
            sd_data["activation text"] = " || ".join(activator)
        else:
            sd_data["activation text"] = ", ".join(activator)

    if model_type in ["lora", "lycoris"]:
        sd_data["preferred weight"] = 0



    if refetch_old:
        if verify_overwrite_eligibility(sd15_file, sd_data):
            write_info(sd_data, sd15_file, "webui")
    else:
        write_info(sd_data, sd15_file, "webui")


def load_model_info(path):
    model_info = None
    with open(os.path.realpath(path), 'r') as json_file:
        try:
            model_info = json.load(json_file)
        except ValueError:
            util.printD(f"Selected file is not json: {path}")
            return None

    return model_info


def get_potential_model_preview_files(model_path, all_prevs=False):
    preview_exts = ["png", "jpg", "jpeg", "webp", "gif"]
    preview_files = []

    base, _ = os.path.splitext(model_path)

    for ext in preview_exts:
        if all_prevs:
            preview_files.append(f"{base}.{ext}")
        preview_files.append(f"{base}.preview.{ext}")

    return preview_files


def get_model_files_from_model_path(model_path):

    base, _ = os.path.splitext(model_path)

    info_file, sd15_file = get_model_info_paths(model_path)
    user_preview_path = f"{base}.png"

    paths = [model_path, info_file, sd15_file, user_preview_path]
    preview_paths = get_potential_model_preview_files(model_path)

    paths = paths + preview_paths

    return [path for path in paths if os.path.isfile(path)]


def get_model_names_by_type(model_type:str) -> list:

    if model_type == "lora" and folders['lycoris']:
        model_folders = [folders[model_type], folders['lycoris']]
    else:
        model_folders = [folders[model_type]]

    model_names = []
    for model_folder in model_folders:
        for root, _, files in os.walk(model_folder, followlinks=True):
            for filename in files:
                item = os.path.join(root, filename)
                _, ext = os.path.splitext(item)
                if ext in EXTS:
                    model_names.append(filename)

    return model_names


def get_model_path_by_type_and_name(model_type:str, model_name:str) -> str:
    util.printD("Run get_model_path_by_type_and_name")
    if not model_name:
        util.printD("model name can not be empty")
        return None

    model_folders = [folders.get(model_type, None)]

    if model_folders[0] is None:
        util.printD(f"unknown model_type: {model_type}")
        return None

    if model_type == "lora" and folders['lycoris']:
        model_folders.append(folders['lycoris'])

    model_path = util.find_file_in_folders(model_folders, model_name)

    msg = util.indented_msg(f"""
        Got following info:
        {model_path=}
    """)
    util.printD(msg)

    return model_path


def get_model_path_by_search_term(model_type, search_term):
    util.printD(f"Search model of {search_term} in {model_type}")
    if folders.get(model_type, None) is None:
        util.printD("Unknown model type: " + model_type)
        return None

    model_hash = search_term.split()[-1]
    model_sub_path = search_term.replace(f" {model_hash}", "")

    if model_type == "hyper":
        model_sub_path = f"{search_term}.pt"

    if model_sub_path[:1] == "/":
        model_sub_path = model_sub_path[1:]

    if model_type == "lora" and folders['lycoris']:
        model_folders = [folders[model_type], folders['lycoris']]
    else:
        model_folders = [folders[model_type]]

    for folder in model_folders:
        model_folder = folder
        model_path = os.path.join(model_folder, model_sub_path)

        if os.path.isfile(model_path):
            break

    msg = util.indented_msg(f"""
        Got following info:
        {model_folder=}
        {model_sub_path=}
        {model_path=}
    """)
    util.printD(msg)

    if not os.path.isfile(model_path):
        util.printD(f"Can not find model file: {model_path}")
        return None

    return model_path


def scan_civitai_info_image_meta():
    util.printD("Start Scan_civitai_info_image_meta")
    output = ""
    count = 0

    directories = [y for x, y in folders.items() if os.path.isdir(y)]
    util.printD(f"{directories=}")
    for directory in directories:
        for root, _, files in os.walk(directory):
            for filename in files:
                if filename.endswith('.civitai.info'):
                    update_civitai_info_image_meta(os.path.join(root, filename))
                    count = count + 1

    output = f"Done. Scanned {count} files."
    util.printD(output)
    return output
