import os
import glob

base_dir = "/Users/admin/Notes/docs/Design/分布式链路追踪实战"
md_files = glob.glob(os.path.join(base_dir, "**/*.md"), recursive=True)

for md_file in md_files:
    with open(md_file, 'r', encoding='utf-8') as f:
        lines = f.read().split('\n')
        
    clean_lines = []
    for line in lines:
        if clean_lines and not clean_lines[-1].strip() and not line.strip():
            continue
        clean_lines.append(line)
        
    with open(md_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(clean_lines))
