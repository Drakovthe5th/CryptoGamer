from src.database.firebase import initialize_firebase, db
from config import Config
import datetime
import csv
import os

def generate_financial_report():
    initialize_firebase(Config.FIREBASE_CREDS)
    
    # Get date range (last 30 days)
    end_date = datetime.datetime.now()
    start_date = end_date - datetime.timedelta(days=30)
    
    # Query transactions
    transactions = db.collection('transactions').where(
        'timestamp', '>=', start_date
    ).stream()
    
    # Prepare report data
    report_data = []
    total_deposits = 0
    total_withdrawals = 0
    total_earnings = 0
    
    for tx in transactions:
        tx_data = tx.to_dict()
        amount = tx_data.get('amount', 0)
        
        # Categorize transaction
        if tx_data['type'] == 'deposit':
            total_deposits += amount
            tx_type = 'Deposit'
        elif tx_data['type'] in ['withdrawal_success', 'withdrawal_completed']:
            total_withdrawals += amount
            tx_type = 'Withdrawal'
        else:
            tx_type = 'Earning'
            total_earnings += amount
        
        report_data.append({
            'Date': tx_data['timestamp'].strftime('%Y-%m-%d %H:%M'),
            'User ID': tx_data['user_id'],
            'Type': tx_type,
            'Amount (XNO)': amount,
            'Method': tx_data.get('method', 'N/A'),
            'Status': tx_data.get('status', 'completed')
        })
    
    # Calculate net revenue
    net_revenue = total_earnings + total_deposits - total_withdrawals
    
    # Generate CSV report
    report_date = end_date.strftime('%Y%m%d')
    filename = f"financial_report_{report_date}.csv"
    os.makedirs('reports', exist_ok=True)
    filepath = os.path.join('reports', filename)
    
    with open(filepath, 'w', newline='') as csvfile:
        fieldnames = ['Date', 'User ID', 'Type', 'Amount (XNO)', 'Method', 'Status']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(report_data)
    
    # Create summary
    summary = (
        f"Financial Report ({report_date})\n"
        f"--------------------------------\n"
        f"Total Deposits: {total_deposits:.6f} XNO\n"
        f"Total Withdrawals: {total_withdrawals:.6f} XNO\n"
        f"Total Earnings: {total_earnings:.6f} XNO\n"
        f"Net Revenue: {net_revenue:.6f} XNO\n"
        f"--------------------------------\n"
        f"Report saved to: {filepath}"
    )
    
    print(summary)
    return filepath

if __name__ == '__main__':
    generate_financial_report()