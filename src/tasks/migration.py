from src.database.mongo import db

# Create a migration script to initialize the new fields
def migrate_to_dual_currency():
    """Migrate existing users to the dual currency system"""
    users = db.users.find({})
    
    for user in users:
        # Initialize new fields with default values
        update_data = {
            'crew_credits': 0,
            'telegram_stars': 0
        }
        
        # If user has existing GC, we could optionally convert some to credits
        # For now, we'll just initialize the new fields
        
        db.users.update_one(
            {'_id': user['_id']},
            {'$set': update_data}
        )
    
    print("Migration completed successfully")

# Run this once during deployment
if __name__ == "__main__":
    migrate_to_dual_currency()