import os
import re

base_dir = "/Users/admin/Notes/docs/Database/MySQL 实战宝典"

def process_file(md_file):
    md_path = os.path.join(base_dir, md_file)
    with open(md_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    new_lines = []
    
    # MD012: remove multiple consecutive blank lines
    # MD001: headings increment by 1
    
    prev_heading = 1 # We assume document starts with # (h1)
    
    blank_count = 0
    for line in lines:
        # MD012
        if line.strip() == '':
            blank_count += 1
            if blank_count > 1:
                continue
        else:
            blank_count = 0
            
        # MD001
        m = re.match(r'^(#+)\s', line)
        if m:
            level = len(m.group(1))
            if level > prev_heading + 1:
                level = prev_heading + 1
                line = '#' * level + ' ' + line.lstrip('#').lstrip()
            prev_heading = level
            
        new_lines.append(line)
        
    with open(md_path, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)

for f in os.listdir(base_dir):
    if f.endswith('.md'):
        process_file(f)
