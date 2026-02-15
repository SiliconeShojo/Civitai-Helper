from __future__ import annotations
from collections.abc import Generator
import os
import platform
import time
from typing import cast, Literal
from tqdm import tqdm
import requests
import urllib3
from . import util


DL_EXT = ".downloading"
MAX_RETRIES = 30

urllib3.disable_warnings()

def calculate_stepback_delay_seconds(
    retries: int
) -> int:

    delay = 3 + ((retries >> 1)**2)
    return delay


def request_get(
    url:str,
    headers:dict | None=None,
    retries=0
) -> tuple[Literal[True], requests.Response] | tuple[Literal[False], str]:

    headers = util.append_default_headers(headers or {})

    try:
        response = requests.get(
            url,
            stream=True,
            verify=False,
            headers=headers,
            proxies=util.PROXIES,
            timeout=util.REQUEST_TIMEOUT
        )

    except TimeoutError:
        output = f"GET Request timed out for {url}"
        print(output)
        return (False, output)

    if not response.ok:
        status_code = response.status_code
        reason = response.reason
        util.printD(util.indented_msg(
            f"""
            GET Request failed with error code:
            {status_code}: {reason}
            """
        ))

        if status_code == 401:
            return (
                False,
                "This download requires Authentication. Please add an API Key to Civitai Helper's settings to continue this download."
            )

        if status_code == 416:
            response.raise_for_status()

        if status_code != 404 and retries < MAX_RETRIES:
            retry_delay = calculate_stepback_delay_seconds(retries)
            util.printD(f"Retrying after {retry_delay} seconds")

            time.sleep(retry_delay)

            return request_get(
                url,
                headers,
                retries + 1
            )

        return (False, reason)

    return (True, response)


def visualize_progress(percent:int, downloaded:int, total:int, speed:int | float, show_bar=True) -> str:

    s_total = f"{human_readable_filesize(total)}"
    s_downloaded = f"{human_readable_filesize(downloaded):>{len(s_total)}}"
    s_percent = f"{percent:>3}"
    s_speed = f'{human_readable_filesize(speed)}Bps'

    snippet = f"`{s_percent}%: {s_downloaded}B / {s_total}B @ {s_speed}`"

    if not show_bar:
        return snippet.replace(" ", "\u00a0")

    progress = "\u2588" * percent

    return f"`[{progress:<100}] {snippet}`".replace(" ", "\u00a0")


def download_progress(
    url:str,
    file_path:str,
    total_size:int,
    headers:dict | None=None,
    response_without_range:requests.Response | None=None
) -> Generator[tuple[bool, str] | str, None, None]:

    if not headers:
        headers = {}

    dl_path = f"{file_path}{DL_EXT}"

    util.printD(f"Downloading to temp file: {dl_path}")

    downloaded_size = 0
    if os.path.exists(dl_path):
        downloaded_size = os.path.getsize(dl_path)
        util.printD(f"Resuming partially downloaded file from progress: {downloaded_size}")

    if response_without_range and downloaded_size == 0:
        response = response_without_range
    else:
        if response_without_range:
            response_without_range.close()

        headers_with_range = util.append_default_headers({
            **headers,
            "Range": f"bytes={downloaded_size:d}-",
        })

        try:
            success, response_or_error = request_get(
                url,
                headers=headers_with_range,
            )

        except requests.exceptions.HTTPError as dl_error:

            if dl_error.response.status_code != 416:
                util.printD(f"An unhandled error has occurred while requesting data: {dl_error.response.status_cude}.")
                raise

            util.printD("Could not resume download from existing temporary file. Restarting download.")

            os.remove(dl_path)

            yield from download_progress(url, file_path, total_size, headers)
            return

        if not success:
            yield (False, cast(str, response_or_error))
            return

        response = cast(requests.Response, response_or_error)

    last_tick = 0
    start = time.time()

    downloaded_this_session = 0

    with open(dl_path, 'ab') as target, tqdm(
        initial=target.tell(),
        total=total_size,
        unit='iB',
        unit_scale=True,
        unit_divisor=1024
    ) as progress_bar:
        for chunk in response.iter_content(chunk_size=256*1024):
            if chunk:
                downloaded_this_session += len(chunk)
                downloaded_size += len(chunk)
                written = target.write(chunk)

                target.flush()

                progress_bar.update(written)

                percent = int(100 * (downloaded_size / total_size))
                timer = time.time()

                if timer - last_tick > 0.2 or percent == 100:

                    last_tick = timer
                    elapsed = timer - start
                    speed = downloaded_this_session // elapsed if elapsed >= 1 \
                        else downloaded_this_session

                    text_progress = visualize_progress(
                        percent,
                        downloaded_size,
                        total_size,
                        speed,
                        False
                    )

                    yield text_progress

    downloaded_size = os.path.getsize(dl_path)
    if downloaded_size != total_size:
        warning = util.indented_msg(
            f"""
            File is not the correct size: {file_path}.
            Expected {total_size:d}, got {downloaded_size:d}.
            The file may be corrupt. If you encounter issues,
            you can try again later or download the file manually: {url}
            """
        )
        util.warning(warning)
        util.printD(warning)

    os.rename(dl_path, file_path)
    output = f"File Downloaded to: {file_path}"
    util.printD(output)

    yield (True, file_path)


def get_file_path_from_service_headers(response:requests.Response, folder:str) -> str | None:

    content_disposition = response.headers.get("Content-Disposition", None)

    if content_disposition is None:
        util.printD("Can not get file name from download url's header")
        return None

    filename = content_disposition.split("=")[1].strip('"')
    filename = filename.encode('iso8859-1').decode('utf-8')
    if not filename:
        util.printD(f"Fail to get file name from Content-Disposition: {content_disposition}")
        return None

    return os.path.join(folder, filename)


def dl_file(
    url:str,
    folder:str | None=None,
    filename:str | None=None,
    file_path:str | None=None,
    headers:dict | None=None,
    duplicate:str | None=None
) -> Generator[tuple[bool, str] | str, None, None]:

    if not headers:
        headers = {}

    success, response_or_error = request_get(url, headers=headers)

    if not success:
        yield (False, cast(str, response_or_error))
        return

    response = cast(requests.Response, response_or_error)

    util.printD(f"Start downloading from: {url}")

    with response:

        if not file_path:
            if not (folder and os.path.isdir(folder)):
                yield (
                    False,
                    "No directory to save model to."
                )
                return

            if filename:
                file_path = os.path.join(folder, filename)
            else:
                file_path = get_file_path_from_service_headers(response, folder)

            if not file_path:
                yield (
                    False,
                    "Could not get a file_path to place saved file."
                )
                return

        util.printD(f"Target file path: {file_path}")
        base, ext = os.path.splitext(file_path)

        if os.path.isfile(file_path):
            if duplicate == "Rename New":
                count = 2
                new_base = base
                while os.path.isfile(file_path):
                    util.printD("Target file already exist.")
                    new_base = f"{base}_{count}"
                    file_path = f"{new_base}{ext}"
                    count += 1

            elif duplicate != "Overwrite":
                yield (
                    False,
                    f"File {file_path} already exists! Download will not proceed."
                )
                return

        total_size = 0
        try:
            total_size = int(response.headers['Content-Length'])
        except(KeyError):
            yield (
                False,
                f"Could not get file size from Civitai. If Civitai is not having network issues, this can happen if you do not provide an API key in Civitai Helper's settings."
            )
            return

        util.printD(f"File size: {total_size} ({human_readable_filesize(total_size)})")

        yield from download_progress(url, file_path, total_size, headers, response)


def human_readable_filesize(size:int | float) -> str:
    prefixes = ["", "K", "M", "G"]

    unit = 1000 if platform.system() == "Darwin" else 1024

    i = 0
    while size > unit and i < len(prefixes) - 1:
        i += 1
        size = size / unit

    return f"{round(size, 2)}{prefixes[i]}"


def error(download_url:str, msg:str) -> str:
    output = util.indented_msg(
        f"""
        Download failed.
        {msg}
        Download url: {download_url}
        """
    )
    util.printD(output)
    return output
