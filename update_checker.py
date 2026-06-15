import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass

from app_info import APP_NAME, APP_RELEASES_API_URL, APP_RELEASES_URL, APP_VERSION


@dataclass(frozen=True)
class UpdateInfo:
    version: str
    url: str
    title: str
    notes: str = ""


def _version_parts(version):
    return tuple(int(part) for part in re.findall(r"\d+", str(version or "")))


def is_newer_version(candidate_version, current_version):
    candidate_parts = _version_parts(candidate_version)
    current_parts = _version_parts(current_version)
    length = max(len(candidate_parts), len(current_parts), 1)
    candidate_parts = candidate_parts + (0,) * (length - len(candidate_parts))
    current_parts = current_parts + (0,) * (length - len(current_parts))
    return candidate_parts > current_parts


class UpdateChecker:
    def __init__(
        self,
        current_version=APP_VERSION,
        release_api_url=APP_RELEASES_API_URL,
        releases_url=APP_RELEASES_URL,
        opener=urllib.request.urlopen
    ):
        self.current_version = current_version
        self.release_api_url = release_api_url
        self.releases_url = releases_url
        self.opener = opener

    def check(self, timeout=5):
        request = urllib.request.Request(
            self.release_api_url,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": f"{APP_NAME}/{self.current_version}"
            }
        )
        try:
            with self.opener(request, timeout=timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            if error.code == 404:
                return None
            raise

        tag_name = payload.get("tag_name") or payload.get("name")
        if not tag_name or not is_newer_version(tag_name, self.current_version):
            return None

        return UpdateInfo(
            version=tag_name,
            url=payload.get("html_url") or self.releases_url,
            title=payload.get("name") or tag_name,
            notes=payload.get("body") or ""
        )
