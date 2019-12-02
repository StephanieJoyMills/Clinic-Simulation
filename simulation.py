#IMPORTS
import random #ability to generate random numbers
import simpy #for simulation features
import math #abilitity to run mathematical calculations
from functools import partial, wraps

RANDOM_SEED = 720 #set seed for randomization
IAT_MIN = 8 #minimum interarrival time
IAT_MAX = 16 #maximum interarrival time
SIM_TIME = 1997200 #time of the simulation

CLINIC_OPERATION = 12 * 7 #HOURS DAYS
global patients_arrived
patients_arrived = 0 #initally 0 patients in clinic

shift = {}

# DEFINE OUR PROBABILITIES
#probability of balking
balking = { 
    "em_ser": 0, #probability of balking from ED as a serious patient
    "em_mod": 0.3,  #probability of balking from ED as a moderate patient
    "img_in": 0, #probability of balking from imaging as an inpatient
    "img_out": 0.15, #probability of balking from imaging as an outpatient
    "lab_in": 0, #probability of balking from lab as an inpatient
    "lab_out": 0.1, #probability of balking from lab as an outpatient
}

#Renegeing threshold in minutes
reneging = {
    "em_ser": None,
    "em_mod": [90, 150],
    "img_in": None,
    "img_out": [30, 90],
    "lab_in": None,
    "lab_out": [30, 90],
}

#Patient arrival rates per department
arrival_times = {
    "em_ser": [[1.5, 1, 1], [1.5, 1, 1], [1.5, 1, 0.5]],
    "em_mod": [[3, 2, 2], [3, 2, 1], [3, 1, 0.5]],
    "img_in": None,
    "img_out": [[12, 8, 0], [10, 5, 0], [5, 2, 0]],
    "lab_in": None,
    "lab_out": [[16, 10, 0], [12, 0, 0], [8, 0, 0]],
}

#The cost of staff resources hourly
costs = {
    "doctor": 200,
    "nurse": 100,
    "imaging_tech": 90,
    "lab_tech": 80,
    "registration": 40
}

#Probability that someone from ER gets referred elsewhere
#Moderate ER Referral
mod_referral = { #CDF
    "imaging": 0.15, #15%
    "lab": 0.35, #20%
    "dep": 1 #65%
}

#Serious ER Referral
ser_referral = { #CDF
    "imaging": 0.2,
    "lab": 0.45,
    "dep": 1
}

#General Staff schedule
staff_schedule = {
    # 8-12, 12-16, 16-20 hours
    "doctor":        [1, 1, 1],
    "nurse":         [2, 2, 2],
    "imaging_tech":  [1, 1, 1],
    "lab_tech":      [1, 1, 1],
    "registration":  [1, 1, 1],
}

#Number of hospital stations available
hosptial_layout = {
    "registration": 1, #1 registration desk
    "ED": 4, #4 Emergency Department rooms
    "imaging": 1, #1 imaging station
    "lab": 2, #2 lab stations
}

#The cost of rooms associated with operation
#Operating rooms per hour
hourly_room_cost = {
    "ED": 500,
    "imaging": 400,
    "lab": 300,
    "registration": 50
}

#Operating Capital Costs (New)
capital_room_cost = {
    "ED": 200000,
    "imaging": 800000,
    "lab": 180000,
    "registration": 30000
}

# VARIABLES USED FOR STATISTICS
patientStats = []

balkingStats = { 
    "em_ser": 0, 
    "em_mod": 0,
    "img_in": 0, 
    "img_out": 0, 
    "lab_in": 0, 
    "lab_out": 0
}

renegingStats = {
    "em_ser": 0,
    "em_mod": 0,
    "img_in": 0,
    "img_out": 0,
    "lab_in": 0,
    "lab_out": 0,
}

VAT = { 
    "em_ser": [0,0], 
    "em_mod": [0,0],
    "img_in": 0,
    "img_out": [0,0],
    "lab_in": 0,
    "lab_out": [0,0],
}

staffUtilTime = {
    "doctor": 0,
    "nurse": 0,
    "imaging_tech": 0,
    "lab_tech": 0,
    "registration": 0
}

operatingTime = 0

roomUtilTime = {
    "registration": 0, 
    "ED": 0, 
    "imaging": 0, 
    "lab": 0, 
}

def get_time(env):
  # Week: Day:   Hour:   Min:
    time = env.now #set the time to the current environment time in simpy
    tempTime = time #stash temp for now (runs in minutes)

    week_min = 10080 #number of minutes in a week
    day_min = 1440 #number of minutes in a day
    hour_min = 60 #number of minutes in an hr

    week = tempTime // week_min #number of hours in a given week is time w/ Floor division
    tempTime = tempTime - week * week_min #update temptime to remove number of weeks
    day = tempTime // day_min # floor division results whole number
    tempTime = tempTime - day * day_min
    hour = tempTime // hour_min
    minu = tempTime - hour * hour_min

    time = {
        "week": week,
        "day": day,
        "hour": hour,
        "minu": minu
    }

    return time #result the time


#CREATE PATIENT OBJECT
class Patient(object):
    def __init__(self, env, num, priority, purpose, prob_balking, reneging_threshold):
        #Each patient has attributes: self and environment
        self.env = env #SimPy requirement to create new simulation events
        self.id = num #Patient identifying number
        self.priority = priority #Priority level of patient
        self.purpose = purpose #Reason patient is visiting the clinc (which department: ED, lab etc.)
        self.prob_balking = prob_balking #Probability the patient balks from the clinic prior to entering queue
        self.reneging_threshold = reneging_threshold #Prob patient leaves while waiting in queue
        # Stats
        self.start =  None #arrival time
        self.registrationWaitTime = None #Wait time for registration 
        self.treatmentWaitTime = None #Wait time for treatment once in room
        self.treatmentTime = None #total treatment time
        self.serviceTime = None  #total service time (treatment + wait)

#CREATE REGISTRATION OBJECT
class Registration(object):
    def __init__(self, env, num_clerks):
        self.env = env 
        self.desk = simpy.Resource(env, hosptial_layout["registration"]) #create room resource at registration desk
        self.clerk = simpy.Resource(env, num_clerks) #create registration clerk object for registration desk

    def service(self, patient):
        temp = self.env.now
        service_time = random.randrange(3, 8) #registration time varies uniformly between 3-8 minutes
        print("Registration service started for patient %s." % (patient))
        yield self.env.timeout(service_time) #timeout patient object for this amount of time
        print("Registration service completed for patient %s." % (patient))
        staffUtilTime["registration"] =  staffUtilTime["registration"] +  self.env.now - temp


#CREATE PRIORITY RESOURCE
class ED(object):
    #INITIALIZE EMERGENCY DEPARTMENT
    def __init__(self, env, num_nurses, num_doctors):
        self.env = env
        self.room = simpy.resources.resource.PriorityResource(env, hosptial_layout["ED"]) #Create emergency department rooms
        self.nurse = simpy.resources.resource.PriorityResource(env, num_nurses) #Create number of nurses specified
        self.doctor = simpy.resources.resource.PriorityResource( env, num_doctors) #Create number of doctors specified

    #NURSE PREPARATION TIME
    def prep(self, patient):
        if (patient.purpose == "em_mod"): #MODERATE
            service_time = random.randint(6, 12)

        else: #SERIOUS
            service_time = random.randint(4, 7)

        temp = self.env.now
        print('Nurse prep service started for patient id: {} type: {}'.format(patient.id, patient.purpose,  get_time(env)))
        yield self.env.timeout(service_time) #Timeout nurse for service on patient
        print('Nurse prep service completed for patient id: {} type: {}'.format(patient.id, patient.purpose,  get_time(env))) #nurse released
        staffUtilTime["nurse"] = staffUtilTime["nurse"] + self.env.now - temp

    #DOCTORS FIRST EXAMINATION ON PATIENT
    def init_exam(self, patient):
        if (patient.purpose == "em_mod"): #Moderate exam
            service_time = random.randint(7, 15)
        else: #Serious Exam
            service_time = random.randint(5, 15)

        temp = self.env.now
        print("Doctor inital exam started for patient id: {} type: {}".format(patient.id, patient.purpose))
        yield self.env.timeout(service_time) #timeout doctor for duration of examination
        print("Doctor inital exam completed for patient id: {} type: {}".format(patient.id, patient.purpose))
        staffUtilTime["doctor"] = staffUtilTime["doctor"] + self.env.now - temp

    #DOCTORS FINAL EXAMINATION ON PATIENT
    def final_exam(self, patient):
        if (patient.purpose == "em_mod"): #moderate exam
            service_time = random.randint(2, 5)
        else: #serious exam
            service_time = random.randint(2, 5)
        temp = self.env.now
        print("Doctor final exam started for patient id: {} type: {}".format(patient.id, patient.purpose))
        yield self.env.timeout(service_time) #timeout doctor & patient for duration of examination
        print("Doctor final exam completed for patient id: {} type: {}".format(patient.id, patient.purpose))
        staffUtilTime["doctor"] = staffUtilTime["doctor"] + self.env.now - temp

#IMAGING DEPARTMENT OBJECT
class Imaging(object):
    def __init__(self, env, num_imaging_techs):
        self.env = env
        #Creating an imaging room
        self.station = simpy.resources.resource.PriorityResource(env, hosptial_layout["imaging"])
        #Add available amount of imaging tech resources
        self.tech = simpy.resources.resource.PriorityResource(env, num_imaging_techs)

    def service(self, patient):
        temp = self.env.now
        service_time = random.triangular(8, 20, 12) #8-20 min, mode = 12 min
        print("Imaging service started for patient id: {} type: {}".format(patient.id, patient.purpose))
        yield self.env.timeout(service_time) #timeout patient & image tech for this duration of time
        print("Imaging service completed for patient id: {} type: {}".format(patient.id, patient.purpose))
        staffUtilTime["imaging_tech"] = staffUtilTime["imaging_tech"] + self.env.now - temp


#LAB DEPARTMENT OBJECT
class Lab(object):
    def __init__(self, env, num_lab_techs):
        self.env = env
        #Initialize lab room objects as specified in dictionary
        self.station = simpy.resources.resource.PriorityResource(env, hosptial_layout["lab"])
        #create number of available lab techs for use
        self.tech = simpy.resources.resource.PriorityResource(env, num_lab_techs)

    def service(self, patient):
        temp = self.env.now
        service_time = random.triangular(4, 10, 6) #between 4-10 min, mode = 6 min.
        print("Lab service started for patient id: {} type: {}".format(patient.id, patient.purpose))
        yield self.env.timeout(service_time) #time out patient & lab resource for service
        print("Lab service completed for patient id: {} type: {}".format(patient.id, patient.purpose))
        staffUtilTime["lab_tech"] = staffUtilTime["lab_tech"] + self.env.now - temp

#REGISTRATION SERVICE
def wait_for_registration(registration, patient, env):
    print('Patient id: {} type: {} enters line for registration at {}'.format(patient.id, patient.purpose,  get_time(env)))
    #Request use of registration desk (is clerk available?)
    with registration.desk.request() as request:
        yield request #if clerk room & later clerk available, yield request
        roomAquired = env.now  
        print('Patient id: {} type: {} enters the registration at {}. Waiting for registration clerk..'.format(
            patient.id, patient.purpose,  get_time(env)))
        with registration.clerk.request() as request:
            yield request
            print("Registration clerk has arrived for service of patient id: {} type: {} at {}".format(
                patient.id, patient.purpose, get_time(env)))
            if (patient.purpose != "em_ser"):
                patient.registrationWaitTime = env.now - patient.start
            yield env.process(registration.service(patient)) #end process & release patient
    roomUtilTime["registration"] = roomUtilTime["registration"] + env.now - roomAquired
    print("Patient id: {} type: {} finished registration service at {}".format(
        patient.id, patient.purpose, get_time(env)))

#DECIDE WHERE PATIENT IS GOING & WHAT THEY'RE DOING
def patient(env, patient, registration, ED, imaging, lab):
    patient.start = env.now
    #Patient purpose is to strictly visit the lab
    if (patient.purpose == "lab_out"):
        #If there all lab stations are full, and there is a queue, will the patient balk?
        if (lab.station.count >= hosptial_layout["lab"] and patient.prob_balking > random.randrange(0, 1)):
            print('Patient id: {} type: {} who arrived for lab service is balking from registration at {}'.format(
                patient.id, patient.purpose,  get_time(env)))
            balkingStats[patient.purpose] = balkingStats[patient.purpose] + 1
            return
        else: # Patient does not balk
            yield env.process(wait_for_registration(registration, patient, env)) #register
            with lab.station.request(priority=patient.priority) as request: #join queue
                print("Patient id: {} type: {} begins waiting for lab at {}.".format(patient.id, patient.purpose, get_time(env)))
                results = yield request | env.timeout(patient.reneging_threshold) #does the patient renege from queue
                if request in results: #lab room is available, patient can enter
                    roomAquired = env.now
                    print("Patient id: {} type: {} enters the lab at {}. Waiting for tech".format(patient.id, patient.purpose, get_time(env)))
                    with lab.tech.request(priority=patient.priority) as request: 
                        yield request#lab tech available
                        print("Lab tech has arrived for service of patient id: {} type: {} at {}.".format( patient.id, patient.purpose, get_time(env)))
                        patient.treatmentWaitTime = env.now - patient.start
                        patient.treatmentTime = env.now
                        yield env.process(lab.service(patient)) #put patient into service with lab tech
                        patient.treatmentTime = env.now - patient.treatmentTime
                        print("Patient id: {} type: {} finished lab service at {}.".format( patient.id, patient.purpose, get_time(env)))
                        roomUtilTime["lab"] = roomUtilTime["lab"] + env.now - roomAquired

                else: #Patient gets sick of waiting and reneges
                    print('Patient id: {} type: {} reneged from lab'.format(patient.id, patient.purpose))
                    renegingStats[patient.purpose] = renegingStats[patient.purpose] + 1
                    return

    #Patient purpose is to strictly visit the imaging department
    elif (patient.purpose == "img_out"):
        if (imaging.station.count >= hosptial_layout["imaging"] and patient.prob_balking > random.randrange(0, 1)):
            print('Patient id: {} type: {} who arrived for imaging is balking from registration at {}'.format(patient.id, patient.purpose,  get_time(env))) #Patient balks
            balkingStats[patient.purpose] = balkingStats[patient.purpose] + 1
            return
        else: #Don't balk from system
            yield env.process(wait_for_registration(registration, patient, env)) #try to register
            with imaging.station.request(priority=patient.priority) as request:
                results = yield request | env.timeout(patient.reneging_threshold)
                if request in results:
                    roomAquired = env.now
                    print("Patient id: {} type: {} enters the imaging at {}.".format(
                        patient.id, patient.purpose, get_time(env)))
                    with imaging.tech.request(priority=patient.priority) as request:
                        yield request
                        print("Imaging tech has arrived for service of patient id: {} type: {} at {}".format(
                            patient.id, patient.purpose, get_time(env)))
                        patient.treatmentWaitTime = env.now - patient.start
                        patient.treatmentTime = env.now
                        yield env.process(imaging.service(patient))
                        patient.treatmentTime =  env.now - patient.treatmentTime
                        print("Patient id: {} type: {} finished imaging service at {}.".format
                              (patient.id, patient.purpose, get_time(env)))
                        roomUtilTime["imaging"] = roomUtilTime["imaging"] + env.now - roomAquired

                else: #Patient reneges from service with imaging
                    print('Patient id: {} type: {} reneged from imaging'.format(patient.id, patient.purpose))
                    renegingStats[patient.purpose] = renegingStats[patient.purpose] + 1
                    return
    elif (patient.purpose == "em_mod"):
        if (ED.room.count >= hosptial_layout["ED"] and patient.prob_balking > random.randrange(0, 1)):
            print('Patient id: {} type: {} who arrived to ED as moderate is balking from registration at {}'.format(patient.id, patient.purpose,  get_time(env))) # Patient Balks
            balkingStats[patient.purpose] = balkingStats[patient.purpose] + 1
            return
        else: #Patient waits in queue until serviced 
            yield env.process(wait_for_registration(registration, patient, env))
            with ED.room.request(priority=patient.priority) as request:
                results = yield request | env.timeout(patient.reneging_threshold) #Does time until renege become exceeded?
                if request in results: #PATIENT WAITS IN QUEUE TO GET INTO AN ER ROOM, AND GETS IN
                    EDAquired = env.now
                    print("Patient id: {} type: {} enters the ED at {}. Waiting for nurse..".format(patient.id, patient.purpose, get_time(env)))
                    with ED.nurse.request(priority=patient.priority) as request: #Wait on nurse
                        yield request #Patient gets access to a nurse in their ER room
                        print("Nurse has arrived for service of patient id: {} type: {} at {}".format(patient.id, patient.purpose, get_time(env)))
                        patient.treatmentWaitTime = env.now - patient.start
                        patient.treatmentTime = env.now
                        yield env.process(ED.prep(patient)) #Nurse completes prep to serve patient
                        patient.treatmentTime = env.now - patient.treatmentTime
                        print("Nurse leaves patient id: {} type: {} at {}. Waiting for doctor".format(patient.id, patient.purpose, get_time(env)))
                    with ED.doctor.request(priority=patient.priority) as request: #Wait on doctors service in room
                        yield request #Patient begins service with doctor
                        print("Doctor has arrived for service of patient id: {} type: {} at {}".format(patient.id, patient.purpose, get_time(env)))
                        temp = env.now
                        yield env.process(ED.init_exam(patient)) #end service with doctor
                        patient.treatmentTime = patient.treatmentTime + env.now - temp
                        referral = random.random() #determine if doc refers for lab or imaging
                        for key, value in mod_referral.items(): #check dictionary CDF percent to see if referred
                            if referral <= value:
                                decision = key
                                break
                    print("Doctor refers patient to {}. Doctor leaves patient id: {} type: {} at {}.".format(
                        decision, patient.id, patient.purpose, get_time(env)))

                    if (decision == "dep"): #PATIENT DEPARTS SERVICE
                        print("Patient id: {} type: {} departs at {}.".format(
                            patient.id, patient.purpose, get_time(env)))
                    else: #PATIENT IS REFERRED
                        if (decision == "imaging"): #REFERRED TO IMAGING
                            print("Patient id: {} type: {} is referred to imaging and begins wait at {}.".format(
                                patient.id, patient.purpose, get_time(env)))
                            with imaging.station.request(priority=patient.priority) as request:
                                yield request #patient able to get imaging done
                                ImagingAquired = env.now #track start of imaging service because patient enters imaging room
                                print("Patient id: {} type: {} who is referred to imaging enters at {}.".format(
                                    patient.id, patient.purpose, get_time(env)))
                                with imaging.tech.request(priority=patient.priority) as request:
                                    yield request #Imaging tech available and begins service on patient
                                    print("Imaging tech has arrived for service of referred patient id: {} type: {} at {}".format(
                                        patient.id, patient.purpose, get_time(env)))
                                    temp = env.now #stash current time
                                    yield env.process(imaging.service(patient))
                                    VAT["img_in"] = VAT["img_in"] + env.now - temp #track VAT time for patient
                                    patient.treatmentTime = patient.treatmentTime + env.now - temp #track patient tratment time
                                    print("Patient id: {} type: {} finished referred imaging service at {} and returns to room.".format(
                                            patient.id, patient.purpose, get_time(env)))
                            wait = random.randint(10, 20) #Generate wait time for patient results
                            roomUtilTime["imaging"] = roomUtilTime["imaging"] + env.now - ImagingAquired #track imaging utilization
                        else: #REFERRED TO LAB
                            print("Patient id: {} type: {} is referred to lab and begins service at {}.".format(
                                patient.id, patient.purpose, get_time(env))) #put patient into lab room when available
                            with lab.station.request(priority=patient.priority) as request:
                                yield request #lab room is available
                                LabAquired = env.now #track time lab room was aquired by patient
                                print("Patient id: {} type: {} who is referred to lab enters at {}. Waiting for tech".format(
                                    patient.id, patient.purpose, get_time(env)))
                                with lab.tech.request(priority=patient.priority) as request:
                                    yield request #lab tech aquired, patient enters service with tech
                                    print("Lab tech has arrived for referred service of patient id: {} type: {} at {}.".format(
                                        patient.id, patient.purpose, get_time(env)))
                                    temp = env.now  #end of service time with lab tech is tracked
                                    yield env.process(lab.service(patient)) #release lab tech & patient after service
                                    VAT["lab_in"] = VAT["lab_in"] + env.now - temp #track VAT time for patient
                                    patient.treatmentTime = patient.treatmentTime + env.now - temp #track lab treatment time
                                    print("Patient id: {} type: {} finished referred lab service at {} and return to room.".format(
                                        patient.id, patient.purpose, get_time(env)))
                            wait = random.randint(4, 20) #generate waiting time for lab results
                            roomUtilTime["lab"] = roomUtilTime["lab"] + env.now - LabAquired
                        print("Patient id: {} type: {}'s diagnostic results will be available in {} minutes.".format(patient.id, patient.purpose, wait))
                        env.timeout(wait) #release results for patient
                        print("Patient id: {} type: {}'s diagnostic results are available now! Begin waiting for doctor at {}.".format(patient.id, patient.purpose, get_time(env)))
                        with ED.doctor.request(priority=patient.priority) as request:
                            yield request #request doctor for second visit to review results
                            print("Doctor has arrived for service of patient id: {} type: {} at {}".format(
                                patient.id, patient.purpose, get_time(env))) #doc arrives to review results
                            temp = env.now #stash current time
                            yield env.process(ED.final_exam(patient)) #timeout doc & patient for review
                            patient.treatmentTime = patient.treatmentTime + env.now - temp #track treatment time
                        print("Patient id: {} type: {} departs clinic at {}".format(
                            patient.id, patient.purpose, get_time(env))) #release patient for review
                        roomUtilTime["ED"] = roomUtilTime["ED"] + env.now - EDAquired
                else: #PATIENT RENEGES FROM SERVICE BEFORE STARTING
                    print('Patient id: {} type: {} reneged from ED at {}'.format(
                        patient.id, patient.purpose, get_time(env)))
                    renegingStats[patient.purpose] = renegingStats[patient.purpose] + 1 #track number of reneges
                    return
    elif (patient.purpose == "em_ser"): #PATIENT ARRIVES FOR ED AS A SERIOUS PATIENT
        print("Patient id: {} type: {} enters queue for ED at {}.".format(
            patient.id, patient.purpose, get_time(env))) #skip registration & request a ER room
        with ED.room.request(priority=patient.priority) as request:
            yield request #ER Room accessed
            EDAquired = env.now #track time room was aquired
            print("Patient id: {} type: {} enters the ED at {}. Waiting for nurse..".format(
                patient.id, patient.purpose, get_time(env)))
            with ED.nurse.request(priority=patient.priority) as request: #Request Nurse for service
                yield request #nurse seized for service
                print("Nurse has arrived for service of patient id: {} type: {} at {}".format(
                    patient.id, patient.purpose, get_time(env)))
                patient.treatmentWaitTime = env.now - patient.start #track waiting time for service
                patient.treatmentTime = env.now #begin treatment service
                yield env.process(ED.prep(patient)) #Nurse completes prep to serve patient
                patient.treatmentTime = env.now - patient.treatmentTime
                print("Nurse leaves patient id: {} type: {} at {}. Waiting for doctor".format(
                    patient.id, patient.purpose, get_time(env)))
            with ED.doctor.request(priority=patient.priority) as request: #Request doctor evaluation
                yield request #doctor requested to sieze 
                print("Doctor has arrived for service of patient id: {} type: {} at {}".format(
                    patient.id, patient.purpose, get_time(env)))
                temp = env.now #track time service started
                yield env.process(ED.init_exam(patient)) #end service with doctor
                patient.treatmentTime = patient.treatmentTime + env.now - temp #track patient treatment time
                referral = random.random() #generate a random number to determine if the patient is referred
                for key, value in ser_referral.items(): #grab vals from dictionary to compare rand# against
                    if referral <= value: #if random prob (referral prob) is less than referral threshold, refer    
                        decision = key #refer to key where key = {lab, imaging or Depart}
            print("Doctor refers patient to {}. Doctor leaves patient id: {} type: {} at {}.".format(
                decision, patient.id, patient.purpose, get_time(env)))
            if (decision == "dep"): #PATIENT REFERRED TO DEPART CLINIC
                print("Patient id: {} type: {} departs at {}.".format(
                    patient.id, patient.purpose, get_time(env))) #Patient departs service
            else: #PATIENT REFERRED TO IMAGING OR LAB
                if (decision == "imaging"): #PATIENT REFERRED TO IMAGING
                    print("Patient id: {} type: {} begins wait for imaging at {}.".format(
                        patient.id, patient.purpose, get_time(env)))
                    with imaging.station.request(priority=patient.priority) as request:
                        yield request
                        ImagingAqued = env.nowir
                        print("Patient id: {} type: {} enters the imaging at {}.".format(
                            patient.id, patient.purpose, get_time(env)))
                        with imaging.tech.request(priority=patient.priority) as request:
                            yield request
                            print("Imaging tech has arrived for service of patient id: {} type: {} at {}".format(
                                patient.id, patient.purpose, get_time(env)))
                            temp = env.now
                            yield env.process(imaging.service(patient))
                            VAT["img_in"] = VAT["img_in"] + env.now - temp
                            patient.treatmentTime = patient.treatmentTime + env.now - temp
                            print("Patient id: {} type: {} finished imaging service at {} and returns to room.".format
                                  (patient.id, patient.purpose, get_time(env)))
                    wait = random.randint(10, 20)
                    roomUtilTime["imaging"] = roomUtilTime["imaging"] + env.now - ImagingAquired
                else:
                    print("Patient id: {} type: {} begins waiting for lab at {}.".format(
                        patient.id, patient.purpose, get_time(env)))
                    with lab.station.request(priority=patient.priority) as request:
                        yield request
                        LabAquired = env.now
                        print("Patient id: {} type: {} enters the lab at {}. Waiting for tech".format(
                            patient.id, patient.purpose, get_time(env)))
                        with lab.tech.request(priority=patient.priority) as request:
                            yield request
                            print("Lab tech has arrived for service of patient id: {} type: {} at {}.".format(
                                patient.id, patient.purpose, get_time(env)))
                            temp = env.now
                            yield env.process(lab.service(patient))
                            VAT["lab_in"] = VAT["lab_in"] + env.now - temp
                            patient.treatmentTime = patient.treatmentTime + env.now - temp
                            print("Patient id: {} type: {} finished lab service at {} and return to room.".format(
                                patient.id, patient.purpose, get_time(env)))
                    wait = random.randint(4, 20)
                    roomUtilTime["lab"] = roomUtilTime["lab"] + env.now - LabAquired
                print("Patient id: {} type: {}'s diagnostic results will be available in {} minutes.".format(
                    patient.id, patient.purpose, wait))
                env.timeout(wait)
                print("Patient id: {} type: {}'s diagnostic results are available now! Begin witing for doctor at {}.".format(
                    patient.id, patient.purpose, get_time(env)))
                with ED.doctor.request(priority=patient.priority) as request:
                    yield request
                    print("Doctor has arrived for service of patient id: {} type: {} at {}".format(
                        patient.id, patient.purpose, get_time(env)))
                    temp = env.now
                    yield env.process(ED.final_exam(patient))
                    patient.treatmentTime = patient.treatmentTime + env.now - temp
                print("Patient id: {} type: {} finishes treatment and proceeds to registration at {}".format(
                    patient.id, patient.purpose, get_time(env)))
                yield env.process(wait_for_registration(registration, patient, env))
                print("Patient id: {} type: {} departs clinic at {}".format(
                    patient.id, patient.purpose, get_time(env)))
                roomUtilTime["ED"] = roomUtilTime["ED"] + env.now - EDAquired
    patient.serviceTime = env.now - patient.start
    patientStats.append(patient)



def get_index_by_time(time):
    hour = time["hour"]
    if (hour >= 8 and hour < 12):
        day_index = 0
    elif (hour >= 12 and hour < 16):
        day_index = 1
    elif (hour >= 16 and hour < 20):
        day_index = 2
    else:
        day_index = None

    week_day = time["day"]
    if (week_day <= 5):
        week_day_index = 0
    if (week_day == 6):
        week_day_index = 1
    else:
        week_day_index = 2
    return {"week_day_index": week_day_index, "day_index": day_index}


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

    iat = get_arrival_times()

    for key in patient_timeouts:
        if patient_timeouts[key] == None:
            time = get_time(env)
            time_indexes = get_index_by_time(time)
            patient_timeouts[key] = None if iat[key] == None or iat[key][time_indexes["week_day_index"]
                                                                         ][time_indexes["day_index"]] == None else iat[key][time_indexes["week_day_index"]
                                                                                                                            ][time_indexes["day_index"]] + env.now
    shift_change = [False, False, False]
    global operatingTime
    temp = 60*8

    while True:
        time = get_time(env)
        time_indexes = get_index_by_time(time)

        if (time_indexes["day_index"] == 0 and shift_change[0] == False):
            print(patient_timeouts)
            print("First shift staffing at {}".format(time))
            registration = Registration(env, staff_schedule["registration"][0])
            ed = ED(env, staff_schedule["nurse"]
                    [0], staff_schedule["doctor"][0])
            imaging = Imaging(env, staff_schedule["imaging_tech"][0])
            lab = Lab(env, staff_schedule["lab_tech"][0])
            shift_change[0] = True

        elif (time_indexes["day_index"] == 1 and shift_change[1] == False):
            print("Second shift change at {}".format(time))
            registration = Registration(env, staff_schedule["registration"][1])
            ed = ED(env, staff_schedule["nurse"]
                    [1], staff_schedule["doctor"][1])
            imaging = Imaging(env, staff_schedule["imaging_tech"][1])
            lab = Lab(env, staff_schedule["lab_tech"][1])
            shift_change[1] = True
        elif (time_indexes["day_index"] == 2 and shift_change[2] == False):
            print("Third shift change at {}".format(time))
            registration = Registration(env, staff_schedule["registration"][2])
            ed = ED(env, staff_schedule["nurse"]
                    [2], staff_schedule["doctor"][2])
            imaging = Imaging(env, staff_schedule["imaging_tech"][2])
            lab = Lab(env, staff_schedule["lab_tech"][2])
            shift_change[2] = True

        minTime = 99999
        # Change shift of staff based on time on new days re-start
        for key, value in patient_timeouts.items():
            if value != None and value < minTime:
                minTime = value
                next_timeout = key
        print(patient_timeouts[next_timeout])
        print(env.now)
        yield env.timeout(patient_timeouts[next_timeout] - env.now)
        priority = (
            2 if next_timeout == "em_ser" else 1 if next_timeout == "em_mod" else 0
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

        if (time_indexes["day_index"] == None):
            operatingTime =  operatingTime + env.now - temp
            print("Clinic is now closed".format(time))
            temp = env.now
            shift_change = [False, False, False]
            # clinic closes for 12 hours
            yield env.timeout(60 * 12)
            time = get_time(env)
            time_indexes = get_index_by_time(time)
            print("Clinic is now open!".format(time))
            temp = env.now - temp
            for key, value in patient_timeouts.items():
                if value != None:
                    patient_timeouts[key] = value + temp
            
        patient_timeouts[next_timeout] = iat[next_timeout][time_indexes["week_day_index"]
                                                           ][time_indexes["day_index"]] + env.now
        patients_arrived += 1


def get_arrival_times():
    arrival_rate = {}
    for key, value in arrival_times.items():
        if (value == None):
            arrival_rate[key] = None
        else:
            arrival_rate[key] = []
            for day in value:
                arr = []
                for time in day:
                    if time == 0:
                        arr.append(4*60)
                    else:
                        iat = 1 / float(time) * 60
                        arr.append(iat)
                arrival_rate[key].append(arr)
    return arrival_rate

def printStats():
    time_until_treatment = { 
    "em_ser": 0, 
    "em_mod": 0,
    "img_in": 0,
    "img_out": 0,
    "lab_in": 0,
    "lab_out": 0,
    }
    time_until_registration = { 
    "em_ser": 0, 
    "em_mod": 0,
    "img_in": 0,
    "img_out": 0,
    "lab_in": 0,
    "lab_out": 0,
    }

    service_time = { 
    "em_ser": 0, 
    "em_mod": 0,
    "img_in": 0,
    "img_out": 0,
    "lab_in": 0,
    "lab_out": 0,
    }
    num_patients = { 
    "em_ser": 0, 
    "em_mod": 0,
    "img_in": 0,
    "img_out": 0,
    "lab_in": 0,
    "lab_out": 0,
    }
    print("Patient Statistics: ")
    for patient in patientStats:
        if (patient.serviceTime != None):
            num_patients[patient.purpose] = num_patients[patient.purpose] + 1
            print("\tPatient ID: {}".format(patient.id))
            print("\tPatient type: {}".format(patient.purpose))
            print("\tTime until treatment: {}".format(patient.treatmentWaitTime))
            print("\tTime until registration: {}".format(patient.registrationWaitTime))
            print("\tTotal service time: {} \n".format(patient.serviceTime))
            VAT[patient.purpose][0] = VAT[patient.purpose][0] + patient.treatmentTime
            VAT[patient.purpose][1] = VAT[patient.purpose][1] + patient.serviceTime
            time_until_treatment[patient.purpose] = time_until_treatment[patient.purpose] + patient.treatmentWaitTime
            service_time[patient.purpose] = service_time[patient.purpose] + patient.serviceTime
            if (patient.purpose != "em_ser"):
                time_until_registration[patient.purpose] = time_until_registration[patient.purpose] + patient.registrationWaitTime
        
    print("Patient Type Statistics: ")
    for purpose, value in VAT.items():
        print("\tPatient Type: {}".format(purpose))
        if ("in" not in purpose):
            vat = value[0]/value[1]
        else:
            vat = value

        print("\t% VAT: {}".format(vat))
        print(num_patients[purpose])
        if (num_patients[purpose] > 0):
            print("\t% of balks: {}".format(balkingStats[purpose]/num_patients[purpose]))
            print("\t% of reneges: {}".format(renegingStats[purpose]/num_patients[purpose]))
            print("\tAvg time until registration: {}".format(time_until_registration[purpose]/ num_patients[purpose]))
            print("\tAvg time until treatment: {}".format(time_until_treatment[purpose]/ num_patients[purpose]))
            print("\tAvg total service time: {}\n".format(service_time[purpose] / num_patients[purpose]))
        else: #num_patients for a given purpose (ED )
            print("\t Statistics irrelevant and not considered")
    
    print()
    print("Total Clinic Operating Time: {}\n".format(operatingTime))

    totalCost = 0
    
    print("Staff Statistics: ")
    for staff, value in staffUtilTime.items():
        print("\tStaff: {}".format(staff))
        print("\tTime: {}".format(value))
        print("\t% Util: {}".format(value / operatingTime))
        print("\tHourly Cost: {}".format(costs[staff]))
        cost = value / 60 * costs[staff]
        totalCost = totalCost + cost
        print("\tCost: {}\n".format(cost))

    print("Facilities Statistics: ")
    for facility, value in roomUtilTime.items():
        print("\tFacility: {}".format(facility))
        print("\tTime: {}".format(value))
        print("\t% Util: {}".format(value / operatingTime))
        print("\tHourly Cost: {}\n".format(hourly_room_cost[facility]))
        cost = value / 60 * hourly_room_cost[facility]
        totalCost = totalCost + cost

    print("Total Operating Cost: {}\n".format(totalCost))



if __name__ == '__main__':
    # Create an environment
    random.seed(RANDOM_SEED)
    env = simpy.Environment(initial_time=60*8)

    # Set-up and Execute!
    env.process(setup(env))
    env.run(until=100000)

    printStats()

# costs = {
#     "doctor": 200,
#     "nurse": 100,
#     "imaging_tech": 90,
#     "lab_tech": 80,
#     "registration": 40
# }

# #The cost of rooms associated with operation
# #Operating rooms per hour
# hourly_room_cost = {
#     "ED": 500,
#     "imaging": 400,
#     "lab": 300,
#     "registration": 50
# }

# total time for each staff
# total time for each room
# Total operating cost
# 





