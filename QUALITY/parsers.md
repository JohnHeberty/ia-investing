# Code Quality Analysis — `parsers` Module

**Data:** 2026-07-21  
**Arquivos analisados:** 3 Python files (__init__.py, _html.py, _pdf.py)  
**Ferramentas usadas:** ruff, mypy, análise manual de padrões  

---

## Resumo Executivo

| Severidade | Quantidade | Descrição |
|------------|-----------|-----------|
| Crítico | 0 | Nenhum problema crítico identificado neste módulo |
| Aviso | 1 | Import circular entre `_html.py` e `_pdf.py` via `ParsedDocument` |
| Sugestão | 3 | Sem tratamento de erros para arquivos PDF corrompidos, classes internas duplicadas no HTML parser, sem testes unitários |

---

## Aviso

### W-01: Dependência cruzada entre submódulos
**Arquivo:** `src/parsers/_html.py:8`  
O módulo `_html.py` importa de `_pdf.py`:
```python
from ._pdf import ParsedDocument
```

Isso cria uma dependência assimétrica — o tipo compartilhado (`ParsedDocument`) vive no módulo PDF mas é usado pelo HTML parser. Se alguém remover ou renomear `_pdf.py`, quebra `_html.py`.

**Recomendação:** Mover `ParsedDocument` para um arquivo dedicado como `_types.py`:
```python
# parsers/_types.py
@dataclass(slots=True)
class ParsedDocument: ...
```

---

## Sugestão

### S-01: Sem tratamento de erros para arquivos PDF corrompidos ou inválidos
**Arquivo:** `src/parsers/_pdf.py:26`  
A função `parse_pdf()` não faz try/except. Se o arquivo estiver corrompido, protegido por senha, ou não for um PDF válido, a exceção de `pdfplumber` propagará sem contexto útil.

**Recomendação:** Envolver em try/except com mensagem clara:
```python
def parse_pdf(file_path: str | Path) -> ParsedDocument:
    import pdfplumber
    
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {path}")
    
    try:
        with pdfplumber.open(path) as pdf:
            ...
    except Exception as exc:
        raise ValueError(f"Failed to parse PDF {path}: {exc}") from exc
```

### S-02: Classes internas duplicadas no HTML parser
**Arquivo:** `src/parsers/_html.py`  
Duas classes aninhadas (`_TextExtractor` e `_TagExtractor`) com lógica similar de parsing. Ambas herdam de `HTMLParser`, implementam `handle_starttag`, `handle_endtag`, `handle_data`, e `get_text()`.

**Recomendação:** Extrair para uma classe base compartilhada fora das funções, reduzindo duplicação:
```python
class _BaseExtractor(HTMLParser):
    ...  # lógica comum de skip/depth tracking
    
class _TextExtractor(_BaseExtractor): ...
class _TagExtractor(_BaseExtractor): ...
```

### S-03: Sem testes unitários
Não foram encontrados testes para o módulo `parsers`. Dado que envolve parsing de documentos externos (PDF, HTML), é crítico ter cobertura com arquivos reais e edge cases.

**Recomendação:** Adicionar testes com PDFs/HTMLs de amostra cobrindo sucesso, arquivo vazio, encoding inválido, tabelas complexas.

---

## Pontos Positivos

- **Módulo pequeno e bem delimitado:** 3 arquivos, responsabilidade clara
- **API limpa via `__init__.py`:** exports organizados com `__all__` ordenado alfabeticamente  
- **Sanitização de tabelas:** função `_sanitize_tables()` converte corretamente `None` para string vazia

---

## Próximos Passos Sugeridos

1. **Mover `ParsedDocument` para arquivo dedicado** (W-01) — quebra dependência cruzada
2. **Adicionar tratamento de erros em `parse_pdf()`** (S-01)
3. **Criar testes unitários com arquivos de amostra** (S-03)
