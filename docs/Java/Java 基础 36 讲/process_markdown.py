import os
import re
import glob

base_dir = "/Users/admin/Notes/docs/Java/Java 基础 36 讲"
assets_dir = os.path.join(base_dir, "assets")

def process_file(filepath):
    filename = os.path.basename(filepath)
    md_name = os.path.splitext(filename)[0]
    
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    new_lines = []
    img_counter = 1
    
    in_code_block = False
    code_block_lines = []
    
    for i, line in enumerate(lines):
        # Handle code blocks
        if line.strip().startswith('```'):
            if not in_code_block:
                in_code_block = True
                code_block_lines.append(line)
            else:
                in_code_block = False
                # Trim inner empty lines in code_block_lines
                # keep first line (```lang) and last line (```)
                # remove leading/trailing empty lines inside the block
                first = code_block_lines[0]
                last = line
                inner = code_block_lines[1:]
                
                # remove leading empty
                while inner and inner[0].strip() == '':
                    inner.pop(0)
                # remove trailing empty
                while inner and inner[-1].strip() == '':
                    inner.pop()
                    
                new_lines.append(first)
                new_lines.extend(inner)
                new_lines.append(last)
                code_block_lines = []
            continue
            
        if in_code_block:
            code_block_lines.append(line)
            continue
            
        # Emails restoration
        line = re.sub(r'\[email protected\]', 'someone@example.com', line) # Might need custom logic if exact email isn't known, usually it's just stripping the protection, but without original we can just leave it or try to decode if it's cfemail. Let's just fix generic @ if needed.
        line = line.replace('&#64;', '@')
        
        # We will do image layout and renaming in a second pass or handle it here
        new_lines.append(line)
        
    content = "".join(new_lines)
    
    # Extract and replace images
    def image_replacer(match):
        nonlocal img_counter
        alt_text = match.group(1)
        img_path = match.group(2)
        
        # Only process images in assets/
        if 'assets/' in img_path:
            img_filename = os.path.basename(img_path)
            ext = os.path.splitext(img_filename)[1]
            new_img_name = f"{md_name}-{img_counter:02d}{ext}"
            new_img_path = f"assets/{new_img_name}"
            
            # Rename the file if it exists
            old_full_path = os.path.join(base_dir, img_path)
            new_full_path = os.path.join(assets_dir, new_img_name)
            if os.path.exists(old_full_path) and old_full_path != new_full_path:
                os.rename(old_full_path, new_full_path)
            
            img_counter += 1
            return f"![{new_img_name.replace(ext, '')}]({new_img_path})"
        return match.group(0)

    # find all images
    # Regex for ![alt](path)
    content = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', image_replacer, content)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

md_files = glob.glob(os.path.join(base_dir, "*.md"))
for md_file in md_files:
    process_file(md_file)

