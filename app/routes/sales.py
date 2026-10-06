from flask import Blueprint, render_template, request
from app.services.bi_analytics import BiAnalytics

bp = Blueprint('sales', __name__, url_prefix='/sales')

@bp.route('/')
def index():
    period = request.args.get('period', 'last_30_days')
    start_str = request.args.get('start_date')
    end_str = request.args.get('end_date')
    channel = request.args.get('channel', 'all')
    status = request.args.get('status', 'all')

    start_date, end_date = BiAnalytics.parse_date_filter(period, start_str, end_str)
    analytics = BiAnalytics.get_sales_analytics(start_date, end_date, channel=channel, status=status)

    return render_template(
        'sales.html',
        analytics=analytics,
        period=period,
        start_date=start_date.strftime('%Y-%m-%d'),
        end_date=end_date.strftime('%Y-%m-%d'),
        channel=channel,
        status=status
    )
