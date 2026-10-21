import pytest
from app.core.version import get_version_info, _parse_commit_message, BASE_VERSION_MAJOR_MINOR

def test_parse_commit_message():
    """Valida a categorização de commits com badges, tipos e escopos."""
    # Teste Feat com escopo
    f1 = _parse_commit_message("feat(sync): sincronizacao desacoplada de produtos")
    assert f1['type'] == 'feat'
    assert f1['scope'] == 'sync'
    assert f1['icon'] == '✨'
    assert f1['title'] == 'sincronizacao desacoplada de produtos'

    # Teste Fix sem escopo
    f2 = _parse_commit_message("fix: corrigir erro de conexao")
    assert f2['type'] == 'fix'
    assert f2['scope'] == ''
    assert f2['icon'] == '🐛'
    assert f2['title'] == 'corrigir erro de conexao'

    # Teste Docs
    f3 = _parse_commit_message("docs(readme): atualizar documentacao")
    assert f3['type'] == 'docs'
    assert f3['scope'] == 'readme'
    assert f3['icon'] == '📝'

    # Teste Perf
    f4 = _parse_commit_message("perf: otimizar consultas sql")
    assert f4['type'] == 'perf'
    assert f4['icon'] == '⚡'


def test_get_version_info():
    """Testa geração do objeto de versão e contagem de commits."""
    info = get_version_info()
    assert 'version' in info
    assert 'tag' in info
    assert 'commit_count' in info
    assert 'short_hash' in info
    assert 'changelog' in info
    assert info['tag'].startswith(f"v{BASE_VERSION_MAJOR_MINOR}.")
    assert info['commit_count'] >= 22
    assert len(info['changelog']) > 0

    first = info['changelog'][0]
    assert 'hash' in first
    assert 'message' in first
    assert 'type' in first
    assert 'date' in first


def test_api_changelog_endpoint(client):
    """Testa se o endpoint /api/changelog responde corretamente."""
    res = client.get('/api/changelog')
    assert res.status_code == 200
    data = res.get_json()
    assert 'version' in data
    assert 'tag' in data
    assert 'commit_count' in data
    assert 'changelog' in data


def test_base_template_renders_version_and_modal(client):
    """Verifica se a tela renderiza o botão de versão clicável e a estrutura do modal."""
    res = client.get('/')
    assert res.status_code == 200
    html = res.get_data(as_text=True)

    # Botão no sidebar-footer
    assert 'btnOpenVersionModal' in html
    assert 'openVersionModal()' in html
    assert 'version-tag-pill' in html

    # Rodapé principal do sistema
    assert 'system-main-footer' in html
    assert 'system-version-btn' in html

    # Modal de histórico
    assert 'id="versionChangelogModal"' in html
    assert 'Histórico de Alterações &amp; Versões' in html or 'Histórico de Alterações & Versões' in html
    assert 'changelog-timeline' in html
