"""Portal REST API helpers for group membership checks."""

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from typing import Optional, Set

logger = logging.getLogger(__name__)

_TIMEOUT = 10  # seconds


def _portal_get(url: str, params: dict) -> dict:
    query    = urllib.parse.urlencode(params)
    full_url = f"{url}?{query}"
    try:
        with urllib.request.urlopen(full_url, timeout=_TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        logger.warning("Portal API HTTP %s for: %s", exc.code, url)
    except Exception as exc:
        logger.warning("Portal API request failed ('%s'): %s", url, exc)
    return {}


def get_username_for_email(portal_url: str, email: str, token: str) -> Optional[str]:
    """Looks up portal username by email. Returns None if not found or on error."""
    url  = f"{portal_url.rstrip('/')}/sharing/rest/community/users"
    data = _portal_get(url, {"f": "json", "q": f"email:{email}", "num": 5, "token": token})
    for result in data.get("results", []):
        if result.get("email", "").lower() == email.lower():
            return result.get("username")
    return None


def get_portal_group_members(portal_url: str, group_id: str, token: str) -> Set[str]:
    """Returns lowercase usernames of all members, admins, and owner of a portal group."""
    url     = f"{portal_url.rstrip('/')}/sharing/rest/community/groups/{group_id}/users"
    data    = _portal_get(url, {"f": "json", "token": token})
    members: Set[str] = set()
    for u in data.get("users", []):
        members.add(u.lower())
    for u in data.get("admins", []):
        members.add(u.lower())
    if data.get("owner"):
        members.add(data["owner"].lower())
    return members


def is_user_in_portal_group(portal_url: str, group_id: str, user_email: str, token: str) -> bool:
    """Returns True if the user (identified by email) is a member of the portal group."""
    username = get_username_for_email(portal_url, user_email, token)
    if not username:
        logger.warning("Could not resolve portal username for email '%s'.", user_email)
        return False
    members = get_portal_group_members(portal_url, group_id, token)
    in_group = username.lower() in members
    if not in_group:
        logger.debug("User '%s' (%s) is not in group '%s'.", username, user_email, group_id)
    return in_group
