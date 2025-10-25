import re
import regex
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field

# Proper markdown parsing with GFM support
from markdown_it import MarkdownIt
from mdit_py_plugins.front_matter import front_matter_plugin
from mdit_py_plugins.footnote import footnote_plugin
from mdit_py_plugins.deflist import deflist_plugin
from mdit_py_plugins.tasklists import tasklists_plugin


@dataclass
class HeaderPath:
    path: List[str] = field(default_factory=list)
    level: int = 0


@dataclass
class SectionContext:
    current_header: Optional[str] = None
    parent_list: Optional[str] = None
    table_header: Optional[str] = None
    depth: int = 0


@dataclass
class ChunkContext:
    header_path: HeaderPath = field(default_factory=HeaderPath)
    section_context: SectionContext = field(default_factory=SectionContext)
    buffer: List[Dict[str, Any]] = field(default_factory=list)
    word_count: int = 0
    token_count: int = 0
    chunks: List[str] = field(default_factory=list)


@dataclass
class ChunkerOptions:
    max_tokens_per_chunk: int = 512
    max_words_per_chunk: int = 100
    max_words_header: int = 45
    path_separator: str = " > "


class GFMContextPathChunker:
    def __init__(self, options: Optional[ChunkerOptions] = None):
        self.options = options or ChunkerOptions()

        # Initialize markdown-it with GFM support
        self.md = (
            MarkdownIt("gfm-like", {"html": True})
            .use(front_matter_plugin)
            .use(footnote_plugin)
            .use(deflist_plugin)
            .use(tasklists_plugin)
            .enable(
                ["table", "strikethrough", "linkify", "replacements", "smartquotes"]
            )
        )

    def count_words(self, text: str) -> int:
        """Count words in text using Unicode-aware regex"""
        if not text:
            return 0
        # Use regex library for proper Unicode word boundary handling
        words = regex.findall(r"\b\w+\b", text, regex.UNICODE)
        return len(words)

    def estimate_jina_token_count(self, text: str) -> int:
        """Estimate token count for Jina embeddings"""
        if not text:
            return 0
        word_count = self.count_words(text)
        # Jina embeddings typically have ~0.75 tokens per word
        return int(word_count * 0.75)

    def split_graphemes(self, text: str) -> List[str]:
        """Split text into graphemes using Unicode-aware segmentation"""
        # Use regex library for proper grapheme cluster support
        return regex.findall(r"\X", text)

    def to_string(self, node: Any) -> str:
        """Extract text content from markdown-it token"""
        if not node:
            return ""

        # Handle markdown-it Token objects
        if hasattr(node, "type"):
            if node.type == "text":
                return getattr(node, "content", "")
            elif node.type == "inline":
                return getattr(node, "content", "")
            elif node.type in ["heading_open", "paragraph_open"]:
                return ""
            elif node.type in ["heading_close", "paragraph_close"]:
                return ""
            elif hasattr(node, "content"):
                return getattr(node, "content", "")

        # Fallback for dict-like objects
        elif isinstance(node, dict):
            if node.get("type") == "text":
                return node.get("content", "")
            elif node.get("type") == "inline":
                return node.get("content", "")
            elif "content" in node:
                return node.get("content", "")

        return ""

    def extract_text_from_tokens(self, tokens: List[Any]) -> str:
        """Extract text content from a list of tokens"""
        text_parts = []
        for token in tokens:
            # Handle Token objects
            if (
                hasattr(token, "type")
                and token.type == "inline"
                and hasattr(token, "children")
                and token.children
            ):
                for child in token.children:
                    text_parts.append(self.to_string(child))
            # Handle dict objects
            elif (
                isinstance(token, dict)
                and token.get("type") == "inline"
                and token.get("children")
            ):
                for child in token["children"]:
                    text_parts.append(self.to_string(child))
            else:
                content = self.to_string(token)
                if content:
                    text_parts.append(content)
        return "".join(text_parts)

    def _get_token_attr(self, token: Any, attr: str, default: Any = None) -> Any:
        """Get attribute from token (handles both Token objects and dicts)"""
        if hasattr(token, attr):
            return getattr(token, attr, default)
        elif isinstance(token, dict):
            return token.get(attr, default)
        return default

    def chunk(self, input_text: str, page_title: str) -> List[str]:
        """Main chunking method with proper markdown parsing"""
        if not input_text or not input_text.strip():
            return []

        try:
            tokens = self.md.parse(input_text)
            if not tokens:
                return []

            context = self._process_tokens(
                tokens, self._create_initial_context(page_title)
            )
            final_context = self._finalize_chunks(context)

            return [
                chunk
                for chunk in final_context.chunks
                if chunk and isinstance(chunk, str) and chunk.strip()
            ]
        except Exception as e:
            print(f"Error during chunking: {e}")
            return []

    def chunk_within_token_limit(
        self,
        input_text: str,
        page_title: str,
        max_tokens_per_batch: int,
        overlap: int = 1,
    ) -> List[List[str]]:
        """Batch chunks within token limits"""
        all_chunks = self.chunk(input_text, page_title)
        if not all_chunks:
            return []

        chunk_tokens = [self.estimate_jina_token_count(chunk) for chunk in all_chunks]
        max_chunk_tokens = max(chunk_tokens)
        if max_chunk_tokens > max_tokens_per_batch:
            raise ValueError(
                f"Individual chunk exceeds token limit: {max_chunk_tokens} > {max_tokens_per_batch}"
            )

        batches = []
        current_index = 0

        while current_index < len(all_chunks):
            batch_tokens = 0
            batch_size = 0

            while (
                current_index + batch_size < len(all_chunks)
                and batch_tokens + chunk_tokens[current_index + batch_size]
                <= max_tokens_per_batch
            ):
                batch_tokens += chunk_tokens[current_index + batch_size]
                batch_size += 1

            batch = all_chunks[current_index : current_index + batch_size]
            batches.append(batch)

            if current_index + batch_size < len(all_chunks):
                current_index += max(1, batch_size - overlap)
            else:
                break

        return batches

    def _create_initial_context(self, page_title: str) -> ChunkContext:
        """Create initial chunking context"""
        return ChunkContext(
            header_path=HeaderPath(path=[page_title] if page_title else [], level=0),
            section_context=SectionContext(),
            buffer=[],
            word_count=0,
            token_count=0,
            chunks=[],
        )

    def _process_tokens(self, tokens: List[Any], context: ChunkContext) -> ChunkContext:
        """Process markdown-it tokens with robust validation"""
        i = 0
        while i < len(tokens):
            token = tokens[i]

            try:
                # Get token type (handle both Token objects and dicts)
                token_type = getattr(token, "type", None) or (
                    token.get("type") if isinstance(token, dict) else None
                )

                # Handle headings with proper sequence validation
                if token_type == "heading_open":
                    heading_result = self._process_heading_sequence(tokens, i)
                    if heading_result:
                        level, heading_text, next_index = heading_result
                        context = self._handle_heading(level, heading_text, context)
                        i = next_index
                        continue

                # Handle tables with validation
                elif token_type == "table_open":
                    try:
                        table_tokens, table_end_idx = self._extract_table_tokens(
                            tokens, i
                        )
                        if table_tokens:
                            context = self._handle_table(table_tokens, context)
                            i = table_end_idx + 1
                            continue
                    except Exception as e:
                        print(f"Error processing table: {e}")

                # Handle lists with validation
                elif token_type in ["bullet_list_open", "ordered_list_open"]:
                    try:
                        list_tokens, list_end_idx = self._extract_list_tokens(tokens, i)
                        if list_tokens:
                            context = self._handle_list(token, list_tokens, context)
                            i = list_end_idx + 1
                            continue
                    except Exception as e:
                        print(f"Error processing list: {e}")

                # Handle code blocks (markdown-it uses 'fence' type)
                elif token_type == "fence":
                    context = self._handle_code_block(token, context)
                    # Code blocks are single tokens, move to next
                    i += 1
                    continue

                # Handle paragraphs with sequence validation
                elif token_type == "paragraph_open":
                    paragraph_result = self._process_paragraph_sequence(tokens, i)
                    if paragraph_result:
                        paragraph_content, next_index = paragraph_result
                        context = self._handle_paragraph(paragraph_content, context)
                        i = next_index
                        continue

                # Handle blockquotes with validation
                elif token_type == "blockquote_open":
                    try:
                        blockquote_tokens, blockquote_end_idx = (
                            self._extract_blockquote_tokens(tokens, i)
                        )
                        if blockquote_tokens:
                            context = self._handle_blockquote(
                                blockquote_tokens, context
                            )
                            i = blockquote_end_idx + 1
                            continue
                    except Exception as e:
                        print(f"Error processing blockquote: {e}")

            except Exception as e:
                print(f"Error processing token at index {i}: {e}")

            i += 1

        return context

    def _update_section_context(
        self, token: Any, context: ChunkContext
    ) -> ChunkContext:
        """Update section context with sophisticated tracking like TypeScript version"""
        new_section_context = SectionContext(
            current_header=context.section_context.current_header,
            parent_list=context.section_context.parent_list,
            table_header=context.section_context.table_header,
            depth=context.section_context.depth,
        )

        token_type = self._get_token_attr(token, "type", "")

        # Update context based on token type with comprehensive tracking
        if token_type == "heading_open":
            # Header context will be updated when heading is processed
            pass
        elif token_type == "table_open":
            # Clear previous table context
            new_section_context.table_header = None
        elif token_type == "tr_open":
            # Check if this is the first row (header row) in a table
            pass  # Will be handled in table processing
        elif token_type in ["bullet_list_open", "ordered_list_open"]:
            list_marker = "1. " if "ordered" in token_type else "• "
            new_section_context.parent_list = list_marker
        elif token_type in ["bullet_list_close", "ordered_list_close"]:
            new_section_context.parent_list = None

        return ChunkContext(
            header_path=context.header_path,
            section_context=new_section_context,
            buffer=context.buffer,
            word_count=context.word_count,
            token_count=context.token_count,
            chunks=context.chunks,
        )

    def _extract_table_header_from_tokens(
        self, table_tokens: List[Any]
    ) -> Optional[str]:
        """Extract table header text like TypeScript version"""
        for i, token in enumerate(table_tokens):
            if self._get_token_attr(token, "type") == "thead_open":
                # Look for the first row in thead
                for j in range(i + 1, len(table_tokens)):
                    if self._get_token_attr(table_tokens[j], "type") == "tr_open":
                        # Extract all cell content from this row
                        header_cells = []
                        depth = 1
                        for k in range(j + 1, len(table_tokens)):
                            if (
                                self._get_token_attr(table_tokens[k], "type")
                                == "tr_open"
                            ):
                                depth += 1
                            elif (
                                self._get_token_attr(table_tokens[k], "type")
                                == "tr_close"
                            ):
                                depth -= 1
                                if depth == 0:
                                    break
                            elif (
                                self._get_token_attr(table_tokens[k], "type")
                                == "inline"
                            ):
                                header_cells.append(
                                    self.extract_text_from_tokens([table_tokens[k]])
                                )

                        return " | ".join(header_cells) if header_cells else None

        return None

    def _process_heading_sequence(
        self, tokens: List[Any], start_idx: int
    ) -> Optional[Tuple[int, str, int]]:
        """Process heading token sequence with validation"""
        if start_idx + 2 >= len(tokens):
            return None

        heading_open = tokens[start_idx]
        inline_token = tokens[start_idx + 1]
        heading_close = tokens[start_idx + 2]

        # Validate sequence
        if (
            self._get_token_attr(heading_open, "type") != "heading_open"
            or self._get_token_attr(inline_token, "type") != "inline"
            or self._get_token_attr(heading_close, "type") != "heading_close"
        ):
            return None

        # Validate matching tags
        open_tag = self._get_token_attr(heading_open, "tag", "")
        close_tag = self._get_token_attr(heading_close, "tag", "")
        if open_tag != close_tag:
            return None

        # Extract level and text
        level = int(open_tag[1:]) if len(open_tag) > 1 and open_tag[1:].isdigit() else 1
        heading_text = self.extract_text_from_tokens([inline_token])

        return level, heading_text, start_idx + 3

    def _process_paragraph_sequence(
        self, tokens: List[Any], start_idx: int
    ) -> Optional[Tuple[str, int]]:
        """Process paragraph token sequence with validation"""
        if start_idx + 2 >= len(tokens):
            return None

        para_open = tokens[start_idx]
        inline_token = tokens[start_idx + 1]
        para_close = tokens[start_idx + 2]

        # Validate sequence
        if (
            self._get_token_attr(para_open, "type") != "paragraph_open"
            or self._get_token_attr(inline_token, "type") != "inline"
            or self._get_token_attr(para_close, "type") != "paragraph_close"
        ):
            return None

        paragraph_content = self.extract_text_from_tokens([inline_token])
        return paragraph_content, start_idx + 3

    def _extract_table_tokens(
        self, tokens: List[Any], start_idx: int
    ) -> Tuple[List[Any], int]:
        """Extract table tokens from start to end"""
        table_tokens = []
        i = start_idx
        depth = 0

        while i < len(tokens):
            token = tokens[i]
            table_tokens.append(token)

            if self._get_token_attr(token, "type") == "table_open":
                depth += 1
            elif self._get_token_attr(token, "type") == "table_close":
                depth -= 1
                if depth == 0:
                    break

            i += 1

        return table_tokens, i

    def _extract_list_tokens(
        self, tokens: List[Any], start_idx: int
    ) -> Tuple[List[Any], int]:
        """Extract list tokens from start to end"""
        list_tokens = []
        i = start_idx
        depth = 0
        list_type = self._get_token_attr(tokens[start_idx], "type")
        close_type = list_type.replace("_open", "_close")

        while i < len(tokens):
            token = tokens[i]
            list_tokens.append(token)

            if self._get_token_attr(token, "type") == list_type:
                depth += 1
            elif self._get_token_attr(token, "type") == close_type:
                depth -= 1
                if depth == 0:
                    break

            i += 1

        return list_tokens, i

    def _extract_blockquote_tokens(
        self, tokens: List[Any], start_idx: int
    ) -> Tuple[List[Any], int]:
        """Extract blockquote tokens"""
        blockquote_tokens = []
        i = start_idx
        depth = 0

        while i < len(tokens):
            token = tokens[i]
            blockquote_tokens.append(token)

            if self._get_token_attr(token, "type") == "blockquote_open":
                depth += 1
            elif self._get_token_attr(token, "type") == "blockquote_close":
                depth -= 1
                if depth == 0:
                    break

            i += 1

        return blockquote_tokens, i

    def _handle_heading(
        self, level: int, heading_text: str, context: ChunkContext
    ) -> ChunkContext:
        """Handle heading with proper path tracking"""
        clean_context = self._finalize_chunks(context)

        # Create new header path
        new_path = clean_context.header_path.path[: level - 1]
        new_path.append(heading_text)

        # Determine if this heading is significant
        is_significant = (
            self.count_words(heading_text) >= 4
            or level == 1
            or "?" in heading_text
            or re.match(r"^\d+[.)]\s", heading_text)
        )

        has_existing_content = len(clean_context.buffer) > 0
        should_create_chunk = has_existing_content or is_significant

        # Create heading node
        heading_node = {"type": "heading", "level": level, "content": heading_text}

        return ChunkContext(
            header_path=HeaderPath(path=new_path, level=level),
            section_context=clean_context.section_context,
            buffer=[heading_node] if should_create_chunk else [],
            word_count=self.count_words(heading_text) if should_create_chunk else 0,
            token_count=self.estimate_jina_token_count(heading_text)
            if should_create_chunk
            else 0,
            chunks=clean_context.chunks,
        )

    def _handle_table(
        self, table_tokens: List[Dict[str, Any]], context: ChunkContext
    ) -> ChunkContext:
        """Handle table with sophisticated row/column splitting"""
        if not table_tokens:
            return context

        # Update section context with table header
        table_header = self._extract_table_header_from_tokens(table_tokens)
        updated_context = context
        if table_header:
            updated_context = ChunkContext(
                header_path=context.header_path,
                section_context=SectionContext(
                    current_header=context.section_context.current_header,
                    parent_list=context.section_context.parent_list,
                    table_header=table_header,
                    depth=context.section_context.depth,
                ),
                buffer=context.buffer,
                word_count=context.word_count,
                token_count=context.token_count,
                chunks=context.chunks,
            )

        # Extract table structure
        table_data = self._parse_table_structure(table_tokens)
        if not table_data:
            return updated_context

        headers = table_data.get("headers", [])
        rows = table_data.get("rows", [])

        if not headers or not rows:
            # Simple table, treat as block
            table_text = self._tokens_to_markdown(table_tokens)
            return self._handle_block_content(table_text, "table", updated_context)

        # Check if table is too wide for a single chunk
        max_cells_per_chunk = max(2, len(headers) // 2)
        current_context = context

        for row_idx, row in enumerate(rows):
            # Check if this row is too long using proper validation
            if self._is_table_row_too_long(row, headers):
                # Split row into chunks
                cell_chunks = self._split_row_into_chunks(
                    row, headers, max_cells_per_chunk
                )

                for chunk_idx, (header_chunk, cell_chunk) in enumerate(cell_chunks):
                    # Add continuation marker for subsequent chunks using createNoteCell logic
                    if chunk_idx > 0:
                        continuation_header = self._create_note_cell(
                            "(Continued from previous section)"
                        )
                        continuation_cell = self._create_note_cell("...")
                        header_chunk = [continuation_header] + header_chunk
                        cell_chunk = [continuation_cell] + cell_chunk

                    table_chunk_text = self._create_table_chunk_text(
                        header_chunk, cell_chunk
                    )
                    current_context = self._handle_block_content(
                        table_chunk_text, "table", current_context
                    )
            else:
                # Include header + row as single chunk
                table_chunk_text = self._create_table_chunk_text(headers, row)
                current_context = self._handle_block_content(
                    table_chunk_text, "table", current_context
                )

        return current_context

    def _parse_table_structure(self, table_tokens: List[Any]) -> Dict[str, List]:
        """Parse table tokens into structured data"""
        headers = []
        rows = []
        current_row = []
        in_header = False
        in_body = False

        for token in table_tokens:
            token_type = self._get_token_attr(token, "type")
            if token_type == "thead_open":
                in_header = True
            elif token_type == "thead_close":
                in_header = False
            elif token_type == "tbody_open":
                in_body = True
            elif token_type == "tbody_close":
                in_body = False
            elif token_type == "tr_open":
                current_row = []
            elif token_type == "tr_close":
                if in_header and current_row:
                    headers = current_row
                elif in_body and current_row:
                    rows.append(current_row)
                current_row = []
            elif token_type in ["th_open", "td_open"]:
                # Next token should be inline with cell content
                continue
            elif token_type == "inline":
                cell_content = self.extract_text_from_tokens([token])
                current_row.append(cell_content)

        return {"headers": headers, "rows": rows}

    def _split_row_into_chunks(
        self, row: List[str], headers: List[str], max_cells_per_chunk: int
    ) -> List[Tuple[List[str], List[str]]]:
        """Split table row into smaller chunks"""
        chunks = []

        for i in range(0, len(row), max_cells_per_chunk):
            end_idx = min(i + max_cells_per_chunk, len(row))
            header_chunk = headers[i:end_idx]
            cell_chunk = row[i:end_idx]
            chunks.append((header_chunk, cell_chunk))

        return chunks

    def _create_table_chunk_text(self, headers: List[str], row: List[str]) -> str:
        """Create markdown table text from headers and row"""
        if not headers or not row:
            return ""

        # Pad row to match headers length
        padded_row = row + [""] * (len(headers) - len(row))

        table_lines = [
            "| " + " | ".join(headers) + " |",
            "| " + " | ".join(["---"] * len(headers)) + " |",
            "| " + " | ".join(padded_row) + " |",
        ]

        return "\n".join(table_lines)

    def _create_note_cell(self, text: str) -> str:
        """Create a note cell like TypeScript createNoteCell method"""
        return text

    def _handle_list(
        self,
        list_open_token: Dict[str, Any],
        list_tokens: List[Dict[str, Any]],
        context: ChunkContext,
    ) -> ChunkContext:
        """Handle list with smart batching"""
        if not list_tokens:
            return context

        list_text = self._tokens_to_markdown(list_tokens)
        list_words = self.count_words(list_text)
        list_tokens_count = self.estimate_jina_token_count(list_text)

        # If the whole list fits, process as single block
        if (
            list_words <= self.options.max_words_per_chunk
            and list_tokens_count <= self.options.max_tokens_per_chunk
        ):
            return self._handle_block_content(list_text, "list", context)

        # Otherwise, split list into smaller chunks
        list_items = self._extract_list_items(list_tokens)
        return self._chunk_list_items(
            list_items, self._get_token_attr(list_open_token, "type"), context
        )

    def _extract_list_items(self, list_tokens: List[Any]) -> List[List[Any]]:
        """Extract individual list items with sophisticated nested handling"""
        items = []
        current_item = []
        depth = 0
        nested_list_depth = 0

        for token in list_tokens:
            token_type = self._get_token_attr(token, "type", "")

            if token_type == "list_item_open":
                if depth == 0:
                    current_item = []
                current_item.append(token)
                depth += 1
            elif token_type == "list_item_close":
                current_item.append(token)
                depth -= 1
                if depth == 0:
                    items.append(current_item)
            elif token_type in ["bullet_list_open", "ordered_list_open"]:
                # Track nested lists
                if depth > 0:
                    current_item.append(token)
                    nested_list_depth += 1
            elif token_type in ["bullet_list_close", "ordered_list_close"]:
                # Track nested lists
                if depth > 0:
                    current_item.append(token)
                    nested_list_depth = max(0, nested_list_depth - 1)
            elif depth > 0:
                current_item.append(token)

        return items

    def _chunk_list_items(
        self, list_items: List[List[Any]], list_type: str, context: ChunkContext
    ) -> ChunkContext:
        """Chunk list items while respecting limits"""
        current_context = context
        current_chunk_items = []
        current_words = 0
        current_tokens = 0

        for item_tokens in list_items:
            item_text = self._tokens_to_markdown(item_tokens)
            item_words = self.count_words(item_text)
            item_tokens_count = self.estimate_jina_token_count(item_text)

            # Check if adding this item would exceed limits
            if current_chunk_items and (
                current_words + item_words > self.options.max_words_per_chunk
                or current_tokens + item_tokens_count
                > self.options.max_tokens_per_chunk
            ):
                # Finalize current chunk
                chunk_text = self._create_list_chunk_text(
                    current_chunk_items, list_type
                )
                current_context = self._handle_block_content(
                    chunk_text, "list", current_context
                )

                # Start new chunk
                current_chunk_items = [item_tokens]
                current_words = item_words
                current_tokens = item_tokens_count
            else:
                # Add to current chunk
                current_chunk_items.append(item_tokens)
                current_words += item_words
                current_tokens += item_tokens_count

        # Handle remaining items
        if current_chunk_items:
            chunk_text = self._create_list_chunk_text(current_chunk_items, list_type)
            current_context = self._handle_block_content(
                chunk_text, "list", current_context
            )

        return current_context

    def _create_list_chunk_text(
        self, item_tokens_list: List[List[Any]], list_type: str
    ) -> str:
        """Create markdown list text from item tokens"""
        list_lines = []
        is_ordered = "ordered" in list_type

        for idx, item_tokens in enumerate(item_tokens_list):
            item_content = self._extract_list_item_content(item_tokens)
            if is_ordered:
                list_lines.append(f"{idx + 1}. {item_content}")
            else:
                list_lines.append(f"- {item_content}")

        return "\n".join(list_lines)

    def _extract_list_item_content(self, item_tokens: List[Any]) -> str:
        """Extract content from list item tokens with nested structure handling"""
        content_parts = []
        i = 0

        while i < len(item_tokens):
            token = item_tokens[i]
            token_type = self._get_token_attr(token, "type", "")

            if token_type == "inline":
                content_parts.append(self.extract_text_from_tokens([token]))
            elif token_type in ["paragraph_open", "paragraph_close"]:
                pass  # Skip paragraph markers
            elif token_type == "list_item_open":
                # Skip the opening token for the main item
                pass
            elif token_type == "list_item_close":
                # Skip the closing token for the main item
                pass
            elif token_type in ["bullet_list_open", "ordered_list_open"]:
                # Handle nested lists by processing them recursively
                nested_list_tokens = []
                depth = 1
                list_type = token_type
                i += 1

                while i < len(item_tokens) and depth > 0:
                    current_token = item_tokens[i]
                    current_type = self._get_token_attr(current_token, "type", "")
                    nested_list_tokens.append(current_token)

                    if current_type in ["bullet_list_open", "ordered_list_open"]:
                        depth += 1
                    elif current_type in ["bullet_list_close", "ordered_list_close"]:
                        depth -= 1

                    i += 1

                # Process the nested list
                if nested_list_tokens:
                    # Remove the last close token
                    if nested_list_tokens and self._get_token_attr(
                        nested_list_tokens[-1], "type"
                    ) in ["bullet_list_close", "ordered_list_close"]:
                        nested_list_tokens = nested_list_tokens[:-1]

                    nested_content = self._process_nested_list_tokens(
                        nested_list_tokens, list_type
                    )
                    if nested_content:
                        content_parts.append("\n" + nested_content)

                # Skip incrementing i since we already advanced it in the while loop
                continue

            i += 1

        return " ".join(content_parts).strip()

    def _process_nested_list_tokens(
        self, nested_tokens: List[Any], parent_list_type: str
    ) -> str:
        """Process nested list tokens with proper indentation"""
        nested_items = []
        current_item = []
        depth = 0
        item_counter = 1

        for token in nested_tokens:
            token_type = self._get_token_attr(token, "type", "")

            if token_type == "list_item_open":
                if depth == 0:
                    current_item = []
                depth += 1
            elif token_type == "list_item_close":
                depth -= 1
                if depth == 0 and current_item:
                    # Process the nested item content
                    item_content = []
                    for item_token in current_item:
                        if self._get_token_attr(item_token, "type") == "inline":
                            item_content.append(
                                self.extract_text_from_tokens([item_token])
                            )

                    if item_content:
                        content = " ".join(item_content)
                        # Use proper indentation (2 spaces) and numbering
                        if parent_list_type == "ordered_list_open":
                            nested_items.append(
                                f"   - {content}"
                            )  # Nested items are bullets even in ordered lists
                        else:
                            nested_items.append(f"   - {content}")
                        item_counter += 1

                    current_item = []
            elif depth > 0:
                current_item.append(token)

        return "\n".join(nested_items) if nested_items else ""

    def _handle_code_block(self, token: Any, context: ChunkContext) -> ChunkContext:
        """Handle code blocks"""
        content = self._get_token_attr(token, "content", "")
        language = self._get_token_attr(token, "info", "")

        if language:
            code_text = f"```{language}\n{content}\n```"
        else:
            code_text = f"```\n{content}\n```"

        return self._handle_block_content(code_text, "code_block", context)

    def _handle_paragraph(self, content: str, context: ChunkContext) -> ChunkContext:
        """Handle paragraph content"""
        return self._handle_block_content(content, "paragraph", context)

    def _handle_blockquote(
        self, blockquote_tokens: List[Dict[str, Any]], context: ChunkContext
    ) -> ChunkContext:
        """Handle blockquotes"""
        blockquote_text = self._tokens_to_markdown(blockquote_tokens)
        return self._handle_block_content(blockquote_text, "blockquote", context)

    def _handle_block_content(
        self, content: str, node_type: str, context: ChunkContext
    ) -> ChunkContext:
        """Generic handler for block-level content"""
        if not content or not content.strip():
            return context

        words = self.count_words(content)
        tokens = self.estimate_jina_token_count(content)

        # Check if adding this would exceed limits
        if (
            context.token_count + tokens > self.options.max_tokens_per_chunk
            or context.word_count + words > self.options.max_words_per_chunk
        ):
            clean_context = self._finalize_chunks(context)
            return self._finalize_chunks(
                ChunkContext(
                    header_path=clean_context.header_path,
                    section_context=clean_context.section_context,
                    buffer=[{"type": node_type, "content": content}],
                    word_count=words,
                    token_count=tokens,
                    chunks=clean_context.chunks,
                )
            )

        # Add to current buffer
        return ChunkContext(
            header_path=context.header_path,
            section_context=context.section_context,
            buffer=context.buffer + [{"type": node_type, "content": content}],
            word_count=context.word_count + words,
            token_count=context.token_count + tokens,
            chunks=context.chunks,
        )

    def _is_content_too_large(self, content: str, context: ChunkContext) -> bool:
        """Check if content is too large for current context"""
        words = self.count_words(content)
        tokens = self.estimate_jina_token_count(content)

        return (
            context.word_count + words > self.options.max_words_per_chunk
            or context.token_count + tokens > self.options.max_tokens_per_chunk
        )

    def _finalize_chunks(self, context: ChunkContext) -> ChunkContext:
        """Finalize chunks from the buffer"""
        if not context.buffer:
            return context

        empty_context = ChunkContext(
            header_path=context.header_path,
            section_context=context.section_context,
            buffer=[],
            word_count=0,
            token_count=0,
            chunks=context.chunks,
        )

        try:
            chunk = self._create_chunk(context.buffer, context.header_path.path)
            if not chunk:
                return empty_context

            chunk_tokens = self.estimate_jina_token_count(chunk)
            if chunk_tokens > self.options.max_tokens_per_chunk:
                split_chunks = self._split_large_chunk(chunk)
                return ChunkContext(
                    header_path=context.header_path,
                    section_context=context.section_context,
                    buffer=[],
                    word_count=0,
                    token_count=0,
                    chunks=context.chunks + split_chunks,
                )

            return ChunkContext(
                header_path=context.header_path,
                section_context=context.section_context,
                buffer=[],
                word_count=0,
                token_count=0,
                chunks=context.chunks + [chunk],
            )

        except Exception as e:
            print(f"Error finalizing chunks: {e}")
            return empty_context

    def _create_chunk(
        self, nodes: List[Dict[str, Any]], header_path: List[str]
    ) -> Optional[str]:
        """Create a chunk from nodes with validation"""
        if not nodes:
            return None

        try:
            # Validate nodes first
            valid_nodes = self._validate_nodes(nodes)
            if not valid_nodes:
                return None

            content_parts = []
            for node in valid_nodes:
                markdown_content = self._node_to_markdown(node)
                if markdown_content and markdown_content.strip():
                    content_parts.append(markdown_content)

            if not content_parts:
                return None

            content = "\n\n".join(content_parts)
            if not content.strip():
                return None

            formatted_path = self._format_header_path(header_path)
            return f"{formatted_path}\n\n{content}" if formatted_path else content

        except Exception as e:
            print(f"Error creating chunk: {e}")
            return None

    def _validate_nodes(self, nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Validate nodes similar to TypeScript version"""
        valid_nodes = []

        for node in nodes:
            if (
                node
                and isinstance(node, dict)
                and "type" in node
                and isinstance(node.get("type"), str)
            ):
                valid_nodes.append(node)

        return valid_nodes

    def _node_to_markdown(self, node: Dict[str, Any]) -> str:
        """Convert a node back to markdown"""
        node_type = node.get("type")
        content = node.get("content", "")

        if node_type == "heading":
            level = node.get("level", 1)
            return "#" * level + " " + content
        elif node_type in [
            "paragraph",
            "text",
            "table",
            "list",
            "code_block",
            "blockquote",
        ]:
            return content
        else:
            return content

    def _format_header_path(self, path: List[str]) -> str:
        """Format header path"""
        if not path:
            return ""

        full_path = self.options.path_separator.join(path)
        words = self.count_words(full_path)

        if words > self.options.max_words_header:
            start = path[:1]
            end = path[-2:]
            return self.options.path_separator.join([*start, "...", *end])

        return full_path

    def _split_large_chunk(self, text: str) -> List[str]:
        """Split a large chunk into smaller pieces with Unicode awareness"""
        chunks = []
        current_chunk = ""
        current_tokens = 0

        # Use proper grapheme segmentation
        graphemes = self.split_graphemes(text)

        for grapheme in graphemes:
            grapheme_tokens = self.estimate_jina_token_count(grapheme)

            if current_tokens + grapheme_tokens > self.options.max_tokens_per_chunk:
                split_index = len(current_chunk)
                break_points = [". ", "? ", "! ", ", ", "; ", " ", "\n"]

                # Find a good break point
                for break_point in break_points:
                    last_break = current_chunk.rfind(break_point)
                    if last_break != -1:
                        split_index = last_break + len(break_point)
                        break

                if split_index < len(current_chunk):
                    chunks.append(current_chunk[:split_index].strip())
                    current_chunk = current_chunk[split_index:]
                    current_tokens = self.estimate_jina_token_count(current_chunk)
                else:
                    chunks.append(current_chunk.strip())
                    current_chunk = ""
                    current_tokens = 0

            current_chunk += grapheme
            current_tokens += grapheme_tokens

        if current_chunk:
            chunks.append(current_chunk.strip())

        return [chunk for chunk in chunks if chunk]

    def _is_table_row_too_long(self, row: List[str], headers: List[str]) -> bool:
        """Check if table row is too long (similar to TypeScript version)"""
        if not row:
            return False

        # Create table representation to measure
        row_text = self._create_table_chunk_text(headers, row)
        row_words = self.count_words(row_text)
        row_tokens = self.estimate_jina_token_count(row_text)

        return (
            row_words > self.options.max_words_per_chunk
            or row_tokens > self.options.max_tokens_per_chunk
        )

    def _tokens_to_markdown(self, tokens: List[Any]) -> str:
        """Convert tokens back to markdown format with proper reconstruction"""
        if not tokens:
            return ""

        try:
            # Use markdown-it renderer to properly reconstruct markdown
            markdown_parts = []

            i = 0
            list_item_counter = 1
            current_list_type = None

            while i < len(tokens):
                token = tokens[i]
                token_type = self._get_token_attr(token, "type", "")

                if token_type == "paragraph_open":
                    if (
                        i + 1 < len(tokens)
                        and self._get_token_attr(tokens[i + 1], "type") == "inline"
                    ):
                        content = self.extract_text_from_tokens([tokens[i + 1]])
                        markdown_parts.append(content)
                        i += 3  # Skip paragraph_open, inline, paragraph_close
                        continue
                elif token_type == "heading_open":
                    if (
                        i + 1 < len(tokens)
                        and self._get_token_attr(tokens[i + 1], "type") == "inline"
                    ):
                        tag = self._get_token_attr(token, "tag", "h1")
                        level = (
                            int(tag[1:]) if len(tag) > 1 and tag[1:].isdigit() else 1
                        )
                        content = self.extract_text_from_tokens([tokens[i + 1]])
                        markdown_parts.append("#" * level + " " + content)
                        i += 3  # Skip heading_open, inline, heading_close
                        continue
                elif token_type in ["ordered_list_open", "bullet_list_open"]:
                    current_list_type = token_type
                    list_item_counter = 1
                elif token_type in ["ordered_list_close", "bullet_list_close"]:
                    current_list_type = None
                    list_item_counter = 1
                elif token_type == "list_item_open":
                    # Handle list items with proper numbering and nested structure
                    item_tokens = []
                    depth = 1
                    i += 1

                    # Collect all tokens for this list item (including nested content)
                    while i < len(tokens) and depth > 0:
                        current_token = tokens[i]
                        current_type = self._get_token_attr(current_token, "type")

                        if current_type == "list_item_open":
                            depth += 1
                        elif current_type == "list_item_close":
                            depth -= 1

                        if depth > 0:  # Include all tokens within this list item
                            item_tokens.append(current_token)

                        i += 1

                    # Process the item content including nested structure
                    if item_tokens:
                        content = self._extract_list_item_content(item_tokens)
                        if current_list_type == "ordered_list_open":
                            markdown_parts.append(f"{list_item_counter}. {content}")
                            list_item_counter += 1
                        else:
                            markdown_parts.append(f"- {content}")
                    continue
                elif token_type == "code_block":
                    content = self._get_token_attr(token, "content", "")
                    info = self._get_token_attr(token, "info", "")
                    if info:
                        markdown_parts.append(f"```{info}\n{content}\n```")
                    else:
                        markdown_parts.append(f"```\n{content}\n```")
                elif token_type == "inline":
                    markdown_parts.append(self.extract_text_from_tokens([token]))
                elif self._get_token_attr(token, "content"):
                    markdown_parts.append(self._get_token_attr(token, "content"))

                i += 1

            return "\n\n".join(filter(None, markdown_parts))

        except Exception as e:
            print(f"Error converting tokens to markdown: {e}")
            # Fallback to simple conversion
            parts = []
            for token in tokens:
                if self._get_token_attr(token, "type") == "inline":
                    parts.append(self.extract_text_from_tokens([token]))
                elif self._get_token_attr(token, "content"):
                    parts.append(self._get_token_attr(token, "content"))

            return " ".join(parts)
