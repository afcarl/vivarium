"""The event framework
"""

from collections import defaultdict

from .util import marker_factory, resource_injector

listens_for = marker_factory('event_system__listens_for', with_priority=True)
listens_for.__doc__ = """Mark a function as a listener for the named event so that
the simulation will call it when that event occurs.
"""

emits = resource_injector('event_system__emits')
emits.__doc__ = """Mark a function as an emitter for the named event. An event emitter function
which can be called to emit the named event will be injected into the functions
arguments whenever it is called.
"""

class Event:
    """An Event object represents the context of an event. It is possible to subclass Event
    to add information for more specialized cases like ceam.framework.population.PopulationEvent

    Attributes
    ----------
    time  : datetime.datetime
            The simulation time at which this event was emitted.
    index : pandas.Index
            An index into the population table containing all simulants effected by this event.
    """

    def __init__(self, index, user_data={}):
        self.index = index
        self.user_data = user_data

        self.time = None

    def split(self, new_index):
        """Create a new event which is a copy of this one but with a new index.
        """
        new_event = Event(new_index, self.user_data)
        new_event.time = self.time
        return new_event

class _EventChannel:
    def __init__(self, manager):
        self.manager = manager

        self.listeners = [[] for i in range(10)]

    def emit(self, event):
        if hasattr(event, 'time'):
            event.time = self.manager.clock()

        for priority_bucket in self.listeners:
            for listener in sorted(priority_bucket, key=lambda x: x.__name__):
                listener(event)


class EventManager:
    """The configuration for the event system.

    Notes
    -----
    Client code should never need to interact with this class
    except through the decorators in this module and the emitter
    function exposed on the builder during the setup phase.
    """

    def __init__(self):
        self.__event_types = defaultdict(lambda :_EventChannel(self))

    def setup(self, builder):
        self.clock = builder.clock()

    def get_emitter(self, name):
        """Get an emitter function for the named event

        Parameters
        ----------
        name : str
               The name of the event

        Returns
        -------
        callable
            A function that accepts an Event object and distributes
            it to all listeners for this event.
        """

        return self.__event_types[name].emit

    def register_listener(self, name, listener, priority=5):
        self.__event_types[name].listeners[priority].append(listener)

    def _emitter_injector(self, func, args, kwargs, label):
        return list(args) + [self.__event_types[label].emit], kwargs

    def setup_components(self, components):
        emits.set_injector(self._emitter_injector)
        for component in components:
            listeners = [(v, component, i) for i,priority in enumerate(listens_for.finder(component)) for v in priority]
            listeners += [(v, getattr(component, att), i) for att in sorted(dir(component)) for i,vs in enumerate(listens_for.finder(getattr(component, att))) for v in vs]

            for event, listener, priority in listeners:
                self.register_listener(event, listener, priority)

            emitters = [(v, component) for v in emits.finder(component)]
            emitters += [(v, getattr(component, att)) for att in sorted(dir(component)) for v in emits.finder(getattr(component, att))]

            # Pre-create the EventChannels for known emitters
            for (args, kwargs), emitter in emitters:
                self.get_emitter(*args, **kwargs)

    def list_events(self):
        """List all event names known to the event system

        Returns
        -------
        list
            A list of all known event names

        Notes
        -----
        This value can change after setup if components dynamically create new event labels.
        """

        return list(self.__event_types.keys())
