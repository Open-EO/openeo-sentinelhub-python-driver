from functools import wraps
from inspect import getfullargspec

import requests
from flask import request

from openeoerrors import AuthenticationRequired, AuthenticationSchemeInvalid, Internal, CredentialsInvalid
from authentication.oidc_providers import oidc_providers
from authentication.user import User


class AuthenticationProvider:
    def __init__(self, oidc_providers=None):
        self.oidc_providers = oidc_providers

    def get_oidc_providers(self):
        return self.oidc_providers

    def authenticate_user(self, access_token, oidc_provider_id):
        oidc_provider = next(
            (oidc_provider for oidc_provider in self.oidc_providers if oidc_provider["id"] == oidc_provider_id), None
        )

        if not oidc_provider:
            return None

        info_url = oidc_provider["issuer"] + ".well-known/openid-configuration"

        general_info = requests.get(info_url)
        general_info.raise_for_status()
        general_info = general_info.json()

        userinfo_url = general_info["userinfo_endpoint"]

        userinfo_resp = requests.get(userinfo_url, headers={"Authorization": f"Bearer {access_token}"})
        userinfo_resp.raise_for_status()
        userinfo = userinfo_resp.json()

        user_id = userinfo["sub"]
        entitlement = userinfo["eduperson_entitlement"]

        user = User(user_id, entitlement)

        if not user.is_in_group("vo.openeo.cloud"):
            return None

        return user

    def with_bearer_auth(self, func):
        @wraps(func)
        def decorated_function(*args, **kwargs):
            if "Authorization" in request.headers:
                try:
                    bearer = request.headers["Authorization"].split()[1].strip()
                    if bearer.startswith("oidc/"):
                        _, provider_id, token = bearer.split("/")
                    else:
                        token = None
                except:
                    token = None

                if not token:
                    raise AuthenticationSchemeInvalid()

                try:
                    user = self.authenticate_user(token, provider_id)
                except Exception as e:
                    raise Internal(f"Problems during authentication: {str(e)}")

                if not user:
                    raise CredentialsInvalid()

                if "user" in getfullargspec(func).args:
                    kwargs["user"] = user

            else:
                raise AuthenticationRequired()
            return func(*args, **kwargs)

        return decorated_function


authentication_provider = AuthenticationProvider(oidc_providers=oidc_providers)
