def create_detector(config):
    if config.method == "iforest":
        from .iforest import IsolationForestDetector
        return IsolationForestDetector(config.model, config.seed)
    from .autoencoder import AutoencoderDetector
    return AutoencoderDetector(268 if config.method == "history_ae" else 134, config.model, config.seed)

def detector_type(method):
    if method == "iforest":
        from .iforest import IsolationForestDetector
        return IsolationForestDetector
    from .autoencoder import AutoencoderDetector
    return AutoencoderDetector
