#!/usr/bin/env python3
"""
Ansible lookup plugin: botrus_secret

Looks up secrets from the Botrus K8s secrets engine API at runtime.
Never writes secrets to disk — fetches them over HTTP with Bearer token auth.

Usage in playbooks/templates:
    {{ lookup('botrus_secret', 'secret_plex_smb-creds_password') }}
    {{ lookup('botrus_secret', 'ansible_become_password') }}

Configuration:
    BOTRUS_SECRETS_KEY  — env var with the Bearer token (required)
    BOTRUS_API_URL      — env var, defaults to http://localhost:4000

Results are cached in-memory for the duration of the playbook run
to avoid repeated HTTP calls for the same key.
"""

from __future__ import annotations

import json
import os
import urllib.request
import urllib.error
from ansible.errors import AnsibleLookupError
from ansible.plugins.lookup import LookupBase
from ansible.utils.display import Display

display = Display()

API_URL = os.environ.get("BOTRUS_API_URL", "http://localhost:4000")
AUTH_TOKEN = os.environ.get("BOTRUS_SECRETS_KEY", "")

# In-memory cache for the playbook run (cleared between playbook executions)
_CACHE: dict[str, str] = {}


class LookupModule(LookupBase):

    def run(self, terms, variables=None, **kwargs):
        if not AUTH_TOKEN:
            raise AnsibleLookupError(
                "BOTRUS_SECRETS_KEY environment variable is not set. "
                "The botrus_secret lookup plugin requires this for API authentication."
            )

        results = []
        for term in terms:
            key = str(term)

            # Check cache first
            if key in _CACHE:
                results.append(_CACHE[key])
                continue

            # Fetch from API
            url = f"{API_URL}/api/vars/lookup?key={key}"
            req = urllib.request.Request(url)
            req.add_header("Authorization", f"Bearer {AUTH_TOKEN}")

            try:
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                body = e.read().decode("utf-8", errors="replace")
                raise AnsibleLookupError(
                    f"Botrus API returned {e.code} for key '{key}': {body}"
                )
            except urllib.error.URLError as e:
                raise AnsibleLookupError(
                    f"Cannot reach Botrus API at {API_URL}: {e.reason}"
                )
            except json.JSONDecodeError:
                raise AnsibleLookupError(
                    f"Botrus API returned invalid JSON for key '{key}'"
                )

            value = data.get("value", "")
            _CACHE[key] = value
            results.append(value)

        return results
