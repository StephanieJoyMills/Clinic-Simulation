import random
import simpy
import math
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

# TIME IS IN MIN
balking = {
    "em_ser": 0,
    "em_mod": 0.3,
    "img_in": 0,
    "img_out": 0.15,
    "lab_in": 0,
    "lab_out": 0.1,
}

reneging = {
    "em_ser": None,
    "em_mod": [90, 150],
    "img_in": None,
    "img_out": [30, 90],
    "lab_in": None,
    "lab_out": [0, 0],
}

timing = {
    "em_ser": [[1.5, 1, 1], [1.5, 1, 1], [1.5, 1, 0.5]],
    "em_mod": [[3, 2, 2], [3, 2, 1], [3, 1, 0.5]],
    "img_in": None,
    "img_out": [[12, 8, 0], [10, 5, 0], [5, 2, 0]],
    "lab_in": None,
    "lab_out": [[16, 10, 0], [12, 0, 0], [8, 0, 0]],
}

costs = {
    "doctor": 200,
    "nurse": 100,
    "imaging_tech": 90,
    "lab_tech": 80,
    "registration": 40
}

hourly_room_cost = {
    "ED": 500,
    "imaging": 400,
    "lab": 300,
    "registration": 50
}

capital_room_cost = {
    "ED": 200000,
    "imaging": 800000,
    "lab": 180000,
    "registration": 30000
}

# if someone from ER gets referred to something else
mod_refferal = {
    "imaging": 0.15,
    "lab": 0.2,
    "dep": 0.65
}

ser_refferal = {
    "imaging": 0.2,
    "lab": 0.25,
    "dep": 0.55
}

staff_schedule = {
    # 8-12, 12-16, 16-20 hours
    "doctor": [1, 1, 1],
    "nurse": [2, 2, 2],
    "imaging_tech": [1, 1, 1],
    "lab_tech": [1, 1, 1],
    "registration": [1, 1, 1],
}

hosptial_layout = {
    "registration": 1,
    "ED": 4,
    "imaging": 1,
    "lab": 2,
}


class Patient(object):
    def __init__(self, env, num, priority, purpose, prob_balking, reneging_threshold):
        self.env = env
        self.id = num
        self.priority = priority
        self.purpose = purpose
        self.prob_balking = prob_balking
        self.reneging_threshold = reneging_threshold


class Registration(object):
    def __init__(self, env, num_clerks):
        self.env = env
        self.desk = simpy.Resource(env, hosptial_layout["registration"])
        self.clerk = simpy.Resource(env, num_clerks)

    def service(self, patient):
        service_time = random.randrange(3, 8)
        yield self.env.timeout(service_time)
        print("Registration service started for patient %s." % (patient))


# priority resource
class ED(object):
    def __init__(self, env, num_nurses, num_doctors):
        self.env = env
        self.room = simpy.resources.resource.PriorityResource(
            env, hosptial_layout["ED"])
        self.nurse = simpy.resources.resource.PriorityResource(env, num_nurses)
        self.doctor = simpy.resources.resource.PriorityResource(
            env, num_doctors)


# priority resource
class Imaging(object):
    def __init__(self, env, num_imaging_techs):
        self.env = env
        self.station = simpy.resources.resource.PriorityResource(
            env, hosptial_layout["imaging"])
        self.tech = simpy.resources.resource.PriorityResource(
            env, num_imaging_techs)

    def service(self, patient):
        service_time = random.triangular(8, 20, 12)
        yield self.env.timeout(service_time)
        print("Imaging service started for patient %s." % (patient))


# priority resource
class Lab(object):
    def __init__(self, env, num_lab_techs):
        self.env = env
        self.station = simpy.resources.resource.PriorityResource(
            env, hosptial_layout["lab"])
        self.tech = simpy.resources.resource.PriorityResource(
            env, num_lab_techs)

    def service(self, patient):
        service_time = random.triangular(4, 10, 6)
        yield self.env.timeout(service_time)
        print("Lab service started for patient %s." % (patient))


def patient(env, patient, registration, ed, imaging, lab):
    # print(patient.__dict__)
    if (patient.purpose == "lab_out"):
        if (lab.station.count >= 5 and patient.prob_balking > random.randrange(0, 1)):
            print('Patient {} is balking'.format(patient.id))
        else:
            print('Patient is not balking')
            waitForRegistration(patient)
            with lab.station.request(priority=patient.priority) as request:
                results = yield request | env.timeout(patient.reneging_threshold)
                if request in results:
                    print("Patient %s enters the lab at %.2f." %
                          (patient.id, env.now))
                    with lab.tech.request(priority=patient.priority) as request:
                        yield request
                        print("Lab tech has arrived for service of patient {} at {}".format(
                            patient.id, env.now))
                        yield env.process(lab.service(patient.id))
                        print("Patient %s finished lab service. Leaving lab at %.2f." %
                              (patient.id, env.now))
                else:
                    print('Patient {} reneged from lab'.format(patient.id))
    if (patient.purpose == "img_out"):
        if (imaging.station.count >= 5 and patient.prob_balking > random.randrange(0, 1)):
            print('Patient {} is balking'.format(patient.id))
        else:
            print('Patient is not balking')
            waitForRegistration(patient)
            with imaging.station.request(priority=patient.priority) as request:
                results = yield request | env.timeout(patient.reneging_threshold)
                if request in results:
                    print("Patient %s enters the imaging at %.2f." %
                          (patient.id, env.now))
                    with imaging.tech.request(priority=patient.priority) as request:
                        yield request
                        print("Imaging tech has arrived for service of patient {} at {}".format(
                            patient.id, env.now))
                        yield env.process(imaging.service(patient.id))
                        print("Patient %s finished imaging service. Leaving imaging at %.2f." %
                              (patient.id, env.now))
                else:
                    print('Patient {} reneged from imaging'.format(patient.id))
    if (patient.purpose == "em_mod"):
        if (ED.room.count >= 5 and patient.prob_balking > random.randrange(0, 1)):
            print('Patient {} is balking'.format(patient.id))
        else:
            print('Patient is not balking')
            waitForRegistration(patient)

            with imaging.station.request(priority=patient.priority) as request:
                results = yield request | env.timeout(patient.reneging_threshold)
                if request in results:
                    print("Patient %s enters the imaging at %.2f." %
                          (patient.id, env.now))
                    with imaging.tech.request(priority=patient.priority) as request:
                        yield request
                        print("Imaging tech has arrived for service of patient {} at {}".format(
                            patient.id, env.now))
                        yield env.process(imaging.service(patient.id))
                        print("Patient %s finished imaging service. Leaving imaging at %.2f." %
                              (patient.id, env.now))
                else:
                    print('Patient {} reneged from imaging'.format(patient.id))


def waitForRegistration(registration, patient):
    with registration.desk.request() as request:
        yield request
        print("Patient %s enters the registration at %.2f." %
              (patient.id, env.now))
        yield env.process(registration.service(patient.id))
        print("Patient %s finished registration service. Leaving registration at %.2f." %
              (patient.id, env.now))


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


def get_time(env):
    # env.now in min
    # Week: Day:   Hour:   Min:
    time = env.now
    tempTime = time
    week_min = 10080
    day_min = 1440
    hour_min = 60
    week = tempTime // week_min
    tempTime = tempTime - week * week_min
    day = tempTime // day_min
    tempTime = tempTime - day * day_min
    hour = tempTime // hour_min
    minu = tempTime - hour * hour_min

    time = {
        "week": week,
        "day": day,
        "hour": hour,
        "minu": minu
    }
    print(time)


def setup(env, registration, ed, imaging, lab):
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
            patient_timeouts[key] = None if timing[key] == None else timing[key][now[0]
                                                                                 ][now[1]] + env.now

    shift_change = [False, False, False]

    while True:

        time = get_time(env)
        hour = time["hour"]
        if (hour > 20):
            print("Clinic is now closed.".format(time))
            shift_change = [False, False, False]
            # clinic closes for 12 hours
            yield env.timeout(60 * 12)
            break

        if (hour > 8 and hour < 12 and shift_change[0] == False):
            registration = Registration(env, staff_schedule["registration"][0])
            ed = ED(env, staff_schedule["nurse"]
                    [0], staff_schedule["doctor"][0])
            imaging = Imaging(env, staff_schedule["imaging_tech"][0])
            lab = Lab(env, staff_schedule["lab_tech"][0])
            shift_change[0] == True

        elif (hour > 12 and hour < 16 and shift_change[1] == False):
            registration = Registration(env, staff_schedule["registration"][1])
            ed = ED(env, staff_schedule["nurse"]
                    [1], staff_schedule["doctor"][1])
            imaging = Imaging(env, staff_schedule["imaging_tech"][1])
            lab = Lab(env, staff_schedule["lab_tech"][1])
            shift_change[1] == True

        elif (hour > 16 and hour < 20 and shift_change[2] == False):
            registration = Registration(env, staff_schedule["registration"][2])
            ed = ED(env, staff_schedule["nurse"]
                    [2], staff_schedule["doctor"][2])
            imaging = Imaging(env, staff_schedule["imaging_tech"][2])
            lab = Lab(env, staff_schedule["lab_tech"][2])
            shift_change[2] == True

        minTime = 99999
        # Change shift of staff based on time on new days re-start
        for key, value in patient_timeouts.items():
            if value != None and value < minTime:
                minTime = value
                next_timeout = key

        yield env.timeout(patient_timeouts[next_timeout])

        priority = (
            2 if next_timeout == "em_ser" else 1 if next_timeout == "em_mod" else None
        )

        prob_balking = balking[next_timeout]
        reneging_threshold = (
            None
            if reneging[next_timeout] == None
            else random.randint(reneging[next_timeout][0], reneging[next_timeout][1])
        )

        new_patient = Patient(env, patients_arrived, priority,
                              next_timeout, prob_balking, reneging_threshold)

        env.process(patient(env, new_patient, registration, ed, imaging, lab))
        patient_timeouts[next_timeout] = timing[key][now[0]][now[1]] + env.now
        patients_arrived += 1


# Create an environment
random.seed(RANDOM_SEED)
env = simpy.Environment(initial_time=60*8)

# Initialize
registration = Registration(env, staff_schedule["registration"][2])
ed = ED(env, staff_schedule["nurse"]
        [2], staff_schedule["doctor"][2])
imaging = Imaging(env, staff_schedule["imaging_tech"][2])
lab = Lab(env, staff_schedule["lab_tech"][2])
print(lab.station.__dict__)

# Set-up and Execute!
env.process(setup(env, registration, ed, imaging, lab))
env.run(until=SIM_TIME)

# print_time(None)
