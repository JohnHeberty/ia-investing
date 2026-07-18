from __future__ import annotations


class TextChunker:
    def chunk_text(self, text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
        chunks: list[str] = []
        start = 0
        text_len = len(text)

        while start < text_len:
            end = min(start + chunk_size, text_len)
            chunk = text[start:end]

            if end < text_len:
                last_space = chunk.rfind(" ")
                if last_space > chunk_size // 2:
                    chunk = chunk[:last_space]
                    end = start + last_space

            chunks.append(chunk.strip())
            start = max(0, end - overlap) if end < text_len else text_len

            if start >= text_len:
                break

        return [c for c in chunks if c]
