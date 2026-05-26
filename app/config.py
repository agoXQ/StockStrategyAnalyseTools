import os

SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-change-me-to-a-secure-random-string")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", str(60 * 24)))
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./stock_strategy.db")
CONFIG_FILE = os.getenv("CONFIG_FILE", "config.yaml")
CORS_ALLOW_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ALLOW_ORIGINS", "*").split(",")
    if origin.strip()
]
BOOTSTRAP_FIRST_USER_AS_ADMIN = os.getenv("BOOTSTRAP_FIRST_USER_AS_ADMIN", "true").lower() in {
    "1",
    "true",
    "yes",
}

ALLOWED_ROLES = {"admin", "vip", "user"}
ROLE_READ_ALL = {"admin", "vip"}
ROLE_WRITE_OWN_ONLY = {"vip", "user"}

DEFAULT_MARKET_TYPE_STOCK = "stock"
DEFAULT_MARKET_TYPE_INDEX = "index"
