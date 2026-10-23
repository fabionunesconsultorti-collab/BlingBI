import os
import json
import subprocess
import logging
from functools import lru_cache

logger = logging.getLogger(__name__)

BASE_VERSION_MAJOR_MINOR = "1.0"
VERSION_FILE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'version_info.json'))

def _parse_commit_message(msg: str) -> dict:
    """
    Classifica a mensagem convencional do commit (ex: 'feat(sync): mensagem').
    Retorna o tipo, escopo, ícone e título formatado.
    """
    clean_msg = (msg or '').strip()
    tag_type = 'update'
    scope = ''
    title = clean_msg
    badge_color = '#64748b'
    icon = '📦'

    lower = clean_msg.lower()
    
    # Detecção de convenção tipo(escopo):
    if lower.startswith('feat'):
        tag_type = 'feat'
        icon = '✨'
        badge_color = '#059669' # Emerald
    elif lower.startswith('fix'):
        tag_type = 'fix'
        icon = '🐛'
        badge_color = '#dc2626' # Red
    elif lower.startswith('perf') or lower.startswith('opt'):
        tag_type = 'perf'
        icon = '⚡'
        badge_color = '#d97706' # Amber
    elif lower.startswith('docs'):
        tag_type = 'docs'
        icon = '📝'
        badge_color = '#2563eb' # Blue
    elif lower.startswith('security') or 'segurança' in lower:
        tag_type = 'security'
        icon = '🔒'
        badge_color = '#7c3aed' # Purple
    elif lower.startswith('refactor'):
        tag_type = 'refactor'
        icon = '♻️'
        badge_color = '#4f46e5' # Indigo
    elif lower.startswith('style'):
        tag_type = 'style'
        icon = '🎨'
        badge_color = '#ec4899' # Pink
    elif lower.startswith('merge'):
        tag_type = 'merge'
        icon = '🔀'
        badge_color = '#64748b'

    # Extrai escopo se houver parenteses (ex: feat(sync): ...)
    if '(' in clean_msg and ')' in clean_msg and clean_msg.find('(') < clean_msg.find(')'):
        start = clean_msg.find('(')
        end = clean_msg.find(')')
        scope = clean_msg[start+1:end].strip()
        # Remove tipo e escopo do título se tiver dois pontos
        colon_pos = clean_msg.find(':')
        if colon_pos > end:
            title = clean_msg[colon_pos+1:].strip()
    elif ':' in clean_msg:
        colon_pos = clean_msg.find(':')
        title = clean_msg[colon_pos+1:].strip()

    return {
        'type': tag_type,
        'type_label': tag_type.upper(),
        'scope': scope,
        'title': title or clean_msg,
        'raw_message': clean_msg,
        'badge_color': badge_color,
        'icon': icon
    }

def _run_git_cmd(args: list[str]) -> str:
    """Executa comando git com captura segura de saída e timeout curto."""
    try:
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
        res = subprocess.run(
            ['git'] + args,
            cwd=base_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=3
        )
        if res.returncode == 0:
            return res.stdout.strip()
    except Exception as e:
        logger.debug(f"[Version] Não foi possível executar git {' '.join(args)}: {e}")
    return ''

def get_git_commit_count() -> int:
    """Retorna o número total de commits do repositório Git."""
    out = _run_git_cmd(['rev-list', '--count', 'HEAD'])
    if out and out.isdigit():
        return int(out)
    return 0

def get_git_short_hash() -> str:
    """Retorna o hash abreviado do último commit."""
    return _run_git_cmd(['rev-parse', '--short', 'HEAD']) or 'latest'

def get_git_changelog(limit=50) -> list[dict]:
    """Retorna a lista estruturada dos últimos commits do repositório."""
    format_str = "%h|%s|%an|%ad"
    date_format = "%d/%m/%Y %H:%M"
    out = _run_git_cmd(['log', f'-n', str(limit), f'--pretty=format:{format_str}', f'--date=format:{date_format}'])
    if not out:
        return []

    commits = []
    lines = out.split('\n')
    for idx, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
        parts = line.split('|', 3)
        if len(parts) >= 4:
            commit_hash, raw_msg, author, commit_date = parts[0], parts[1], parts[2], parts[3]
        elif len(parts) == 3:
            commit_hash, raw_msg, author = parts[0], parts[1], parts[2]
            commit_date = ''
        else:
            continue

        meta = _parse_commit_message(raw_msg)
        commits.append({
            'index': idx + 1,
            'hash': commit_hash,
            'message': meta['title'],
            'raw_message': raw_msg,
            'type': meta['type'],
            'type_label': meta['type_label'],
            'scope': meta['scope'],
            'icon': meta['icon'],
            'badge_color': meta['badge_color'],
            'author': author,
            'date': commit_date,
            'is_latest': (idx == 0)
        })
    return commits

def load_version_cache() -> dict:
    """Carrega as informações de versão do arquivo JSON estático caso o Git não esteja acessível."""
    if os.path.exists(VERSION_FILE_PATH):
        try:
            with open(VERSION_FILE_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"[Version] Erro ao carregar cache de versão: {e}")
    return {}

def save_version_cache(data: dict) -> bool:
    """Grava as informações de versão no arquivo JSON estático para persistência em deploy."""
    try:
        with open(VERSION_FILE_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.warning(f"[Version] Erro ao salvar cache de versão: {e}")
        return False

def is_git_shallow() -> bool:
    """Verifica se o repositório Git local é um shallow clone (ex: Render, CI/CD)."""
    try:
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
        if os.path.exists(os.path.join(base_dir, '.git', 'shallow')):
            return True
        out = _run_git_cmd(['rev-parse', '--is-shallow-repository'])
        if out.lower() == 'true':
            return True
    except Exception:
        pass
    return False

_CACHED_VERSION_DATA = None

def get_version_info(force_refresh: bool = False) -> dict:
    """
    Retorna as informações completas de versão da aplicação.
    A versão é calculada automaticamente como: v{MAJOR}.{MINOR}.{COMMIT_COUNT}
    Garantindo incremento automático a cada commit realizado no repositório.
    Protegido contra clones rasos (shallow clone com --depth 1 no Render/CI).
    Utiliza cache em memória para não penalizar performance das requisições HTTP.
    """
    global _CACHED_VERSION_DATA
    if _CACHED_VERSION_DATA is not None and not force_refresh:
        return _CACHED_VERSION_DATA

    # 1. Carrega dados estáticos versionados no repositório (base confiável)
    cached = load_version_cache() or {}
    cached_count = cached.get('commit_count', 0)
    cached_hash = cached.get('short_hash', '')
    cached_changelog = cached.get('changelog', [])

    # 2. Inspeciona o ambiente Git
    git_count = get_git_commit_count()
    git_hash = get_git_short_hash()
    is_shallow = is_git_shallow() or (0 < git_count < cached_count)

    # 3. Decide a melhor estratégia entre Git e Cache
    if is_shallow or (git_count == 0 and cached_count > 0):
        # No Render ou container com clone raso (--depth 1):
        # O histórico completo do Git não está disponível no disco.
        # Preserva o commit_count e o changelog histórico do cache.
        final_count = cached_count if cached_count > 0 else max(git_count, 1)
        final_hash = git_hash if git_hash and git_hash != 'latest' else (cached_hash or 'prod')

        merged_changelog = list(cached_changelog)
        top_cached_hash = cached_changelog[0].get('hash', '') if cached_changelog else ''

        # Se o commit atual do Git for diferente do commit em cache, temos commits novos
        if git_hash and top_cached_hash and git_hash != top_cached_hash and git_hash != cached_hash:
            git_recent = get_git_changelog(5)
            new_commits = []
            for commit in git_recent:
                c_hash = commit.get('hash', '')
                if c_hash and c_hash != top_cached_hash and not any(item.get('hash') == c_hash for item in merged_changelog):
                    new_commits.append(commit)
                else:
                    break
            if new_commits:
                for commit in reversed(new_commits):
                    merged_changelog.insert(0, commit)
                    final_count += 1
        elif not merged_changelog:
            merged_changelog = get_git_changelog(5)

        # Reindexa os itens do changelog
        for idx, item in enumerate(merged_changelog):
            item['index'] = idx + 1
            item['is_latest'] = (idx == 0)

        version_str = f"{BASE_VERSION_MAJOR_MINOR}.{final_count}"
        info = {
            'version': version_str,
            'tag': f"v{version_str}",
            'commit_count': final_count,
            'short_hash': final_hash,
            'changelog': merged_changelog[:50],
            'total_releases': len(merged_changelog[:50])
        }
        _CACHED_VERSION_DATA = info
        return info

    elif git_count > 0 and git_count >= cached_count:
        # Repositório Git completo (desenvolvimento local):
        # O Git possui o histórico íntegro e atualizado.
        changelog = get_git_changelog(50)
        version_str = f"{BASE_VERSION_MAJOR_MINOR}.{git_count}"
        info = {
            'version': version_str,
            'tag': f"v{version_str}",
            'commit_count': git_count,
            'short_hash': git_hash,
            'changelog': changelog,
            'total_releases': len(changelog)
        }
        try:
            save_version_cache(info)
        except Exception:
            pass
        _CACHED_VERSION_DATA = info
        return info

    elif cached and 'version' in cached:
        # Fallback confiável para o cache estático
        _CACHED_VERSION_DATA = cached
        return cached

    # Fallback padrão mínimo
    default_version = f"{BASE_VERSION_MAJOR_MINOR}.1"
    info = {
        'version': default_version,
        'tag': f"v{default_version}",
        'commit_count': 1,
        'short_hash': git_hash or 'prod',
        'changelog': [],
        'total_releases': 0
    }
    _CACHED_VERSION_DATA = info
    return info
