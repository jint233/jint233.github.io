import os
import glob
import re

base_dir = "/Users/admin/Notes/docs/Java/Java 基础 36 讲"
md_files = glob.glob(os.path.join(base_dir, "*.md"))

for md_file in md_files:
    with open(md_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Replace any text followed directly by an image with text \n\n image
    # We will do this carefully. 
    # If there's text before ![, add \n\n
    new_content = re.sub(r'([^\n])(\!\[.*?\]\(.*?\))', r'\1\n\n\2', content)
    # If there's multiple images on same line, split them
    new_content = re.sub(r'(\!\[.*?\]\(.*?\))([ \t]*)(\!\[.*?\]\(.*?\))', r'\1\n\n\3', new_content)
    # If there's text after image on same line, split
    new_content = re.sub(r'(\!\[.*?\]\(.*?\))([^\n])', r'\1\n\n\2', new_content)
    
    if new_content != content:
        with open(md_file, 'w', encoding='utf-8') as f:
            f.write(new_content)
