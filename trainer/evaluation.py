import numpy as np
import quaternion

import math

from .utils import select_location, select_rotation, dictzip, try_get_pre_positions
from .simulation import apply_joints


def calc_effector_reward(motion, robot, effectors, *, ke, wl, wr):
    diff = 0
    c = 0
    for name, effector in effectors.items():
        pose = robot.link_state(name).pose
        root_pose = robot.link_state(robot.root_link).pose
        weight = motion.effector_weight(name)
        ty = motion.effector_type(name)
        if effector.location:
            target = select_location(ty.location, effector.location.vector, root_pose)
            diff += wl * np.linalg.norm(pose.vector - np.array(target)) ** 2 * weight.location
            c += 1
        if effector.rotation:
            target = select_rotation(ty.rotation, effector.rotation.quaternion, root_pose)
            quat1 = np.quaternion(*target)
            q = pose.quaternion
            quat2 = np.quaternion(q[3], q[0], q[1], q[2])
            diff += wr * quaternion.rotation_intrinsic_distance(quat1, quat2) ** 2 * weight.rotation
            c += 1
    normalized = ke * diff / c
    try:
        return - math.exp(normalized) + 1
    except OverflowError:
        return - math.inf;

def calc_stabilization_reward(positions, pre_positions, *, ks):
    if pre_positions is None:
        return 0

    change_sum = sum((p1 - p2) ** 2 for _, (p1, p2) in dictzip(positions, pre_positions))
    normalized = ks * change_sum / len(positions)
    try:
        return - math.exp(normalized) + 1
    except OverflowError:
        return - math.inf;


def calc_reward(motion, robot, effectors, positions, pre_positions, *, we=1, ws=0.1, ke=1, ks=1, wl=1, wr=0.005):
    # TODO: Use more clear naming of hyperparameters

    e = calc_effector_reward(motion, robot, effectors, ke=ke, wl=wl, wr=wr)
    s = calc_stabilization_reward(positions, pre_positions, ks=ks)
    return e * we + s * ws


def evaluate(scene, motion, robot, loop=2, **kwargs):
    reward_sum = 0

    pre_positions = try_get_pre_positions(scene, motion)

    for t, frame in motion.frames(scene.dt):
        if t > motion.length() * loop:
            break

        apply_joints(robot, frame.positions)

        scene.step()

        reward_sum += calc_reward(motion, robot, frame.effectors, frame.positions, pre_positions, **kwargs)
        pre_positions = frame.positions

    score = reward_sum / math.ceil(motion.length() / scene.dt * loop)
    return score
