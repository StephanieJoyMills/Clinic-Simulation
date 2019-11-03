import random
import simpy
from functools import partial, wraps

# Define our probabilities
CLINIC_OPERATION = 12 * 7 
# Define our tracking vars
global workers_arrived
workers_arrived = 0
global workers_served
workers_served = 0
global all_busy
all_busy = False
global wait
wait = [[0] * 1000, [0] * 1000, [0] * 1000]
global worker_wait
worker_wait = [0] * 1000
global cachier_wait
cachier_wait = 0
global cachier_worker_wait
cachier_worker_wait = [0] * 1000

class Patient(object):
    def __init__(self, env, id, priority, purpose):
        self.id = id
        self.priority = priority
        self.purpose = 0
        self.probBulking = 0
        self.propReneging = 0
        self.env = env

# priority resource
class Registration(object):
    def __init__(self, env, id, priority):
        self.id = id
        self.priority = priority
        self.env = env
        self.env = simpy.Resource(env, 1)

    def service(self, patient):
        service_time = random.randrange(3, 8)
        yield self.env.timeout(service_time)
        print('Registration for patient %s has started servicing %s.' % (self.id, patient))

# priority resource
class ED(object):
    def __init__(self, env, id, priority):
        self.id = id
        self.priority = priority
        self.env = env
        self.room = simpy.resources.resource.PriorityResource(env, 4)

# priority resource
class Imaging(object):
    def __init__(self, env, id, priority):
        self.id = id
        self.priority = priority
        self.env = env
        self.station = simpy.resources.resource.PriorityResource(env, 1)

# priority resource
class Lab(object):
    def __init__(self, env, id, priority):
        self.id = id
        self.priority = priority
        self.env = env
        self.station = simpy.resources.resource.PriorityResource(env, 2)

class Clerk(object):
    def __init__(self, env, id):
        self.id = id
        self.env = env
        self.clerk = simpy.Resource(env, 1)

    def service(self, worker):
        """The clerk service process. It takes a ``worker`` processes and tries
        to service it."""
        service_time = random.randrange(
            CLERK_SERVICE_TIME_MIN, CLERK_SERVICE_TIME_MAX)
        yield self.env.timeout(service_time)
        print('Clerk %s has started servicing %s.' % (self.id, worker))

    def __str__(self):
        return str(self.__class__) + ": " + str(self.__dict__)


class Cachier(object):
    def __init__(self, env, id):
        self.env = env
        self.id = id
        self.cachier = simpy.Resource(env, 1)

    def checkout(self, worker):
        """The cachier check_out process. It takes a ``worker`` processes and tries
        to check it out."""
        checkout_time = random.randrange(
            CACHIER_SERVICE_TIME_MIN, CACHIER_SERVICE_TIME_MAX)
        yield self.env.timeout(checkout_time)
        print("Cachier services ", worker)

    def __str__(self):
        return str(self.__class__) + ": " + str(self.__dict__)


def worker(env, worker, clerks, cachier):
    global all_busy
    global workers_served
    global cachier_wait
    # Set all_busy to True is all clerks are busy at the same time
    if not all_busy and len(clerks.items) == 0:
        all_busy = True
    name = "Worker" + str(worker)
    # Grab an available Clerk - otherwise wait until one is available (FIFO)
    print('%s arrives at the store at %.2f.' % (name, env.now))
    worker_wait[worker] = env.now
    clerk = yield clerks.get()
    start = env.now

    with clerk.clerk.request() as request:
        yield request
        worker_wait[worker] = env.now - worker_wait[worker]
        clerk_waiting_time[clerk.id] = clerk_waiting_time[clerk.id] + \
            worker_wait[worker]

        print('%s enters the service at %.2f.' % (name, env.now))
        yield env.process(clerk.service(name))

        print('%s finished being serviced. Leaves the clerk %s at %.2f.' %
              (name, clerk.id, env.now))

    # Keep track of how many workers are serviced by a clerk, and the totoal time a clerk is busy for
    clerk_num_served[clerk.id] += 1
    clerk_busy[clerk.id] += env.now - start
    yield clerks.put(clerk)

    # Grab the cachier when avaialble (Queue FIFO)
    cachier_worker_wait[worker] = env.now
    with cachier.cachier.request() as request:
        yield request
        cachier_worker_wait[worker] = env.now - cachier_worker_wait[worker]
        cachier_wait = cachier_wait + cachier_worker_wait[worker]

        print('%s enters the cachier at %.2f.' % (name, env.now))
        yield env.process(cachier.checkout(name))

        print('%s finished checking out. Leaves the cachier at %.2f.' %
              (name, env.now))
    # Keep track of how many workers are fully served (make it throuch chachier)
    workers_served += 1


def setup(env, clerks, cachier):
    """Keep creating workers approx. every ``IAT`` minutes +-1 IAT_range ."""
    global workers_arrived
    while True:
        timeout = env.timeout(random.randint(IAT_MIN, IAT_MAX))
        yield timeout
        env.process(worker(env, workers_arrived, clerks, cachier))
        workers_arrived += 1


# Create an environment
random.seed(RANDOM_SEED)
env = simpy.Environment()

# Initialize clerk data for clerk A, B and C
clerk_num_served = [0, 0, 0]
clerk_busy = [0, 0, 0]
clerk_waiting_time = [0, 0, 0]

# Initialize cachier data
cachier_wait = 0

# Create store of clerks and initialize and add in each clerk
clerks = simpy.Store(env, 3)
clerk_a = Clerk(env, 0)
clerk_b = Clerk(env, 1)
clerk_c = Clerk(env, 2)
clerks.put(clerk_a)
clerks.put(clerk_b)
clerks.put(clerk_c)

# Initialize cachier
cachier = Cachier(env, 3)

# Set-up and Execute!
env.process(setup(env, clerks, cachier))
env.run(until=SIM_TIME)


# Print statistics
clerks = ["Clerk A", "Clerk B", "Clerk C"]

print(clerk_busy)
print(SIM_TIME)
print("System's Statisitcs:")
print("\t Workers Arrived: ", workers_arrived)
print("\t Workers Served: ", workers_served)
print("\t Clerks all busy at same time: ", all_busy)
print("\t Avg time busy: %i" % (sum(clerk_busy) / len(clerk_busy)))
print("\t Avg busy clerk: %.2f\n\n" %
      (sum(clerk_busy) / len(clerk_busy) / SIM_TIME))

for x in range(3):
    print("%s's Statisitcs:" % (clerks[x]))
    print("\t Number of Workers Served: ", clerk_num_served[x])
    print("\t Time Busy: ", clerk_busy[x])
    print("\t Util: %.2f" % (clerk_busy[x] / SIM_TIME))
    print("\t Total Waiting Time: ", clerk_waiting_time[x])
    print("\t Average Waiting Time: %.2f\n\n" %
          (clerk_waiting_time[x] / clerk_num_served[x]))

print("Cachier's Statisitcs:")
print("\t Number of Workers Served: ", workers_served)
print("\t Total Waiting Time: ", cachier_wait)
print("\t Average Waiting Time: %.2f" % (cachier_wait / workers_served))
