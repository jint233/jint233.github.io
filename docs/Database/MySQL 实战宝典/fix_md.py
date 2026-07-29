import os
import re

base_dir = "/Users/admin/Notes/docs/Database/MySQL 实战宝典"
assets_dir = os.path.join(base_dir, "assets")

def fix_email(content):
    content = re.sub(r'\[email&#160;protected\]', '@', content)
    content = re.sub(r'\[email\s*protected\]', '@', content)
    return content

def process_file(md_file):
    md_name = md_file[:-3]
    md_path = os.path.join(base_dir, md_file)
    with open(md_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    new_lines = []
    img_idx = 1
    used_assets = set()
    
    for i, line in enumerate(lines):
        # Fix emails
        line = fix_email(line)
        
        # Find images
        # We might have inline images or block images. Usually it's block.
        # Handle ![(alt)](assets/hash.ext)
        matches = re.finditer(r'!\[(.*?)\]\((assets/[^)]+)\)', line)
        
        new_line = line
        for match in matches:
            alt_text, img_path = match.group(1), match.group(2)
            
            # Check if generic alt
            if alt_text.lower() in ["img", "file", "image", "image.png", "image.jpg"]:
                alt_text = f"{md_name} 图{img_idx}"
            
            filename = os.path.basename(img_path)
            ext = os.path.splitext(filename)[1]
            
            # rename to MarkdownName-Index.ext
            new_filename = f"{md_name}-{img_idx:02d}{ext}"
            new_img_path = f"assets/{new_filename}"
            
            # rename file in fs if exists
            old_fs_path = os.path.join(base_dir, img_path)
            new_fs_path = os.path.join(base_dir, new_img_path)
            if os.path.exists(old_fs_path) and old_fs_path != new_fs_path:
                os.rename(old_fs_path, new_fs_path)
            elif os.path.exists(new_fs_path):
                # maybe already renamed
                pass
            
            used_assets.add(new_filename)
            
            # replace in line
            new_line = new_line.replace(match.group(0), f"![{alt_text}]({new_img_path})")
            img_idx += 1
            
        # Image rendering layout: ensure blank lines before and after.
        # If the line contains an image and nothing else (except whitespace/list markers), we can try to enforce spacing.
        # But maybe we just rely on markdownlint to tell us what to fix, or do it automatically.
        new_lines.append(new_line)
        
    with open(md_path, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
        
    return used_assets

all_used = set()
for f in sorted(os.listdir(base_dir)):
    if f.endswith('.md'):
        used = process_file(f)
        all_used.update(used)

# Remove unused assets
for f in os.listdir(assets_dir):
    if f not in all_used:
        os.remove(os.path.join(assets_dir, f))
        print(f"Removed unused asset: {f}")

print("Processing complete.")
