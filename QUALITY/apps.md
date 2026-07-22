# Code Quality Analysis — `apps` Module

**Data:** 2026-07-21  
**Última atualização:** 2026-07-22 — W-01/02/03/04 corrigidos  
**Arquivos analisados:** ~44 Python files (api/, worker/, scheduler/)  
**Ferramentas usadas:** ruff, mypy, análise manual de padrões  

---

## Resumo Executivo

| Severidade | Original | Corrigido | Restante | Descrição |
|------------|----------|-----------|----------|-----------|
| Crítico | 1 | 0 | 1 | C-01 — mypy path config |
| Aviso | 4 | 4 | 0 | W-01/02/03/04 corrigidos |
| Sugestão | 3 | 0 | 3 | S-01/02/03 — refatorações maiores pendentes |

---

## Crítico

### C-01: Imports absolutos quebrados — mypath não resolve módulos
**Arquivos:** múltiplos (`app_factory.py`, `security.py`, `dependencies.py`, `main.py`)  
Mypy reporta 30+ erros `[import-not-found]`. Os imports usam caminhos como `apps.api.auth`, `ia_investing.orchestration.policies` que funcionam em runtime (via PYTHONPATH) mas não são resolvidos pelo type checker sem configuração adequada de path no mypy config.

**Recomendação:** Configurar `mypy.ini` com:
```ini
[mypy]
python_path = src
MYPY_PATH = src
```

Ou usar imports relativos dentro do mesmo pacote (`from .auth import ...`).

---

## Aviso

### W-01: Ruff reporta imports desordenados — 1 arquivo  
**Arquivo:** `src/apps/api/routes/health.py`  
Ruff `[I001]` detecta bloco de imports não ordenado (`database.core` antes de `ia_investing.settings`). Corrigível com `ruff check --fix`.  
*Nota: `worker/main.py` foi substituído pelo overlay Candidate Intelligence e agora tem imports ordenados.*

**Corrigido:** `ruff check --fix` aplicado.

### W-02: Formato inconsistente em `app_factory.py`
**Arquivo:** `src/apps/api/app_factory.py`  
Ruff format reporta que o arquivo precisa ser reformatted — provavelmente tabs vs spaces ou trailing whitespace.

**Corrigido:** `ruff format` aplicado.

### W-03: Função sem return type annotation
**Arquivo:** `src/apps/api/security.py:166`  
A função `require_permission()` não tem return type annotation, violando a política de tipagem estrita do projeto. Deveria retornar `Callable[[str], Callable[..., Awaitable[AuthContext]]]`.

**Corrigido:** Adicionado return type `-> Callable[[AuthContext], Awaitable[AuthContext]]`.

### W-04: Lambda inference failure
**Arquivo:** `src/apps/scheduler/temporal_schedules.py:172`  
Mypy `[misc]` — não consegue inferir tipo do lambda. Adicionar type annotation explícita ao parâmetro ou converter para função named.

**Corrigido:** Substituído lambda por `async def _updater` com parâmetro `_schedule` default bound — resolve mypy + ruff B023 (loop variable capture).

---

## Sugestão

### S-01: Lifespan com imports internos é frágil
**Arquivo:** `src/apps/api/app_factory.py:63-64,70`  
Os imports dentro de `_build_lifespan()` (`_build_oidc_verifier`, `ArtifactLoader`, `close_db`) estão no corpo da função para evitar circular import — mas isso mascara dependências reais e dificulta debugging.

### S-02: `__init__.py` re-exportando tudo sem `__all__`
Múltiplos `__init__.py` fazem imports de submódulos internos (`from apps.worker.main import ...`) que mypy não resolve — o padrão deveria ser usar imports relativos ou declarar explicitamente a API pública.

### S-03: Routers listados manualmente em `_AUTH_ROUTERS`
**Arquivo:** `src/apps/api/app_factory.py:83-107`  
A lista de routers autenticados é manual e longa (23 entradas). Se um novo router for adicionado mas esquecido da lista, ele fica público sem autenticação.

---

## Pontos Positivos

- **Boa separação entre public/authenticated routes** (`_PUBLIC_ROUTERS`, `_AUTH_ROUTERS`)  
- **Lifespan pattern correto** com async context manager para setup/teardown
- **Error handling centralizado** via `install_problem_handlers`

---

## Próximos Passos Sugeridos

1. **Corrigir mypy path configuration (C-01)** — adicionar `python_path = src` ao config  
2. **Rodar `ruff check --fix .` para corrigir imports desordenados** (W-01)
3. **Adicionar return type annotation a `require_permission()`** (W-03)
