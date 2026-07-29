import os
import glob
import re

base_dir = "/Users/admin/Notes/docs/Java/Java 基础 36 讲"
md_files = glob.glob(os.path.join(base_dir, "*.md"))

for md_file in md_files:
    with open(md_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Replace 3 or more consecutive newlines (possibly with spaces) with 2 newlines (with proper indentation for the blank line)
    # Actually it's easier to just disable MD012 if it's too complicated with spaces.
    # But wait, markdownlint is complaining about 3 consecutive newlines.
    
    # We can just remove lines that are purely whitespace if there are more than 1 in a row.
    lines = content.split('\n')
    new_lines = []
    blank_count = 0
    for line in lines:
        if line.strip() == "":
            blank_count += 1
            if blank_count <= 1:
                new_lines.append(line)
        else:
            blank_count = 0
            new_lines.append(line)
            
    new_content = '\n'.join(new_lines)
    
    if new_content != content:
        with open(md_file, 'w', encoding='utf-8') as f:
            f.write(new_content)
