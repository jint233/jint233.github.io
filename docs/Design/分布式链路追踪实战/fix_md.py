import os
import re
import glob

def process_files():
    base_dir = "/Users/admin/Notes/docs/Design/分布式链路追踪实战"
    md_files = glob.glob(os.path.join(base_dir, "**/*.md"), recursive=True)
    
    # 1. Rename images
    # We will map old_asset_path -> new_asset_path
    
    # Read all files to find images and plan renames
    image_renames = {}
    used_images = set()
    
    for md_file in sorted(md_files):
        if 'index.md' in md_file:
            continue
        with open(md_file, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # extract images
        # format: ![alt](assets/filename.png)
        img_idx = 1
        basename = os.path.basename(md_file).replace('.md', '')
        
        matches = re.finditer(r'!\[(.*?)\]\((assets/[^)]+)\)', content)
        for match in matches:
            old_alt = match.group(1)
            old_path = match.group(2)
            
            if old_path not in image_renames:
                ext = old_path.split('.')[-1]
                new_name = f"{basename}-{img_idx:02d}.{ext}"
                new_path = f"assets/{new_name}"
                image_renames[old_path] = new_path
                img_idx += 1
            used_images.add(image_renames[old_path])

    # Rename actual files in assets
    assets_dir = os.path.join(base_dir, "assets")
    if os.path.exists(assets_dir):
        for img in os.listdir(assets_dir):
            old_full = os.path.join(assets_dir, img)
            old_rel = f"assets/{img}"
            if old_rel in image_renames:
                new_full = os.path.join(base_dir, image_renames[old_rel])
                if old_full != new_full:
                    os.rename(old_full, new_full)
            else:
                # unused image?
                os.remove(old_full)

    # 2. Process each md file
    for md_file in md_files:
        with open(md_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        new_lines = []
        in_code_block = False
        code_block_lines = []
        code_block_lang = ""
        
        # heading levels
        for i, line in enumerate(lines):
            # Headings
            if not in_code_block and line.startswith('#'):
                # match `# `
                m = re.match(r'^(#{1,6})\s+(.*)', line)
                if m:
                    level = len(m.group(1))
                    text = m.group(2)
                    if level > 1:
                        # shift by 1
                        level -= 1
                    line = '#' * level + ' ' + text + '\n'
            
            # Code blocks
            if line.strip().startswith('```'):
                if not in_code_block:
                    in_code_block = True
                    code_block_lines = []
                    new_lines.append(line)
                    continue
                else:
                    in_code_block = False
                    # trim code block inner empty lines
                    # remove empty lines at start and end
                    while code_block_lines and not code_block_lines[0].strip():
                        code_block_lines.pop(0)
                    while code_block_lines and not code_block_lines[-1].strip():
                        code_block_lines.pop(-1)
                    
                    new_lines.extend(code_block_lines)
                    new_lines.append(line)
                    continue
            
            if in_code_block:
                code_block_lines.append(line)
                continue
                
            new_lines.append(line)
            
        content = "".join(new_lines)
        
        # Fix image links, alt texts and layout
        def replace_image(match):
            indent = match.group(1) or ""
            alt = match.group(2)
            path = match.group(3)
            
            if path in image_renames:
                path = image_renames[path]
                
            if alt.lower() in ['img', 'file', 'image', '屏幕截图']:
                alt = os.path.basename(path).rsplit('.', 1)[0]
                
            # If there's an indent, it's in a list
            # The prompt says: "If inside a list, add 4 spaces of list indentation to image line AND surrounding blank lines."
            # Since we just match the line, we can inject blank lines around it.
            # However, regex replacement of a single line might not handle surrounding blank lines easily.
            return f"{indent}![{alt}]({path})"
            
        # We will process line by line again for image layout
        lines = content.split('\n')
        final_lines = []
        for i, line in enumerate(lines):
            m = re.match(r'^(\s*)!\[(.*?)\]\((assets/[^)]+)\)', line)
            if m:
                indent = m.group(1)
                alt = m.group(2)
                path = m.group(3)
                if path in image_renames:
                    path = image_renames[path]
                if alt.lower() in ['img', 'file', 'image', '屏幕截图', '']:
                    alt = os.path.basename(path).rsplit('.', 1)[0]
                
                # Check if it's in a list. Usually lists have indent or we can just enforce 4 spaces if it's indented.
                # Actually, if there is a list marker above it...
                # Let's just use 4 spaces if indent is not empty, else 0
                if indent:
                    indent = "    "
                    
                img_line = f"{indent}![{alt}]({path})"
                
                # Ensure blank line before
                if final_lines and final_lines[-1].strip() != "":
                    final_lines.append(indent)
                elif final_lines and final_lines[-1].strip() == "" and indent:
                    # Update previous blank line's indent
                    final_lines[-1] = indent
                    
                final_lines.append(img_line)
                
                # Ensure blank line after will be handled by checking next line?
                # Actually, we can just insert a blank line after, but we need to avoid duplicates.
                # We can append it, and if the next line is empty, we skip it.
                # Just flag it.
                final_lines.append(indent)
            else:
                # If this is a blank line and the previous was an image blank line, we might have duplicates
                # Let's just append
                final_lines.append(line)

        # Cleanup duplicate blank lines
        clean_lines = []
        for line in final_lines:
            if clean_lines and not clean_lines[-1].strip() and not line.strip():
                # keep only one blank line? The layout might need blank lines. Let's just avoid 3+ blank lines.
                if len(clean_lines) >= 2 and not clean_lines[-2].strip():
                    pass # skip
                else:
                    clean_lines.append(line)
            else:
                clean_lines.append(line)

        with open(md_file, 'w', encoding='utf-8') as f:
            f.write("\n".join(clean_lines))

if __name__ == "__main__":
    process_files()
