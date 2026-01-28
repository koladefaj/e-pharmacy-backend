class PasswordVerificationError(Exception):
    """Raised when password hashing or verification fails."""
    pass

class AuthenticationFailed(Exception):
    """
    Raised when a user provides incorrect credentials (email/password) 
    or an invalid/expired JWT.
    
    Expected Result: 401 Unauthorized
    """
    pass

class NotAuthorized(Exception):
    """
    Raised when a user is authenticated but does not have permission 
    to access a specific resource (e.g., trying to view another user's document).
    
    Expected Result: 403 Forbidden
    """
    pass

class InsufficientStockError(Exception):
    """
    Raised when an Inventory stock is insuffient
    
    """
    pass