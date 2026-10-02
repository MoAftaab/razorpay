from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    """Runtime configuration loaded from environment variables."""

    search_url: str = "https://search.f-droid.org/"
    item_url: str = "https://f-droid.org/en/packages"
    timeout_seconds: float = 10.0
    user_agent: str = "fdroid-catalog-adapter/1.0 (respectful public-page client)"

    @classmethod
    def from_env(cls) -> "Settings":
        timeout = float(os.getenv("UPSTREAM_TIMEOUT_SECONDS", "10"))
        if timeout <= 0 or timeout > 60:
            raise ValueError("UPSTREAM_TIMEOUT_SECONDS must be between 0 and 60")

        return cls(
            search_url=os.getenv("FDROID_SEARCH_URL", cls.search_url),
            item_url=os.getenv("FDROID_ITEM_URL", cls.item_url).rstrip("/"),
            timeout_seconds=timeout,
            user_agent=os.getenv("UPSTREAM_USER_AGENT", cls.user_agent),
        )

