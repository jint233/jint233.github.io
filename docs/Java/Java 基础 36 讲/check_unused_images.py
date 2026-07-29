import os
import glob
import re

base_dir = "/Users/admin/Notes/docs/Java/Java 基础 36 讲"
assets_dir = os.path.join(base_dir, "assets")

md_files = glob.glob(os.path.join(base_dir, "*.md"))
all_content = ""
for md_file in md_files:
    with open(md_file, 'r', encoding='utf-8') as f:
        all_content += f.read()

used_images = set(re.findall(r'!\[.*?\]\((assets/.*?)\)', all_content))
used_image_names = {os.path.basename(img) for img in used_images}

asset_files = glob.glob(os.path.join(assets_dir, "*"))
asset_names = {os.path.basename(img) for img in asset_files}

unused = asset_names - used_image_names
for img in unused:
    print(f"Removing unused image: {img}")
    os.remove(os.path.join(assets_dir, img))

print(f"Removed {len(unused)} unused images.")
