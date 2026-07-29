import os, glob, re

for md_file in glob.glob("*.md"):
    with open(md_file, "r", encoding="utf-8") as f:
        lines = f.readlines()
        
    new_lines = []
    for line in lines:
        if line.startswith('###### '):
            new_lines.append(line.replace('###### ', '##### ', 1))
        elif line.startswith('##### '):
            new_lines.append(line.replace('##### ', '#### ', 1))
        elif line.startswith('#### '):
            new_lines.append(line.replace('#### ', '### ', 1))
        elif line.startswith('### '):
            new_lines.append(line.replace('### ', '## ', 1))
        else:
            # Check for MD036: **bold** acting as a heading
            m = re.match(r'^\*\*(.*?)\*\*\s*$', line)
            if m and len(m.group(1)) > 0:
                # Is it really acting as a heading? The lint reported specific ones.
                # Let's only fix if it's the exact ones from lint
                pass
            new_lines.append(line)
            
    with open(md_file, "w", encoding="utf-8") as f:
        f.writelines(new_lines)
