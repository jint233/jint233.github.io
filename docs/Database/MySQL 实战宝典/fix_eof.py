import os

base_dir = "/Users/admin/Notes/docs/Database/MySQL 实战宝典"

def process_file(md_file):
    md_path = os.path.join(base_dir, md_file)
    with open(md_path, 'r', encoding='utf-8') as f:
        content = f.read()
        
    # strip trailing whitespace/newlines entirely, then add exactly one \n
    content = content.rstrip() + '\n'
    
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(content)

for f in os.listdir(base_dir):
    if f.endswith('.md'):
        process_file(f)
