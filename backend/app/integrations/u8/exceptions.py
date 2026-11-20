class U8Error(Exception): pass
class U8BusinessError(U8Error):
    def __init__(self,message,code=None):
        super().__init__(message)
        self.code=code
class U8UncertainError(U8Error): pass
class U8TemporaryError(U8UncertainError): pass
