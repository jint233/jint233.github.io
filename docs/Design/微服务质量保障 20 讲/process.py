import os
import re
import glob

base_dir = "/Users/admin/Notes/docs/Design/微服务质量保障 20 讲"
assets_dir = os.path.join(base_dir, "assets")
os.chdir(base_dir)

md_files = sorted(glob.glob("*.md"))

# 1. Rename images and fix image links
img_pattern = re.compile(r'!\[([^\]]*)\]\((assets/[^)]+)\)')

asset_to_new_name = {}
md_image_count = {}

for md_file in md_files:
    with open(md_file, "r", encoding="utf-8") as f:
        content = f.read()
        
    matches = img_pattern.findall(content)
    md_base_name = md_file[:-3]
    md_image_count[md_base_name] = 0
    
    for alt, img_path in matches:
        filename = os.path.basename(img_path)
        if filename not in asset_to_new_name:
            md_image_count[md_base_name] += 1
            ext = os.path.splitext(filename)[1]
            if not ext:
                ext = '.png'
            new_filename = f"{md_base_name}-{md_image_count[md_base_name]:02d}{ext}"
            asset_to_new_name[filename] = new_filename

# apply renames
for md_file in md_files:
    with open(md_file, "r", encoding="utf-8") as f:
        lines = f.readlines()

    new_lines = []
    in_code_block = False
    code_block_lines = []
    
    # We will process line by line to handle code blocks and image layouts
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Check for code blocks
        if line.lstrip().startswith('```'):
            if not in_code_block:
                in_code_block = True
                code_block_lines = [line]
            else:
                code_block_lines.append(line)
                # Process the captured code block
                # Trim inner empty lines
                first_line = code_block_lines[0]
                last_line = code_block_lines[-1]
                inner_lines = code_block_lines[1:-1]
                
                # Trim leading empty lines
                while inner_lines and inner_lines[0].strip() == '':
                    inner_lines.pop(0)
                # Trim trailing empty lines
                while inner_lines and inner_lines[-1].strip() == '':
                    inner_lines.pop()
                
                new_lines.append(first_line)
                new_lines.extend(inner_lines)
                new_lines.append(last_line)
                
                in_code_block = False
            i += 1
            continue
            
        if in_code_block:
            code_block_lines.append(line)
            i += 1
            continue
            
        # Not in code block
        
        # Check for images
        # We need to enforce: blank line before and after image.
        # Indent 4 spaces if in list.
        # Let's detect if there's an image in the line
        m = re.search(r'^(\s*)!\[([^\]]*)\]\((assets/[^)]+)\)', line)
        if m:
            indent = m.group(1)
            alt = m.group(2)
            img_path = m.group(3)
            
            filename = os.path.basename(img_path)
            new_filename = asset_to_new_name.get(filename, filename)
            
            if alt.lower() in ["", "img", "image", "file", "drawing", "image.png"] or alt.startswith("Drawing"):
                alt = os.path.splitext(new_filename)[0]
                
            new_img_str = f"![{alt}](assets/{new_filename})"
            
            # Determine if we should indent (if we are in a list)
            # A simple heuristic: if previous non-empty line was a list item or indented, we should indent by 4 spaces.
            # But maybe the current indent is already there. Let's use max(4 (if in list), len(current indent))
            
            # Look backwards in new_lines to see if we are in a list
            in_list = False
            for prev_line in reversed(new_lines):
                if prev_line.strip() == '':
                    continue
                if re.match(r'^(\s*)([-*+]|\d+\.)\s+', prev_line):
                    in_list = True
                break
                
            final_indent = indent
            if in_list and len(indent) < 4:
                final_indent = "    "
            
            # Ensure blank line before
            if len(new_lines) > 0 and new_lines[-1].strip() != '':
                new_lines.append(final_indent + '\n')
            elif len(new_lines) > 0 and new_lines[-1] != final_indent + '\n':
                # Replace the empty line with properly indented empty line
                new_lines[-1] = final_indent + '\n'
                
            new_lines.append(final_indent + new_img_str + '\n')
            
            # We also need a blank line after, but we can't look ahead easily without just setting a flag or inserting it.
            # We'll insert it, and if the next line is also empty, we might have duplicates, which we can clean up later.
            new_lines.append(final_indent + '\n')
            
            # Skip any immediately following empty lines in the original text to avoid extra spaces
            j = i + 1
            while j < len(lines) and lines[j].strip() == '':
                j += 1
            i = j
            continue
            
        new_lines.append(line)
        i += 1

    # Final cleanup of multiple consecutive empty lines
    cleaned_lines = []
    for line in new_lines:
        if line.strip() == '' and len(cleaned_lines) > 0 and cleaned_lines[-1].strip() == '':
            continue
        cleaned_lines.append(line)

    with open(md_file, "w", encoding="utf-8") as f:
        f.writelines(cleaned_lines)

# Rename files in assets dir
if os.path.exists(assets_dir):
    for old_name, new_name in asset_to_new_name.items():
        old_path = os.path.join(assets_dir, old_name)
        new_path = os.path.join(assets_dir, new_name)
        if os.path.exists(old_path) and old_path != new_path:
            os.rename(old_path, new_path)

    # Delete unused images
    all_assets_after = set(os.listdir(assets_dir))
    used_new_names = set(asset_to_new_name.values())

    for asset in all_assets_after:
        if asset not in used_new_names:
            asset_path = os.path.join(assets_dir, asset)
            if os.path.isfile(asset_path):
                os.remove(asset_path)
