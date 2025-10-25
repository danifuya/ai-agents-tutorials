-- Add PGroonga indexes for full-text search functionality
-- Using TokenNgram with bigram tokenization (n=2) and NormalizerAuto for case normalization

-- PGroonga index for document_chunks content (for keyword matching)
CREATE INDEX idx_document_chunks_content_pgroonga
ON document_chunks USING pgroonga (content)
WITH (
  tokenizer = 'TokenNgram("n", 2, "unify_alphabet", false)',
  normalizers = 'NormalizerAuto'
);

-- PGroonga index for document summaries (for document-level search)
CREATE INDEX idx_documents_summary_pgroonga
ON documents USING pgroonga (summary)
WITH (
  tokenizer = 'TokenNgram("n", 2, "unify_alphabet", false)',
  normalizers = 'NormalizerAuto'
);
