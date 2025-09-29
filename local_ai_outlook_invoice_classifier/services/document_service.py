from docling.document_converter import DocumentConverter


class DocumentService:
    """Service class to handle document processing with docling"""

    def __init__(self):
        self.converter = DocumentConverter()

    async def scan_document(self, file_path: str, filename: str):
        """
        Scan document and return markdown content
        """
        try:
            print(f"     🔍 Scanning document: {filename}")

            # Convert document to markdown
            doc = self.converter.convert(file_path).document
            markdown_content = doc.export_to_markdown()

            print(f"     📋 Document Content:")
            print("=" * 60)
            print(markdown_content)
            print("=" * 60)

            return markdown_content

        except Exception as e:
            print(f"     ❌ Error scanning document: {e}")
            return None