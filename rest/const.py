from enum import Enum

from sentinelhub import BatchRequestStatus, BatchUserAction
from openeoerrors import BillingPlanInvalid


class openEOBatchJobStatus(Enum):
    CREATED = "created"
    QUEUED = "queued"
    CANCELED = "canceled"
    RUNNING = "running"
    FINISHED = "finished"
    ERROR = "error"

    @staticmethod
    def from_sentinelhub_batch_job_status(sentinelhub_batch_job_status, sentinelhub_batch_user_action):
        conversion_table = {
            BatchRequestStatus.CREATED: openEOBatchJobStatus.CREATED,
            BatchRequestStatus.ANALYSING: openEOBatchJobStatus.CREATED,
            BatchRequestStatus.ANALYSIS_DONE: openEOBatchJobStatus.CREATED,
            BatchRequestStatus.PROCESSING: openEOBatchJobStatus.RUNNING,
            BatchRequestStatus.DONE: openEOBatchJobStatus.FINISHED,
            BatchRequestStatus.FAILED: openEOBatchJobStatus.ERROR,
            BatchRequestStatus.PARTIAL: openEOBatchJobStatus.ERROR,
            BatchRequestStatus.CANCELED: openEOBatchJobStatus.CANCELED,
        }
        if sentinelhub_batch_user_action == BatchUserAction.START and sentinelhub_batch_job_status in [
            BatchRequestStatus.CREATED,
            BatchRequestStatus.ANALYSIS_DONE,
        ]:
            return openEOBatchJobStatus.QUEUED
        return conversion_table.get(sentinelhub_batch_job_status)


global_parameters_xyz = {
    "spatial_extent_west": 1,
    "spatial_extent_south": 2,
    "spatial_extent_east": 3,
    "spatial_extent_north": 4,
}

optional_process_parameters = [
    "summary",
    "description",
    "parameters",
    "returns",
    "categories",
    "deprecated",
    "experimental",
    "exceptions",
    "examples",
    "links",
]


class SentinelhubDeployments:
    MAIN = "https://services.sentinel-hub.com"
    USWEST = "https://services-uswest2.sentinel-hub.com"
    CREODIAS = "https://creodias.sentinel-hub.com"


class BillingPlan(Enum):
    def __init__(self, name, description, is_paid, url):
        self._name = name
        self._description = description
        self._is_paid = is_paid
        self._url = url

    @property
    def name(self):
        return self._name

    @property
    def description(self):
        return self._description

    @property
    def is_paid(self):
        return self._is_paid

    @property
    def url(self):
        return self._url


class OpenEOPBillingPlan(BillingPlan):
    FREE = ("free", "", False, "https://openeo.cloud/free-tier/")
    EARLY_ADOPTER = ("early-adopter", "", False, "https://openeo.cloud/early-adopters/")

    @staticmethod
    def get_billing_plan(entitlements):
        free_plan_supported = False

        for entitlement in entitlements:
            if entitlement["namespace"] in ("urn:mace:egi.eu", "urn:mace:egi-dev.eu") and entitlement["group"] in (
                "vo.openeo.cloud"
            ):
                if entitlement["role"].lower() in ("early_adopter", "early-adopter", "earlyadopter"):
                    return OpenEOPBillingPlan.EARLY_ADOPTER
                free_plan_supported = True

        if free_plan_supported:
            return OpenEOPBillingPlan.FREE

        raise BillingPlanInvalid()


class SentinelHubBillingPlan(BillingPlan):
    TRIAL = ("trial", "Trial", False, "https://www.sentinel-hub.com/pricing/")
    EXPLORATION = ("exploration", "Exploration", True, "https://www.sentinel-hub.com/pricing/")
    BASIC = ("basic", "Basic", True, "https://www.sentinel-hub.com/pricing/")
    ENTERPRISE = ("enterprise", "Enterprise", True, "https://www.sentinel-hub.com/pricing/")
    ENTERPRISE_S = ("enterprise-s", "Enterprise S", True, "https://www.sentinel-hub.com/pricing/")
    ENTERPRISE_L = ("enterprise-l", "Enterprise L", True, "https://www.sentinel-hub.com/pricing/")

    @staticmethod
    def get_billing_plan(plan_number):
        sentinel_hub_plan_types = {
            11000: SentinelHubBillingPlan.TRIAL,
            12000: SentinelHubBillingPlan.EXPLORATION,
            13000: SentinelHubBillingPlan.BASIC,
            14000: SentinelHubBillingPlan.ENTERPRISE,
            14001: SentinelHubBillingPlan.ENTERPRISE_S,
            14002: SentinelHubBillingPlan.ENTERPRISE_L,
        }
        try:
            return sentinel_hub_plan_types[plan_number]
        except:
            raise BillingPlanInvalid()
