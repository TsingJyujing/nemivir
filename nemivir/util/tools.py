from collections import Callable


class LazyResource:
    def __init__(self, create_resource: Callable):
        self.__create_res_func = create_resource
        self.__res_flag = False
        self.__res = None

    @property
    def resource(self):
        if not self.__res_flag:
            self.__res = self.__create_res_func()
            self.__res_flag = True
        return self.__res

    def set_resource(self, resource):
        self.__res = resource
        self.__res_flag = True
