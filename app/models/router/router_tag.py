from enum import StrEnum


class RouterTag(StrEnum):
    browser_fingerprint = "浏览器指纹"
    browser_control = "浏览器控制"


class VersionTag(StrEnum):
    v1 = "v1"
