import pymupdf4llm
import pathlib
from typing import Union, Optional


class PDFParser:
    def __init__(self):
        pass
    
    def parse_to_markdown(self, pdf_path: Union[str, pathlib.Path]) -> str:
        pdf_path = str(pdf_path)
        markdown_text = pymupdf4llm.to_markdown(pdf_path)
        return markdown_text
    
    def save_to_file(self, content: str, output_path: Union[str, pathlib.Path]) -> None:
        output_path = pathlib.Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content, encoding='utf-8')
    
    def parse_and_save(self, pdf_path: Union[str, pathlib.Path], output_path: Optional[Union[str, pathlib.Path]] = None) -> str:
        markdown_content = self.parse_to_markdown(pdf_path)
        
        if output_path:
            self.save_to_file(markdown_content, output_path)
        
        return markdown_content
