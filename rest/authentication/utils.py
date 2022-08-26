import os

import jwt
from cryptography.x509 import load_pem_x509_certificate
from cryptography.hazmat.backends import default_backend

from openeoerrors import TokenInvalid


def decode_sh_access_token(access_token):
    script_dir = os.path.dirname(__file__)
    abs_filepath = os.path.join(script_dir, "cert.pem")

    with open(abs_filepath, "rb") as f:
        cert_str = f.read()

    cert_obj = load_pem_x509_certificate(cert_str, default_backend())

    try:
        return jwt.decode(access_token, cert_obj.public_key(), algorithms="RS256", options={"verify_aud": False})
    except:
        raise TokenInvalid()
