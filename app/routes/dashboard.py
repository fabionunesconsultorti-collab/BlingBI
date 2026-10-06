from flask import Blueprint, render_template, request
from app.services.bi_analytics import BiAnalytics
from app.models.setting import Setting

bp = Blueprint('dashboard', __name__)

@bp.route('/')
def index():
    period = request.args.get('period', 'last_30_days')
    start_str = request.args.get('start_date')
    end_str = request.args.get('end_date')

    start_date, end_date = BiAnalytics.parse_date_filter(period, start_str, end_str)
    metrics = BiAnalytics.get_dashboard_metrics(start_date, end_date)

    last_sync = Setting.get('last_sync_date', 'Nunca sincronizado')
    last_status = Setting.get('last_sync_status', 'Pendente')

    return render_template(
        'dashboard.html',
        metrics=metrics,
        period=period,
        start_date=start_date.strftime('%Y-%m-%d'),
        end_date=end_date.strftime('%Y-%m-%d'),
        last_sync=last_sync,
        last_status=last_status
    )
