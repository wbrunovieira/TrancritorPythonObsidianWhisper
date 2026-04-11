# Plano de Migração para Arquitetura de Produção

**Projeto:** Transcritor  
**Objetivo:** Migrar de script CLI local para serviço de produção consumível por outros apps no mesmo servidor  
**Abordagem:** TDD — cada implementação começa pelo teste  
**Fluxo de entrega:** ao final de cada fase → commit + push + revisão manual

---

## Contexto e Decisões de Arquitetura

### O que o sistema precisa fazer em produção
- Expor uma REST API HTTP local (`localhost:8000`)
- Outros apps no mesmo servidor consomem via HTTP
- Dois recursos principais: transcrição de áudio e transcrição de vídeo
- Suportar dois tipos de input: upload de arquivo e URL externa (ex: Google Drive signed URL)
- Processar transcrições de forma assíncrona (jobs) — transcrições longas não bloqueiam

### Stack definida
| Componente | Tecnologia |
|---|---|
| API | FastAPI |
| Documentação | Swagger UI — automático via FastAPI em `/docs`, sem lib extra |
| Fila de jobs | Celery + Redis |
| Configuração | pydantic-settings |
| YouTube | yt-dlp (substitui pytube) |
| Testes | pytest + pytest-asyncio + httpx |
| Deploy | Docker Compose |

> **Nota:** CLI (Click) foi descartado. O app é exclusivamente um backend REST.
> Futuramente um frontend pode consumir a mesma API.

### Rotas da API — completas

```
# ── Transcrição de áudio ──────────────────────────────────────────
POST   /transcriptions/audio              # upload de arquivo de áudio
POST   /transcriptions/audio/url          # via URL externa (Google Drive, etc)
POST   /transcriptions/audio/batch        # upload de múltiplos arquivos

# ── Transcrição de vídeo ──────────────────────────────────────────
POST   /transcriptions/video              # upload de arquivo de vídeo
POST   /transcriptions/video/url          # via URL externa ou YouTube (yt-dlp)
POST   /transcriptions/video/batch        # upload de múltiplos vídeos
POST   /transcriptions/video/extract      # só extrai o áudio, sem transcrever

# ── Consulta de jobs ──────────────────────────────────────────────
GET    /transcriptions                    # lista jobs recentes (paginado)
GET    /transcriptions/{job_id}           # status do job
GET    /transcriptions/{job_id}/result    # resultado quando concluído

# ── Infraestrutura ────────────────────────────────────────────────
GET    /health                            # liveness
GET    /ready                             # readiness (Redis + modelo)
```

### Mapeamento: opções originais → rotas

| Opção original | Rota | Situação |
|---|---|---|
| 1. Transcrever áudio | `POST /transcriptions/audio` | ✅ fase 5 |
| 2. Múltiplos áudios | `POST /transcriptions/audio/batch` | 🔲 fase 7 |
| 3. Transcrever vídeo | `POST /transcriptions/video` | ✅ fase 5 |
| 4. Extrair áudio de vídeo | `POST /transcriptions/video/extract` | 🔲 fase 7 |
| 5. Gravar áudio do sistema | — | ⛔ só faz sentido em desktop local |
| 6. Áudio do ambiente local | — | ⛔ incompleto, descartado |
| 7. Analisar voz | — | ⛔ `voice_analysis.py` não existe |
| 8. Todos os vídeos da pasta | `POST /transcriptions/video/batch` | 🔲 fase 7 |
| 10. YouTube | `POST /transcriptions/video/url` | ⚠️ rota existe, yt-dlp na fase 7 |

### Fluxo de um job
```
App externo
  → POST /transcriptions/video/url { "url": "https://..." }
  ← { "job_id": "abc123", "status": "pending" }

  → GET /transcriptions/abc123
  ← { "status": "processing" }

  → GET /transcriptions/abc123
  ← { "status": "done" }

  → GET /transcriptions/abc123/result
  ← { "text": "...", "language": "pt", "duration_seconds": 142.3 }
```

---

## Estrutura de Diretórios Final

```
transcritor/
├── docker-compose.yml
├── Dockerfile
├── .env.example
├── pyproject.toml
├── docs/
│   └── plans/
│       └── production_architecture.md   ← este arquivo
│
├── src/
│   └── transcritor/
│       ├── core/
│       │   ├── models.py           # TranscriptionJob, TranscriptionResult, JobStatus
│       │   └── exceptions.py       # exceções de domínio
│       ├── config.py               # Settings com pydantic-settings
│       ├── engine/
│       │   ├── whisper_engine.py   # WhisperEngine — único lugar que importa torch
│       │   └── registry.py        # get_engine() → singleton por processo worker
│       ├── sources/
│       │   ├── base.py             # Protocol AudioSource: .acquire() -> Path
│       │   ├── file_source.py      # arquivo recebido via upload
│       │   ├── url_source.py       # download de URL externa (Drive, S3, etc)
│       │   ├── video_source.py     # extração de áudio de vídeo via moviepy
│       │   └── system_audio.py     # gravação de sistema — apenas CLI local
│       ├── storage/
│       │   ├── file_store.py       # persistência do resultado em disco
│       │   └── job_store.py        # status dos jobs no Redis
│       ├── services/
│       │   └── transcription_service.py
│       ├── workers/
│       │   ├── celery_app.py
│       │   └── tasks.py
│       ├── api/
│       │   ├── app.py
│       │   ├── dependencies.py
│       │   ├── schemas.py
│       │   └── routers/
│       │       ├── transcriptions.py
│       │       └── health.py
│       └── cli/
│           └── commands.py
│
└── tests/
    ├── conftest.py
    ├── unit/
    ├── integration/
    └── e2e/
```

---

## Regras de TDD neste projeto

1. **Red → Green → Refactor** — escrever o teste que falha, depois o código mínimo para passar, depois refatorar
2. **Nenhum código de produção sem um teste que o justifique**
3. **Testes unitários:** sem I/O real, sem torch, sem Redis — rodam em milissegundos
4. **Testes de integração:** FastAPI real + filesystem real + engine stubado + `CELERY_TASK_ALWAYS_EAGER=True`
5. **Testes e2e:** tudo real, apenas na fase final — rodam em CI no merge
6. **Cobertura mínima por fase:** definida abaixo em cada fase

---

## Fase 1 — Fundação: domínio, configuração e engine

**Objetivo:** estrutura do projeto, modelos de domínio, configuração via env vars e wrapper do Whisper com singleton. Nenhuma funcionalidade exposta ainda, mas a base está testada e sólida.

**O que será construído:**
- `pyproject.toml` substituindo `requirements.txt`
- Estrutura `src/transcritor/` com `__init__.py` em cada pacote
- `core/models.py` — `JobStatus`, `TranscriptionJob`, `TranscriptionResult`
- `core/exceptions.py` — `TranscriptionError`, `UnsupportedFormatError`, `SourceUnavailableError`
- `config.py` — `Settings` com pydantic-settings (substitui o `config.py` atual)
- `engine/whisper_engine.py` — `WhisperEngine` com `load()` e `transcribe()`
- `engine/registry.py` — `get_engine()` singleton

**TDD — testes a escrever primeiro:**
```
tests/unit/
├── test_models.py
│   ├── test_job_status_transitions       # PENDING → PROCESSING → DONE / FAILED
│   ├── test_transcription_result_fields  # campos obrigatórios e opcionais
│   └── test_job_serialization            # serialização JSON correta
│
└── test_whisper_engine.py
    ├── test_transcribe_raises_if_not_loaded   # RuntimeError antes de load()
    ├── test_transcribe_returns_result          # mock do whisper.load_model
    ├── test_get_engine_returns_singleton       # mesma instância em duas chamadas
    └── test_engine_loads_configured_model      # usa Settings.whisper_model
```

**Cobertura esperada:** 100% de `core/` e `engine/`

**Critério de aceite da fase:**
- [ ] `pytest tests/unit/` passa com 0 falhas
- [ ] `get_engine()` retorna singleton — verificado em teste
- [ ] `WhisperEngine.transcribe()` com mock retorna `TranscriptionResult` correto
- [ ] `Settings` lê variáveis de ambiente corretamente
- [ ] Código revisado e push para `main`

---

## Fase 2 — Sources: como o áudio chega ao sistema

**Objetivo:** implementar todas as origens de áudio com TDD. Cada source é independente e testável sem torch ou FFmpeg real.

**O que será construído:**
- `sources/base.py` — `AudioSource` Protocol
- `sources/file_source.py` — recebe `Path` de arquivo já local
- `sources/url_source.py` — baixa de URL externa (requests/httpx)
- `sources/video_source.py` — extrai áudio de vídeo via moviepy
- `sources/system_audio.py` — migração do `system_audio.py` atual (sem alteração de lógica)

**TDD — testes a escrever primeiro:**
```
tests/unit/
├── test_file_source.py
│   ├── test_acquire_returns_path_for_valid_audio
│   ├── test_acquire_raises_unsupported_format      # .xyz, .pdf, etc
│   └── test_acquire_raises_if_file_not_found
│
├── test_url_source.py
│   ├── test_acquire_downloads_file_to_temp_dir     # mock httpx
│   ├── test_acquire_raises_on_http_error           # 403, 404, timeout
│   └── test_acquire_infers_extension_from_content_type
│
└── test_video_source.py
    ├── test_acquire_extracts_audio_to_wav          # mock VideoFileClip
    ├── test_acquire_returns_path_in_audio_dir
    └── test_acquire_raises_on_corrupt_video        # mock lança exceção
```

**Cobertura esperada:** 100% de `sources/` (exceto `system_audio.py` — requer hardware)

**Critério de aceite da fase:**
- [ ] `pytest tests/unit/` passa com 0 falhas
- [ ] Nenhum teste importa `torch`, `whisper` ou `moviepy` diretamente
- [ ] `UnsupportedFormatError` funciona para extensões inválidas em `FileSource`
- [ ] `UrlSource` funciona com mock de URL — sem chamada HTTP real nos testes
- [ ] Código revisado e push para `main`

---

## Fase 3 — Storage e Service: persistência e orquestração

**Objetivo:** implementar a camada de persistência e o serviço que orquestra tudo. O `TranscriptionService` é o coração do sistema — coordena engine, sources e storage sem fazer I/O diretamente.

**O que será construído:**
- `storage/file_store.py` — salva e lê resultados em disco (`.json` + `.md`)
- `storage/job_store.py` — interface sobre Redis para status dos jobs
- `services/transcription_service.py` — `submit_job()`, `get_job()`, `get_result()`

**TDD — testes a escrever primeiro:**
```
tests/unit/
├── test_file_store.py
│   ├── test_save_result_creates_json_file      # tmp_path fixture do pytest
│   ├── test_save_result_creates_markdown_file
│   ├── test_load_result_returns_correct_data
│   └── test_load_result_raises_if_not_found
│
├── test_job_store.py
│   ├── test_save_job_stores_in_redis           # mock Redis
│   ├── test_load_job_returns_correct_status
│   ├── test_update_status_changes_job
│   └── test_load_raises_if_job_not_found
│
└── test_transcription_service.py
    ├── test_submit_job_creates_pending_job     # FakeJobStore, FakeEngine
    ├── test_submit_job_dispatches_to_queue     # verifica task.delay() chamado
    ├── test_get_job_returns_current_status
    ├── test_get_result_raises_if_not_done      # status PENDING ou PROCESSING
    └── test_get_result_returns_text_when_done
```

**Cobertura esperada:** 100% de `storage/` e `services/`

**Critério de aceite da fase:**
- [ ] `pytest tests/unit/` passa com 0 falhas
- [ ] `TranscriptionService` testado com 100% de fakes — zero dependências reais
- [ ] `FileStore` usa `tmp_path` do pytest — nenhum arquivo criado fora do diretório de teste
- [ ] `JobStore` mockado — nenhum Redis necessário para rodar os testes
- [ ] Código revisado e push para `main`

---

## Fase 4 — Workers: Celery e processamento assíncrono

**Objetivo:** implementar o worker Celery que processa os jobs em background. O modelo Whisper é carregado uma única vez na inicialização do worker.

**O que será construído:**
- `workers/celery_app.py` — instância Celery, configuração, `@worker_process_init`
- `workers/tasks.py` — `transcribe_task()` que chama o service

**TDD — testes a escrever primeiro:**
```
tests/unit/
└── test_tasks.py
    ├── test_task_calls_service_with_correct_args   # CELERY_TASK_ALWAYS_EAGER
    ├── test_task_updates_status_to_processing
    ├── test_task_updates_status_to_done_on_success
    └── test_task_updates_status_to_failed_on_error

tests/integration/
└── test_worker_task.py
    ├── test_full_task_with_real_audio_file    # WAV fixture de 3s, modelo real — @pytest.mark.slow
    └── test_task_retry_on_transient_error     # CELERY_TASK_ALWAYS_EAGER + erro simulado
```

**Arquivo de fixture de áudio:**
- `tests/fixtures/sample_audio.wav` — 3 segundos, 8kHz, mono, silêncio ou tom simples
- Gerado programaticamente no `conftest.py` com numpy — sem arquivo binário no repositório

**Cobertura esperada:** 100% de `workers/`

**Critério de aceite da fase:**
- [ ] `pytest tests/unit/` passa com 0 falhas
- [ ] `pytest tests/integration/ -m "not slow"` passa com 0 falhas
- [ ] `transcribe_task` com `ALWAYS_EAGER=True` e engine stubado funciona end-to-end
- [ ] Worker carrega modelo uma vez — verificado por log/mock de `WhisperEngine.load()`
- [ ] Código revisado e push para `main`

---

## Fase 5 — API: FastAPI e as rotas de transcrição

**Objetivo:** expor o serviço via HTTP. A API é uma camada fina sobre o `TranscriptionService` — sem lógica de negócio nas rotas.

**O que será construído:**
- `api/app.py` — instância FastAPI com lifespan
- `api/dependencies.py` — `get_service()`, `get_settings()` via `Depends()`
- `api/schemas.py` — schemas de request/response (separados dos domain models)
- `api/routers/transcriptions.py` — as 6 rotas de transcrição
- `api/routers/health.py` — `/health` e `/ready`

**Schemas de request/response:**
```python
# POST /transcriptions/audio e /transcriptions/video
class FileTranscriptionRequest:   # multipart/form-data
    file: UploadFile

class UrlTranscriptionRequest:    # application/json
    url: HttpUrl

# Resposta de criação de job
class JobCreatedResponse:
    job_id: str
    status: JobStatus

# Resposta de status
class JobStatusResponse:
    job_id: str
    status: JobStatus
    created_at: datetime
    completed_at: datetime | None

# Resposta de resultado
class TranscriptionResultResponse:
    job_id: str
    text: str
    language: str | None
    duration_seconds: float | None
```

**TDD — testes a escrever primeiro:**
```
tests/integration/
└── test_api_transcriptions.py
    # setup: httpx.AsyncClient + override get_service() com FakeService
    #        CELERY_TASK_ALWAYS_EAGER=True
    │
    ├── test_post_audio_upload_returns_202_with_job_id
    ├── test_post_audio_url_returns_202_with_job_id
    ├── test_post_video_upload_returns_202_with_job_id
    ├── test_post_video_url_returns_202_with_job_id
    ├── test_get_job_status_pending
    ├── test_get_job_status_done
    ├── test_get_job_status_404_for_unknown_id
    ├── test_get_result_returns_text_when_done
    ├── test_get_result_returns_409_when_not_done   # job ainda processando
    ├── test_post_audio_unsupported_format_returns_422
    ├── test_health_returns_200
    └── test_ready_returns_503_when_redis_unavailable
```

**Cobertura esperada:** 100% de `api/`

**Critério de aceite da fase:**
- [ ] `pytest tests/integration/` passa com 0 falhas
- [ ] Nenhum teste de integração sobe Redis real ou worker real
- [ ] Documentação automática disponível em `http://localhost:8000/docs` (Swagger)
- [ ] Todos os status HTTP corretos: 202 (criado), 200 (ok), 404 (não encontrado), 409 (conflito), 422 (validação), 503 (serviço indisponível)
- [ ] Código revisado e push para `main`

---

## Fase 6 — Docker: containerização e ambiente de produção

**Objetivo:** empacotar o sistema em containers. A partir desta fase o sistema roda idêntico em qualquer máquina.

**O que será construído:**
- `Dockerfile` — multi-stage: instala dependências, copia código
- `docker-compose.yml` — três serviços: `api`, `worker`, `redis`
- `.env.example` — documenta todas as variáveis de ambiente
- Volume para o modelo do Whisper — não re-baixa a cada deploy

**`docker-compose.yml` (estrutura):**
```yaml
services:
  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data

  api:
    build: .
    command: uvicorn transcritor.api.app:app --host 0.0.0.0 --port 8000
    ports:
      - "8000:8000"
    env_file: .env
    depends_on: [redis]
    volumes:
      - transcriptions_data:/data/transcriptions

  worker:
    build: .
    command: celery -A transcritor.workers.celery_app worker --loglevel=info
    env_file: .env
    depends_on: [redis]
    volumes:
      - whisper_models:/root/.cache/whisper   # modelo persistido entre deploys
      - transcriptions_data:/data/transcriptions

volumes:
  redis_data:
  whisper_models:
  transcriptions_data:
```

**TDD — testes a escrever primeiro:**
```
tests/e2e/
└── test_full_pipeline.py
    # setup: docker-compose up via pytest-docker ou subprocess
    │
    ├── test_health_endpoint_reachable
    ├── test_audio_upload_full_pipeline      # fixture WAV real → poll → texto não vazio
    └── test_video_url_full_pipeline         # URL de vídeo de teste público → poll → texto
```

**Critério de aceite da fase:**
- [ ] `docker-compose up` sobe sem erros
- [ ] `curl http://localhost:8000/health` retorna `200`
- [ ] `curl http://localhost:8000/ready` retorna `200` com Redis rodando
- [ ] Upload de arquivo de áudio via API processa e retorna transcrição
- [ ] Modelo do Whisper não é re-baixado em `docker-compose down && up`
- [ ] `pytest tests/e2e/ -m e2e` passa com ambiente Docker rodando
- [ ] Código revisado e push para `main`

---

## Fase 7 — Rotas completas do backend

> **CLI (Click) descartado.** O app é um backend puro — todas as funcionalidades
> são expostas via rotas REST. Futuramente um frontend consumirá esta API.

**Objetivo:** cobrir todas as operações que existiam no menu original como rotas HTTP.
Deletar o código legado do menu.

**O que será construído:**

- `api/routers/transcriptions.py` — novas rotas:
  - `POST /transcriptions/audio/batch` — múltiplos uploads de áudio
  - `POST /transcriptions/video/batch` — múltiplos uploads de vídeo
  - `POST /transcriptions/video/extract` — extrai áudio sem transcrever
  - `GET  /transcriptions` — lista jobs recentes (paginado, `?limit=20&offset=0`)
- `sources/youtube.py` — yt-dlp substituindo pytube quebrado
- Deletar código morto: `main.py`, `menu.py`, `utils.py`, `youtube_downloader.py`

**Novas rotas em detalhe:**

```
POST /transcriptions/audio/batch
  body: multipart com N arquivos
  response: { "jobs": [{ "job_id": "...", "filename": "...", "status": "pending" }] }

POST /transcriptions/video/batch
  body: multipart com N vídeos
  response: { "jobs": [...] }

POST /transcriptions/video/extract
  body: multipart (arquivo) ou JSON { "url": "..." }
  response: { "job_id": "...", "status": "pending" }
  # o resultado em /result retorna { "audio_path": "..." } ao invés de texto

GET /transcriptions?limit=20&offset=0
  response: { "items": [...], "total": N, "limit": 20, "offset": 0 }
```

**TDD — testes a escrever primeiro:**
```
tests/integration/
└── test_api_batch.py
    ├── test_audio_batch_returns_202_with_job_list
    ├── test_audio_batch_creates_one_job_per_file
    ├── test_video_batch_returns_202_with_job_list
    ├── test_video_extract_returns_202
    ├── test_list_jobs_returns_paginated_results
    ├── test_list_jobs_respects_limit_param
    └── test_youtube_url_dispatches_video_url_source
```

**Critério de aceite da fase:**
- [ ] `pytest tests/unit/ tests/integration/` passa com 0 falhas
- [ ] `POST /transcriptions/audio/batch` com 3 arquivos retorna 3 job_ids
- [ ] `POST /transcriptions/video/url` com link do YouTube cria job (yt-dlp)
- [ ] `GET /transcriptions` retorna lista paginada
- [ ] `main.py`, `menu.py`, `utils.py`, `youtube_downloader.py` deletados
- [ ] Swagger em `/docs` mostra todas as rotas documentadas
- [ ] Código revisado e push para `main`

---

## Fase 8 — Logging e hardening

**Objetivo:** logging estruturado, tratamento de erros consistente e atualização da documentação.

**O que será feito:**
- Substituir todos os `print()` restantes por `logging` estruturado (stdlib logging com formato JSON em produção)
- Garantir que todas as exceções retornam mensagens úteis na API (sem stack traces expostos)
- Atualizar `CLAUDE.md` com a arquitetura final completa
- Revisar `pyproject.toml` — remover deps não utilizados após deleção do código legado

**Critério de aceite da fase:**
- [ ] Nenhum `print()` no código de produção (`src/`)
- [ ] Erros da API retornam JSON estruturado: `{ "detail": "mensagem clara" }`
- [ ] `pytest` (todas as suites exceto e2e) passa sem falhas
- [ ] `pytest tests/e2e/ -m e2e` passa com Docker rodando
- [ ] `CLAUDE.md` atualizado com arquitetura final
- [ ] Código revisado e push para `main`

---

## Resumo das fases

| Fase | Entrega | Testes |
|---|---|---|
| 1 | Domínio, config, engine Whisper | Unit: models, engine |
| 2 | Sources (file, url, video) | Unit: todos os sources |
| 3 | Storage, TranscriptionService | Unit: store, service |
| 4 | Workers Celery | Unit + Integration: tasks |
| 5 | API FastAPI com todas as rotas | Integration: todos os endpoints |
| 6 | Docker, ambiente de produção | E2E: pipeline completo |
| 7 | CLI Click | Unit: comandos |
| 8 | Limpeza, YouTube, logging | Todas as suites |

---

## Convenções de commit por fase

```
feat(phase-1): add domain models and whisper engine singleton
feat(phase-2): add audio sources (file, url, video)
feat(phase-3): add storage layer and transcription service
feat(phase-4): add celery workers and async job processing
feat(phase-5): add fastapi with transcription routes
feat(phase-6): add docker compose for production deployment
feat(phase-7): replace interactive menu with click cli
feat(phase-8): add youtube support, structured logging, cleanup
```

---

*Documento criado em: 2026-04-11*  
*Atualizar este documento ao final de cada fase com o que mudou em relação ao planejado.*
