from supabase import create_client
from src.config.env_config import ENV

supabase = create_client(ENV.SUPABASE_PROJECT_URL, ENV.SUPABASE_SERVICE_KEY)
