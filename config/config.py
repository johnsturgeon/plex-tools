"""Configuration file"""

import os
from dataclasses import dataclass
from dotenv import load_dotenv


# pylint: disable=too-few-public-methods
# pylint: disable=too-many-instance-attributes
@dataclass
class Config:
    """Base configuration class"""

    # pylint: disable=invalid-name
    APP_CLIENT_ID: str
    APP_FORWARD_URL: str
    APP_PRODUCT_NAME: str
    COOKIE_RETENTION_DAYS: int
    ENVIRONMENT: str
    PLEX_AUTH_URL: str
    PLEX_PIN_URL: str
    PLEX_USER_URL: str

    @classmethod
    def get_config(cls):
        """Factory method for returning the correct config"""
        load_dotenv()
        config = cls(
            APP_CLIENT_ID=os.getenv("APP_CLIENT_ID"),
            APP_FORWARD_URL=os.getenv("APP_FORWARD_URL"),
            APP_PRODUCT_NAME=os.getenv("APP_PRODUCT_NAME"),
            COOKIE_RETENTION_DAYS=int(os.getenv("COOKIE_RETENTION_DAYS")),
            ENVIRONMENT=os.getenv("ENVIRONMENT"),
            PLEX_AUTH_URL=os.getenv("PLEX_AUTH_URL"),
            PLEX_PIN_URL=os.getenv("PLEX_PIN_URL"),
            PLEX_USER_URL=os.getenv("PLEX_USER_URL"),
        )
        return config
