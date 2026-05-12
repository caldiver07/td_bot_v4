
from flask import Flask

from .config import Config
from .client import Client
from .bot import Bot
from .models.events import Event
from .models.bot_log import BotLog

from redis import Redis

### assert if the app is being initialized more than once
if 'app' in globals():
    raise RuntimeError("Flask app is being initialized more than once!")

print("Initializing Flask app")

app = Flask(__name__ ,template_folder='templates' )
app.config.from_object(Config)

redis_client = Redis(
    host='localhost',
    port=6379,
    decode_responses=True,
    socket_connect_timeout=5
)
# Test Redis connection
try:
    redis_client.ping()
    print("Redis connection successful")
except Exception as e:
    print(f"WARNING: Redis connection failed: {e}") 
    redis_client = None

events = Event(app.config['WRITE_TO_ES'])
bot_logs = BotLog(app.config['WRITE_TO_ES'])

if app.config['WRITE_TO_ES']:
    events.refresh_counters_from_es()
    
schwab_client = Client(app_key=Config.SCHWAB_API_KEY,app_secret=Config.SCHWAB_SECRET_KEY,callback_url=Config.SCHWAB_CALLBACK_URL, tokens_file=Config.TOKENS_FILE, use_session=True, events=events, redis_client=redis_client)
trading_bot = Bot(schwab_client, events)

platform = "please set"
symbols = []

# Register blueprints first
from .routes import routes
app.register_blueprint(routes.main)

from .routes.bot_routes import bot
app.register_blueprint(bot)