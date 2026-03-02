import mimetypes
import requests
from django.core.files.storage import Storage
from django.core.files.base import ContentFile
from django.conf import settings
from django.utils.deconstruct import deconstructible

@deconstructible
class SupabaseStorage(Storage):
    def __init__(self):
        self.base_url = settings.SUPABASE_URL.rstrip('/')
        self.bucket = settings.SUPABASE_BUCKET
        self.api_key = settings.SUPABASE_SERVICE_ROLE_KEY
        self.headers_base = {
            "apikey": self.api_key,
            "Authorization": f"Bearer {self.api_key}",
        }
        self.public_base = f"{self.base_url}/storage/v1/object/public/{self.bucket}"
        self.object_base = f"{self.base_url}/storage/v1/object/{self.bucket}"

    def _normalize_name(self, name: str) -> str:
        return name.lstrip('/').replace("\\", "/")

    def _public_url(self, name: str) -> str:
        name = self._normalize_name(name)
        return f"{self.public_base}/{name}"

    def _upload_url(self, name: str) -> str:
        name = self._normalize_name(name)
        return f"{self.object_base}/{name}"

    def _open(self, name, mode='rb'):
        url = self._public_url(name)
        try:
            r = requests.get(url, timeout=10)
        except requests.RequestException as e:
            raise FileNotFoundError(f"Network error fetching '{name}': {e}")
        if r.status_code == 200:
            return ContentFile(r.content)
        raise FileNotFoundError(f"File '{name}' not found in Supabase (status={r.status_code}).")

    def _save(self, name, content):
        print(f"Uploading to Supabase: {name}")
  
        name = self._normalize_name(name)

        if hasattr(content, 'seek'):
            try:
                content.seek(0)
            except Exception:
                pass

        data = content.read()

        guessed_type, _ = mimetypes.guess_type(name)
        content_type = getattr(getattr(content, 'file', None), 'content_type', None) or guessed_type or 'application/octet-stream'

        headers = {
            **self.headers_base,
            "Content-Type": content_type,
            "x-upsert": "true",
        }

        url = self._upload_url(name)
        try:
            r = requests.put(url, headers=headers, data=data, timeout=30)
        except requests.RequestException as e:
            raise Exception(f"Upload request failed for '{name}': {e}")

        if r.status_code in (200, 201):
            return name

        raise Exception(f"Failed to upload '{name}' to Supabase ({r.status_code}): {r.text}")

    def exists(self, name):
        url = self._public_url(name)
        try:
            r = requests.head(url, timeout=10)
        except requests.RequestException:
            return False
        return r.status_code == 200

    def url(self, name):
        return self._public_url(name)
