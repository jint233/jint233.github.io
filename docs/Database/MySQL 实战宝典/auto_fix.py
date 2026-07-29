import os
import re

base_dir = "/Users/admin/Notes/docs/Database/MySQL 实战宝典"

def process_file(md_file):
    md_path = os.path.join(base_dir, md_file)
    with open(md_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    # Trim excess blank lines
    new_lines = []
    blank_count = 0
    for line in lines:
        if line.strip() == '':
            blank_count += 1
            if blank_count <= 1:
                new_lines.append('\n')
        else:
            blank_count = 0
            # Trim trailing spaces
            new_lines.append(line.rstrip() + '\n')
            
    # Fix code blocks (ensure language, trim blank lines inside code block)
    in_code_block = False
    cleaned_lines = []
    code_content = []
    lang = ''
    for line in new_lines:
        if line.strip().startswith('```'):
            if not in_code_block:
                in_code_block = True
                lang = line.strip()[3:].strip()
                if not lang:
                    lang = 'sql' # assume sql for DB book if not specified
                # Ensure blank line before
                if cleaned_lines and cleaned_lines[-1].strip() != '':
                    cleaned_lines.append('\n')
                cleaned_lines.append(f'```{lang}\n')
            else:
                in_code_block = False
                # Trim leading/trailing blank lines in code block
                start = 0
                while start < len(code_content) and code_content[start].strip() == '':
                    start += 1
                end = len(code_content)
                while end > start and code_content[end-1].strip() == '':
                    end -= 1
                cleaned_lines.extend(code_content[start:end])
                cleaned_lines.append('```\n')
                code_content = []
                # ensure blank line after
                cleaned_lines.append('\n')
        else:
            if in_code_block:
                code_content.append(line)
            else:
                cleaned_lines.append(line)
                
    if in_code_block:
        # unclosed block, just dump
        cleaned_lines.extend(code_content)

    # Fix images (blank line before and after, indent in lists)
    final_lines = []
    for i, line in enumerate(cleaned_lines):
        if '![' in line and '](' in line:
            # simple check if line is purely an image
            stripped = line.strip()
            if stripped.startswith('![') and stripped.endswith(')'):
                is_list = False
                indent = ''
                # check previous lines to see if we're in a list
                if i > 0:
                    prev = cleaned_lines[i-1].rstrip()
                    if prev.lstrip().startswith('- ') or prev.lstrip().startswith('* ') or re.match(r'^\s*\d+\.\s', prev):
                        is_list = True
                        # match indent
                        match = re.match(r'^(\s*)', prev)
                        if match:
                            indent = match.group(1) + '    '
                
                # ensure blank line before
                if final_lines and final_lines[-1].strip() != '':
                    final_lines.append('\n')
                
                if is_list:
                    final_lines.append(indent + stripped + '\n')
                else:
                    final_lines.append(stripped + '\n')
                
                # ensure blank line after (we can just add it, and if next line is blank, duplicate blank removal will handle it)
                final_lines.append('\n')
                continue
                
        # skip duplicate blanks
        if line.strip() == '' and final_lines and final_lines[-1].strip() == '':
            continue
            
        final_lines.append(line)
        
    # ensure single newline at EOF
    while final_lines and final_lines[-1].strip() == '':
        final_lines.pop()
    final_lines.append('\n')

    with open(md_path, 'w', encoding='utf-8') as f:
        f.writelines(final_lines)

for f in os.listdir(base_dir):
    if f.endswith('.md'):
        process_file(f)
