import os
import re

directory = '/Users/admin/Notes/docs/Database/ElasticSearch 知识体系详解'
assets_dir = os.path.join(directory, 'assets')

used_images = set()

# Process each markdown file
for filename in os.listdir(directory):
    if not filename.endswith('.md'):
        continue
    filepath = os.path.join(directory, filename)
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # We will rename images in this file to MarkdownName-Index.ext
    base_md_name = os.path.splitext(filename)[0]
    
    # Find all images
    matches = list(re.finditer(r'!\[(.*?)\]\((assets/[^)]+)\)', content))
    
    if not matches:
        continue
        
    for i, match in enumerate(matches, start=1):
        alt_text = match.group(1)
        old_img_path = match.group(2)
        old_img_name = os.path.basename(old_img_path)
        ext = os.path.splitext(old_img_name)[1]
        
        # New image name
        new_img_name = f"{base_md_name}-{i:02d}{ext}"
        new_img_path = f"assets/{new_img_name}"
        
        # fix alt text if generic
        if alt_text.lower() in ['img', 'file', 'image', '']:
            alt_text = f"{base_md_name} 图{i}"
            
        content = content.replace(f"![{match.group(1)}]({old_img_path})", f"![{alt_text}]({new_img_path})")
        
        # Rename the file if it exists
        old_full_path = os.path.join(directory, old_img_path)
        new_full_path = os.path.join(directory, new_img_path)
        if os.path.exists(old_full_path):
            os.rename(old_full_path, new_full_path)
        
        used_images.add(new_img_name)
        
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

# Clean up unused images in assets/
for img in os.listdir(assets_dir):
    if img not in used_images:
        os.remove(os.path.join(assets_dir, img))

print("Done")
