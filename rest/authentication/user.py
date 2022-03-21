class User:
    def __init__(self, user_id=None, entitlements=None):
        self.user_id = user_id
        self.entitlements = [self.convert_entitlement(entitlement) for entitlement in entitlements]

    @staticmethod
    def convert_entitlement(entitlement):
        namespace, rest = entitlement.split(":group:")
        group, rest = rest.split(":")
        role, group_authority = rest.split("#")
        role = role.lstrip("role=")
        return {"namespace": namespace, "group": group, "role": role, "group_authority": group_authority}

    def is_in_group(self, group):
        for entitlement in self.entitlements:
            if entitlement["group"] == group:
                return True
        return False
