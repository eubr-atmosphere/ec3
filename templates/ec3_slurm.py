#!/usr/bin/env python

# Experimental control for SLURM

import sys, subprocess, argparse

def run_command(command):
    try:
        p=subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        (out, err) = p.communicate()
        if p.returncode != 0:
            raise Exception("return code: %d\nError output: %s" % (p.returncode, err))
        return out
    except Exception, e:
        raise Exception("Error executing '%s': %s" % (" ".join(command), str(e)))

def parse_scontrol(out):
    if out.find("=") < 0: return []
    r = []
    for line in out.split("\n"):
        line = line.strip()
        if not line: continue
        d = {}; r.append(d); s = False
        for k in [ j for i in line.split("=") for j in i.rsplit(" ", 1) ]:
            if s: d[f] = k
            else: f = k
            s = not s
    return r

def get_queued_jobs():
    root = parse_scontrol(run_command("scontrol -o show jobs".split(" ")))
    r = {}
    for j in root:
        if j["JobState"] == "PENDING":
            r[j["Partition"]] = r.get(j["Partition"], 0) + int(j["NumNodes"].split("-")[0])
    return r

def get_meta_state():
    root = parse_scontrol(run_command("scontrol -o show nodes".split(" ")))
    STATES = { "IDLE": "idle", "FAIL": "idle-off", "FAILING": "idle-off", "DOWN*": "off", "DOWN": "idle-off",
               "DRAIN": "idle-off", "DRAINED": "idle-off", "ERROR": "idle-off", "MIXED": "busy", "ALLOC": "busy",
               "ALLOCATED": "busy", "COMPLETING": "busy" }
    PRIO = { "off": 2, "idle": 0, "idle-off": 1, "busy": 3 }
    def find_state(states):
        if not states: return "off"
        states = [ STATES.get(s.strip(" "), "off") for s in states ]
        return max([ (PRIO[s], s) for s in states ])[1]
    return dict([ (node.get("NodeName", None), find_state(node.get("State", "DOWN").split("+")))
                  for node in root ])

def disable_node(hostname):
    subprocess.check_call("scontrol update NodeName=%s State=DRAIN Reason=Ec3_control" % hostname, shell=True)

def remove_node(hostname, alsodo=None):
    if alsodo: alsodo(hostname)
    subprocess.check_call("scontrol update NodeName=%s State=RESUME Reason=Ec3_control" % hostname, shell=True)

def enable_node(hostname, _=None):
    subprocess.check_call("scontrol update NodeName=%s State=RESUME Reason=Ec3_control" % hostname, shell=True)

def ec3_init(Control):
    Control.get_meta_state = staticmethod(get_meta_state)
    Control.get_queued_jobs = staticmethod(get_queued_jobs)
    Control.enable_node = staticmethod(enable_node)
    Control.disable_node = staticmethod(disable_node)
    old_remove_node = Control.remove_node
    Control.remove_node = staticmethod(lambda h: remove_node(h, old_remove_node))
 
def get_queued_jobs_cmd(_):
    sys.stdout.write("%s\n" % get_queued_jobs())

def get_meta_state_cmd(_):
    meta = get_meta_state()
    sys.stdout.write("%s\n" % meta)

def enable_node_cmd(options):
    enable_node(options.hostname, None)

def disable_node_cmd(options):
    disable_node(options.hostname)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(title="subcommands", description="valid subcommands", help="additional help")
    parser0 = subparsers.add_parser("queued_jobs", help="return how many queued jobs there are")
    parser0.set_defaults(func=get_queued_jobs_cmd)
    parser0 = subparsers.add_parser("meta_state", help="return the state of the nodes")
    parser0.set_defaults(func=get_meta_state_cmd)
    parser0 = subparsers.add_parser("disable_node", help="disable a node")
    parser0.add_argument("hostname", help="node's hostname")
    parser0.set_defaults(func=disable_node_cmd)
    parser0 = subparsers.add_parser("enable_node", help="enable a node")
    parser0.add_argument("hostname", help="node's hostname")
    parser0.set_defaults(func=enable_node_cmd)
    options = parser.parse_args()
    try:
        options.func(options)
    except KeyboardInterrupt:
        sys.stderr.write("Program interrupted by the user.\n")
    sys.exit(0)
