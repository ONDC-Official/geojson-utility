from slowapi import Limiter
from slowapi.util import get_remote_address
import os

RATE_LIMIT = os.environ.get('RATE_LIMIT', '100/minute')
limiter = Limiter(key_func=get_remote_address, default_limits=[RATE_LIMIT]) 