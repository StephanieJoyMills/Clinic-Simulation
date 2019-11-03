import random
import simpy
from functools import partial, wraps

RANDOM_SEED = 42
# NUM_CLERKS = 3  # Number of clerks
# NUM_CACHIER = 1
# Must generate by uniform dist (12, 28)
CLERK_SERVICE_TIME = 5
IAT = 5       # IAT 8 TO 16 (MUST GENERATE)
# SIM_TIME = 7200     # Simulation time in minutes
SIM_TIME = 100


def patch_resource(resource, pre=None, post=None):
    """Patch *resource* so that it calls the callable *pre* before each
    put/get/request/release operation and the callable *post* after each
    operation.  The only argument to these functions is the resource
    instance.

    """
    def get_wrapper(func):
        # Generate a wrapper for put/get/request/release
        @wraps(func)
        def wrapper(*args, **kwargs):
            # This is the actual wrapper
            # Call "pre" callback
            if pre:
                pre(resource)

            # Perform actual operation
            ret = func(*args, **kwargs)

            # Call "post" callback
            if post:
                post(resource)

            return ret
        return wrapper

    # Replace the original operations with our wrapper
    for name in ['put', 'get', 'request', 'release']:
        if hasattr(resource, name):
            setattr(resource, name, get_wrapper(getattr(resource, name)))


def monitor(data, resource):
    """This is our monitoring callback."""
    item = (
        resource._env.now,  # The current simulation time
        resource.count,  # The number of users
        len(resource.queue),  # The number of queued processes
    )
    data.append(item)


class Store(object):
    def __init__(self, env, monitor):
        self.env = env
        self.clerk = simpy.Resource(env, 3)
        self.cashier = simpy.Resource(env, 1)

        patch_resource(self.clerk, post=monitor)

    def service(self, worker):
        """The clerk service process. It takes a ``worker`` processes and tries
        to service it."""
        service_time = random.randrange(12, 28)
        yield self.env.timeout(service_time)
        print("Clerk services ", worker)

    def checkout(self, worker):
        """The cachier check_out process. It takes a ``worker`` processes and tries
        to service it."""
        checkout_time = random.randrange(1, 11)
        yield self.env.timeout(checkout_time)
        print("Cachier services ", worker)

    def __str__(self):
        return str(self.__class__) + ": " + str(self.__dict__)


def worker(env, name, store):
    """The worker process (each worker has a ``name``) arrives at the store
    (``clerk``) and requests a clerk.

    It then starts the clerk service, waits for it to finish  HCANGEand
    leaves to never come back ...

    """
    print('%s arrives at the store at %.2f.' % (name, env.now))
    with store.clerk.request() as request:
        yield request

        print('%s enters the service at %.2f.' % (name, env.now))
        yield env.process(store.service(name))
        # change
        print('%s finished being serviced. Leaves the clerk at %.2f.' %
              (name, env.now))

    with store.cashier.request() as request:
        yield request

        print('%s enters the cachier at %.2f.' % (name, env.now))
        yield env.process(store.checkout(name))

        print('%s finished checking out. Leaves the cachier at %.2f.' %
              (name, env.now))


def setup(env, iat, monitor):
    """Create a store, a number of initial workers and keep creating workers
    approx. every ``t_inter`` minutes."""
    # Create the carwash
    store = Store(env, monitor)
    i = 1
    while True:
        timeout = env.timeout(random.randint(iat - 4, iat + 4))
        yield timeout
        env.process(worker(env, 'Worker %d' % i, store))
        i += 1


random.seed(RANDOM_SEED)  # This helps reproducing the results

# Create an environment and start the setup process
env = simpy.Environment()
data = []

monitors = partial(monitor, data)

env.process(setup(env, IAT, monitors))

# Execute!
env.run(until=SIM_TIME)
print(data)

# get the utilization of each clerk
