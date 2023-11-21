import base64
import traceback
from enum import Enum
from functools import wraps
from inspect import getfullargspec
from logging import log, INFO, WARN, ERROR

import requests
from flask import request, g

from openeoerrors import (
    OpenEOError,
    AuthenticationRequired,
    AuthenticationSchemeInvalid,
    Internal,
    CredentialsInvalid,
    BillingPlanInvalid,
    TokenInvalid,
)
from authentication.oidc_providers import oidc_providers
from authentication.user import OIDCUser, SHUser
from authentication.utils import decode_sh_access_token

from openeoerrors import TokenInvalid


class AuthScheme(Enum):
    BASIC = "basic"
    OIDC = "oidc"


class AuthenticationProvider:
    def __init__(self, oidc_providers=None):
        self.oidc_providers = oidc_providers

    def get_oidc_providers(self):
        return self.oidc_providers

    def authenticate_user_oidc(self, access_token, oidc_provider_id):
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

        try:
            userinfo_resp = requests.get(userinfo_url, headers={"Authorization": f"Bearer {access_token}"})
            userinfo_resp.raise_for_status()
        except:
            raise TokenInvalid()

        userinfo = userinfo_resp.json()

        user_id = userinfo["sub"]

        try:
            user = OIDCUser(user_id, oidc_userinfo=userinfo, access_token=access_token)
        except BillingPlanInvalid:
            return None

        if not user.is_in_group("vo.openeo.cloud"):
            return None

        return user

    def authenticate_user_basic(self, access_token):
        decoded = decode_sh_access_token(access_token)
        try:
            user = SHUser(decoded["sub"], sh_access_token=access_token, sh_userinfo=decoded)
        except BillingPlanInvalid:
            return None

        return user

    def authenticate_user(self, bearer):
        try:
            if bearer.startswith("oidc/"):
                _, provider_id, token = bearer.split("/")
                auth_scheme = AuthScheme.OIDC
            elif bearer.startswith("basic//"):
                token = bearer.split("basic//")[1].strip()
                auth_scheme = AuthScheme.BASIC
            else:
                token = None
        except:
            token = None

        if not token:
            raise AuthenticationSchemeInvalid()

        try:
            if auth_scheme == AuthScheme.OIDC:
                return self.authenticate_user_oidc(token, provider_id)
            if auth_scheme == AuthScheme.BASIC:
                return self.authenticate_user_basic(token)
        except OpenEOError:
            raise
        except Exception as e:
            log(ERROR, traceback.format_exc())
            raise Internal(f"Problems during authentication: {str(e)}")

    def parse_credentials_from_header(self):
        if "Authorization" in request.headers:
            try:
                encoded_credentials = request.headers["Authorization"].split("Basic")[1].strip()
                credentials = base64.b64decode(bytes(encoded_credentials, "ascii")).decode("ascii")
                username, password = credentials.strip().split(":", 1)
                return username, password
            except:
                raise AuthenticationSchemeInvalid()
        raise AuthenticationRequired()

    def check_credentials_basic(self):
        """We expect HTTP Basic username / password to be SentinelHub clientId / clientSecret, with
        which we obtain the auth token from the service.
        Password (clientSecret) can be supplied verbatim or as base64-encoded string, to avoid
        problems with non-ASCII characters. Anything longer than 50 characters will be treated
        as BASE64-encoded string.
        """
        username, password = self.parse_credentials_from_header()
        secret = password if len(password) <= 50 else base64.b64decode(bytes(password, "ascii")).decode("ascii")
        r = requests.post(
            "https://services.sentinel-hub.com/oauth/token",
            data={
                "grant_type": "client_credentials",
                "client_id": username,
                "client_secret": secret,
            },
        )
        if r.status_code != 200:
            log(INFO, f"Access denied: {r.status_code} {r.text}")
            raise CredentialsInvalid()

        j = r.json()
        access_token = j.get("access_token")
        if not access_token:
            log(ERROR, f"Error decoding access token from: {r.text}")
            raise Internal(f"Problems during authentication: Error decoding access token from: {r.text}")

        return access_token

    def with_bearer_auth(self, func):
        @wraps(func)
        def decorated_function(*args, **kwargs):
            if "Authorization" in request.headers:
                try:
                    bearer = request.headers["Authorization"].split()[1].strip()
                except:
                    raise AuthenticationSchemeInvalid()

                user = self.authenticate_user(bearer)

                if not user:
                    raise CredentialsInvalid()

                g.user = user

                if "user" in getfullargspec(func).args:
                    kwargs["user"] = user

            else:
                raise AuthenticationRequired()
            return func(*args, **kwargs)

        return decorated_function


authentication_provider = AuthenticationProvider(oidc_providers=oidc_providers)
