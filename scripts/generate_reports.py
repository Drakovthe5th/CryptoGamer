import logging
from src.database.firebase import db
from datetime import datetime, timedelta
import csv
import os

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def generate_daily_report():
    """Generate daily financial report"""
    end_time = datetime.now()
    start_time = end_time - timedelta(days=1)
    
    # Query transactions
    transactions = db.collection('transactions').where('timestamp', '>=', start_time).where('timestamp', '<=', end_time).stream()
    
    # Prepare report data
    report_data = []
    ton_in = 0
    ton_out = 0
    cash_out = 0
    
    for tx in transactions:
        tx_data = tx.to_dict()
        if tx_data['type'] == 'reward':
            ton_in += tx_data['amount']
        elif tx_data['type'] == 'withdrawal':
            ton_out += tx_data['amount']
        elif tx_data['type'] == 'otc':
            cash_out += tx_data['fiat_amount']
            
        report_data.append({
            'timestamp': tx_data['timestamp'],
            'user_id': tx_data['user_id'],
            'type': tx_data['type'],
            'amount_ton': tx_data.get('amount', 0),
            'fiat_amount': tx_data.get('fiat_amount', 0),
            'fiat_currency': tx_data.get('currency', 'TON'),
            'description': tx_data.get('description', '')
        })
    
    # Create report directory
    report_dir = "reports/daily"
    os.makedirs(report_dir, exist_ok=True)
    
    # Generate CSV
    report_date = end_time.strftime("%Y-%m-%d")
    filename = f"{report_dir}/daily_report_{report_date}.csv"
    
    with open(filename, 'w', newline='') as csvfile:
        fieldnames = ['timestamp', 'user_id', 'type', 'amount_ton', 'fiat_amount', 'fiat_currency', 'description']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        writer.writeheader()
        for row in report_data:
            writer.writerow(row)
    
    # Create summary
    summary = f"""Daily Report - {report_date}
    
TON Rewarded: {ton_in:.6f}
TON Withdrawn: {ton_out:.6f}
Cash Out: {cash_out:.2f} USD
Net TON Movement: {(ton_in - ton_out):.6f}
"""
    
    with open(f"{report_dir}/summary_{report_date}.txt", 'w') as f:
        f.write(summary)
    
    logger.info(f"Generated daily report: {filename}")
    return filename

if __name__ == '__main__':
    generate_daily_report()