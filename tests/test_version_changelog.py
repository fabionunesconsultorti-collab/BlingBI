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


def test_shallow_clone_resilience(monkeypatch):
    """
    Testa que um clone raso (--depth 1) como no Render ou CI
    não reseta o commit_count para 1 nem apaga o histórico do changelog.
    """
    from unittest.mock import patch
    import app.core.version as ver_module

    # Mock de ambiente Render: is_shallow=True, git_count=1
    fake_cached = {
        'version': '1.0.29',
        'tag': 'v1.0.29',
        'commit_count': 29,
        'short_hash': '8115410',
        'changelog': [
            {'index': 1, 'hash': '8115410', 'message': 'commit recente', 'type': 'fix', 'badge_color': '#dc2626', 'icon': '🐛', 'author': 'Fabio', 'date': '22/10/2026', 'is_latest': True},
            {'index': 2, 'hash': 'd98e556', 'message': 'commit anterior', 'type': 'feat', 'badge_color': '#059669', 'icon': '✨', 'author': 'Fabio', 'date': '22/10/2026', 'is_latest': False}
        ],
        'total_releases': 2
    }

    with patch.object(ver_module, 'is_git_shallow', return_value=True), \
         patch.object(ver_module, 'get_git_commit_count', return_value=1), \
         patch.object(ver_module, 'get_git_short_hash', return_value='8115410'), \
         patch.object(ver_module, 'load_version_cache', return_value=fake_cached):
        
        info = ver_module.get_version_info(force_refresh=True)
        assert info['commit_count'] == 29
        assert info['version'] == '1.0.29'
        assert info['tag'] == 'v1.0.29'
        assert len(info['changelog']) == 2
        assert info['changelog'][0]['hash'] == '8115410'


def test_shallow_clone_merges_new_unseen_commit(monkeypatch):
    """
    Testa que se houver um commit mais recente no git raso que ainda
    não estava no cache, ele é anexado no topo e incrementa a versão.
    """
    from unittest.mock import patch
    import app.core.version as ver_module

    fake_cached = {
        'version': '1.0.29',
        'tag': 'v1.0.29',
        'commit_count': 29,
        'short_hash': '8115410',
        'changelog': [
            {'index': 1, 'hash': '8115410', 'message': 'commit anterior', 'type': 'fix', 'badge_color': '#dc2626', 'icon': '🐛', 'author': 'Fabio', 'date': '22/10/2026', 'is_latest': True}
        ],
        'total_releases': 1
    }

    new_commit_from_git = [
        {'index': 1, 'hash': '9999999', 'message': 'novo commit em deploy', 'raw_message': 'feat: novo commit em deploy', 'type': 'feat', 'type_label': 'FEAT', 'scope': '', 'icon': '✨', 'badge_color': '#059669', 'author': 'Fabio', 'date': '23/10/2026', 'is_latest': True}
    ]

    with patch.object(ver_module, 'is_git_shallow', return_value=True), \
         patch.object(ver_module, 'get_git_commit_count', return_value=1), \
         patch.object(ver_module, 'get_git_short_hash', return_value='9999999'), \
         patch.object(ver_module, 'get_git_changelog', return_value=new_commit_from_git), \
         patch.object(ver_module, 'load_version_cache', return_value=fake_cached):
        
        info = ver_module.get_version_info(force_refresh=True)
        assert info['commit_count'] == 30
        assert info['version'] == '1.0.30'
        assert info['tag'] == 'v1.0.30'
        assert len(info['changelog']) == 2
        assert info['changelog'][0]['hash'] == '9999999'
        assert info['changelog'][0]['is_latest'] is True
        assert info['changelog'][1]['hash'] == '8115410'
        assert info['changelog'][1]['is_latest'] is False

