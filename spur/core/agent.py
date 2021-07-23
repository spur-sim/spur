class Train:
    __name__ = "Train"

    def __init__(self, model, component):
        self.model = model
        self.component = component
        self.component.add_train(self)
        self.action = model.process(self.run())

    def run(self):
        print("Starting to roll at", self.model.now)
        roll_duration = 5
        yield self.model.process(self.move(roll_duration))

        print("Start rolling at", self.model.now)
        trip_duration = 2
        yield self.model.timeout(trip_duration)

    def move(self, duration):
        yield self.model.timeout(duration)
