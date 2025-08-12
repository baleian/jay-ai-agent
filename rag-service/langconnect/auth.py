"""Auth to resolve user object."""

from typing import Annotated

from fastapi import Depends
from fastapi.exceptions import HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from gotrue.types import User
from starlette.authentication import BaseUser


security = HTTPBearer()


class AuthenticatedUser(BaseUser):
    """An authenticated user following the Starlette authentication model."""

    def __init__(self, user_id: str, display_name: str) -> None:
        """Initialize the AuthenticatedUser.

        Args:
            user_id: Unique identifier for the user.
            display_name: Display name for the user.
        """
        self.user_id = user_id
        self._display_name = display_name

    @property
    def is_authenticated(self) -> bool:
        """Return True if the user is authenticated."""
        return True

    @property
    def display_name(self) -> str:
        """Return the display name of the user."""
        return self._display_name

    @property
    def identity(self) -> str:
        """Return the identity of the user. This is a unique identifier."""
        return self.user_id


def get_current_user(authorization: str) -> User:
    # TODO: Authenticate a user by validating their JWT token.
    user = None

    if not user:
        raise HTTPException(status_code=401, detail="Invalid token or user not found")
    return user


# TODO: Resolve user by credentials
# def resolve_user(
#     credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
# ) -> AuthenticatedUser | None:
#     """Resolve user from the credentials."""
#     if credentials.scheme != "Bearer":
#         raise HTTPException(status_code=401, detail="Invalid authentication scheme")

#     if not credentials.credentials:
#         raise HTTPException(status_code=401, detail="Invalid credentials")

#     if config.IS_TESTING:
#         if credentials.credentials in {"user1", "user2"}:
#             return AuthenticatedUser(credentials.credentials, credentials.credentials)
#         raise HTTPException(
#             status_code=401, detail="Invalid credentials or user not found"
#         )

#     user = get_current_user(credentials.credentials)

#     if not user:
#         raise HTTPException(status_code=401, detail="Invalid credentials")

#     return AuthenticatedUser(user.id, user.user_metadata.get("name", "User"))

# TODO: Resolve user by credentials
def resolve_user() -> AuthenticatedUser | None:
    return AuthenticatedUser("system_user_id", "system_user")
