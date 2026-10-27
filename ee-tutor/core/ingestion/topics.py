"""Keyword-based topic guesser, used only to pre-fill sources.yaml for a new book.
It is a starting guess, not a classifier you need to trust -- open sources.yaml
afterward and fix the topic list by hand if it guessed wrong or too broadly.
"""
import re
from collections import Counter

TOPIC_KEYWORDS = {
    "thevenin": ["thevenin", "norton equivalent", "source transformation"],
    "rc_transient": ["rc circuit", "time constant", "charging capacitor", "transient response", "rc transient"],
    "phasors": ["phasor", "ac steady state", "impedance", "sinusoidal steady"],
    "mosfet": ["mosfet", "nmos", "pmos", "threshold voltage", "channel length modulation", "drain current"],
    "bjt": ["bjt", "bipolar junction", "base current", "collector current", "beta transistor"],
    "digital_logic": ["boolean algebra", "logic gate", "truth table", "karnaugh"],
    "combinational_circuits": ["multiplexer", "decoder", "encoder", "combinational circuit", "adder circuit"],
    "sequential_circuits": ["flip-flop", "flip flop", "latch", "state machine", "sequential circuit"],
    "flip_flops": ["jk flip-flop", "d flip-flop", "sr latch", "master-slave"],
    "counters": ["ripple counter", "synchronous counter", "counter circuit"],
    "registers": ["shift register", "register transfer"],
    "opamp": ["operational amplifier", "op-amp", "virtual ground", "inverting amplifier"],
    "filters": ["low-pass filter", "high-pass filter", "band-pass", "cutoff frequency"],
    "control_systems": ["transfer function", "root locus", "bode plot", "state space"],
    "power_systems": ["three-phase", "transmission line", "per unit system", "load flow"],
}


def guess_topics(text, max_topics=6):
    text_low = text.lower()
    hits = Counter()
    for topic, keywords in TOPIC_KEYWORDS.items():
        for kw in keywords:
            hits[topic] += text_low.count(kw)
    ranked = [t for t, c in hits.most_common() if c > 0]
    return ranked[:max_topics] or ["general"]
