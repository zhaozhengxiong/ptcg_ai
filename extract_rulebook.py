#!/usr/bin/env python3
"""Extract text from PTCG rulebook PDF using PyMuPDF.

This script extracts text from doc/par_rulebook_en.pdf and saves it to
doc/rulebook_extracted.txt for use with RuleKnowledgeBase.
"""
import sys
from pathlib import Path

try:
    import fitz  # PyMuPDF
except ImportError:
    print("错误：未找到 PyMuPDF 库")
    print("请先安装：pip install PyMuPDF")
    sys.exit(1)


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
            
            # 清理文本：移除多余的空白行，但保留基本结构
            lines = text.split('\n')
            cleaned_lines = []
            prev_empty = False
            
            for line in lines:
                line = line.strip()
                # 跳过连续的空行
                if not line:
                    if not prev_empty:
                        cleaned_lines.append('')
                    prev_empty = True
                else:
                    cleaned_lines.append(line)
                    prev_empty = False
            
            text_content.append('\n'.join(cleaned_lines))
            
            if (page_num + 1) % 10 == 0:
                print(f"  已处理 {page_num + 1}/{total_pages} 页...")
        
        print(f"提取完成，共 {total_pages} 页")
        
    finally:
        doc.close()
    
    return '\n\n'.join(text_content)


def main():
    """Main extraction function."""
    # 设置路径
    project_root = Path(__file__).parent
    pdf_path = project_root / "doc" / "par_rulebook_en.pdf"
    output_path = project_root / "doc" / "rulebook_extracted.txt"
    
    # 检查 PDF 是否存在
    if not pdf_path.exists():
        print(f"错误：找不到 PDF 文件: {pdf_path}")
        print(f"请确保文件存在于: {pdf_path.absolute()}")
        sys.exit(1)
    
    try:
        # 提取文本
        text = extract_pdf_text(pdf_path)
        
        # 保存到文件
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(text, encoding="utf-8")
        
        # 统计信息
        lines = text.split('\n')
        non_empty_lines = [line for line in lines if line.strip()]
        
        print(f"\n提取成功！")
        print(f"输出文件: {output_path}")
        print(f"总行数: {len(lines)}")
        print(f"非空行数: {len(non_empty_lines)}")
        print(f"文件大小: {len(text)} 字符")
        
        # 检查是否有符合规则格式的行（以数字编号开头）
        import re
        pattern = re.compile(r"^(\d+(?:\.\d+)*)\s+(.*)$", re.MULTILINE)
        matches = list(pattern.finditer(text))
        print(f"检测到规则条目: {len(matches)} 条")
        
        if matches:
            print("\n示例规则条目（前5条）:")
            for i, match in enumerate(matches[:5]):
                section, body = match.groups()
                print(f"  {section}: {body[:60]}...")
        else:
            print("\n警告：未检测到符合格式的规则条目（以数字编号开头的行）")
            print("可能需要手动调整文本格式")
        
    except Exception as e:
        print(f"错误：提取失败 - {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

