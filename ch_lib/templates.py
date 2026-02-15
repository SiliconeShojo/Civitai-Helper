from string import Template
from . import util

article = Template(util.dedent("""
    <article style="margin: 5px; clear: both;">
        $thumbnail
        <div style="font-size:16px">
            File: $model_path
        </div>
        $download
        <div style="font-size:20px;margin:6px 0px;">
            <b>Model: <a href="$url" target="_blank"><u>$model_name</u></a></b>
        </div>
    </article>
""").strip())

thumbnail = Template(util.dedent("""
    <img src='$img_url' style='float: left; margin: 5px;'>
""").strip())

description = Template(util.dedent("""
    <blockquote style="font-size:16px;margin:6px 0px;">
        $description
    </blockquote>
    <br>
""").strip())

download = Template(util.dedent("""
    <div style="font-size:16px;margin:6px 0px;">
        New Version: <u><a href="$download_url" target="_blank" style="margin:0px 10px;">$new_version_name</a></u>
        <u><a href='#' style='margin:0px 10px;' onclick="ch_dl_model_new_version(event, '$model_path', '$new_version_id', '$download_url', '$model_type')">[Download into SD]</a></u>
    </div>
""").strip())

no_download = Template(util.dedent("""
    <div style="font-size:16px;margin:6px 0px;">
        New Version: $new_version_name
    </div>
""").strip())

duplicate_card = Template(util.dedent("""
    <a href='#' onclick="remove_dup_card(event, '$model_type', '$search_term')" onmouseover="display_ch_path(event, '$path')" onmouseout="hide_ch_path(event)" onmousemove="move_ch_path(event)">
        <div class='card' style=$style data-name="$name">
            $background_image
            <div class='actions'>
                <div class='additional'>
                    <span style="display:none">$search_term</span>
                </div>
                <span class='name'>$name</span>
                <span class='description'>$description</span>
            </div>
        </div>
    </a>
""").strip())

duplicate_preview = Template(util.dedent("""
    <img src="./sd_extra_networks/thumb?filename=$bg_image" class="preview" loading="lazy">
""").strip())

duplicate_article = Template(util.dedent("""
    <article>
        <h1>
            $section_name
        </h1>
        $contents
    </article>
""").strip())

duplicate_row = Template(util.dedent("""
    <div id="ch_$hash">
        <div class=civitai_name>
            <h2>
                $civitai_name
            </h2>
        </div>
        <div class=duplicate_model id="ch_${hash}_cards">
            $columns
        </div>
    </div>
""").strip())


duplicate_column = Template(util.dedent("""
        <div class=dup_$count>
            $card
        </div>
""").strip())

update_card_grid = Template(util.dedent("""
    <div class="ch-update-grid">
        $cards
    </div>
""").strip())

update_card = Template(util.dedent("""
    <div class="ch-update-card">
        <div class="ch-update-card-media">
            $media
        </div>
        <div class="ch-update-card-content">
            <div class="ch-update-card-title" title="$model_name">$model_name</div>
            <div class="ch-update-card-version">
                <span>🔔 New: $new_version_name</span>
            </div>
            <div class="ch-update-card-desc">
                $description
            </div>
            <div class="ch-update-card-actions">
                <a href='$url' target='_blank' class='ch-update-btn' style='background:#555;'>View</a>
                $download_btn
            </div>
        </div>
    </div>
""").strip())

update_download_btn = Template(util.dedent("""
    <a href='#' class='ch-update-btn' onclick="ch_dl_model_new_version(event, '$model_path', '$new_version_id', '$download_url', '$model_type')">Download</a>
""").strip())
