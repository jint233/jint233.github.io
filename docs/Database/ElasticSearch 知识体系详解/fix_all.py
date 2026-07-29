import os
import re

directory = '/Users/admin/Notes/docs/Database/ElasticSearch 知识体系详解'

def fix_image_layout(content):
    # This is tricky because we don't want to mess up existing correct layouts.
    # We will search for all lines containing `![` and process them.
    lines = content.split('\n')
    new_lines = []
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # If line contains an image but it's not the ONLY thing on the line,
        # or it is missing blank lines around it.
        # Let's see if we can identify standalone images or images in list.
        m = re.match(r'^(\s*(?:-\s+|\d+\.\s+)?)!\[(.*?)\]\((.*?)\)\s*$', line)
        if m:
            prefix = m.group(1)
            alt = m.group(2)
            url = m.group(3)
            
            if prefix.strip():
                # It's an image in a list (e.g., `- ![alt](...)`)
                # Convert to:
                # - 
                # 
                #     ![alt](...)
                indent = len(prefix) # approximately. if `- `, it's 2. But we want 4 to be safe for child elements or matching list depth.
                # Actually, standard is 4 spaces or matching list item prefix length.
                # If prefix is `- `, len is 2. But standard Markdown says child blocks should be indented by 4 spaces or aligned with text.
                # Let's indent by 4 spaces.
                # But wait, we shouldn't replace the item text if there was text? 
                # The regex `^(\s*(?:-\s+|\d+\.\s+)?)!\[(.*?)\]\((.*?)\)\s*$` ensures there's ONLY an image after the prefix.
                
                # Check previous line to ensure no duplication
                if new_lines and new_lines[-1].strip() != '':
                    new_lines.append('')
                
                new_lines.append(prefix)
                new_lines.append('')
                new_lines.append(' ' * 4 + f'![{alt}]({url})')
                new_lines.append('')
                
            else:
                # Standalone image
                # Ensure blank line before
                if new_lines and new_lines[-1].strip() != '':
                    new_lines.append('')
                new_lines.append(f'{prefix}![{alt}]({url})')
                new_lines.append('') # Ensure blank line after, we'll strip multiple blanks later
        else:
            # Does it have image inline with text?
            # like: `- **验证结果**![第08讲 图4](assets/...)`
            m_inline = re.search(r'^(.*?)(!\[.*?\]\(.*?\))(.*)$', line)
            if m_inline and not line.strip().startswith('!['):
                # Only if there's text before the image
                before = m_inline.group(1)
                img = m_inline.group(2)
                after = m_inline.group(3)
                
                # If before contains list marker, indent the image
                # Let's just put the image on the next line with 4 spaces indent.
                new_lines.append(before)
                if not before.strip().endswith(':'): # just a heuristic
                    pass
                new_lines.append('')
                
                # Determine indent based on before
                list_match = re.match(r'^(\s*(?:-\s+|\d+\.\s+))', before)
                indent_str = '    ' if list_match else ''
                
                new_lines.append(indent_str + img)
                new_lines.append('')
                if after.strip():
                    new_lines.append(indent_str + after)
            else:
                new_lines.append(line)
        i += 1

    # Remove more than 2 consecutive empty lines
    final_lines = []
    empty_count = 0
    for line in new_lines:
        if line.strip() == '':
            empty_count += 1
            if empty_count <= 1:
                final_lines.append(line)
        else:
            empty_count = 0
            final_lines.append(line)
            
    return '\n'.join(final_lines)

for filename in os.listdir(directory):
    if not filename.endswith('.md'):
        continue
    filepath = os.path.join(directory, filename)
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Manual fixes before layout parsing
    if filename == '第01讲.md':
        content = re.sub(r'\n    - ', '\n  - ', content)
        content = re.sub(r'[ \t]+\n', '\n', content)
    
    if filename == '第07讲.md':
        content = content.replace("### 概念\n\n比如搜索逻辑是 name = 'apple'", "### 概念 (boosting query)\n\n比如搜索逻辑是 name = 'apple'")
        content = content.replace("### 例子\n\n首先创建数据", "### 例子 (constant_score)\n\n首先创建数据")
        content = content.replace("### 例子\n\n假设有个网站允许用户搜索博客的内容", "### 例子 (dis_max)\n\n假设有个网站允许用户搜索博客的内容")
        content = content.replace("### 例子\n\n以最简单的 random_score 为例", "### 例子 (function_score)\n\n以最简单的 random_score 为例")
        
    if filename == '第08讲.md':
        pass # Will be handled by layout parsing, but let's ensure:
        
    if filename == '第13讲.md':
        content = content.replace("**版本**\n", "### 版本\n")
        
    if filename == '第19讲.md':
        content = content.replace("\n# General\n", "\n## General\n")
        content = content.replace("\n# Contributing\n", "\n## Contributing\n")
        content = content.replace("\n## Other\n", "\n## Other Resources\n")

    content = fix_image_layout(content)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

print("Applied fixes")
