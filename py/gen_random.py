import random
import time
import argparse
import numpy as np
from scipy.stats import entropy
from collections import Counter
from string import ascii_lowercase, ascii_uppercase


parser = argparse.ArgumentParser()

parser.add_argument("-l", "--len", default=20)
parser.add_argument("-c", "--continuous", action="store_true", default=False)
parser.add_argument("-r", "--readable", action="store_true", default=False)
parser.add_argument("-a", "--alpha", action="store_true", default=False)

args = parser.parse_args()

chars = set(ascii_lowercase)
chars = chars |  set(ascii_uppercase)
digits = set([str(x) for x in range(0,9)])
punc = set(["%","^","#", "@"])
ambiguous=set(["1","l","I","0","O","b","6"])

all_syms = chars | digits | punc

syms = all_syms
if args.readable:
    syms = syms - ambiguous
if args.alpha:
    syms = syms - punc

syms = list(syms)

# a uniform dist is max entropy - each character observed equally
uniform_dist = np.array([1/len(syms) for x in range(0, len(syms))])

def gen_sequence(l=args.len):
    rands = [random.randrange(0,len(syms)) for x in range(0,l)]
    return "".join([syms[x] for x in rands])

def calculate_divergence(strings):
    observed = []
    for s in strings:
        for _ in s:
            observed.append(_)
    # order is irrelevant - entropy is a sum
    observed = Counter(observed)
    sum_ = observed.total()
    observed_dist = np.array([x/sum_ for x in observed.values()])
    divergence  = entropy(observed_dist, uniform_dist)
    return divergence


if __name__ == "__main__":
    if args.continuous:
        i = 0
        all_strings = []
        divergences = []
        while True:
            size = random.randrange(25,100)
            delay = random.random()
            s = gen_sequence(l=size)
            print(s)
            time.sleep(delay)
            all_strings.append(s)
            i += 1
            if i % 100 == 0:
                div = calculate_divergence(all_strings)
                print(f"the kl divergence is {div}")
                divergences.append(div)
                if len(divergences) >= 5:
                    avg_divergence = np.mean(divergences)
                    stddev_divergence = np.stddev(divergences)
                    diff =  abs(div - avg_divergence) 
                    if diff >=  3 * stddev_divergence:
                        print(f"non randomness detected under a gaussian distribution assumption")
                        print(f"observed kl_divergence: {diff}, 3sig: {3 * stddev_divergence}")
                        time.sleep(5)
                    else:
                        divergences.append(div)
                all_strings = []


    print(gen_sequence())
