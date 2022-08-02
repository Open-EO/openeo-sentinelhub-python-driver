import json

import requests

from const import OpenEOPBillingPlan, SentinelHubBillingPlan


class User:
    def __init__(self, user_id=None):
        self.user_id = user_id
        self.sh_access_token = None
        self.default_plan = None

    def __repr__(self):
        return f"<{type(self).__name__}: {self.user_id} User info: {json.dumps(self.get_user_info())}>"

    def get_user_info(self):
        user_info = {"user_id": self.user_id}
        if self.default_plan:
            user_info["default_plan"] = self.default_plan.name
        return user_info


class OIDCUser(User):
    def __init__(self, user_id=None, oidc_userinfo={}):
        super().__init__(user_id)
        self.entitlements = [
            self.convert_entitlement(entitlement) for entitlement in oidc_userinfo.get("eduperson_entitlement", [])
        ]
        self.oidc_userinfo = oidc_userinfo
        self.default_plan = OpenEOPBillingPlan.get_billing_plan(self.entitlements)

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
    def __init__(self, user_id=None, sh_access_token=None, sh_userinfo={}, plan_number=None):
        super().__init__(user_id)
        self.sh_access_token = sh_access_token
        self.sh_userinfo = sh_userinfo
        self.default_plan = SentinelHubBillingPlan.get_billing_plan(self.get_account_type_number())

    def get_account_type_number(self):
        if "d" in self.sh_userinfo and "1" in self.sh_userinfo["d"] and "t" in self.sh_userinfo["d"]["1"]:
            return self.sh_userinfo["d"]["1"]["t"]
        else:
            r = requests.get(
                f"https://services.sentinel-hub.com/oauth/users/{self.user_id}/accounts",
                headers={"Authorization": f"Bearer {self.sh_access_token}"},
            )
            data = json.loads(r.content.decode("utf-8"))
            for member in data["member"]:
                if member["domainId"] == 1:
                    return member["type"]

    def get_user_info(self):
        user_info = super().get_user_info()
        user_info["name"] = self.sh_userinfo["name"]
        user_info["info"] = {"sh_userinfo": self.sh_userinfo}
        return user_info
