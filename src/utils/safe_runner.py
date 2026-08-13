
import logging

logger = logging.getLogger(__name__)

def safe_execute(func, default_return=None, *args, **kwargs):
    """
    Execute function safely with error handling
    (Emergency Recovery Utility)
    """
    try:
        return func(*args, **kwargs)
    except NameError as e:
        logger.error(f"NameError in {func.__name__ if hasattr(func, '__name__') else 'lambda'}: {e}")
        return default_return or f"Error: Variable not defined - {e}"
    except KeyError as e:
        logger.error(f"KeyError in {func.__name__ if hasattr(func, '__name__') else 'lambda'}: {e}")
        return default_return or f"Error: Missing key - {e}"
    except Exception as e:
        logger.error(f"Unexpected error in {func.__name__ if hasattr(func, '__name__') else 'lambda'}: {e}")
        return default_return or f"Error: {str(e)}"
