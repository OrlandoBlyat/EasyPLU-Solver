"""Job-local upstream session shared by authentication and product requests."""
from backend.infrastructure.jobs import SessionProxy

BASE_URL = "https://easy-plu.knowledge-hero.com/api/plu"
session = SessionProxy()
