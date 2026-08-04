from abc import ABC, abstractmethod


class BaseLight(ABC):

    @abstractmethod
    def pixel_on(self, led_index, r, g, b): ...

    @abstractmethod
    def pixel_off(self, led_index): ...

    @abstractmethod
    def all_pixel_on(self, r, g, b): ...

    @abstractmethod
    def all_pixel_off(self): ...
