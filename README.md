# Civitai Helper
Stable Diffusion Webui Extension for Civitai, to handle your models much more easily.


> [!NOTE]
> This is a personal modified fork of [Stable-Diffusion-Webui-Civitai-Helper](https://github.com/zixaphir/Stable-Diffusion-Webui-Civitai-Helper), designed to be fully compatible with [SD-WebUI Forge Neo](https://github.com/Haoming02/sd-webui-forge-classic/tree/neo).

---

# Features
* Scans all models to download model information and preview images from Civitai.
* Link local model to a civitai model by civitai model's url
* Download a model by Civitai Url into SD's model folder or subfolders.
* Checking all your local models for new versions from Civitai
* Download a new version directly into SD model folder
* Modified Built-in "Extra Network" cards, to add the following buttons on each card:
  - 🖼️: Modified "replace preview" text into this icon
  - 🌐: Open this model's Civitai url in a new tab
  - 💡: Add this model's trigger words to prompt
  - ✏️: Rename model
  - ❌: Remove/Delete model
* Automatically add metadata of model resources used to all generated images. Useful for uploading to Civitai.

---

# Install
Go to SD webui's extension tab, go to `Install from url` sub-tab.
Copy this project's url into it, click install.

Alternatively, download this project as a zip file, and unzip it to `Your SD webui folder/extensions`.

Everytime you install or update this extension, you need to shutdown SD Webui and Relaunch it. Just "Reload UI" won't work for this extension.

Some functionality from Civitai, like downloading models, requires having an account and adding your API key.

---