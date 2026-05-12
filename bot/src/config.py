import os

class Config:

    SECRET_KEY = os.environ.get('SECRET_KEY') or 'a_default_secret_key'
    DEBUG = os.environ.get('DEBUG', 'False').lower() in ('true', '1', 't')
    STREAMING_TIMEOUT = 60  # Timeout for streaming responses in seconds
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # Maximum content length for uploads (16 MB)

    SCHWAB_API_KEY = '5lgELfNeymMFp8b4GXsHk312kBr5LHPrqn1SjLPujr6GWDZH'
    SCHWAB_SECRET_KEY = '0421icCEGSIJk7yTrphXMILpTuxK3izGTCrWVBaAtPAiwaDMsiT9gjk77661a5MR'
    SCHWAB_CALLBACK_URL = 'https://127.0.0.1:5002'
    TOKENS_FILE = "c:/td_bot/token/tokens_cb.json"

    WRITE_TO_ES = True