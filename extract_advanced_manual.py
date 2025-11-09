#!/usr/bin/env python3
"""Extract text from PTCG Advanced Manual PDF using PyMuPDF.

This script extracts text from doc/advanced-manual_EN.pdf and saves it to
doc/advanced-manual_extracted.txt and doc/advanced-manual_extracted.md
for use with Agents and AI systems.
"""
import sys
import re
from pathlib import Path

try:
    import fitz  # PyMuPDF
except ImportError:
    print("错误：未找到 PyMuPDF 库")
    print("请先安装：pip install PyMuPDF")
    sys.exit(1)


def clean_text(text: str) -> str:
    """Clean and normalize extracted text.
    
    Args:
        text: Raw extracted text
        
    Returns:
        Cleaned text with normalized whitespace
    """
    lines = text.split('\n')
    cleaned_lines = []
    prev_empty = False
    
    for line in lines:
        line = line.strip()
        # Skip excessive empty lines
        if not line:
            if not prev_empty:
                cleaned_lines.append('')
            prev_empty = True
        else:
            cleaned_lines.append(line)
            prev_empty = False
    
    return '\n'.join(cleaned_lines)


def extract_pdf_text(pdf_path: Path) -> str:
    """Extract all text from PDF file.
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        Extracted text content
        
    Raises:
        FileNotFoundError: If PDF file doesn't exist
        Exception: If PDF extraction fails
    """
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF 文件不存在: {pdf_path}")
    
    print(f"正在提取 PDF: {pdf_path}")
    doc = fitz.open(pdf_path)
    text_content = []
    
    try:
        total_pages = len(doc)
        print(f"总页数: {total_pages}")
        
        for page_num in range(total_pages):
            page = doc[page_num]
            text = page.get_text()
            
            # Clean text: remove excessive whitespace but preserve structure
            cleaned_text = clean_text(text)
            text_content.append(cleaned_text)
            
            if (page_num + 1) % 10 == 0:
                print(f"  已处理 {page_num + 1}/{total_pages} 页...")
        
        print(f"提取完成，共 {total_pages} 页")
        
    finally:
        doc.close()
    
    return '\n\n'.join(text_content)


def convert_to_markdown(text: str) -> str:
    """Convert plain text to Markdown format for better readability.
    
    Args:
        text: Plain text content
        
    Returns:
        Markdown formatted text
    """
    lines = text.split('\n')
    markdown_lines = []
    prev_empty = False
    
    for i, line in enumerate(lines):
        stripped = line.strip()
        
        # Skip empty lines but preserve structure
        if not stripped:
            if not prev_empty:
                markdown_lines.append('')
            prev_empty = True
            continue
        
        prev_empty = False
        
        # Skip page numbers (single digit on a line by itself, often followed by title)
        if re.match(r'^\d+$', stripped) and i + 1 < len(lines):
            next_line = lines[i + 1].strip()
            # If next line is the title, skip this page number
            if 'Pokémon Card Game Advanced Players' in next_line:
                continue
        
        # Skip repeated title lines
        if stripped == "Pokémon Card Game Advanced Players' Rulebook Ver.2.2":
            continue
        
        # Pattern 1: Roman numerals with periods (I., II., etc.) - Main sections
        roman_pattern = re.compile(r'^([IVX]+)\.\s+(.+)$', re.IGNORECASE)
        roman_match = roman_pattern.match(stripped)
        if roman_match:
            markdown_lines.append('## ' + stripped)
            continue
        
        # Pattern 2: Single letter with period (A., B., C., etc.) - Subsections
        letter_pattern = re.compile(r'^([A-Z])\.\s+(.+)$')
        letter_match = letter_pattern.match(stripped)
        if letter_match:
            markdown_lines.append('### ' + stripped)
            continue
        
        # Pattern 3: Letter-number codes (A-01, B-02, etc.) - Sub-subsections
        # Handle both with and without space after dash
        code_pattern = re.compile(r'^([A-Z])-(\d+)\s*(.+)$')
        code_match = code_pattern.match(stripped)
        if code_match:
            # Normalize spacing
            normalized = f"{code_match.group(1)}-{code_match.group(2)} {code_match.group(3).strip()}"
            markdown_lines.append('#### ' + normalized)
            continue
        
        # Pattern 4: Numbered sections (1., 2., 1.1, etc.) but not step numbers
        # Only treat as heading if it's a major section, not a step
        numbered_pattern = re.compile(r'^(\d+(?:\.\d+)*)\.\s+(.+)$')
        numbered_match = numbered_pattern.match(stripped)
        if numbered_match:
            heading_text = numbered_match.group(2).strip()
            # Check if it's a step within a procedure (usually follows "Steps for..." or similar)
            is_procedure_step = False
            if i > 0:
                # Look back a few lines for procedure indicators
                for j in range(max(0, i-5), i):
                    prev_line = lines[j].strip().lower()
                    if any(keyword in prev_line for keyword in ['steps for', 'follow the steps', 'steps below']):
                        is_procedure_step = True
                        break
            
            # If it's a step (ends with colon, is short, or is in a procedure), don't make it a heading
            if not is_procedure_step and not (heading_text.endswith(':') and len(heading_text) < 60):
                level = len(numbered_match.group(1).split('.'))
                markdown_lines.append('#' * min(level + 1, 6) + ' ' + heading_text)
                continue
        
        # Pattern 5: Lines ending with colons that are short (likely headings)
        # But exclude step numbers (1., 2., etc.) and numbered steps
        if stripped.endswith(':') and len(stripped) < 100:
            # Check if it's not part of a sentence and not a step
            # Exclude numbered steps (1., 2., etc.) and steps within procedures
            is_numbered_step = re.match(r'^\d+\.', stripped)
            # Check if previous line suggests this is part of a procedure
            is_procedure_step = False
            if i > 0:
                prev_line = lines[i-1].strip().lower()
                if any(keyword in prev_line for keyword in ['steps', 'follow', 'procedure', 'below']):
                    is_procedure_step = True
            
            if not stripped[0].islower() and not is_numbered_step and not is_procedure_step:
                # Check if previous line is empty or a heading
                if i == 0 or not lines[i-1].strip() or lines[i-1].strip().startswith('#'):
                    markdown_lines.append('### ' + stripped)
                    continue
        
        # Pattern 6: All caps short lines (likely headings) - but exclude very short ones
        if stripped.isupper() and 15 < len(stripped) < 100:
            # Check if next line is not empty (might be a heading)
            if i + 1 < len(lines) and lines[i+1].strip():
                markdown_lines.append('## ' + stripped)
                continue
        
        # Regular paragraph
        markdown_lines.append(stripped)
    
    return '\n'.join(markdown_lines)


def main():
    """Main extraction function."""
    # Set paths
    project_root = Path(__file__).parent
    pdf_path = project_root / "doc" / "advanced-manual_EN.pdf"
    output_txt_path = project_root / "doc" / "advanced-manual_extracted.txt"
    output_md_path = project_root / "doc" / "advanced-manual_extracted.md"
    
    # Check if PDF exists
    if not pdf_path.exists():
        print(f"错误：找不到 PDF 文件: {pdf_path}")
        print(f"请确保文件存在于: {pdf_path.absolute()}")
        sys.exit(1)
    
    try:
        # Extract text
        text = extract_pdf_text(pdf_path)
        
        # Save plain text version
        output_txt_path.parent.mkdir(parents=True, exist_ok=True)
        output_txt_path.write_text(text, encoding="utf-8")
        print(f"\n✓ 已保存纯文本版本: {output_txt_path}")
        
        # Convert to Markdown and save
        markdown_text = convert_to_markdown(text)
        output_md_path.write_text(markdown_text, encoding="utf-8")
        print(f"✓ 已保存 Markdown 版本: {output_md_path}")
        
        # Statistics
        lines = text.split('\n')
        non_empty_lines = [line for line in lines if line.strip()]
        
        print(f"\n提取成功！")
        print(f"总行数: {len(lines)}")
        print(f"非空行数: {len(non_empty_lines)}")
        print(f"文件大小: {len(text)} 字符")
        
        # Check for structured content patterns
        import re
        
        # Check for numbered sections
        numbered_pattern = re.compile(r'^(\d+(?:\.\d+)*)\s+', re.MULTILINE)
        numbered_matches = list(numbered_pattern.finditer(text))
        print(f"检测到编号章节: {len(numbered_matches)} 条")
        
        # Check for potential headings (all caps short lines)
        heading_pattern = re.compile(r'^[A-Z][A-Z\s]{2,50}$', re.MULTILINE)
        heading_matches = list(heading_pattern.finditer(text))
        print(f"检测到可能的标题: {len(heading_matches)} 条")
        
        if numbered_matches:
            print("\n示例章节（前5条）:")
            for i, match in enumerate(numbered_matches[:5]):
                section = match.group(1)
                context = text[match.end():match.end()+60].strip()
                print(f"  {section}: {context[:60]}...")
        
    except Exception as e:
        print(f"错误：提取失败 - {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

