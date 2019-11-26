# To run simulation 200 times in terminal run: for i in {1..100}; do python a416.py; done;
import random
import simpy
import csv


IAT_MEAN = 11
RANDOM_SEED = 720
SIM_TIME = 60 * 16
global patients_arrived
patients_arrived = 0
time_in_syst = [None]*300

# Create and define patient


class Patient(object):
    def __init__(self, env, num):
        self.env = env
        self.id = num

# Create a define registration


class Registration(object):
    def __init__(self, env):
        self.env = env
        self.desk = simpy.Resource(env, 1)

    def service(self, patient):
        service_time = random.triangular(6, 10, 19)
        yield self.env.timeout(service_time)
        print("Registration service started for patient %s." % (patient))

# Create and define staff


class Staff(object):
    def __init__(self, env, id):
        self.env = env
        self.doctor = simpy.Resource(env, 1)
        self.lunchTaken = False
        self.id = id

    def lunch(self):
        print("Doctor {} has begun eating lunch!".format(self.id))
        self.lunchTaken = True
        yield self.env.timeout(30)

# Create and define exam


class ExamRoom(object):
    def __init__(self, env):
        self.env = env
        self.room = simpy.Resource(env, 3)

    def service(self, patient):
        service_type = random.randrange(0, 1)
        if (service_type < 0.55):
            service_time = random.triangular(14, 22, 39)
        else:
            service_time = random.triangular(24, 36, 59)
        yield self.env.timeout(service_time)
        print("Exam service started for patient %s." % (patient))

# Each new patient is run through this patient function  to simulate the process of going to the clinic


def patient(env, patient, registration, exam_room, staff):
    global time_in_syst
    print("Patient {} arrives in system at {}".format(patient.id, env.now))
    time_in_syst[patient.id] = env.now
    # When patient first arrives they enter the registration
    with registration.desk.request() as request:
        yield request
        print("Patient %s enters the registration at %.2f." %
              (patient.id, env.now))
        yield env.process(registration.service(patient.id))
        print("Patient %s finished registration service. Leaving registration at %.2f." %
              (patient.id, env.now))
    # After registration the patient goes to a room
    with exam_room.room.request() as request:
        yield request
        print("Patient %s enters the exam room at %.2f." %
              (patient.id, env.now))
        # Patient waits until doctor is available
        doc = yield staff.get()
        print("Doctors arrived for treatment of Patient {}".format(patient.id))
        yield env.process(exam_room.service(patient.id))
        print("Patient %s finished exam room service. Leaving exam room at %.2f." %
              (patient.id, env.now))
        staff.put(doc)
    # Keep track of how long patient was in  service
    time_in_syst[patient.id] = env.now - time_in_syst[patient.id]
    print(time_in_syst[patient.id])


def setup(env, registration, exam_room, staff):
    global patients_arrived
    # refrash doctors on new shift
    next_shift = False

    while True:
        time = env.now
        # check to see if we are above 8 hours - if we are change the doctors
        if not next_shift and time > 8 * 60:
            with staff.get(lambda doctor: doctor.lunchTaken == False) as doc:
                results = yield doc | env.timeout(0)
                if doc not in results:
                    print("---------SHIFT CHANGE--------")
                    next_shift = True
                    staff = simpy.FilterStore(env, 3)
                    doc_a = Staff(env, 0)
                    doc_b = Staff(env, 1)
                    doc_c = Staff(env, 2)
                    staff.put(doc_a)
                    staff.put(doc_b)
                    staff.put(doc_c)
        # Check if there is any free doctors and it is during a feasible lunch time - see if any doctors need to take thir lunch
        if (len(staff.items) != 0 and time < 8 * 60 and time > 3.5 * 60 or time > (8 + 3.5) * 60):
            with staff.get(lambda doctor: doctor.lunchTaken == False) as doc:
                results = yield doc | env.timeout(0)
                if doc in results:
                    print(results[doc])
                    env.process(results[doc].lunch())
                    yield staff.put(results[doc])

        yield env.timeout(random.expovariate(1/IAT_MEAN))

        new_patient = Patient(env, patients_arrived)

        env.process(patient(env, new_patient, registration, exam_room, staff))
        patients_arrived += 1

# Write average patient time to file for replication


def writeAvg(file_name, avg):
    with open(file_name + '.csv', 'a') as csvfile:
        writer = csv.writer(csvfile, delimiter=',')
        writer.writerow([avg])


# Create an environment
env = simpy.Environment()

# Create store of doctors and initialize
staff = simpy.FilterStore(env, 3)
doc_a = Staff(env, 0)
doc_b = Staff(env, 1)
doc_c = Staff(env, 2)
staff.put(doc_a)
staff.put(doc_b)
staff.put(doc_c)

# Initialize
registration = Registration(env)
exam_room = ExamRoom(env)

# Set-up and Execute!
env.process(setup(env, registration, exam_room, staff))
env.run(until=SIM_TIME)

# Stastics printing
sum = 0
count = 0
for i, time in enumerate(time_in_syst):
    if (time == None or time > 900):
        count = i
        break
    sum = sum + time
    print('Patient {} was in system for {} minutes'.format(i + 1, time))
avg = sum / count
writeAvg("avgs", avg)
