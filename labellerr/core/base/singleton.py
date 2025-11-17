import threading


class Singleton:
    _instances = {}
    _locks = {}

    def __new__(cls, *args, **kwargs):
        if cls not in cls._locks:
            cls._locks[cls] = threading.Lock()

        if cls not in cls._instances:
            with cls._locks[cls]:
                if cls not in cls._instances:
                    cls._instances[cls] = super().__new__(cls)
        return cls._instances[cls]

    def __init__(self, *args):
        if type(self) is Singleton:
            raise TypeError("Can't instantiate Singleton class")
