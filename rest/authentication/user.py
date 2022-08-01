import json


class User:
    def __init__(self, user_id=None):
        self.user_id = user_id
        self.sh_access_token = None

    def __repr__(self):
        return f"<{type(self).__name__}: {self.user_id} User info: {json.dumps(self.get_user_info())}>"

    def get_user_info(self):
        return {"user_id": self.user_id}


class OIDCUser(User):
    def __init__(self, user_id=None, oidc_userinfo={}):
        super().__init__(user_id)
        self.entitlements = [
            self.convert_entitlement(entitlement) for entitlement in oidc_userinfo.get("eduperson_entitlement", [])
        ]
        self.oidc_userinfo = oidc_userinfo

    @staticmethod
    def convert_entitlement(entitlement):
        namespace, rest = entitlement.split(":group:")
        group, rest = rest.split(":role=")
        role, group_authority = rest.split("#")
        return {"namespace": namespace, "group": group, "role": role, "group_authority": group_authority}

    def is_in_group(self, group):
        for entitlement in self.entitlements:
            if entitlement["group"] == group:
                return True
        return False

    def get_user_info(self):
        user_info = super().get_user_info()
        user_info["info"] = {"oidc_userinfo": self.oidc_userinfo}
        return user_info


class SHUser(User):
    def __init__(self, user_id=None, sh_access_token=None, sh_userinfo={}):
        super().__init__(user_id)
        self.sh_access_token = sh_access_token
        self.sh_userinfo = sh_userinfo

    def get_user_info(self):
        user_info = super().get_user_info()
        user_info["name"] = self.sh_userinfo["name"]
        user_info["info"] = {"sh_userinfo": self.sh_userinfo}
        return user_info
