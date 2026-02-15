from __future__ import annotations
import os
import io
import re
import hashlib
import textwrap
import time
import gradio as gr
from modules import shared
from modules.shared import opts
from modules import hashes


try:
    import modules.cache as sha256_cache
except ModuleNotFoundError:
    import modules.hashes as sha256_cache



DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPad; CPU OS 12_2 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148"
    )
}

PROXIES = {
    "http": None,
    "https": None,
}

REQUEST_TIMEOUT = 300
REQUEST_RETRIES = 5

_MINUTE = 60
_HOUR = _MINUTE * 60
_DAY = _HOUR * 24

GRADIO_FALLBACK = False

script_dir = None

def printD(msg:any) -> str:
    print(f"[Civitai-Helper]: {msg}")


def append_default_headers(headers:dict) -> dict:

    for key, val in DEFAULT_HEADERS.items():
        if key not in headers:
            headers[key] = val
    return headers


def indented_msg(msg:str) -> str:

    msg_parts = textwrap.dedent(
        msg
    ).strip().split('\n')
    msg = [msg_parts.pop(0)]
    for part in msg_parts:
        part = ": ".join(part.split("="))
        msg.append(f"   {part}")
    msg = "\n".join(msg)

    return msg


def delay(seconds:float) -> None:
    time.sleep(seconds)


def is_stale(timestamp:float) -> bool:
    cur_time = ch_time()
    elapsed = cur_time - timestamp

    if elapsed > _DAY:
        return True

    return False


def info(msg:str) -> None:
    gr.Info(msg)


def warning(msg:str) -> None:
    gr.Warning(msg)


def error(msg:str) -> None:
    gr.Error(msg)


def ch_time() -> int:
    return int(time.time())


def dedent(text:str) -> str:
    return textwrap.dedent(text)


def get_name(model_path:str, model_type:str) -> str:

    model_name = os.path.splitext(os.path.basename(model_path))[0]
    return f"{model_type}/{model_name}"


def get_opts(key):
    return opts.data.get(key, None)


def gen_file_sha256(filename:str, model_type="lora", use_addnet_hash=False) -> str:

    cache = sha256_cache.cache
    dump_cache = sha256_cache.dump_cache
    model_name = get_name(filename, model_type)

    sha256_hashes = None
    if use_addnet_hash:
        sha256_hashes = cache("hashes-addnet")
    else:
        sha256_hashes = cache("hashes")

    sha256_value = hashes.sha256_from_cache(filename, model_name, use_addnet_hash)
    if sha256_value is not None:
        yield sha256_value
        return

    if shared.cmd_opts.no_hashing:
        printD("SD WebUI Civitai Helper requires hashing functions for this feature. \
            Please remove the commandline argument `--no-hashing` for this functionality.")
        yield None
        return

    with open(filename, "rb") as model_file:
        result = None
        for result in calculate_sha256(model_file, use_addnet_hash):
            yield result
        sha256_value = result

    printD(f"sha256: {sha256_value}")

    sha256_hashes[model_name] = {
        "mtime": os.path.getmtime(filename),
        "sha256": sha256_value,
    }

    dump_cache()

    yield sha256_value


def calculate_sha256(model_file, use_addnet_hash=False):

    blocksize= 1 << 20
    sha256_hash = hashlib.sha256()

    size = os.fstat(model_file.fileno()).st_size

    offset = 0
    if use_addnet_hash:
        model_file.seek(0)
        header= model_file.read(8)
        offset = int.from_bytes(header, "little") + 8
        model_file.seek(offset)

    pos = 0
    for block in read_chunks(model_file, size=blocksize):
        pos += len(block)

        percent = (pos - offset) / (size - offset)

        yield (percent, f"hashing model {model_file.name}")

        sha256_hash.update(block)

    hash_value =  sha256_hash.hexdigest()
    yield hash_value


def read_chunks(file, size=io.DEFAULT_BUFFER_SIZE) -> bytes:
    while True:
        chunk = file.read(size)
        if not chunk:
            break
        yield chunk


def get_subfolders(folder:str) -> list[str]:
    printD(f"Get subfolder for: {folder}")
    if not folder:
        printD("folder can not be None")
        return []

    if not os.path.isdir(folder):
        printD("path is not a folder")
        return []

    prefix_len = len(folder)
    full_dirs_searched = []
    subfolders = []
    for root, dirs, _ in os.walk(folder, followlinks=True):
        if root == folder:
            continue

        follow = []
        for directory in dirs:
            full_dir_path = os.path.join(root, directory)
            try:
                canonical_dir = os.path.realpath(full_dir_path, strict=True)
                if canonical_dir not in full_dirs_searched:
                    full_dirs_searched.append(canonical_dir)
                    follow.append(directory)

            except OSError:
                printD(f"Symlink loop: {directory}")
                continue

        subfolder = root[prefix_len:]
        subfolders.append(subfolder)

        dirs[:] = follow

    return subfolders


def find_file_in_folders(folders:list, filename:str) -> str:
    for folder in folders:
        for root, _, files in os.walk(folder, followlinks=True):
            if filename in files:
                return os.path.join(root, filename)

    return None


def get_relative_path(item_path:str, parent_path:str) -> str:

    if not (item_path and parent_path):
        return ""

    if not item_path.startswith(parent_path):
        return item_path

    relative = item_path[len(parent_path):]
    if relative[:1] == "/" or relative[:1] == "\\":
        relative = relative[1:]

    return relative


whitelist = re.compile(r"</?(a|img|br|p|b|strong|i|h[0-9]|code)[^>]*>")

attrs = re.compile(r"""(?:href|src|target)=['"]?[^\s'"]*['"]?""")

def safe_html_replace(match) -> str:
    tag = None
    attr = None
    close = False

    match = whitelist.match(match.group(0))
    if match is not None:
        html_elem = match.group(0)
        tag = match.group(1)
        close = html_elem[1] == "/"
        if (tag in ["a", "img"]) and not close:
            sub_match = attrs.findall(html_elem)
            if sub_match is not None:
                attr = " ".join(sub_match)

        if close:
            return f"</{tag}>"

        return f"<{tag} {attr}>" if attr else f"<{tag}>"

    return ""

def safe_html(html:str) -> str:

    return re.sub("<[^<]+?>", safe_html_replace, html)


def trim_html(html:str) -> str:

    def sub_tag(match):
        tag = match.group(1)
        if tag == "/p":
            return "\n\n"
        if tag == "br":
            return "\n"
        if tag == "li":
            return "* "
        if tag in ["code", "/code"]:
            return "`"
        return ''

    def sub_escaped(match):
        escaped = match.group(1)
        unescaped = {
            "gt": ">",
            "lt": "<",
            "quot": '"',
            "amp": "&"
        }
        return unescaped.get(escaped, "")

    html = html.replace("\u00a0", "")

    html = re.sub(r"<(/?[a-zA-Z]+)(?:[^>]+)?>", sub_tag, html)

    html = re.sub(r"\&(gt|lt|quot|amp)\;", sub_escaped, html)

    return html.strip()





filename_re = re.compile(r"[^A-Za-z\d\s\^\-\+_.\(\)\[\]]")
def bash_filename(filename:str) -> str:
    return re.sub(filename_re, "", filename)
