#!/usr/bin/env python3
"""
Interactive Document Parser Example

This script provides an interactive interface to:
1. Discover PDF files in a source directory
2. Select documents to parse
3. Parse PDFs to markdown using pymupdf4llm
4. Save results to the documents folder

Usage:
  # Parse from default input directory
  python parse_documents.py
  
  # Parse from custom input directory
  python parse_documents.py --input-dir /path/to/pdfs
  
  # Parse specific file
  python parse_documents.py --file document.pdf
  
  # List available PDFs
  python parse_documents.py --list
"""

import os
import sys
import argparse
from pathlib import Path
from typing import List, Optional
import time

# Add the backend directory to Python path so we can import from app
# Find the backend directory by looking for the directory containing 'app'
script_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = script_dir
while backend_dir != '/' and not os.path.exists(os.path.join(backend_dir, 'app')):
    backend_dir = os.path.dirname(backend_dir)

if os.path.exists(os.path.join(backend_dir, 'app')):
    sys.path.insert(0, backend_dir)
else:
    raise ImportError("Could not find backend directory containing 'app' module")

from app.rag.parsers.pdf_parser import PDFParser


class DocumentParserInterface:
    """
    Document parser with selection capabilities
    """
    
    def __init__(self):
        """
        Initialize the document parser interface
        Always uses rag/documents directory for both input and output
        """
        self.parser = PDFParser()
        
        # Find the rag/documents directory relative to this script
        # From parsers/examples/, go up two levels to get to rag/, then to documents/
        rag_dir = Path(__file__).parent.parent.parent
        self.documents_dir = rag_dir / "documents"
        
        # Both input and output use the same directory
        self.input_dir = self.documents_dir
        self.output_dir = self.documents_dir
    
    def find_pdf_files(self) -> List[Path]:
        """
        Find all PDF files in the input directory
        
        Returns:
            List of PDF file paths
        """
        if not self.input_dir.exists():
            return []
        
        # Search for PDF files recursively
        pdf_files = []
        for pdf_pattern in ["*.pdf", "*.PDF"]:
            pdf_files.extend(self.input_dir.rglob(pdf_pattern))
        
        return sorted(pdf_files)
    
    def list_available_pdfs(self) -> None:
        """Display all available PDF files"""
        print(f"📁 Searching for PDF files in: {self.input_dir}")
        print("=" * 80)
        
        pdf_files = self.find_pdf_files()
        
        if not pdf_files:
            print(f"❌ No PDF files found in {self.input_dir}")
            return
        
        print(f"✅ Found {len(pdf_files)} PDF file(s):")
        print("-" * 60)
        
        for i, pdf_file in enumerate(pdf_files, 1):
            # Show relative path from input directory
            rel_path = pdf_file.relative_to(self.input_dir)
            file_size = pdf_file.stat().st_size / (1024 * 1024)  # MB
            print(f"  {i:2d}. 📄 {rel_path} ({file_size:.1f} MB)")
    
    def parse_document(self, pdf_path: Path, output_name: str = None) -> Optional[Path]:
        """
        Parse a single PDF document to markdown
        
        Args:
            pdf_path: Path to the PDF file
            output_name: Optional custom output filename (without extension)
            
        Returns:
            Path to the saved markdown file, or None if failed
        """
        if not pdf_path.exists():
            print(f"❌ File not found: {pdf_path}")
            return None
        
        print(f"📖 Parsing: {pdf_path.name}")
        start_time = time.time()
        
        try:
            # Parse PDF to markdown
            markdown_content = self.parser.parse_to_markdown(pdf_path)
            
            # Always use PDF filename with .md extension (ignore output_name parameter)
            # This ensures consistent naming: PDF name -> MD name
            output_filename = pdf_path.stem + ".md"
            output_path = self.output_dir / output_filename
            
            # Save markdown content
            self.parser.save_to_file(markdown_content, output_path)
            
            processing_time = time.time() - start_time
            
            print(f"✅ Successfully parsed in {processing_time:.2f}s")
            print(f"   📄 Input:  {pdf_path}")
            print(f"   💾 Output: {output_path}")
            print(f"   📊 Content: {len(markdown_content)} characters")
            
            return output_path
            
        except Exception as e:
            processing_time = time.time() - start_time
            print(f"❌ Parsing failed after {processing_time:.2f}s: {str(e)}")
            return None
    
    def parse_all_documents(self) -> None:
        """Parse all PDF documents found in input directory"""
        pdf_files = self.find_pdf_files()
        
        if not pdf_files:
            print(f"❌ No PDF files found in {self.input_dir}")
            return
        
        print(f"🚀 Parsing all {len(pdf_files)} documents...")
        successful = 0
        failed = 0
        
        for pdf_file in pdf_files:
            result = self.parse_document(pdf_file)
            if result:
                successful += 1
            else:
                failed += 1
            print()  # Add spacing between documents
        
        print(f"🎉 Batch parsing completed!")
        print(f"   ✅ Successful: {successful}")
        print(f"   ❌ Failed: {failed}")


def main():
    """Main function with argument parsing"""
    parser = argparse.ArgumentParser(
        description="Document parser for PDF to Markdown conversion",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List PDFs in rag/documents directory
  python parse_documents.py --list
  
  # Parse specific file (PDF must be in rag/documents)
  python parse_documents.py --file document.pdf
  
  # Parse all PDFs in rag/documents
  python parse_documents.py --all
        """
    )
    
    
    parser.add_argument(
        '--all', '-a',
        action='store_true',
        help='Parse all PDF files in the input directory'
    )
    
    parser.add_argument(
        '--file', '-f',
        help='Specific PDF file to parse'
    )
    
    
    parser.add_argument(
        '--list', '-l',
        action='store_true',
        help='List available PDF files and exit'
    )
    
    args = parser.parse_args()
    
    # Initialize the parser interface (always uses rag/documents)
    doc_parser = DocumentParserInterface()
    
    if args.list:
        # List available PDFs
        doc_parser.list_available_pdfs()
        return
    
    if args.file:
        # Parse specific file
        file_path = Path(args.file)
        
        # If it's not absolute, look in rag/documents directory
        if not file_path.is_absolute():
            candidate = doc_parser.documents_dir / args.file
            if candidate.exists():
                file_path = candidate
        
        if not file_path.exists():
            print(f"❌ File not found: {args.file}")
            return
        
        print(f"🚀 SINGLE DOCUMENT PARSER")
        print("=" * 60)
        doc_parser.parse_document(file_path)
        
    elif args.all:
        # Parse all documents
        print(f"🚀 BATCH DOCUMENT PARSER")
        print("=" * 60)
        print(f"📂 Working directory: {doc_parser.documents_dir}")
        print("=" * 60)
        doc_parser.parse_all_documents()
        
    else:
        # Default to listing if no specific action
        doc_parser.list_available_pdfs()


if __name__ == "__main__":
    main()