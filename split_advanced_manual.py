#!/usr/bin/env python3
"""Split advanced-manual_extracted.md into smaller, manageable files.

This script splits the large markdown file into smaller files based on
detailed entries (A-01, B-02, etc.), making it easier for AI and Agents 
to read and process. Each file contains one detailed entry with its full content.
"""
import re
from pathlib import Path
from typing import List, Tuple, Dict, Optional


def split_manual(input_path: Path, output_dir: Path, max_lines: int = 500):
    """Split the manual into smaller files based on detailed entries."""
    print(f"Reading {input_path}...")
    content = input_path.read_text(encoding='utf-8')
    lines = content.split('\n')
    total_lines = len(lines)
    
    # Find all detailed entries (A-01, B-02, etc.)
    entries = []  # (line_num, part, sub, detail_id, title)
    
    current_part = None
    current_sub = None
    
    for i, line in enumerate(lines):
        # Track main sections for context
        main_match = re.match(r'^##\s+([IVX]+)\.\s+(.+)$', line)
        if main_match:
            current_part = main_match.group(1)
            continue
        
        # Track subsections for context
        sub_match = re.match(r'^###\s+([A-Z])\.\s+(.+)$', line)
        if sub_match:
            current_sub = sub_match.group(1)
            continue
        
        # Find detailed entries - these are what we'll split on
        # Handle both "A-01" and "A-0 2" formats
        detail_match = re.match(r'^####\s+([A-Z])-\s*(\d+)\s+(.+)$', line)
        if detail_match:
            # Normalize: "A-0 2" -> "A-02"
            letter = detail_match.group(1)
            number = detail_match.group(2).zfill(2)  # Ensure 2 digits
            detail_id = f"{letter}-{number}"
            entries.append((i, current_part, current_sub, detail_id, detail_match.group(3).strip()))
    
    print(f"Found {len(entries)} detailed entries")
    
    if not entries:
        print("No detailed entries found. Splitting by subsections instead...")
        # Fallback: split by subsections
        subsections = []
        for i, line in enumerate(lines):
            sub_match = re.match(r'^###\s+([A-Z])\.\s+(.+)$', line)
            if sub_match:
                main_match = None
                # Find the main section this belongs to
                for j in range(i, -1, -1):
                    main_match = re.match(r'^##\s+([IVX]+)\.\s+(.+)$', lines[j])
                    if main_match:
                        break
                current_part = main_match.group(1) if main_match else None
                subsections.append((i, current_part, sub_match.group(1), sub_match.group(2).strip()))
        
        entries = [(line, part, sub, None, title) for line, part, sub, title in subsections]
    
    # Group entries into files
    files = []
    
    for idx, (start_line, part, sub, detail_id, title) in enumerate(entries):
        # Determine end line (next entry or end of file)
        if idx + 1 < len(entries):
            end_line = entries[idx + 1][0] - 1
        else:
            end_line = total_lines - 1
        
        # Check if this entry is too large
        entry_size = end_line - start_line + 1
        
        if entry_size > max_lines:
            # Split large entries into chunks
            chunk_size = max_lines
            chunk_num = 1
            chunk_start = start_line
            
            while chunk_start <= end_line:
                chunk_end = min(chunk_start + chunk_size - 1, end_line)
                
                files.append({
                    'start': chunk_start,
                    'end': chunk_end,
                    'part': part,
                    'sub': sub,
                    'detail': detail_id,
                    'title': title,
                    'chunk': chunk_num if chunk_end < end_line else None
                })
                
                chunk_start = chunk_end + 1
                chunk_num += 1
        else:
            files.append({
                'start': start_line,
                'end': end_line,
                'part': part,
                'sub': sub,
                'detail': detail_id,
                'title': title,
                'chunk': None
            })
    
    # Generate filenames and titles
    for file_info in files:
        # Build filename
        parts = []
        if file_info['part']:
            parts.append(f"part_{file_info['part']}")
        if file_info['sub']:
            parts.append(file_info['sub'])
        if file_info['detail']:
            parts.append(file_info['detail'])
        else:
            # Use subsection as identifier
            if file_info['sub']:
                parts.append(f"{file_info['sub']}_section")
        if file_info['chunk']:
            parts.append(f"chunk{file_info['chunk']}")
        
        file_info['filename'] = '_'.join(parts) + '.md'
        
        # Build title
        title_parts = []
        if file_info['part']:
            title_parts.append(f"{file_info['part']}.")
        if file_info['sub']:
            title_parts.append(f"{file_info['sub']}.")
        if file_info['detail']:
            title_parts.append(f"{file_info['detail']}")
        if file_info['title']:
            title_parts.append(file_info['title'])
        if file_info['chunk']:
            title_parts.append(f"(Part {file_info['chunk']})")
        
        file_info['full_title'] = ' '.join(title_parts)
    
    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Write files
    index_lines = [
        "# Advanced Players' Rulebook - Index\n",
        "This manual has been split into multiple files for easier reading by AI and Agents.\n",
        f"Each file contains one detailed entry (A-01, B-02, etc.) and is typically 50-{max_lines} lines.\n",
        "\n## Files\n\n"
    ]
    
    file_list = []
    current_part = None
    
    for file_info in files:
        # Get content
        file_lines = lines[file_info['start']:file_info['end'] + 1]
        file_content = '\n'.join(file_lines)
        
        # Determine part name for header
        part_name = None
        if file_info['part'] == 'I':
            part_name = "I. Supplement to the Players' Guide"
        elif file_info['part'] == 'II':
            part_name = "II. Card Text"
        
        # Create header
        header = f"# {file_info['full_title']}\n\n"
        if part_name:
            header += f"*Part of: {part_name}*\n\n"
        header += "---\n\n"
        
        full_content = header + file_content
        
        # Write file
        filepath = output_dir / file_info['filename']
        filepath.write_text(full_content, encoding='utf-8')
        
        # Stats
        file_size = len(full_content)
        line_count = len(file_lines)
        
        file_list.append({
            'filename': file_info['filename'],
            'title': file_info['full_title'],
            'size': file_size,
            'lines': line_count,
            'part': part_name
        })
        
        print(f"  Created: {file_info['filename']} ({line_count} lines, {file_size:,} bytes)")
    
    # Build index
    file_list.sort(key=lambda x: (x['part'] or '', x['filename']))
    
    for info in file_list:
        if info['part'] != current_part:
            if current_part is not None:
                index_lines.append("")
            current_part = info['part']
            if current_part:
                index_lines.append(f"### {current_part}\n")
        
        size_kb = info['size'] / 1024
        index_lines.append(
            f"- [{info['title']}]({info['filename']}) "
            f"({info['lines']} lines, {size_kb:.1f} KB)"
        )
    
    # Write index
    index_path = output_dir / "00_index.md"
    index_path.write_text('\n'.join(index_lines), encoding='utf-8')
    print(f"\nCreated index: {index_path.name}")
    
    # Summary
    total_size = sum(info['size'] for info in file_list)
    total_lines = sum(info['lines'] for info in file_list)
    avg_size = total_size / len(file_list) if file_list else 0
    avg_lines = total_lines / len(file_list) if file_list else 0
    
    print(f"\nSummary:")
    print(f"  Total files: {len(file_list)}")
    print(f"  Total size: {total_size:,} bytes ({total_size/1024:.1f} KB)")
    print(f"  Total lines: {total_lines:,}")
    print(f"  Average: {avg_size:,.0f} bytes ({avg_lines:.0f} lines)")
    if file_list:
        print(f"  Min lines: {min(info['lines'] for info in file_list)}")
        print(f"  Max lines: {max(info['lines'] for info in file_list)}")


def main():
    """Main function."""
    project_root = Path(__file__).parent
    input_path = project_root / "doc" / "advanced-manual_extracted.md"
    output_dir = project_root / "doc" / "advanced-manual-split"
    
    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}")
        return 1
    
    # Clean output directory
    if output_dir.exists():
        import shutil
        shutil.rmtree(output_dir)
    
    try:
        split_manual(input_path, output_dir, max_lines=500)
        print(f"\n✓ Success! Files saved to: {output_dir}")
        return 0
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
