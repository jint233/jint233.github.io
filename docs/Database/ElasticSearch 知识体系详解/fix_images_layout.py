import os
import re

directory = '/Users/admin/Notes/docs/Database/ElasticSearch 知识体系详解'

for filename in os.listdir(directory):
    if not filename.endswith('.md'):
        continue
    filepath = os.path.join(directory, filename)
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # fix email protection: [email protected] -> @
    # and <a href="/cdn-cgi/l/email-protection"...>[email protected]</a>
    content = re.sub(r'\[email\s+protected\]', '@', content)
    content = re.sub(r'<a[^>]*data-cfemail[^>]*>.*?</a>', '@', content)
    
    # We want to ensure blank line before and after `![alt](path)`.
    # And fix indentation.
    lines = content.split('\n')
    new_lines = []
    
    for i, line in enumerate(lines):
        # find images in line
        if re.search(r'!\[.*?\]\(.*?\)', line):
            # If the line has text other than the image and list markers, we shouldn't just break it up unless it's just ` - ![alt]`
            # A simple approach is just to check if the line only contains an image (with optional leading spaces/list markers)
            m = re.match(r'^(\s*(?:-\s+|\d+\.\s+)?)!\[(.*?)\]\((.*?)\)\s*$', line)
            if m:
                # it's a line with just an image and maybe a list marker
                prefix = m.group(1)
                
                # If there's a list marker, we want the image to be part of the list item.
                # Usually:
                # - text
                # 
                #     ![alt](path)
                # We can replace `- ![alt](...)` with:
                # - 
                # 
                #     ![alt](...)
                # Wait, if it's just `- ![alt]`, maybe it's fine? Markdownlint might complain.
                pass

    # Actually, simpler: just let's check for MD files manually or with a more robust script
