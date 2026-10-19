import logging
from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from app.database import db
from app.models.master import MasterUser, PasswordResetToken, MasterSegment
from app.core.tenant_manager import TenantManager

logger = logging.getLogger(__name__)

bp = Blueprint('auth', __name__)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Por favor, faça login para acessar esta página.', 'info')
            return redirect(url_for('auth.login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Acesso restrito. Faça login como administrador.', 'warning')
            return redirect(url_for('auth.login', next=request.url))
        if not session.get('is_admin'):
            flash('Acesso negado! Esta área é exclusiva para o Administrador Geral (admgeral).', 'danger')
            return redirect(url_for('dashboard.index'))
        return f(*args, **kwargs)
    return decorated_function

def requires_segment_screen(screen_name: str):
    """
    Bloqueia acesso a rotas que não pertencem ao segmento do cliente logado.
    O Administrador Geral sempre tem acesso total.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if session.get('is_admin') and not session.get('impersonate_user_id'):
                return f(*args, **kwargs)

            allowed = session.get('allowed_screens', [])
            if screen_name not in allowed:
                flash(f"A tela '{screen_name}' não está disponível para o segmento cadastrado da sua empresa.", 'warning')
                return redirect(url_for('dashboard.index'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        if session.get('is_admin') and not session.get('impersonate_user_id'):
            return redirect(url_for('admin.index'))
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        login_input = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        remember = bool(request.form.get('remember'))

        if not login_input or not password:
            flash('Preencha o usuário/e-mail e a senha.', 'warning')
            return render_template('auth/login.html')

        with TenantManager.master_scope():
            user = MasterUser.query.filter(
                (MasterUser.username == login_input) | (MasterUser.email == login_input)
            ).first()

        if not user or not user.check_password(password):
            flash('Usuário ou senha inválidos. Verifique suas credenciais.', 'danger')
            return render_template('auth/login.html')

        if not user.is_active:
            flash('Esta conta foi desativada pelo Administrador Geral. Entre em contato com o suporte.', 'danger')
            return render_template('auth/login.html')

        # Registra sessão
        session.clear()
        session['user_id'] = user.id
        session['username'] = user.username
        session['email'] = user.email
        session['company_name'] = user.company_name
        session['role'] = user.role
        session['is_admin'] = user.is_admin
        session.permanent = remember

        if user.is_admin:
            flash(f"Bem-vindo, Administrador Geral ({user.username})!", 'success')
            return redirect(url_for('admin.index'))
        else:
            # Configura segmento e permissões do cliente
            session['segment_id'] = user.segment_id
            if user.segment:
                session['segment_name'] = user.segment.name
                session['segment_icon'] = user.segment.icon
                session['allowed_screens'] = user.segment.allowed_screens
                session['allowed_reports'] = user.segment.allowed_reports
                session['allowed_tabs'] = user.segment.allowed_tabs
            else:
                session['segment_name'] = 'Geral'
                session['segment_icon'] = '🏢'
                session['allowed_screens'] = ['dashboard', 'sales', 'products', 'customers', 'finance', 'reports', 'integrations']
                session['allowed_reports'] = ['dre', 'cash_flow', 'rfm', 'stock_coverage', 'multichannel']
                session['allowed_tabs'] = []

            # Configura conexão da base de dados do cliente
            session['tenant_db_uri'] = user.db_uri
            if user.db_uri:
                try:
                    TenantManager.init_tenant_database(user.db_uri)
                except Exception as e:
                    logger.error(f"Erro ao inicializar base do tenant no login: {e}")

            flash(f"Bem-vindo ao BlingBI, {user.company_name}!", 'success')
            next_url = request.args.get('next')
            return redirect(next_url or url_for('dashboard.index'))

    return render_template('auth/login.html')


@bp.route('/logout')
def logout():
    session.clear()
    flash('Você saiu da sua conta com sucesso.', 'info')
    return redirect(url_for('auth.login'))


@bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    """Permite ao usuário autenticado (admgeral ou cliente) alterar sua própria senha."""
    if request.method == 'POST':
        current_password = request.form.get('current_password', '').strip()
        new_password = request.form.get('new_password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()

        if not current_password or not new_password or not confirm_password:
            flash('Todos os campos são obrigatórios.', 'warning')
            return render_template('auth/change_password.html')

        if new_password != confirm_password:
            flash('A nova senha e a confirmação não coincidem.', 'danger')
            return render_template('auth/change_password.html')

        if len(new_password) < 6:
            flash('A nova senha deve possuir pelo menos 6 caracteres.', 'warning')
            return render_template('auth/change_password.html')

        with TenantManager.master_scope():
            user = MasterUser.query.get(session['user_id'])
            if not user or not user.check_password(current_password):
                flash('Senha atual incorreta.', 'danger')
                return render_template('auth/change_password.html')

            user.set_password(new_password)
            db.session.commit()

        flash('Sua senha foi alterada com sucesso!', 'success')
        if session.get('is_admin') and not session.get('impersonate_user_id'):
            return redirect(url_for('admin.index'))
        return redirect(url_for('dashboard.index'))

    return render_template('auth/change_password.html')


@bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Solicita token de recuperação de senha."""
    if request.method == 'POST':
        identifier = request.form.get('identifier', '').strip()
        if not identifier:
            flash('Informe seu usuário ou e-mail cadastrado.', 'warning')
            return render_template('auth/forgot_password.html')

        with TenantManager.master_scope():
            user = MasterUser.query.filter(
                (MasterUser.username == identifier) | (MasterUser.email == identifier)
            ).first()

            if user:
                token_obj = PasswordResetToken.create_token(user, expires_hours=2)
                reset_url = url_for('auth.reset_password', token=token_obj.token, _external=True)

                # Log com destaque para recuperação imediata (Render Logs / Console)
                logger.warning(
                    f"\n============================================================\n"
                    f"🔒 SOLICITAÇÃO DE RECUPERAÇÃO DE SENHA:\n"
                    f"Usuário: {user.username} ({user.email})\n"
                    f"Link de Recuperação (Válido por 2 horas):\n{reset_url}\n"
                    f"============================================================\n"
                )

                flash(
                    f"Instruções geradas com sucesso para {user.email}! "
                    f"O link seguro de recuperação expira em 2 horas.",
                    'info'
                )
                return render_template('auth/forgot_password.html', reset_url=reset_url, username=user.username)
            else:
                flash('Se o usuário ou e-mail existir no sistema, as instruções foram emitidas.', 'info')

    return render_template('auth/forgot_password.html')


@bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    """Redefine a senha através do token seguro."""
    with TenantManager.master_scope():
        token_obj = PasswordResetToken.query.filter_by(token=token, used=False).first()

        if not token_obj or not token_obj.is_valid():
            flash('Este link de recuperação é inválido ou já expirou. Solicite um novo link.', 'danger')
            return redirect(url_for('auth.forgot_password'))

        if request.method == 'POST':
            new_password = request.form.get('new_password', '').strip()
            confirm_password = request.form.get('confirm_password', '').strip()

            if not new_password or not confirm_password:
                flash('Informe a nova senha e confirme-a.', 'warning')
                return render_template('auth/reset_password.html', token=token)

            if new_password != confirm_password:
                flash('As senhas digitadas não coincidem.', 'danger')
                return render_template('auth/reset_password.html', token=token)

            if len(new_password) < 6:
                flash('A senha deve conter no mínimo 6 caracteres.', 'warning')
                return render_template('auth/reset_password.html', token=token)

            user = token_obj.user
            user.set_password(new_password)
            token_obj.used = True
            db.session.commit()

            flash(f"Senha do usuário '{user.username}' redefinida com sucesso! Você já pode entrar com a nova senha.", 'success')
            return redirect(url_for('auth.login'))

    return render_template('auth/reset_password.html', token=token)
