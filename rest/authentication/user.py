class User:
    def __init__(self, user_id=None, entitlements=[], sh_access_token=None):
        self.user_id = user_id
        self.entitlements = [self.convert_entitlement(entitlement) for entitlement in entitlements]
        self.sh_access_token = sh_access_token

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
