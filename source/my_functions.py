import math


class  Shape:


    def area(self):
        pass

    def perimeter(self):
        pass


class Circle(Shape):

    def __init__(self, radius):
        self.radius = radius


    def area(self):
        return math.pi * self.radius ** 2
    
    def perimeter(self):
        return 2 * math.pi




def add(n1, n2):
    return n1 + n2

def divide(n1, n2):
    return n1 / n2


