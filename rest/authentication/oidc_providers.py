oidc_providers = [
    {
        "default_clients": [
            {
                "grant_types": [
                    "authorization_code+pkce",
                    "urn:ietf:params:oauth:grant-type:device_code+pkce",
                    "refresh_token",
                ],
                "id": "vito-default-client",
                "redirect_urls": ["https://editor.openeo.org", "http://localhost:1410/"],
            }
        ],
        "id": "egi",
        "issuer": "https://aai.egi.eu/oidc/",
        "scopes": ["openid", "email", "eduperson_entitlement", "eduperson_scoped_affiliation"],
        "title": "EGI Check-in",
    }
]
