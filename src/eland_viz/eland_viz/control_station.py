#!/usr/bin/env python3
"""Control station: the HUD plus a keyboard, in one window.

    ros2 run eland_viz control_station

Exists because every landing test used to start from wherever the vehicle was
spawned, and the site the detector picks is usually the patch of grass
immediately beneath it. Being able to fly somewhere first -- over the road,
next to the person, onto the paved yard -- turns one scenario per launch into
as many as you care to fly.

WHY MANUAL CONTROL AND NOT OFFBOARD

The vehicle is flown by publishing ManualControlSetpoint on
/fmu/in/manual_control_input, which PX4 treats exactly like a joystick: it
flies in Position mode, holding altitude and position when the sticks are
centred, and the sticks are body-relative so forward means where the nose is
pointing. Verified in SITL before this file was written -- PX4 switched to
nav_state 2 and flew 14.8 m on a 0.6 pitch stick.

The alternative would have been offboard setpoints, which is precisely the
mechanism this whole project exists to avoid: it bypasses PX4's mode and
failsafe logic. A test tool has no business doing that when a supported input
path exists.

STICKS ARE STICKY

OpenCV reports key presses but not releases, so a key sets a stick value that
stays set until you centre it. In practice that suits testing better than a
held key would: point the vehicle, watch it fly, press SPACE.

IT ALSO HOLDS THE GCS LINK OPEN, AND HAS TO

PX4 tracks whether a ground station is talking to it, and NAV_DLL_ACT defaults
to Return. With no GCS attached at all, `gcs_connection_lost` goes true
COM_DL_LOSS_T (10 s) after takeoff and that failsafe fires -- and since the
Emergency Landing mode is registered in place of Return, the vehicle lands
itself roughly fifteen seconds into every flight, whatever you were trying to
do with it. That is not a bug in this station; it is the failsafe working, and
it made the first three teleop attempts here look like broken controls.

So the station sends a GCS heartbeat, because that is what a ground station
is. The link exists while the window is open and drops when it closes -- at
which point the failsafe brings up the landing mode, which is the intended
demonstration rather than an accident.

ONE MORE CONSEQUENCE

Once manual control is streaming, PX4 also has a manual control link, and
COM_RC_LOSS_T is 0.5 s. That is why the stream runs on its own timer under a
background executor and not from the render loop: a stall in cv2.imshow must
not be able to look like a lost transmitter.
"""

import math
import threading
import time

import cv2
import numpy as np
import rclpy
import rclpy.executors
from px4_msgs.msg import (FailsafeFlags, ManualControlSetpoint, VehicleCommand,
                          VehicleLocalPosition, VehicleStatus)
from rclpy.node import Node
from sensor_msgs.msg import Image
from std_msgs.msg import Bool
from eland_common import px4_topics
from eland_common.qos import PX4_QOS, SENSOR_QOS

FONT = cv2.FONT_HERSHEY_SIMPLEX

CMD_SET_NAV_STATE = 100001
NAV_POSCTL = 2
NAV_LAND = 18
NAV_EXTERNAL1 = 23

#: How far one key press deflects a stick in `sticky` mode. Small enough that
#: a single tap is a nudge rather than a lurch; press twice to go faster.
STICK_STEP = 0.3
STICK_MAX = 1.0

#: Seconds of neutral sticks to stream before asking PX4 for Position mode.
#: Two was enough in every test; one was not always.
MANUAL_SETTLE_S = 2.0

KEY_HELP = [
    ('W / S', 'ileri / geri'),
    ('A / D', 'sola / saga kay'),
    ('Q / E', 'sola / saga don'),
    ('R / F', 'yuksel / alcal'),
    ('SPACE', 'cubuklari ortala'),
    ('', ''),
    ('1', 'arm'),
    ('2', 'kalkis'),
    ('3', 'manuel kontrolu al (POSCTL)'),
    ('0', 'ACIL INIS modunu tetikle'),
    ('9', 'modu kaydini KALDIR (gercek RTL)'),
    ('L', "PX4 ile in"),
    ('X', 'disarm'),
    ('ESC', 'cik'),
]


class ControlStation(Node):
    def __init__(self) -> None:
        super().__init__('control_station')

        self.declare_parameter('hud_topic', '/eland/hud')
        # 33 Hz rather than 20. Measured against a steady 20 Hz stream, the
        # rate PX4 actually accepted swung between 0 and 31 Hz -- the messages
        # arrive in bursts with gaps in between, and every gap longer than
        # COM_RC_LOSS_T is a lost transmitter as far as the failsafe is
        # concerned. Sending faster does not fix the gaps, it just puts more
        # messages in each burst; run_sim.sh widens the timeout, which is the
        # part that actually matters.
        self.declare_parameter('manual_rate_hz', 33.0)
        # Hold the operator's intention. If a failsafe takes the aircraft back
        # while the operator is flying it, ask again rather than leaving them
        # pressing a key that appears to do nothing.
        self.declare_parameter('reassert_manual', True)
        self.declare_parameter('reassert_period_s', 2.0)
        # Start streaming sticks without waiting for a keypress. For measuring
        # this node's own timing without a human in the loop; leave it false
        # for flying, where taking control should be a deliberate act.
        self.declare_parameter('start_manual', False)
        # How often to report the stream's own regularity. PX4 calls the link
        # lost after COM_RC_LOSS_T of silence, so the number that matters is
        # not the average rate but the longest gap -- an average of 20 Hz with
        # one two-second hole in it is a failsafe, not a healthy link.
        self.declare_parameter('stream_report_s', 10.0)
        # Open a window at all. Off means no keyboard -- everything else (the
        # stick stream, the GCS heartbeat, holding the operator's intent) runs
        # unchanged, which is what makes the station measurable without a
        # display and usable over a connection that has none.
        self.declare_parameter('window', True)
        # How the keys drive the sticks.
        #
        #   momentary  a held key ramps the axis up, letting go lets it fall
        #              back to centre. What a transmitter does, and what one
        #              tap should NOT do is peg the axis.
        #   sticky     a tap sets the axis and it stays there until centred.
        #              The original behaviour, kept because it is genuinely
        #              easier for "point it that way and watch": no key has to
        #              be held for the twenty seconds of a traverse.
        #
        # OpenCV reports key presses but never releases, so `momentary` infers
        # the release: an axis is considered held while key events keep
        # arriving and starts falling back once they stop. That makes
        # stick_hold_timeout_s the one number that has to match the machine --
        # X delays about half a second before it starts repeating a held key,
        # and a timeout under that would make a held key stutter.
        self.declare_parameter('stick_mode', 'momentary')
        self.declare_parameter('stick_ramp_per_s', 1.5)
        self.declare_parameter('stick_decay_per_s', 2.5)
        # Two timeouts, because the key repeat stream has two phases. X waits
        # about half a second before it starts repeating a held key, so the
        # first press has to be trusted for that long or a held key stutters.
        # Once repeats are arriving every 30 ms, waiting that long again just
        # adds a second of drift after the key is let go -- so as soon as the
        # repeats are flowing, the shorter timeout takes over and the axis
        # falls back promptly.
        self.declare_parameter('stick_hold_timeout_s', 0.7)
        self.declare_parameter('stick_repeat_timeout_s', 0.15)
        # 14550 is where PX4 sends; 18570 is where its "Normal" mavlink
        # instance listens. Heartbeats aimed at 14550 are never seen by the
        # autopilot, so the link it is meant to notice would never exist.
        self.declare_parameter('gcs_heartbeat', True)
        self.declare_parameter('px4_mavlink_endpoint', 'udpout:127.0.0.1:18570')
        self.declare_parameter(
            'vehicle_local_position_topic', px4_topics.VEHICLE_LOCAL_POSITION)
        self.declare_parameter('vehicle_status_topic', '/fmu/out/vehicle_status_v4')

        self.hud = None
        self.pos = None
        self.status = None
        self.flags = None
        self.manual_active = False
        self.posctl_request_at = None
        # What the operator asked for, as opposed to what PX4 is doing. The
        # difference between the two is the thing worth showing.
        self.wants_manual = False
        self.last_reassert = 0.0
        self.takeovers = 0
        self.publish_stamps = []
        self.worst_gap = 0.0
        self.sticks = {'roll': 0.0, 'pitch': 0.0, 'yaw': 0.0, 'throttle': 0.0}
        # Which way each axis is being pushed, and until when that push counts
        # as still happening.
        self.hold = {'roll': 0.0, 'pitch': 0.0, 'yaw': 0.0, 'throttle': 0.0}
        self.hold_until = {'roll': 0.0, 'pitch': 0.0, 'yaw': 0.0, 'throttle': 0.0}
        self.last_advance = time.time()
        # What actually went out, snapshotted at publish time. The panel shows
        # this rather than the working value, so the gauge cannot show a
        # deflection the aircraft was never told about.
        self.last_sent = dict(self.sticks)
        self.stick_mode = self.get_parameter('stick_mode').value
        self.ramp = float(self.get_parameter('stick_ramp_per_s').value)
        self.decay = float(self.get_parameter('stick_decay_per_s').value)
        self.hold_timeout = float(
            self.get_parameter('stick_hold_timeout_s').value)
        self.repeat_timeout = float(
            self.get_parameter('stick_repeat_timeout_s').value)
        self.last_press = {'roll': 0.0, 'pitch': 0.0, 'yaw': 0.0, 'throttle': 0.0}
        self.notice = 'baslatildi -- 1: arm, 2: kalkis, 3: manuel kontrol'

        self.manual_pub = self.create_publisher(
            ManualControlSetpoint, '/fmu/in/manual_control_input', PX4_QOS)
        self.cmd_pub = self.create_publisher(
            VehicleCommand, '/fmu/in/vehicle_command', PX4_QOS)
        # The escape hatch. While the landing mode is registered in place of
        # Return, a deliberate RTL lands here instead of flying home, and the
        # replacement cannot be changed at runtime. What can be changed is
        # whether the mode is registered at all: this asks it to unregister,
        # after which PX4 uses its own Return. One way -- coming back is a
        # relaunch, on the ground.
        self.mode_enable_pub = self.create_publisher(
            Bool, '/eland/mode_enable', 10)
        self.create_subscription(
            Image, self.get_parameter('hud_topic').value, self.on_hud, SENSOR_QOS)
        self.create_subscription(
            VehicleLocalPosition,
            self.get_parameter('vehicle_local_position_topic').value,
            self.on_pos, PX4_QOS)
        self.create_subscription(
            VehicleStatus, self.get_parameter('vehicle_status_topic').value,
            self.on_status, PX4_QOS)
        # Why PX4 is doing what it is doing. Without this the station can say
        # "the aircraft is landing" but not "because it thinks your control
        # link is gone", and those need different reactions from the operator.
        self.create_subscription(
            FailsafeFlags, '/fmu/out/failsafe_flags', self.on_flags, PX4_QOS)

        # The manual control stream runs on its own timer, spun by a background
        # executor, deliberately not from the render loop. PX4 treats a gap
        # longer than COM_RC_LOSS_T (0.5 s by default) as a lost transmitter,
        # and with the Emergency Landing mode registered in place of Return
        # that failsafe takes the aircraft. A momentary stall in cv2.imshow is
        # not something the flight link should depend on.
        period = 1.0 / float(self.get_parameter('manual_rate_hz').value)
        self.create_timer(period, self.publish_manual)
        self.create_timer(0.1, self.service_pending_mode)
        self.create_timer(0.5, self.hold_manual)
        self.create_timer(float(self.get_parameter('stream_report_s').value),
                          self.report_stream)

        if bool(self.get_parameter('start_manual').value):
            for a in self.sticks:
                self.sticks[a] = 0.0
            self.manual_active = True
            self.wants_manual = True
            self.posctl_request_at = self.now() + MANUAL_SETTLE_S
            self.get_logger().info(
                'start_manual: cubuk akisi tuşa basilmadan baslatildi')

        self.gcs = None
        if bool(self.get_parameter('gcs_heartbeat').value):
            self.start_gcs_heartbeat()
        self.get_logger().info('control_station up -- pencereye tikla, klavye orada calisir')

    # ------------------------------------------------------------------
    def start_gcs_heartbeat(self) -> None:
        """Announce ourselves as a ground station, once per second.

        Over MAVLink rather than DDS because "is a GCS connected" is a MAVLink
        notion: PX4 counts heartbeats arriving at its mavlink instance, and no
        uORB topic substitutes for that.
        """
        try:
            from pymavlink import mavutil
        except ImportError:
            self.get_logger().warning(
                'pymavlink yok -- GCS heartbeat gonderilemiyor. PX4 '
                'COM_DL_LOSS_T (10 s) sonra baglanti kaybi failsafe ine girer '
                've arac kendi kendine iner. Kur: pip install pymavlink')
            return

        endpoint = self.get_parameter('px4_mavlink_endpoint').value
        try:
            self.gcs = mavutil.mavlink_connection(
                endpoint, source_system=255, source_component=190)
        except Exception as exc:  # noqa: BLE001 - never take the station down
            self.get_logger().warning(f'GCS heartbeat acilamadi ({exc})')
            return

        def beat():
            while rclpy.ok():
                try:
                    self.gcs.mav.heartbeat_send(
                        mavutil.mavlink.MAV_TYPE_GCS,
                        mavutil.mavlink.MAV_AUTOPILOT_INVALID, 0, 0,
                        mavutil.mavlink.MAV_STATE_ACTIVE)
                except Exception:  # noqa: BLE001
                    return
                time.sleep(1.0)

        threading.Thread(target=beat, daemon=True).start()
        self.get_logger().info(f'GCS heartbeat -> {endpoint}')

    # ------------------------------------------------------------------
    def on_hud(self, msg: Image) -> None:
        self.hud = np.frombuffer(msg.data, np.uint8).reshape(
            msg.height, msg.width, 3).copy()

    def on_pos(self, msg: VehicleLocalPosition) -> None:
        self.pos = msg

    def on_status(self, msg: VehicleStatus) -> None:
        self.status = msg

    def on_flags(self, msg: FailsafeFlags) -> None:
        self.flags = msg

    def failsafe_reason(self) -> str:
        """The conditions PX4 is currently unhappy about, in the order they
        matter to an operator. Only the ones that can take the aircraft away
        from them -- the list also carries things like a missing mission that
        are true the whole flight and mean nothing here."""
        f = self.flags
        if f is None:
            return ''
        named = [
            (f.manual_control_signal_lost, 'kumanda baglantisi kopuk sayiliyor'),
            (f.gcs_connection_lost, 'GCS baglantisi kopuk'),
            (f.battery_low_remaining_time, 'batarya suresi kritik'),
            (f.geofence_breached, 'geofence asildi'),
            (f.local_position_invalid, 'konum kestirimi gecersiz'),
            (f.fd_critical_failure, 'kritik ucus arizasi'),
        ]
        return ', '.join(text for flag, text in named if flag)

    def hold_manual(self) -> None:
        """Keep asking for POSCTL while the operator is flying and PX4 is not
        letting them.

        A failsafe outranks a mode request, so the request can be accepted and
        then undone a second later -- measured: the link was declared lost
        again about four seconds after a successful handover, and the landing
        mode took the aircraft back. Pressing 3 harder does not help; the
        station asks again on the operator's behalf and, more importantly,
        says why it is having to.
        """
        if not (self.wants_manual and self.manual_active):
            return
        if not bool(self.get_parameter('reassert_manual').value):
            return
        st = self.status
        if st is None or st.nav_state == NAV_POSCTL:
            return
        now = self.now()
        if now - self.last_reassert < float(
                self.get_parameter('reassert_period_s').value):
            return
        self.last_reassert = now
        self.takeovers += 1
        self.set_nav_state(NAV_POSCTL)
        why = self.failsafe_reason()
        self.notice = (f'PX4 kontrolu geri aldi ({why or "failsafe"}) -- '
                       f'manuel istegi tekrarlaniyor ({self.takeovers})')

    # ------------------------------------------------------------------
    def now(self) -> float:
        return self.get_clock().now().nanoseconds * 1e-9

    def stamp(self) -> int:
        return int(self.get_clock().now().nanoseconds / 1000)

    def service_pending_mode(self) -> None:
        """Send the deferred Position mode request once the stream is live."""
        if self.posctl_request_at is None or self.now() < self.posctl_request_at:
            return
        self.posctl_request_at = None
        self.set_nav_state(NAV_POSCTL)
        self.notice = 'manuel kontrol alindi (POSCTL) -- WASD/QE/RF ile ucur'

    def publish_manual(self) -> None:
        """Stream the sticks. Must keep going once started, or PX4 sees a lost
        manual control link within COM_RC_LOSS_T."""
        if not self.manual_active:
            return
        now = time.time()
        self.advance_sticks(now - self.last_advance, now)
        self.last_advance = now
        self.publish_stamps.append(now)
        m = ManualControlSetpoint()
        m.timestamp = m.timestamp_sample = self.stamp()
        m.valid = True
        m.data_source = ManualControlSetpoint.SOURCE_MAVLINK_0
        m.roll = float(self.sticks['roll'])
        m.pitch = float(self.sticks['pitch'])
        m.yaw = float(self.sticks['yaw'])
        m.throttle = float(self.sticks['throttle'])
        m.sticks_moving = any(abs(v) > 0.01 for v in self.sticks.values())
        self.manual_pub.publish(m)
        self.last_sent = dict(self.sticks)

    def report_stream(self) -> None:
        """Say how regular this node's own output actually was.

        Worth logging rather than assuming: the failsafe that keeps taking the
        aircraft is triggered by a gap in this stream, and a node that is late
        cannot tell the difference between a link that is broken and a link it
        is starving. If the longest gap here is under COM_RC_LOSS_T and PX4
        still calls the link lost, the problem is downstream of this process.
        """
        stamps, self.publish_stamps = self.publish_stamps, []
        if len(stamps) < 3:
            return
        gaps = sorted(b - a for a, b in zip(stamps, stamps[1:]))
        worst = gaps[-1]
        self.worst_gap = max(self.worst_gap, worst)
        span = stamps[-1] - stamps[0]
        over = sum(1 for g in gaps if g > 0.5)
        level = self.get_logger().warning if worst > 0.5 else self.get_logger().info
        level(f'manuel akis: {len(stamps)} mesaj, {len(stamps) / span:.1f} Hz, '
              f'aralik p50 {gaps[len(gaps) // 2] * 1000:.0f} ms, '
              f'en uzun {worst * 1000:.0f} ms, '
              f'>0.5 s bosluk {over} (kosu boyunca en uzun '
              f'{self.worst_gap * 1000:.0f} ms)')

    def advance_sticks(self, dt: float, now: float) -> None:
        """Move each axis toward where the keys are asking it to go.

        Pure arithmetic on self.sticks, separated out so the ramp can be
        checked without a window, a simulator or a person: feed it a sequence
        of (dt, key events) and the trajectory is reproducible.
        """
        if self.stick_mode != 'momentary':
            return
        dt = max(0.0, min(dt, 0.25))  # a stalled render must not lurch the axis
        for axis, value in self.sticks.items():
            pushed = self.hold[axis] if now < self.hold_until[axis] else 0.0
            if pushed:
                target = pushed * STICK_MAX
                step = self.ramp * dt
                value = (min(value + step, target) if target > value
                         else max(value - step, target))
            else:
                step = self.decay * dt
                value = max(value - step, 0.0) if value > 0 else min(value + step, 0.0)
            self.sticks[axis] = float(value)

    def press(self, axis: str, direction: float) -> None:
        """A key event on an axis: nudge it (sticky) or start pushing it
        (momentary)."""
        if self.stick_mode == 'momentary':
            now = self.now_wall()
            # Repeats arriving means the key is genuinely down, and a release
            # will be obvious within one repeat interval. Before they arrive,
            # the only evidence is the single press, which has to be trusted
            # across the repeat delay.
            repeating = (now - self.last_press[axis]) < self.repeat_timeout
            self.last_press[axis] = now
            self.hold[axis] = direction
            self.hold_until[axis] = now + (
                self.repeat_timeout if repeating else self.hold_timeout)
        else:
            self.sticks[axis] = float(
                np.clip(self.sticks[axis] + direction * STICK_STEP,
                        -STICK_MAX, STICK_MAX))

    @staticmethod
    def now_wall() -> float:
        return time.time()

    def send_command(self, command: int, p1=0.0, p2=0.0) -> None:
        c = VehicleCommand()
        c.timestamp = self.stamp()
        c.command = command
        c.param1 = float(p1)
        c.param2 = float(p2)
        c.target_system = c.target_component = 1
        c.source_system = 255
        c.source_component = 190
        c.from_external = True
        self.cmd_pub.publish(c)

    def set_nav_state(self, nav_state: int) -> None:
        self.send_command(CMD_SET_NAV_STATE, nav_state)

    # ------------------------------------------------------------------
    def handle_key(self, key: int) -> bool:
        """Returns False to quit."""
        k = chr(key).lower() if 32 <= key < 127 else ''
        if key == 27:  # ESC
            return False
        elif k == 'w':
            self.press('pitch', 1.0)
        elif k == 's':
            self.press('pitch', -1.0)
        elif k == 'd':
            self.press('roll', 1.0)
        elif k == 'a':
            self.press('roll', -1.0)
        elif k == 'e':
            self.press('yaw', 1.0)
        elif k == 'q':
            self.press('yaw', -1.0)
        elif k == 'r':
            self.press('throttle', 1.0)
        elif k == 'f':
            self.press('throttle', -1.0)
        elif key == 32:  # space
            for a in self.sticks:
                self.sticks[a] = 0.0
                self.hold[a] = 0.0
                self.hold_until[a] = 0.0
            self.notice = 'cubuklar ortalandi'
        elif k == '1':
            # -f: without a GCS attached the preflight check refuses on "no
            # connection to the GCS", which is not a real problem in SITL.
            self.send_command(VehicleCommand.VEHICLE_CMD_COMPONENT_ARM_DISARM,
                              1.0, 21196.0)
            self.notice = 'arm istendi'
        elif k == 'x':
            self.send_command(VehicleCommand.VEHICLE_CMD_COMPONENT_ARM_DISARM,
                              0.0, 21196.0)
            self.notice = 'disarm istendi'
        elif k == '2':
            self.send_command(VehicleCommand.VEHICLE_CMD_NAV_TAKEOFF)
            self.notice = 'kalkis istendi'
        elif k == '3':
            # Start the stream now, ask for the mode a moment later. PX4 will
            # not hand over to a manual control source it has not yet seen, and
            # requesting POSCTL in the same breath as enabling the publisher
            # means exactly zero messages have gone out when the request
            # arrives. Measured: doing both at once left the vehicle in AUTO
            # with sticks deflected, and the failsafe took it 7 s later.
            for a in self.sticks:
                self.sticks[a] = 0.0
            self.manual_active = True
            self.wants_manual = True
            self.takeovers = 0
            self.posctl_request_at = self.now() + MANUAL_SETTLE_S
            self.notice = 'manuel kontrol kuruluyor...'
        elif k == 'l':
            self.wants_manual = False
            self.set_nav_state(NAV_LAND)
            self.notice = "PX4 iniş modu"
        elif k == '0':
            # Asking for the landing mode is also giving up manual control;
            # without this the station would spend the whole descent trying to
            # take the aircraft back from a mode the operator just selected.
            self.wants_manual = False
            self.set_nav_state(NAV_EXTERNAL1)
            self.notice = 'ACIL INIS modu tetiklendi'
        elif k == '9':
            self.mode_enable_pub.publish(Bool(data=False))
            self.notice = ('acil inis modunun kaydi kaldiriliyor -- '
                           'RTL artik PX4 kendi Return modu')
        return True

    # ------------------------------------------------------------------
    def render(self) -> np.ndarray:
        if self.hud is not None:
            hud = self.hud
        else:
            hud = np.full((520, 850, 3), 24, np.uint8)
            cv2.putText(hud, 'HUD bekleniyor (/eland/hud)', (30, 260), FONT,
                        0.7, (120, 120, 120), 1, cv2.LINE_AA)

        strip = np.full((250, hud.shape[1], 3), 18, np.uint8)
        cv2.line(strip, (0, 0), (strip.shape[1], 0), (70, 70, 70), 1)

        # Key help, two columns.
        for i, (key, what) in enumerate(KEY_HELP):
            col, row = divmod(i, 7)
            x = 14 + col * 250
            y = 26 + row * 20
            if key:
                cv2.putText(strip, key, (x, y), FONT, 0.44, (120, 200, 255), 1,
                            cv2.LINE_AA)
                cv2.putText(strip, what, (x + 62, y), FONT, 0.40, (200, 200, 200),
                            1, cv2.LINE_AA)

        # Stick state, as bars, so a stick left deflected is obvious.
        bx = 14 + 2 * 250
        cv2.putText(strip, 'CUBUKLAR', (bx, 26), FONT, 0.42, (130, 190, 240), 1,
                    cv2.LINE_AA)
        for i, axis in enumerate(('pitch', 'roll', 'yaw', 'throttle')):
            y = 48 + i * 22
            v = self.last_sent[axis]
            cv2.putText(strip, f'{axis:9s}{v:+.1f}', (bx, y + 4), FONT, 0.40,
                        (200, 200, 200), 1, cv2.LINE_AA)
            x0 = bx + 110
            cv2.line(strip, (x0, y), (x0 + 120, y), (60, 60, 60), 3)
            mid = x0 + 60
            cv2.line(strip, (mid, y - 5), (mid, y + 5), (90, 90, 90), 1)
            end = int(mid + v * 58)
            if abs(v) > 0.01:
                cv2.line(strip, (mid, y), (end, y), (120, 235, 120), 3)

        # Vehicle state.
        sx = bx + 250
        cv2.putText(strip, 'DURUM', (sx, 26), FONT, 0.42, (130, 190, 240), 1,
                    cv2.LINE_AA)
        armed = ''
        nav = ''
        failsafe = ''
        if self.status is not None:
            armed = ('ARMED' if self.status.arming_state == 2 else 'disarmed')
            nav = f'nav_state {self.status.nav_state}' + (
                ' (POSCTL)' if self.status.nav_state == NAV_POSCTL else
                ' (ACIL INIS)' if self.status.nav_state == NAV_EXTERNAL1 else '')
            if self.status.failsafe:
                failsafe = 'FAILSAFE'
        manual = 'manuel: AKTIF' if self.manual_active else 'manuel: kapali'
        rows = [armed, nav, manual]
        if failsafe:
            rows.append(failsafe)
        if self.pos is not None:
            rows.append(f'alt {-self.pos.z:.1f} m')
            rows.append(f'hiz {math.hypot(self.pos.vx, self.pos.vy):.1f} m/s')
        for i, text in enumerate(rows):
            color = (120, 235, 120) if text == 'ARMED' else (200, 200, 200)
            if text == 'FAILSAFE':
                color = (90, 90, 250)
            cv2.putText(strip, text, (sx, 48 + i * 20), FONT, 0.40, color, 1,
                        cv2.LINE_AA)

        # The reason, when there is one. An operator who can see "the link is
        # considered lost" knows the aircraft is not ignoring them and knows
        # what would fix it; without it, the same event is just the vehicle
        # doing something unaccountable.
        why = self.failsafe_reason()
        if why:
            cv2.putText(strip, f'sebep: {why}', (14, strip.shape[0] - 34), FONT,
                        0.42, (90, 160, 250), 1, cv2.LINE_AA)

        cv2.putText(strip, self.notice, (14, strip.shape[0] - 14), FONT, 0.42,
                    (240, 200, 120), 1, cv2.LINE_AA)
        return np.vstack([hud, strip])


def main(args=None) -> None:
    rclpy.init(args=args)
    node = ControlStation()
    windowed = bool(node.get_parameter('window').value)

    # Spin in the background so the timers keep firing while the main thread is
    # busy drawing. Rendering must never be able to interrupt the flight link.
    executor = rclpy.executors.SingleThreadedExecutor()
    executor.add_node(node)
    spinner = threading.Thread(target=executor.spin, daemon=True)
    spinner.start()

    if not windowed:
        node.get_logger().info(
            'window:=false -- klavye yok, akis ve heartbeat calisiyor')
        try:
            spinner.join()
        except KeyboardInterrupt:
            pass
        node.destroy_node()
        rclpy.try_shutdown()
        return

    window = 'eland control station'
    cv2.namedWindow(window, cv2.WINDOW_AUTOSIZE)
    try:
        while rclpy.ok():
            cv2.imshow(window, node.render())
            key = cv2.waitKey(30)
            if key != -1 and not node.handle_key(key & 0xFF):
                break
    except KeyboardInterrupt:
        pass
    finally:
        cv2.destroyAllWindows()
        executor.shutdown()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
