def validate_phone(phone: str) -> bool:
    return len(phone) == 12 and phone.startswith('254') and phone[3:].isdigit()

def validate_account(account: str) -> bool:
    return account.isdigit() and len(account) in [10, 12]