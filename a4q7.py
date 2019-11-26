import random
import simpy
import csv
from functools import partial, wraps

SIM_TIME = 20000
fans_arrived = 0
time_in_syst = [None]*10000
op_busy = [0]*4

# Create and define fans


class Fan(object):
    def __init__(self, env, num):
        self.env = env
        self.id = num

# Create and define operators


class Operator(object):
    def __init__(self, env, id, time):
        self.env = env
        self.worker = simpy.Resource(env, 1)
        self.id = id
        self.time = time

    def work(self, fan, defective):
        print("Operators {} begins assembling fan {}".format(self.id, fan))
        time = random.triangular(self.time[0], self.time[1], self.time[2])
        if (defective):
            time = time * 1.3
        yield env.timeout(time)

# Each fan is run through assemble process


def assemble(env, fan, operators):
    global time_in_syst
    print("Fan {} arrives in system at {}".format(fan.id, env.now))
    time_in_syst[fan.id] = env.now
    # Grab an operator when available to assembple the fan
    operator = yield operators.get()
    op_start = env.now
    print("Operator {} arrived at {}".format(operator.id, env.now))
    # run build operation based on specific operators time
    yield env.process(operator.work(fan.id, False))
    print("Operator {} finished building fan {} at {}".format(
        operator.id, fan.id, env.now))
    # Check if fan is defective - if it is re-assemble with increased 30% (defined by flagging second param true)
    defect = random.random()
    # Assume a defective fan will be repaired properly.
    if (defect <= 0.07):
        print("Fan {} is defected!".format(fan.id))
        yield env.process(operator.work(fan.id, True))
        print("Operator {} finished building fan {} at {}".format(
            operator.id, fan.id, env.now))
    op_busy[operator.id] = op_busy[operator.id] + env.now - op_start
    operators.put(operator)
    time_in_syst[fan.id] = env.now - time_in_syst[fan.id]


def setup(env, operators):
    global fans_arrived
    next_shift = False

    while True:
        time = env.now

        yield env.timeout(random.triangular(2, 5, 10))

        new_fan = Fan(env, fans_arrived)

        env.process(assemble(env, new_fan, operators))
        fans_arrived += 1


# Create an environment
env = simpy.Environment()

# Create store of operators and initialize
operators = simpy.FilterStore(env, 4)
op_a = Operator(env, 0, [15, 18, 21])
op_b = Operator(env, 1, [16, 19, 22])
op_c = Operator(env, 2, [16, 20, 24])
op_d = Operator(env, 3, [17, 20, 23])
operators.put(op_a)
operators.put(op_b)
operators.put(op_c)
operators.put(op_d)

# Set-up and Execute!
env.process(setup(env, operators))
env.run(until=SIM_TIME)
print("Fan Statisitcs:")
for i, time in enumerate(time_in_syst):
    if (time == None or time > 1000):
        count = i
        break
    print('\t Fan {} was in system for {} minutes'.format(i + 1, time))
print("Operator Statisitcs:")
for i, time in enumerate(op_busy):
    print("\t Utilization: {}".format(time/SIM_TIME))
