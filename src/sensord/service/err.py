class ServiceException(Exception):
    pass


class APINotStarted(ServiceException):
    pass


class ServiceNotStarted(ServiceException):
    pass


class ErrorDuringShutdown(ServiceException):
    pass


class ServiceAlreadyRunning(ServiceException):
    pass


class InvalidConfiguration(ServiceException):
    pass


class MissingConfigurationField(ServiceException):

    def __init__(self, field):
        self.field = field
        super().__init__(f"Missing configuration field: {field}")


class UnknownSensorType(ServiceException):

    def __init__(self, sensor_type):
        self.sensor_type = sensor_type
        super().__init__(f"Unknown sensor type: {sensor_type}")


class AlreadyRegistered(ServiceException):
    pass
