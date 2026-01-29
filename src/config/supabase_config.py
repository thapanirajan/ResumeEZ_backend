from supabase import create_client
from src.config.env_config import ENV_CONFIG

supabase = create_client(ENV_CONFIG.SUPABASE_PROJECT_URL, ENV_CONFIG.SUPABASE_SERVICE_KEY)
