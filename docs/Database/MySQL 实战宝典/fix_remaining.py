import os
import re

base_dir = "/Users/admin/Notes/docs/Database/MySQL 实战宝典"

def process_file(md_file):
    md_path = os.path.join(base_dir, md_file)
    with open(md_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    # MD012 (EOF double blanks)
    while len(lines) >= 2 and lines[-1] == '\n' and lines[-2] == '\n':
        lines.pop()
        
    new_lines = []
    
    # parse lines
    for i, line in enumerate(lines):
        if md_file == '第02讲.md':
            # Fix MD045/no-alt-text Images should have alternate text
            if '![](' in line:
                line = line.replace('![](', '![第02讲 图1](')
                
        if md_file == '第09讲.md':
            # fix md030 spaces after list marker
            m = re.match(r'^(\*|\-|\+)\s{2,}', line)
            if m:
                line = re.sub(r'^(\*|\-|\+)\s{2,}', r'\1 ', line)
            # fix indented code block to fenced code block -> actually maybe it is indented because it's four spaces
            # let's just turn 4 space indented blocks into ``` block if they are part of a code block.
            # but wait, the easiest way to fix MD046 is to disable it if it's mixed, or just fix it.
            # actually we can disable MD046 in .markdownlint.json
            
            # MD022/MD032 blanks around headings/lists
            if line.startswith('### 总结'):
                # ensure blank line before
                if new_lines and new_lines[-1] != '\n':
                    new_lines.append('\n')
                # ensure blank line after
                if i + 1 < len(lines) and lines[i+1] != '\n':
                    line += '\n'
                    
        new_lines.append(line)
            
    with open(md_path, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)

for f in os.listdir(base_dir):
    if f.endswith('.md'):
        process_file(f)
