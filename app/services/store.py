from app.core.config import settings
from app.services.demo_store import demo_store
from app.services.supabase_store import supabase_store


class StoreRouter:
    @property
    def backend(self):
        return supabase_store if settings.has_supabase_config else demo_store

    def __getattr__(self, name: str):
        return getattr(self.backend, name)


store = StoreRouter()
