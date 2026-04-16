# ==============================================================================
# FEATURE DESATIVADA — YouTube download via VPS (Contabo)
# ==============================================================================
#
# PROBLEMA (diagnosticado em 2026-04-15):
#   O IP do servidor Contabo (45.90.123.190) está em blocklist do Google a nível
#   de rede. Todas as tentativas de download via yt-dlp retornam LOGIN_REQUIRED
#   independentemente do cliente usado (web, web_safari, android_vr, mweb).
#
# O QUE FOI TENTADO (sem sucesso):
#   - Cookies de browser exportados → Google invalida imediatamente ao usar de IP diferente
#   - Plugin bgutil-ytdlp-pot-provider v1.3.1 (container brainicism/bgutil-ytdlp-pot-provider)
#     → gera PO Tokens válidos (confirmado nos logs do servidor bgutil), mas o
#     YouTube retorna LOGIN_REQUIRED mesmo assim — o bloqueio é por IP, não por botguard
#   - Múltiplos player_clients (web, web_safari, android_vr, mweb, tvhtml5) → todos falham
#   - yt-dlp com fetch_pot=always → token gerado e enviado, resultado idêntico
#   - OAuth2 (yt-dlp-youtube-oauth2) → plugin obsoleto, client ID bloqueado pelo Google
#
# SOLUÇÃO PROPOSTA para reativar:
#   Opção A (recomendada) — proxy residencial:
#     1. Contratar um serviço de proxy com IPs residenciais (ex: Webshare, Brightdata, Oxylabs)
#     2. Adicionar env var YOUTUBE_PROXY=socks5://user:pass@host:port (ou http://)
#     3. Em acquire(), passar --proxy {proxy_url} para o yt-dlp se YOUTUBE_PROXY estiver definido
#     4. Reativar o card no frontend (remover opacity/pointer-events de index.html)
#
#   Opção B — mudar provedor de VPS:
#     Migrar para DigitalOcean, Hetzner ou Vultr (IPs de datacenter com menor taxa de bloqueio
#     pelo Google). Não é garantido, mas há relatos de sucesso.
#
#   Opção C — serviço externo de download:
#     Usar uma Lambda/Cloud Function em provider residencial apenas para o download do YouTube,
#     recebendo o áudio e encaminhando para o worker transcrever.
#
# INFRAESTRUTURA ATUAL (mantida, só o frontend está desativado):
#   - Container bgutil (brainicism/bgutil-ytdlp-pot-provider:latest) está rodando na porta 4416
#   - yt-dlp configurado em /home/appuser/.config/yt-dlp/config com:
#       --js-runtimes node:/usr/bin/node
#       --extractor-args youtubepot-bgutilhttp:base_url=http://bgutil:4416
#   - Assim que o proxy for configurado, adicionar na linha de comando do acquire():
#       --extractor-args "youtube:fetch_pot=always"
#     para garantir que o bgutil gere o token antes da requisição ao player API
# ==============================================================================

import subprocess
from pathlib import Path
from uuid import uuid4

from transcritor.core.exceptions import SourceUnavailableError

_YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "youtu.be", "m.youtube.com"}


def _is_youtube_url(url: str) -> bool:
    try:
        from urllib.parse import urlparse
        host = urlparse(url).netloc.lower()
        return host in _YOUTUBE_HOSTS
    except Exception:
        return False


class YouTubeSource:
    def __init__(self, url: str, download_dir: Path | None = None, cookies_file: Path | None = None):
        if not _is_youtube_url(url):
            raise ValueError(f"Invalid YouTube URL: {url!r}")
        self._url = url
        self._download_dir = download_dir or Path("/tmp")
        self._cookies_file = Path(cookies_file) if cookies_file else None

    def acquire(self) -> Path:
        uuid_stem = uuid4().hex
        output_template = str(self._download_dir / f"{uuid_stem}.%(ext)s")

        # bgutil-ytdlp-pot-provider is installed and generates PO tokens automatically.
        # No cookies or OAuth needed — the plugin handles bot detection bypass.
        cmd = [
            "yt-dlp",
            "--no-playlist",
            "--format", "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio/best",
            "--output", output_template,
            "--quiet",
            "--no-warnings",
            "--extract-audio",
            "--audio-format", "m4a",
        ]

        cmd.append(self._url)

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                stderr = result.stderr.strip() or result.stdout.strip()
                raise SourceUnavailableError(
                    f"YouTube download unavailable for {self._url}: {stderr}"
                )
            return self._find_downloaded_file(output_template, uuid_stem)
        except SourceUnavailableError:
            raise
        except Exception as e:
            raise SourceUnavailableError(
                f"Failed to download YouTube video {self._url}: {e}"
            ) from e

    def _find_downloaded_file(self, output_template: str, uuid_stem: str) -> Path:
        parent = Path(output_template).parent
        for ext in ("m4a", "mp3", "ogg", "opus", "wav", "webm"):
            candidate = parent / f"{uuid_stem}.{ext}"
            if candidate.exists():
                return candidate
        raise SourceUnavailableError(
            f"Downloaded file not found for template: {output_template}"
        )
