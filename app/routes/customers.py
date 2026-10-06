from flask import Blueprint, render_template, request
from app.services.bi_analytics import BiAnalytics

bp = Blueprint('customers', __name__, url_prefix='/customers')

@bp.route('/')
def index():
    period = request.args.get('period', 'last_30_days')
    start_str = request.args.get('start_date')
    end_str = request.args.get('end_date')

    start_date, end_date = BiAnalytics.parse_date_filter(period, start_str, end_str)
    analytics = BiAnalytics.get_customers_analytics(start_date, end_date)

    return render_template(
        'customers.html',
        analytics=analytics,
        period=period,
        start_date=start_date.strftime('%Y-%m-%d'),
        end_date=end_date.strftime('%Y-%m-%d')
    )
