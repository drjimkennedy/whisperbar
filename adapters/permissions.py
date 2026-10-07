"""Read-only macOS permission checks; never prompt or change system settings."""
from functools import lru_cache
import objc


@lru_cache(maxsize=1)
def _audio_authorization_api():
    scope = {}
    bundle = objc.loadBundle('AVFoundation', scope,
                             bundle_path='/System/Library/Frameworks/AVFoundation.framework')
    objc.loadBundleVariables(bundle, scope, [('AVMediaTypeAudio', b'@')])
    return objc.lookUpClass('AVCaptureDevice'), scope['AVMediaTypeAudio']


def microphone_permission():
    try:
        device, media_type = _audio_authorization_api()
        status = device.authorizationStatusForMediaType_(media_type)
        return {0: 'not requested', 1: 'restricted', 2: 'denied', 3: 'allowed'}.get(status, 'unknown')
    except Exception:
        return 'unknown'
