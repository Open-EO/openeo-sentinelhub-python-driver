import json
from usage_reporting.report_usage import usageReporting

import requests
from sentinelhub import SentinelHubSession

from const import OpenEOPBillingPlan, SentinelHubBillingPlan
from authentication.sh_session import central_user_sentinelhub_session
from authentication.utils import decode_sh_access_token


class User:
    def __init__(self, user_id=None):
        self.user_id = user_id
        self.sh_access_token = None
        self.default_plan = None
        self.session = central_user_sentinelhub_session

    def __repr__(self):
        return f"<{type(self).__name__}: {self.user_id} User info: {json.dumps(self.get_user_info())}>"

    def get_user_info(self):
        user_info = {"user_id": self.user_id}
        if self.default_plan:
            user_info["default_plan"] = self.default_plan.name
        return user_info

    def get_leftover_credits(self):
        pass

    def report_usage(self, pu_spent, job_id=None):
        pass


class OIDCUser(User):
    def __init__(self, user_id=None, oidc_userinfo={}, access_token=None):
        super().__init__(user_id)
        self.entitlements = [
            self.convert_entitlement(entitlement) for entitlement in oidc_userinfo.get("eduperson_entitlement", [])
        ]
        self.oidc_userinfo = oidc_userinfo
        self.default_plan = OpenEOPBillingPlan.get_billing_plan(self.entitlements)
        self.session = central_user_sentinelhub_session
        self.access_token = access_token

    def __str__(self):
        return f"{self.__class__.__name__}: {self.user_id}"

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

    def get_leftover_credits(self):
        return usageReporting.get_leftover_credits_for_user(self.access_token)

    def report_usage(self, pu_spent, job_id=None):
        usageReporting.report_usage(self.user_id, pu_spent, job_id)


class SHUser(User):
    def __init__(self, user_id=None, sh_access_token=None, sh_userinfo={}, plan_number=None):
        super().__init__(user_id)
        self.sh_access_token = sh_access_token

        if sh_access_token and not sh_userinfo:
            self.sh_userinfo = decode_sh_access_token(sh_access_token)
        else:
            self.sh_userinfo = sh_userinfo

        self.default_plan = SentinelHubBillingPlan.get_billing_plan(self.get_account_type_number())
        self.session = SentinelHubSession(
            _token={"access_token": self.sh_access_token, "expires_at": 99999999999999}, refresh_before_expiry=None
        )

    def get_account_type_number(self):
        if "d" in self.sh_userinfo and "1" in self.sh_userinfo["d"] and "t" in self.sh_userinfo["d"]["1"]:
            return self.sh_userinfo["d"]["1"]["t"]
        else:
            r = requests.get(
                f"https://services.sentinel-hub.com/ims/accounts/{self.user_id}/account-info",
                headers={"Authorization": f"Bearer {self.sh_access_token}"},
            )

            data = json.loads(r.content.decode("utf-8"))
            return data["type"]

    def get_user_info(self):
        user_info = super().get_user_info()
        if "name" in self.sh_userinfo:
            user_info["name"] = self.sh_userinfo["name"]
        user_info["info"] = {"sh_userinfo": self.sh_userinfo}
        return user_info
