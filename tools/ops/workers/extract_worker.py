import sys
import re

def extract_script(file_path):
    # Attempt to read as utf-8 (ignore errors for safety)
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    # Split by the boundary found in the first line
    lines = content.splitlines()
    if not lines or not lines[0].startswith("--"):
        # Not a multipart formatted like Cloudflare's usual curl output?
        # Maybe single file? Return as is.
        return content

    boundary = lines[0].strip()
    parts = content.split(boundary)

    # Look for the part containing JS code
    # Usually: 'Content-Disposition: form-data; name="worker.js"\n\n<code>\n'
    for part in parts:
        if not part.strip() or part.strip() == "--": 
            continue
            
        # Check headers (case insensitive usually, but CF is standard)
        if 'name="worker.js"' in part or 'name="index.js"' in part or 'name="ops-worker.js"' in part or 'application/javascript' in part:
            # Find the empty line separating headers from body
            header_end = part.find('\n\n')
            if header_end != -1:
                # The content is everything after the double newline
                script_body = part[header_end+2:].strip()
                return script_body
    
    # Fallback: Return original if no clear part found
    return content

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python extract_worker.py <file>")
        sys.exit(1)
        
    fpath = sys.argv[1]
    cleaned = extract_script(fpath)
    
    # Overwrite
    with open(fpath, 'w', encoding='utf-8') as f:
        f.write(cleaned)
    print(f"Extracted: {fpath}")
