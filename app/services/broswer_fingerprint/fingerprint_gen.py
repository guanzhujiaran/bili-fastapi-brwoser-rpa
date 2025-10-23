from crawlee.fingerprint_suite import DefaultFingerprintGenerator, HeaderGeneratorOptions
import random
from browserforge.fingerprints import Fingerprint

from app.models.RPA_browser.models import BaseFingerprintBrowserInitParams, PlatformEnum, UserBrowserInfoCreateParams, \
    BrowserEnum

desktop_fingerprint_generator = DefaultFingerprintGenerator(
    header_options=HeaderGeneratorOptions(
        browsers=['chrome'],
        operating_systems=['windows'],
        devices=['desktop'],
        locales=['zh-CN', 'zh', 'en', 'en-GB', 'en-US']
    ),
)
mobile_fingerprint_generator = DefaultFingerprintGenerator(
    header_options=HeaderGeneratorOptions(
        operating_systems=['android', 'ios'],
        devices=['mobile'],
    ),
)


def gen_from_browserforge_fingerprint(
        *,
        params: UserBrowserInfoCreateParams = UserBrowserInfoCreateParams()
) -> BaseFingerprintBrowserInitParams:
    if params.fingerprint_int:
        return BaseFingerprintBrowserInitParams(
            fingerprint=params.fingerprint_int
        )
    if params.is_desktop:
        rand_fingerprint: Fingerprint = desktop_fingerprint_generator.generate()
    else:
        rand_fingerprint: Fingerprint = mobile_fingerprint_generator.generate()
    bf_fingerprint_hashmap = {
        'Win32': PlatformEnum.windows,
        'MacIntel': PlatformEnum.macos,
        'Linux x86_64': PlatformEnum.linux,
    }
    platform = bf_fingerprint_hashmap.get(rand_fingerprint.navigator.platform, PlatformEnum.windows)
    brand = random.choice(list(BrowserEnum))
    brand_version = rand_fingerprint.navigator.userAgentData.get('uaFullVersion')
    platform_version = rand_fingerprint.navigator.userAgentData.get('platformVersion')
    return BaseFingerprintBrowserInitParams(
        fingerprint=random.randint(-2147483648, 2147483647),
        fingerprint_platform=platform,
        fingerprint_platform_version=platform_version,
        fingerprint_browser=brand,
        fingerprint_brand_version=brand_version,
        fingerprint_hardware_concurrency=rand_fingerprint.navigator.hardwareConcurrency,
        fingerprint_gpu_vendor=rand_fingerprint.videoCard.vendor,
        fingerprint_gpu_renderer=rand_fingerprint.videoCard.renderer,
        lang=rand_fingerprint.navigator.language,
        accept_lang=','.join(rand_fingerprint.navigator.languages)
    )


if __name__ == '__main__':
    for i in range(10):
        print(gen_from_browserforge_fingerprint())
