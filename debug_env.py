
import os
from pathlib import Path
from dotenv import load_dotenv

env_path = Path('.env')
print(f"Testing environment loading from {env_path.absolute()}")
print(f"File exists: {env_path.exists()}")

loaded = load_dotenv(dotenv_path=env_path, verbose=True)
print(f"load_dotenv returned: {loaded}")

fb_phone = os.getenv('FB_PHONE')
fb_password = os.getenv('FB_PASSWORD')

print(f"FB_PHONE: '{fb_phone}'")
print(f"FB_PASSWORD: '{'******' if fb_password else 'None'}'")
