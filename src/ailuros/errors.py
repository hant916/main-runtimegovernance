class AilurosStorageError(RuntimeError):
    pass


class AilurosNotFoundError(AilurosStorageError):
    pass


class AilurosDataCorruptionError(AilurosStorageError):
    pass
