class SensordException(Exception):
    pass


class APINotStarted(SensordException):
    pass


class ServiceNotStarted(SensordException):
    pass


class ErrorDuringShutdown(SensordException):
    pass


class ServiceAlreadyRunning(SensordException):
    pass


class InvalidConfiguration(SensordException):
    pass


class MissingConfigurationField(SensordException):

    def __init__(self, field):
        self.field = field
        super().__init__(f"Missing configuration field: {field}")


class UnknownSensorType(SensordException):

    def __init__(self, sensor_type):
        self.sensor_type = sensor_type
        super().__init__(f"Unknown sensor type: {sensor_type}")


class AlreadyRegistered(SensordException):
    pass
