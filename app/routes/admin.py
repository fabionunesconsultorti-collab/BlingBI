import os
import logging
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify, send_file
from werkzeug.utils import secure_filename
from app.database import db
from app.models.master import MasterUser, MasterSegment, MasterBackupRecord, MasterBackupConfig
from app.routes.auth import admin_required
from app.core.tenant_manager import TenantManager
from app.core.feature_registry import FEATURES_CATALOG
from app.reports.registry import report_registry
from app.services.backup_service import BackupService

logger = logging.getLogger(__name__)

bp = Blueprint('admin', __name__, url_prefix='/admin')

ALL_SCREENS = [
    {'id': 'dashboard', 'name': 'Dashboard 360°', 'icon': '📊', 'desc': 'Painel executivo com cards de KPIs, gráficos e ranking de vendas.'},
    {'id': 'sales', 'name': 'Vendas & Pedidos', 'icon': '🛒', 'desc': 'Análise de pedidos, canais de venda, vendedores e malas condicionais.'},
    {'id': 'products', 'name': 'Produtos & Estoque', 'icon': '📦', 'desc': 'Catálogo de itens, Curva ABC, cobertura de dias de estoque e devoluções.'},
    {'id': 'customers', 'name': 'Clientes & CRM', 'icon': '👥', 'desc': 'Base de clientes, Segmentação RFM, curva ABC de clientes e pós-venda NPS.'},
    {'id': 'finance', 'name': 'Financeiro & DRE', 'icon': '💰', 'desc': 'Contas a pagar/receber, DRE Gerencial, fluxo de caixa e aging list.'},
    {'id': 'fashion', 'name': 'Moda & Vestuário', 'icon': '👗', 'desc': 'Módulo especializado para lojas de vestuário, malas consignadas e trocas.'},
    {'id': 'reports', 'name': 'Central de Relatórios', 'icon': '📑', 'desc': 'Hub de relatórios analíticos dinâmicos com exportação Excel e PDF.'},
    {'id': 'integrations', 'name': 'Configurar API & Bling', 'icon': '⚙️', 'desc': 'Conexão OAuth 2.0 com Bling ERP, sincronização e webhooks.'}
]

@bp.route('')
@bp.route('/')
@admin_required
def index():
    """Dashboard de visão geral da administração geral."""
    with TenantManager.master_scope():
        total_clients = MasterUser.query.filter_by(role='client').count()
        active_clients = MasterUser.query.filter_by(role='client', is_active=True).count()
        inactive_clients = total_clients - active_clients
        total_segments = MasterSegment.query.count()
        recent_clients = MasterUser.query.filter_by(role='client').order_by(MasterUser.created_at.desc()).limit(8).all()
        segments = MasterSegment.query.order_by(MasterSegment.name).all()

    return render_template(
        'admin/dashboard.html',
        total_clients=total_clients,
        active_clients=active_clients,
        inactive_clients=inactive_clients,
        total_segments=total_segments,
        recent_clients=recent_clients,
        segments=segments
    )


@bp.route('/clients')
@admin_required
def clients_list():
    """Lista todos os clientes/empresas cadastrados."""
    with TenantManager.master_scope():
        search = request.args.get('q', '').strip()
        segment_filter = request.args.get('segment', '').strip()
        
        query = MasterUser.query.filter_by(role='client')
        if search:
            query = query.filter(
                (MasterUser.company_name.ilike(f"%{search}%")) |
                (MasterUser.username.ilike(f"%{search}%")) |
                (MasterUser.email.ilike(f"%{search}%"))
            )
        if segment_filter:
            query = query.filter_by(segment_id=int(segment_filter))

        clients = query.order_by(MasterUser.company_name.asc()).all()
        segments = MasterSegment.query.order_by(MasterSegment.name).all()

    return render_template(
        'admin/clients.html',
        clients=clients,
        segments=segments,
        search=search,
        segment_filter=segment_filter
    )


@bp.route('/clients/new', methods=['GET', 'POST'])
@admin_required
def client_create():
    """Cadastra um novo cliente com sua respectiva base de dados e segmento."""
    with TenantManager.master_scope():
        segments = MasterSegment.query.order_by(MasterSegment.name).all()

        if request.method == 'POST':
            username = request.form.get('username', '').strip().lower()
            email = request.form.get('email', '').strip().lower()
            password = request.form.get('password', '').strip()
            company_name = request.form.get('company_name', '').strip()
            segment_id = request.form.get('segment_id', type=int)
            db_type = request.form.get('db_type', 'sqlite').strip()
            custom_uri = request.form.get('db_uri', '').strip()
            seed_data = bool(request.form.get('seed_data'))

            # Validações
            if not username or not email or not password or not company_name:
                flash('Preencha todos os campos obrigatórios (Usuário, E-mail, Senha e Nome da Empresa).', 'warning')
                return render_template('admin/client_form.html', segments=segments, client=None)

            if len(password) < 6:
                flash('A senha deve conter no mínimo 6 caracteres.', 'warning')
                return render_template('admin/client_form.html', segments=segments, client=None)

            # Verifica unicidade
            existing_user = MasterUser.query.filter(
                (MasterUser.username == username) | (MasterUser.email == email)
            ).first()
            if existing_user:
                flash('Já existe um usuário cadastrado com este nome de usuário ou e-mail.', 'danger')
                return render_template('admin/client_form.html', segments=segments, client=None)

            # Resolve a URI da base de dados do cliente
            if db_type == 'sqlite':
                resolved_db_uri = TenantManager.build_sqlite_tenant_uri(username)
            else:
                if not custom_uri:
                    flash('Para conexão externa personalizada, a String de Conexão (URI) é obrigatória.', 'warning')
                    return render_template('admin/client_form.html', segments=segments, client=None)
                resolved_db_uri = custom_uri

            # Cria o cliente no Master DB
            new_client = MasterUser(
                username=username,
                email=email,
                company_name=company_name,
                role='client',
                segment_id=segment_id,
                db_type=db_type,
                db_uri=resolved_db_uri,
                is_active=True
            )
            new_client.set_password(password)
            db.session.add(new_client)
            db.session.commit()

            # Inicializa as tabelas na base dedicada do novo cliente
            try:
                TenantManager.init_tenant_database(resolved_db_uri)
                if seed_data and new_client.segment:
                    TenantManager.seed_tenant_data(resolved_db_uri, niche=new_client.segment.slug)
                flash(f"🎉 Cliente '{company_name}' cadastrado com sucesso e base de dados criada!", 'success')
            except Exception as e:
                logger.error(f"Erro ao inicializar base do novo cliente {username}: {e}", exc_info=True)
                flash(f"Cliente criado, mas houve um aviso na inicialização da base: {e}", 'warning')

            return redirect(url_for('admin.clients_list'))

    return render_template('admin/client_form.html', segments=segments, client=None)


@bp.route('/clients/<int:client_id>/edit', methods=['GET', 'POST'])
@admin_required
def client_edit(client_id):
    """Edição dos dados cadastrais, segmento, base de dados e redefinição de senha do cliente."""
    with TenantManager.master_scope():
        client = MasterUser.query.get_or_404(client_id)
        if client.role == 'admin':
            flash('O usuário Administrador Geral deve ser editado no seu próprio perfil.', 'warning')
            return redirect(url_for('admin.clients_list'))

        segments = MasterSegment.query.order_by(MasterSegment.name).all()

        if request.method == 'POST':
            client.company_name = request.form.get('company_name', '').strip()
            client.email = request.form.get('email', '').strip().lower()
            client.segment_id = request.form.get('segment_id', type=int)
            client.is_active = bool(request.form.get('is_active'))
            
            # Atualização de Base de Dados
            db_type = request.form.get('db_type', 'sqlite').strip()
            custom_uri = request.form.get('db_uri', '').strip()
            client.db_type = db_type
            if db_type == 'sqlite':
                if not client.db_uri or 'sqlite' not in client.db_uri:
                    client.db_uri = TenantManager.build_sqlite_tenant_uri(client.username)
            else:
                if custom_uri:
                    client.db_uri = custom_uri

            # Redefinição direta de senha pelo administrador
            new_password = request.form.get('new_password', '').strip()
            if new_password:
                if len(new_password) < 6:
                    flash('A nova senha deve ter no mínimo 6 caracteres.', 'warning')
                    return render_template('admin/client_form.html', segments=segments, client=client)
                client.set_password(new_password)
                flash(f"A senha de acesso de '{client.company_name}' foi atualizada!", 'info')

            db.session.commit()
            flash(f"Dados da empresa '{client.company_name}' atualizados com sucesso!", 'success')
            return redirect(url_for('admin.clients_list'))

    return render_template('admin/client_form.html', segments=segments, client=client)


@bp.route('/clients/<int:client_id>/toggle-status', methods=['POST'])
@admin_required
def client_toggle_status(client_id):
    """Ativa ou desativa o acesso de um cliente."""
    with TenantManager.master_scope():
        client = MasterUser.query.get_or_404(client_id)
        if client.role == 'admin':
            return jsonify({'success': False, 'message': 'Não é permitido desativar o Administrador Geral.'}), 400

        client.is_active = not client.is_active
        db.session.commit()

        status_str = "ativado" if client.is_active else "desativado"
        return jsonify({
            'success': True,
            'is_active': client.is_active,
            'message': f"Cliente '{client.company_name}' {status_str} com sucesso!"
        })


@bp.route('/clients/<int:client_id>/test-connection', methods=['POST'])
@admin_required
def client_test_connection(client_id):
    """Testa a conexão com o banco de dados do cliente."""
    with TenantManager.master_scope():
        client = MasterUser.query.get_or_404(client_id)
        if not client.db_uri:
            return jsonify({'success': False, 'message': 'Nenhuma base de dados configurada para este cliente.'})

        success, message = TenantManager.test_connection(client.db_uri)
        return jsonify({'success': success, 'message': message})


@bp.route('/clients/<int:client_id>/impersonate')
@admin_required
def client_impersonate(client_id):
    """Permite ao admgeral auditar e visualizar o BI exatamente como o cliente selecionado."""
    with TenantManager.master_scope():
        client = MasterUser.query.get_or_404(client_id)
        if client.role == 'admin':
            flash('Você já é o Administrador Geral.', 'info')
            return redirect(url_for('admin.index'))

        session['impersonate_user_id'] = client.id
        session['impersonate_username'] = client.username
        session['impersonate_company_name'] = client.company_name
        session['impersonate_tenant_uri'] = client.db_uri
        
        if client.segment:
            session['impersonate_segment_name'] = client.segment.name
            session['impersonate_segment_icon'] = client.segment.icon
            session['allowed_screens'] = client.segment.allowed_screens
            session['allowed_reports'] = client.segment.allowed_reports
            session['allowed_tabs'] = client.segment.allowed_tabs
        else:
            session['impersonate_segment_name'] = 'Geral'
            session['impersonate_segment_icon'] = '🏢'
            session['allowed_screens'] = ['dashboard', 'sales', 'products', 'customers', 'finance', 'reports', 'integrations']
            session['allowed_reports'] = ['dre', 'cash_flow', 'rfm', 'stock_coverage', 'multichannel']
            session['allowed_tabs'] = []

        flash(
            f"🔍 Modo de Auditoria Ativado: Você está navegando como '{client.company_name}'. "
            f"As telas e dados exibidos correspondem à base e segmento deste cliente.",
            'warning'
        )
        return redirect(url_for('dashboard.index'))


@bp.route('/impersonate/exit')
@admin_required
def impersonate_exit():
    """Sai do modo de impersonate e volta à visão do Administrador Geral."""
    session.pop('impersonate_user_id', None)
    session.pop('impersonate_username', None)
    session.pop('impersonate_company_name', None)
    session.pop('impersonate_tenant_uri', None)
    session.pop('impersonate_segment_name', None)
    session.pop('impersonate_segment_icon', None)
    session.pop('allowed_screens', None)
    session.pop('allowed_reports', None)
    session.pop('allowed_tabs', None)

    flash('Modo de auditoria encerrado. Você retornou ao Painel do Administrador Geral.', 'info')
    return redirect(url_for('admin.clients_list'))


# =============================================================================
# GESTÃO DE SEGMENTOS E TELAS
# =============================================================================

@bp.route('/segments')
@admin_required
def segments_list():
    """Lista todos os segmentos cadastrados com suas telas e relatórios liberados."""
    with TenantManager.master_scope():
        segments = MasterSegment.query.order_by(MasterSegment.name.asc()).all()

    return render_template(
        'admin/segments.html',
        segments=segments,
        all_screens=ALL_SCREENS
    )


@bp.route('/segments/new', methods=['GET', 'POST'])
@admin_required
def segment_create():
    """Criação de um novo segmento com mapeamento de telas e relatórios."""
    all_reports = report_registry.get_all()

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        slug = request.form.get('slug', '').strip().lower()
        icon = request.form.get('icon', '📊').strip()
        description = request.form.get('description', '').strip()

        selected_screens = request.form.getlist('screens')
        selected_reports = request.form.getlist('reports')

        if not name or not slug:
            flash('Informe o Nome e o Identificador (Slug) do segmento.', 'warning')
            return render_template('admin/segment_form.html', segment=None, all_screens=ALL_SCREENS, all_reports=all_reports)

        with TenantManager.master_scope():
            existing = MasterSegment.query.filter(
                (MasterSegment.name == name) | (MasterSegment.slug == slug)
            ).first()
            if existing:
                flash('Já existe um segmento com este nome ou identificador.', 'danger')
                return render_template('admin/segment_form.html', segment=None, all_screens=ALL_SCREENS, all_reports=all_reports)

            seg = MasterSegment(
                name=name,
                slug=slug,
                icon=icon or '📊',
                description=description
            )
            seg.allowed_screens = selected_screens
            seg.allowed_reports = selected_reports
            db.session.add(seg)
            db.session.commit()

        flash(f"🎉 Segmento '{name}' criado com sucesso!", 'success')
        return redirect(url_for('admin.segments_list'))

    return render_template('admin/segment_form.html', segment=None, all_screens=ALL_SCREENS, all_reports=all_reports)


@bp.route('/segments/<int:segment_id>/edit', methods=['GET', 'POST'])
@admin_required
def segment_edit(segment_id):
    """Edita nome, telas e relatórios associados a um segmento."""
    with TenantManager.master_scope():
        segment = MasterSegment.query.get_or_404(segment_id)
        all_reports = report_registry.get_all()

        if request.method == 'POST':
            segment.name = request.form.get('name', '').strip()
            segment.icon = request.form.get('icon', '📊').strip()
            segment.description = request.form.get('description', '').strip()
            
            segment.allowed_screens = request.form.getlist('screens')
            segment.allowed_reports = request.form.getlist('reports')

            db.session.commit()
            flash(f"Segmento '{segment.name}' atualizado com sucesso! As permissões foram sincronizadas.", 'success')
            return redirect(url_for('admin.segments_list'))

    return render_template('admin/segment_form.html', segment=segment, all_screens=ALL_SCREENS, all_reports=all_reports)


# ==============================================================================
# GESTÃO DE CONTINGÊNCIA, BACKUP GERAL E RESTAURAÇÃO
# ==============================================================================

@bp.route('/backups')
@admin_required
def backups_index():
    """Painel principal de contingência, gerenciamento de backups e restauração."""
    BackupService.check_and_run_scheduled_backup()

    with TenantManager.master_scope():
        config = MasterBackupConfig.get_or_create()
        records = MasterBackupRecord.query.order_by(MasterBackupRecord.created_at.desc()).all()
        
        total_backups = len(records)
        total_size_bytes = sum(r.filesize_bytes or 0 for r in records)
        
        if total_size_bytes < 1024 * 1024:
            total_size_formatted = f"{total_size_bytes / 1024:.1f} KB"
        else:
            total_size_formatted = f"{total_size_bytes / (1024 * 1024):.2f} MB"

    return render_template(
        'admin/backups.html',
        records=records,
        config=config,
        total_backups=total_backups,
        total_size_formatted=total_size_formatted
    )


@bp.route('/backups/create', methods=['POST'])
@admin_required
def backup_create():
    """Dispara a geração manual e imediata de um backup geral compactado em ZIP."""
    notes = request.form.get('notes', '').strip() or 'Backup manual disparado pelo painel'
    try:
        record = BackupService.create_backup(backup_type='manual', notes=notes)
        flash(f"🎉 Backup '{record.filename}' ({record.filesize_formatted}) gerado com sucesso!", 'success')
    except Exception as e:
        logger.error(f"Erro ao gerar backup manual: {e}", exc_info=True)
        flash(f"Erro ao gerar backup: {str(e)}", 'danger')

    return redirect(url_for('admin.backups_index'))


@bp.route('/backups/config', methods=['POST'])
@admin_required
def backup_save_config():
    """Atualiza a política de agendamento automático, retenção e componentes de backup."""
    with TenantManager.master_scope():
        config = MasterBackupConfig.get_or_create()
        
        config.auto_backup_enabled = bool(request.form.get('auto_backup_enabled'))
        config.frequency = request.form.get('frequency', 'daily')
        config.preferred_hour = int(request.form.get('preferred_hour', 3))
        config.interval_hours = int(request.form.get('interval_hours', 24))
        config.max_backups_to_keep = max(1, min(100, int(request.form.get('max_backups_to_keep', 10))))
        
        config.include_master = bool(request.form.get('include_master'))
        config.include_tenants = bool(request.form.get('include_tenants'))
        config.include_settings = bool(request.form.get('include_settings'))
        
        config.next_backup_at = BackupService.calculate_next_run(config)
        db.session.commit()

    flash("Configurações de rotina de backup salvas com sucesso!", 'success')
    return redirect(url_for('admin.backups_index'))


@bp.route('/backups/download/<filename>')
@admin_required
def backup_download(filename):
    """Download do arquivo .zip de backup."""
    safe_name = secure_filename(filename)
    filepath = os.path.join(BackupService.get_backups_dir(), safe_name)
    if not os.path.isfile(filepath):
        flash('Arquivo de backup não encontrado no servidor.', 'danger')
        return redirect(url_for('admin.backups_index'))

    return send_file(
        filepath,
        mimetype='application/zip',
        as_attachment=True,
        download_name=safe_name
    )


@bp.route('/backups/restore/<filename>', methods=['POST'])
@admin_required
def backup_restore(filename):
    """Restaura o sistema a partir de um arquivo de backup existente no servidor."""
    safe_name = secure_filename(filename)
    filepath = os.path.join(BackupService.get_backups_dir(), safe_name)
    restore_mode = request.form.get('restore_mode', 'full')

    confirmation = request.form.get('confirmation', '').strip().upper()
    if confirmation != 'RESTAURAR':
        flash("Para confirmar a restauração, digite 'RESTAURAR' no campo de verificação.", 'warning')
        return redirect(url_for('admin.backups_index'))

    success, msg, stats = BackupService.restore_backup(filepath, restore_mode=restore_mode)
    if success:
        flash(f"🎉 {msg}", 'success')
    else:
        flash(f"❌ {msg}", 'danger')

    return redirect(url_for('admin.backups_index'))


@bp.route('/backups/upload-restore', methods=['POST'])
@admin_required
def backup_upload_restore():
    """Permite fazer upload de um arquivo .zip de backup externo e restaurar imediatamente."""
    file = request.files.get('backup_file')
    if not file or not file.filename:
        flash('Nenhum arquivo de backup selecionado.', 'warning')
        return redirect(url_for('admin.backups_index'))

    safe_name = secure_filename(file.filename)
    if not safe_name.lower().endswith('.zip'):
        flash('Formato inválido. Selecione um arquivo compactado (.zip).', 'danger')
        return redirect(url_for('admin.backups_index'))

    confirmation = request.form.get('confirmation', '').strip().upper()
    if confirmation != 'RESTAURAR':
        flash("Para confirmar a restauração por upload, digite 'RESTAURAR' no campo de verificação.", 'warning')
        return redirect(url_for('admin.backups_index'))

    restore_mode = request.form.get('restore_mode', 'full')
    dest_path = os.path.join(BackupService.get_backups_dir(), f"uploaded_{safe_name}")
    file.save(dest_path)

    try:
        filesize = os.path.getsize(dest_path)
        sha256 = BackupService.calculate_file_sha256(dest_path)
        with TenantManager.master_scope():
            rec = MasterBackupRecord(
                filename=f"uploaded_{safe_name}",
                filepath=dest_path,
                filesize_bytes=filesize,
                backup_type='uploaded',
                status='success',
                sha256=sha256,
                notes='Backup importado via upload pelo Administrador Geral'
            )
            db.session.add(rec)
            db.session.commit()
    except Exception as e:
        logger.warning(f"Erro ao registrar backup importado: {e}")

    success, msg, stats = BackupService.restore_backup(dest_path, restore_mode=restore_mode)
    if success:
        flash(f"🎉 {msg}", 'success')
    else:
        flash(f"❌ {msg}", 'danger')

    return redirect(url_for('admin.backups_index'))


@bp.route('/backups/delete/<filename>', methods=['POST'])
@admin_required
def backup_delete(filename):
    """Exclui um arquivo de backup do servidor e do histórico."""
    safe_name = secure_filename(filename)
    filepath = os.path.join(BackupService.get_backups_dir(), safe_name)

    try:
        if os.path.isfile(filepath):
            os.remove(filepath)

        with TenantManager.master_scope():
            rec = MasterBackupRecord.query.filter_by(filename=safe_name).first()
            if rec:
                db.session.delete(rec)
                db.session.commit()

        flash(f"Backup '{safe_name}' excluído com sucesso.", 'info')
    except Exception as e:
        logger.error(f"Erro ao excluir backup: {e}")
        flash(f"Erro ao excluir backup: {str(e)}", 'danger')

    return redirect(url_for('admin.backups_index'))

