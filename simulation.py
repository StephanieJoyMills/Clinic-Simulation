import random
import simpy
from functools import partial, wraps

RANDOM_SEED = 720
IAT_MIN = 8
IAT_MAX = 16
SIM_TIME = 1997200
# Define our probabilities
CLINIC_OPERATION = 12 * 7
global patients_arrived
patients_arrived = 0

shift = {}

bulking = {
    "em_ser": 0.3,
    "em_mod": 0,
    "img_in": 0.15,
    "img_out": 0,
    "lab_in": 0.1,
    "lab_out": 0,
}

reneging = {
    "em_ser": [90, 150],
    "em_mod": None,
    "img_in": [30, 90],
    "img_out": None,
    "lab_in": [30, 90],
    "lab_out": None,
}

timing = {
    "em_ser": [[1.5, 1, 1],[1.5, 1, 1],[1.5, 1, 0.5]],
    "em_mod": [[3, 2, 2],[3, 2, 1],[3, 1, 0.5]],
    "img_in": None,
    "img_out": [[12, 8, 0],[10, 5, 0],[5, 2, 0]],
    "lab_in": None,
    "lab_out": [[16, 10, 0],[12, 0, 0],[8, 0, 0]],
}


class Patient(object):
    def __init__(self, env, num, priority, purpose, prob_bulking, prob_reneging):
        self.env = env
        self.id = num
        self.priority = priority
        self.purpose = purpose
        self.prob_bulking = prob_bulking
        self.prop_reneging = prob_reneging

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
        print(
            "Registration for patient %s has started servicing %s." % (self.id, patient)
        )


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


def patient(env, patient):
    print(patient.__dict__)
    yield env.timeout(1)  

def convert_time(time):
    tot_hours = time / 60 / 60
    week_hours = tot_hours % 84
    if (week_hours < 60):
        weekIndex = 0
    elif (week_hours > 72):
        weekIndex = 2
    else:
        weekIndex = 1

    day_hours = week_hours % 12
    if (day_hours < 4):
        dayIndex = 0
    elif (day_hours > 8):
        dayIndex = 2
    else:
        dayIndex = 1
    return [weekIndex, dayIndex]

def setup(env):
    """Keep creating workers approx. every ``IAT`` minutes +-1 IAT_range ."""
    global patients_arrived
    patient_timeouts = {
        "em_ser": None,
        "em_mod": None,
        "img_in": None,
        "img_out": None,
        "lab_in": None,
        "lab_out": None,
    }
    for key in patient_timeouts:
        if patient_timeouts[key] == None:
            now = convert_time(env.now)
            patient_timeouts[key] = None if timing[key] == None else timing[key][now[0]][now[1]] + env.now


    while True:
        minTime = 99999
        for key, value in patient_timeouts.items():
            if value != None and value < minTime:
                minTime = value
                next_timeout = key

        yield env.timeout(patient_timeouts[next_timeout])

        priority = (
            2 if next_timeout == "em_ser" else 1 if next_timeout == "em_mod" else None
        )

        prob_bulking = bulking[next_timeout]
        prob_reneging = (
            None
            if reneging[next_timeout] == None
            else random.randint(reneging[next_timeout][0], reneging[next_timeout][0])
        )
        
        new_patient = Patient(env, patients_arrived, priority, next_timeout, prob_bulking, prob_reneging)

        env.process(patient(env, new_patient))
        patient_timeouts[next_timeout] = timing[key][now[0]][now[1]] + env.now
        patients_arrived += 1


# Create an environment
random.seed(RANDOM_SEED)
env = simpy.Environment()

# Initialize cachier
# cachier = Cachier(env, 3)

# Set-up and Execute!
env.process(setup(env))
env.run(until=SIM_TIME)
