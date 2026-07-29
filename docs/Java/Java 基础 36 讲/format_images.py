import os
import re
import glob

base_dir = "/Users/admin/Notes/docs/Java/Java 基础 36 讲"

def process_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    new_lines = []
    
    img_pattern = re.compile(r'^(\s*)!\[(.*?)\]\((.*?)\)\s*$')
    list_pattern = re.compile(r'^(\s*)([-*+]|\d+\.)\s+')
    
    in_list_indent = ""
    
    for i, line in enumerate(lines):
        # Determine if we are in a list context
        list_match = list_pattern.match(line)
        if list_match:
            # The base indent of the list item + 4 spaces
            in_list_indent = list_match.group(1) + "    "
        elif line.strip() == "":
            pass # keep list context across blank lines maybe?
        elif not img_pattern.match(line) and not line.startswith("    "):
            # If it's regular text, not indented, we drop list context
            in_list_indent = ""
            
        img_match = img_pattern.match(line)
        if img_match:
            current_indent = img_match.group(1)
            # Use the calculated list indent if we're in a list, else default to whatever it had (or 0)
            target_indent = in_list_indent if in_list_indent else ""
            
            # Ensure blank line before
            if new_lines and new_lines[-1].strip() != "":
                new_lines.append(target_indent + "\n")
            elif new_lines and new_lines[-1].strip() == "":
                # Replace the previous blank line with one that has target_indent
                if target_indent:
                    new_lines[-1] = target_indent + "\n"
                    
            # Add the image line with target_indent
            new_lines.append(target_indent + f"![{img_match.group(2)}]({img_match.group(3)})\n")
            
            # For the blank line after, we just note that we need to insert it if the NEXT line is not blank
            # But we can't easily peek ahead without a loop, so let's handle "blank line after" by
            # injecting a blank line into new_lines, and if the next line is also blank, we'll skip adding it.
            # Wait, the next iteration will handle the next line.
            # Let's add the target_indent blank line now.
            new_lines.append(target_indent + "\n")
            continue
            
        # If it's a blank line and the previous was our injected blank line, skip it
        if line.strip() == "" and new_lines and new_lines[-1].strip() == "" and "![" not in new_lines[-1]:
            # Wait, we injected a blank line with target_indent. 
            # If the current line is just empty, we can just skip it to avoid double blank lines.
            if len(new_lines) >= 2 and new_lines[-2].strip().startswith("!["):
                continue

        new_lines.append(line)
        
    # Clean up any trailing blank lines if needed
    content = "".join(new_lines)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

md_files = glob.glob(os.path.join(base_dir, "*.md"))
for md_file in md_files:
    process_file(md_file)
