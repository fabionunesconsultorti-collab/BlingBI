import os
import logging
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from app.models.setting import Setting
from app.services.bling_api import BlingApiClient
from app.services.sync_service import SyncService
from app.services.demo_data import seed_demo_data
from app.services.niche_demo_data import NICHE_METADATA, seed_niche_demo_data

logger = logging.getLogger(__name__)
bp = Blueprint('integrations', __name__, url_prefix='/integrations')

@bp.route('/')
def index():
    client_id = Setting.get('bling_client_id', '').strip()
    client_secret = Setting.get('bling_client_secret', '').strip()
    access_token = Setting.get('bling_access_token', '').strip()
    refresh_token = Setting.get('bling_refresh_token', '').strip()
    last_sync = Setting.get('last_sync_date', 'Nunca')
    last_status = Setting.get('last_sync_status', 'Nenhuma sincronização recente')
    demo_active = Setting.get('demo_mode_active', '0') == '1'
    demo_niche_id = Setting.get('demo_niche_id', 'fashion')
    demo_niche_name = Setting.get('demo_niche_name', 'Moda & Vestuário')
    niches = list(NICHE_METADATA.values())

    # Monta a URL de Callback OAuth exatamente como o host atual está servindo
    redirect_uri = request.host_url.rstrip('/') + url_for('integrations.oauth_callback')
    custom_webhook_url = Setting.get('bling_webhook_url', '')
    webhook_url = custom_webhook_url if custom_webhook_url else (request.host_url.rstrip('/') + url_for('integrations.webhook_listener'))

    from app.models.order import Order
    from app.models.product import Product
    from app.models.customer import Customer
    from app.models.financial import FinancialEntry

    orders_count = Order.query.count()
    products_count = Product.query.count()
    customers_count = Customer.query.count()
    finance_count = FinancialEntry.query.count()

    from app.services.tunnel_service import TunnelService
    tunnel_info = TunnelService.get_status()

    return render_template(
        'settings.html',
        client_id=client_id,
        client_secret=client_secret,
        access_token=access_token,
        refresh_token=refresh_token,
        last_sync=last_sync,
        last_status=last_status,
        demo_active=demo_active,
        demo_niche_id=demo_niche_id,
        demo_niche_name=demo_niche_name,
        niches=niches,
        redirect_uri=redirect_uri,
        custom_webhook_url=custom_webhook_url,
        webhook_url=webhook_url,
        tunnel_active=tunnel_info['active'],
        orders_count=orders_count,
        products_count=products_count,
        customers_count=customers_count,
        finance_count=finance_count
    )

@bp.route('/tunnel/start', methods=['POST'])
def start_tunnel_route():
    from app.services.tunnel_service import TunnelService
    success, result = TunnelService.start_tunnel(port=5000)
    if success:
        return jsonify({'success': True, 'url': result, 'message': 'Túnel HTTPS iniciado com sucesso!'})
    return jsonify({'success': False, 'message': result}), 500

@bp.route('/tunnel/stop', methods=['POST'])
def stop_tunnel_route():
    from app.services.tunnel_service import TunnelService
    TunnelService.stop_tunnel()
    return jsonify({'success': True, 'message': 'Túnel encerrado.'})

@bp.route('/tunnel/status', methods=['GET'])
def status_tunnel_route():
    from app.services.tunnel_service import TunnelService
    return jsonify(TunnelService.get_status())

@bp.route('/save-webhook', methods=['POST'])
def save_webhook_url():
    url = request.form.get('webhook_url', '').strip()
    Setting.set('bling_webhook_url', url)
    flash('URL pública HTTPS do Webhook salva com sucesso!', 'success')
    return redirect(url_for('integrations.index'))

@bp.route('/save', methods=['POST'])
def save_settings():
    Setting.set('bling_client_id', request.form.get('client_id', '').strip())
    Setting.set('bling_client_secret', request.form.get('client_secret', '').strip())
    Setting.set('bling_access_token', request.form.get('access_token', '').strip())
    Setting.set('bling_refresh_token', request.form.get('refresh_token', '').strip())

    flash('Credenciais salvas com sucesso!', 'success')
    return redirect(url_for('integrations.index'))

@bp.route('/authorize')
def oauth_authorize():
    """Inicia o fluxo OAuth 2.0 do Bling, redirecionando o usuário para autorização."""
    client_id = Setting.get('bling_client_id', '').strip()
    if not client_id:
        flash('Por favor, informe e salve o Client ID antes de conectar.', 'warning')
        return redirect(url_for('integrations.index'))

    redirect_uri = request.host_url.rstrip('/') + url_for('integrations.oauth_callback')
    client = BlingApiClient()
    auth_url = client.get_authorization_url(redirect_uri)
    
    if not auth_url:
        flash('Erro ao gerar URL de autorização. Verifique seu Client ID.', 'danger')
        return redirect(url_for('integrations.index'))

    logger.info(f"Redirecionando para autorização Bling: {auth_url}")
    return redirect(auth_url)

@bp.route('/callback')
def oauth_callback():
    """Recebe o authorization code retornado pelo Bling e gera os tokens de acesso."""
    code = request.args.get('code', '').strip()
    error = request.args.get('error')

    if error:
        flash(f'Erro na autorização do Bling: {error}', 'danger')
        return redirect(url_for('integrations.index'))

    if not code:
        flash('Código de autorização não recebido do Bling.', 'danger')
        return redirect(url_for('integrations.index'))

    redirect_uri = request.host_url.rstrip('/') + url_for('integrations.oauth_callback')
    client = BlingApiClient()
    logger.info(f"Recebido callback do Bling com code={code[:8]}... Troca de token iniciada.")
    success, message = client.exchange_code_for_token(code, redirect_uri=redirect_uri)

    if success:
        flash('🎉 Conta Bling conectada com sucesso! Token gerado e renovação automática ativada.', 'success')
    else:
        flash(f'{message}', 'danger')

    return redirect(url_for('integrations.index'))

@bp.route('/test-connection', methods=['POST'])
def test_connection():
    client = BlingApiClient()
    success, message = client.test_connection()
    return jsonify({'success': success, 'message': message})

@bp.route('/sync-now', methods=['POST'])
def sync_now():
    data = request.get_json(silent=True) or {}
    options = {
        'customers': bool(data.get('customers', True)),
        'products': bool(data.get('products', True)),
        'orders': bool(data.get('orders', True)),
        'receivables': bool(data.get('receivables', True)),
        'payables': bool(data.get('payables', True)),
    }
    success, result = SyncService.sync_selected(options)
    if success:
        return jsonify({
            'success': True,
            'message': 'Sincronização concluída com sucesso!',
            'details': result
        })
    else:
        return jsonify({
            'success': False,
            'message': f'Falha na sincronização: {result}'
        }), 400

CLEAR_DATABASE_PASSWORD = os.environ.get('CLEAR_DATABASE_PASSWORD', 'c4nib4l')

@bp.route('/demo-niches', methods=['GET'])
def list_demo_niches():
    """Retorna a lista de setores/nichos comerciais disponíveis para demonstração."""
    return jsonify({
        'success': True,
        'niches': list(NICHE_METADATA.values()),
        'current_niche': Setting.get('demo_niche_id', 'fashion')
    })

@bp.route('/seed-demo', methods=['POST'])
def seed_demo():
    try:
        data = request.get_json(silent=True) or {}
        password = data.get('password', '').strip() if request.is_json else request.form.get('password', '').strip()
        niche = (data.get('niche') or request.form.get('niche') or 'fashion').strip().lower()

        if password != CLEAR_DATABASE_PASSWORD:
            return jsonify({
                'success': False,
                'message': 'Senha de segurança incorreta! A base não foi alterada.'
            }), 403

        result = seed_niche_demo_data(niche=niche, clear_first=True)
        flash(f"Base de dados de demonstração ({result['niche_name']}) carregada com sucesso! Todos os dashboards foram populados.", 'success')
        return jsonify({
            'success': True,
            'message': f"Base de demonstração do nicho '{result['niche_name']}' populada com sucesso!",
            'details': result
        })
    except Exception as e:
        logger.error(f"Erro ao popular dados demo do nicho: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@bp.route('/clear-demo', methods=['POST'])
def clear_demo():
    try:
        data = request.get_json(silent=True) or {}
        password = data.get('password', '').strip() if request.is_json else request.form.get('password', '').strip()

        if password != CLEAR_DATABASE_PASSWORD:
            return jsonify({
                'success': False,
                'message': 'Senha de segurança incorreta! A base não foi alterada.'
            }), 403

        from app.services.demo_data import clear_demo_data
        clear_demo_data()
        flash('Base de dados zerada com sucesso! Todos os registros demonstrativos foram removidos e suas credenciais do Bling foram mantidas.', 'success')
        return jsonify({
            'success': True,
            'message': 'Base zerada com sucesso! Todos os registros operacionais foram apagados.'
        })
    except Exception as e:
        logger.error(f"Erro ao zerar base de dados: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@bp.route('/webhook', methods=['POST'])
def webhook_listener():
    """Recebe webhooks do Bling em tempo real."""
    try:
        data = request.get_json(force=True, silent=True)
        if not data:
            return jsonify({'status': 'ignored', 'message': 'No JSON payload'}), 400
        
        event_type = data.get('tipo', 'desconhecido')
        logger.info(f"Webhook recebido do Bling: Tipo={event_type}")

        return jsonify({'status': 'received', 'event': event_type}), 200
    except Exception as e:
        logger.error(f"Erro ao processar Webhook Bling: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500
