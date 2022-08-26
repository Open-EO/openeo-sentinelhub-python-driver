oidc_providers = [
    {
        "default_clients": [
            {
                "grant_types": [
                    "authorization_code+pkce",
                    "urn:ietf:params:oauth:grant-type:device_code+pkce",
                    "refresh_token",
                ],
                "id": "sentinel-hub-default-client",
                "redirect_urls": [
                    "https://editor.openeo.org",
                    "http://localhost:5000",
                    "http://localhost:5000/callback",
                ],
            }
        ],
        "id": "egi",
        "issuer": "https://aai.egi.eu/auth/realms/egi/",
        "scopes": ["openid", "email", "eduperson_entitlement", "eduperson_scoped_affiliation"],
        "title": "EGI Check-in",
    },
    {
        "default_clients": [
            {
                "grant_types": [
                    "authorization_code+pkce",
                    "urn:ietf:params:oauth:grant-type:device_code+pkce",
                    "refresh_token",
                ],
                "id": "sentinel-hub-default-client",
                "redirect_urls": [
                    "https://editor.openeo.org",
                    "http://localhost:5000",
                    "http://localhost:5000/callback",
                ],
            }
        ],
        "id": "egi-legacy",
        "issuer": "https://aai.egi.eu/oidc/",
        "scopes": ["openid", "email", "eduperson_entitlement", "eduperson_scoped_affiliation"],
        "title": "EGI Check-in (legacy)",
    },
]
