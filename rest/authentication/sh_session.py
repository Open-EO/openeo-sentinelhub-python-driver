import os

from sentinelhub import SentinelHubSession, SHConfig

sh_config = SHConfig()
sh_config.sh_client_id = os.environ.get("SH_CLIENT_ID")
sh_config.sh_client_secret = os.environ.get("SH_CLIENT_SECRET")

central_user_sentinelhub_session = SentinelHubSession(config=sh_config)
