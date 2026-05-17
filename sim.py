"""
DreamLoop AR Environment — V10
==============================
What's new vs V9:
  * Scenario 4: URBAN STORM — wet city street with a stop sign / parked-car
    obstacle 28m ahead. Same physics + skid mechanics as 1-3, plus an
    obstacle layer that determines if you stop in time.
  * AR DANGER ZONE: a red, pulsing stop line projected on the road that
    slides toward the camera as you approach. Turns to a collision marker
    if you blow through it.
  * Outcome badge: SAFE STOP / COLLISION fires after the car stops, with
    distance-to-obstacle readout in the HUD when scenario 4 is active.
  * Keypad 4 selects the new scenario.
"""

import cv2
import numpy as np
import random
import math


# ============================================================
#  VISUAL EFFECTS
# ============================================================

def apply_dashcam_filter(img, mode, freeze_intensity=0.0):
    """Color grade + scanlines + bullet-time cyan tint."""
    if mode == "1":
        img = cv2.convertScaleAbs(img, alpha=1.10, beta=10)
        img[:, :, 1] = cv2.add(img[:, :, 1], 10)
        img[:, :, 2] = cv2.add(img[:, :, 2], 15)
    elif mode == "2":
        img = cv2.convertScaleAbs(img, alpha=1.20, beta=-10)
        img[:, :, 0] = cv2.add(img[:, :, 0], 25)
        img[:, :, 2] = cv2.subtract(img[:, :, 2], 15)
    elif mode == "3":
        img = cv2.convertScaleAbs(img, alpha=1.15, beta=20)
        img[:, :, 0] = cv2.add(img[:, :, 0], 30)
        img[:, :, 1] = cv2.add(img[:, :, 1], 15)

    img[::3, :] = (img[::3, :] * 0.8).astype(np.uint8)

    if freeze_intensity > 0:
        tint = np.zeros_like(img)
        tint[:, :, 0] = 90
        tint[:, :, 1] = 40
        alpha = min(0.32, freeze_intensity * 0.32)
        img = cv2.addWeighted(img, 1.0 - alpha, tint, alpha, 0)
    return img


def apply_motion_blur(img, intensity, angle_deg=0.0):
    kernel_size = max(3, int(intensity))
    if kernel_size % 2 == 0:
        kernel_size += 1
    if kernel_size < 3:
        return img
    kernel = np.zeros((kernel_size, kernel_size), dtype=np.float32)
    angle_rad = math.radians(angle_deg)
    c = kernel_size // 2
    for i in range(kernel_size):
        offset = i - c
        x = int(round(c + offset * math.cos(angle_rad)))
        y = int(round(c + offset * math.sin(angle_rad)))
        if 0 <= x < kernel_size and 0 <= y < kernel_size:
            kernel[y, x] = 1.0
    s = kernel.sum()
    if s > 0:
        kernel /= s
    return cv2.filter2D(img, -1, kernel)


def apply_chromatic_aberration(img, intensity):
    if intensity < 1:
        return img
    shift = int(min(intensity, 10))
    h, w = img.shape[:2]
    b, g, r = cv2.split(img)
    M_r = np.float32([[1, 0,  shift], [0, 1, 0]])
    M_b = np.float32([[1, 0, -shift], [0, 1, 0]])
    r = cv2.warpAffine(r, M_r, (w, h), borderMode=cv2.BORDER_REPLICATE)
    b = cv2.warpAffine(b, M_b, (w, h), borderMode=cv2.BORDER_REPLICATE)
    return cv2.merge([b, g, r])


# ============================================================
#  AR LANE OVERLAY
# ============================================================

def draw_ar_lane_lines(img, lateral_drift, skid_angle, width, height):
    vp_x = width // 2
    vp_y = int(height * 0.50)

    drift_norm = max(-1.0, min(1.0, lateral_drift / 45.0))
    drift_px = -int(drift_norm * 240)
    drift_top_px = drift_px // 4
    skid_rad = math.radians(skid_angle * 0.4)

    def rot(x, y):
        dx, dy = x - vp_x, y - vp_y
        cs, sn = math.cos(skid_rad), math.sin(skid_rad)
        return int(vp_x + dx * cs - dy * sn), int(vp_y + dx * sn + dy * cs)

    lane_half = 220
    bl = rot(vp_x - lane_half + drift_px, height)
    br = rot(vp_x + lane_half + drift_px, height)
    tl = rot(vp_x - 32 + drift_top_px, vp_y)
    tr = rot(vp_x + 32 + drift_top_px, vp_y)

    drift_severity = min(1.0, abs(drift_norm))
    overlay = img.copy()

    if drift_severity > 0.45:
        fill = (0, 0, int(170 * drift_severity))
    else:
        fill = (int(90 * (1 - drift_severity)),
                int(130 * (1 - drift_severity)),
                30)
    lane_poly = np.array([bl, tl, tr, br], dtype=np.int32)
    cv2.fillPoly(overlay, [lane_poly], fill)
    cv2.addWeighted(overlay, 0.28, img, 0.72, 0, img)

    rail = (255, 200, 0) if drift_severity < 0.5 else (40, 80, 255)
    cv2.line(img, bl, tl, rail, 3, cv2.LINE_AA)
    cv2.line(img, br, tr, rail, 3, cv2.LINE_AA)

    bottom_center_x = vp_x + drift_px
    top_center_x = vp_x + drift_top_px
    for i in range(8):
        t1 = i / 8.0
        t2 = (i + 0.55) / 8.0
        x1 = int(bottom_center_x * (1 - t1) + top_center_x * t1)
        y1 = int(height * (1 - t1) + vp_y * t1)
        x2 = int(bottom_center_x * (1 - t2) + top_center_x * t2)
        y2 = int(height * (1 - t2) + vp_y * t2)
        x1, y1 = rot(x1, y1)
        x2, y2 = rot(x2, y2)
        thickness = max(1, int(5 * (1 - t1)))
        cv2.line(img, (x1, y1), (x2, y2), (255, 255, 255), thickness, cv2.LINE_AA)

    if drift_severity > 0.6:
        side = 1 if lateral_drift > 0 else -1
        for i in range(3):
            cxw = vp_x - side * (160 + i * 55)
            cyw = height - 90 - i * 28
            pts = np.array([[cxw - 22, cyw + 16],
                            [cxw,     cyw - 16],
                            [cxw + 22, cyw + 16]], dtype=np.int32)
            cv2.polylines(img, [pts], False, (40, 80, 255), 4, cv2.LINE_AA)


def draw_ar_danger_zone(img, dist_remaining_m, total_obstacle_m,
                        lateral_drift, skid_angle, time_elapsed,
                        outcome, width, height):
    """Red AR stop line that slides toward camera as the car closes in.
    Turns to a collision splash when distance_remaining <= 0."""
    if total_obstacle_m is None:
        return

    vp_x = width // 2
    vp_y = int(height * 0.50)

    # Same lane math as the lane drawer so the marker sits on the road plane
    drift_norm = max(-1.0, min(1.0, lateral_drift / 45.0))
    drift_px = -int(drift_norm * 240)
    drift_top_px = drift_px // 4
    skid_rad = math.radians(skid_angle * 0.4)

    def rot(x, y):
        dx, dy = x - vp_x, y - vp_y
        cs, sn = math.cos(skid_rad), math.sin(skid_rad)
        return int(vp_x + dx * cs - dy * sn), int(vp_y + dx * sn + dy * cs)

    # Map distance remaining -> screen-y on the road plane
    # 0m remaining = right under the camera (y = height)
    # total obstacle distance = on the horizon (y = vp_y)
    t = max(0.0, min(1.0, dist_remaining_m / total_obstacle_m))
    # Non-linear perspective compression — things close to horizon move slow
    t_curve = t ** 1.6
    obs_y = int(vp_y + (height - vp_y) * (1 - t_curve))

    # Lane width at this y — linear blend between top and bottom edges
    lane_half_top, lane_half_bot = 32, 220
    lane_half = lane_half_top + (lane_half_bot - lane_half_top) * (1 - t_curve)
    obs_x_offset = int(drift_top_px + (drift_px - drift_top_px) * (1 - t_curve))

    pulse = (math.sin(time_elapsed * 7) + 1) / 2  # 0..1
    base_red = (40, 60, 220)

    if outcome == "COLLISION" or dist_remaining_m <= 0:
        # Slammed through it — flash splash near the car
        splash_y = height - 80
        splash_overlay = img.copy()
        for r, a in [(220, 0.55), (160, 0.7), (95, 0.9)]:
            cv2.ellipse(splash_overlay, (vp_x + int(drift_px * 0.3), splash_y),
                        (r, int(r * 0.45)), 0, 0, 360, (40, 60, 240), -1)
        cv2.addWeighted(splash_overlay, 0.5, img, 0.5, 0, img)
        # X marker
        x_size = 50
        cv2.line(img, (vp_x - x_size, splash_y - x_size),
                 (vp_x + x_size, splash_y + x_size), (255, 255, 255), 4, cv2.LINE_AA)
        cv2.line(img, (vp_x + x_size, splash_y - x_size),
                 (vp_x - x_size, splash_y + x_size), (255, 255, 255), 4, cv2.LINE_AA)
        return

    # ---- Danger band: filled red trapezoid on the road plane ----
    band_height = max(6, int(28 * (1 - t_curve) + 6))
    p_top_l = rot(vp_x - int(lane_half * 0.92) + obs_x_offset, obs_y - band_height // 2)
    p_top_r = rot(vp_x + int(lane_half * 0.92) + obs_x_offset, obs_y - band_height // 2)
    p_bot_l = rot(vp_x - int(lane_half) + obs_x_offset, obs_y + band_height // 2)
    p_bot_r = rot(vp_x + int(lane_half) + obs_x_offset, obs_y + band_height // 2)

    overlay = img.copy()
    cv2.fillPoly(overlay, [np.array([p_top_l, p_top_r, p_bot_r, p_bot_l], dtype=np.int32)], base_red)
    alpha = 0.35 + pulse * 0.30
    cv2.addWeighted(overlay, alpha, img, 1 - alpha, 0, img)

    # Hash-marks across the band for a "construction tape" feel
    n_hashes = 10
    for i in range(n_hashes):
        u1 = i / n_hashes
        u2 = (i + 0.45) / n_hashes
        x1_top = int(p_top_l[0] * (1 - u1) + p_top_r[0] * u1)
        y1_top = int(p_top_l[1] * (1 - u1) + p_top_r[1] * u1)
        x2_top = int(p_top_l[0] * (1 - u2) + p_top_r[0] * u2)
        y2_top = int(p_top_l[1] * (1 - u2) + p_top_r[1] * u2)
        x1_bot = int(p_bot_l[0] * (1 - u1) + p_bot_r[0] * u1)
        y1_bot = int(p_bot_l[1] * (1 - u1) + p_bot_r[1] * u1)
        x2_bot = int(p_bot_l[0] * (1 - u2) + p_bot_r[0] * u2)
        y2_bot = int(p_bot_l[1] * (1 - u2) + p_bot_r[1] * u2)
        pts = np.array([(x1_top, y1_top), (x2_top, y2_top),
                        (x2_bot, y2_bot), (x1_bot, y1_bot)], dtype=np.int32)
        cv2.fillPoly(img, [pts], (255, 255, 255))

    # ---- Floating distance label above the band ----
    if dist_remaining_m > 0.5:
        label_y = max(vp_y + 10, obs_y - band_height - 8)
        label_x = vp_x + obs_x_offset
        label = f"{dist_remaining_m:.1f}M"
        scale = 0.45 + (1 - t_curve) * 0.5
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, scale, 2)
        bg = img.copy()
        cv2.rectangle(bg, (label_x - tw // 2 - 8, label_y - th - 6),
                      (label_x + tw // 2 + 8, label_y + 6),
                      (10, 14, 24), -1)
        cv2.rectangle(bg, (label_x - tw // 2 - 8, label_y - th - 6),
                      (label_x + tw // 2 + 8, label_y + 6),
                      base_red, 2)
        cv2.addWeighted(bg, 0.8, img, 0.2, 0, img)
        cv2.putText(img, label, (label_x - tw // 2, label_y),
                    cv2.FONT_HERSHEY_SIMPLEX, scale, (60, 80, 255), 2, cv2.LINE_AA)


def draw_outcome_badge(img, outcome, width, height, time_elapsed):
    """Center-screen verdict shown after the car stops in a scenario with obstacle."""
    if outcome not in ("SAFE", "COLLISION"):
        return

    pulse = (math.sin(time_elapsed * 4) + 1) / 2
    if outcome == "SAFE":
        title = "SAFE STOP"
        sub = "OBSTACLE AVOIDED"
        col = (80, 230, 120)
    else:
        title = "COLLISION"
        sub = "STOPPING DISTANCE EXCEEDED"
        col = (40, 70, 255)

    cx, cy = width // 2, int(height * 0.32)
    bw, bh = 360, 100

    overlay = img.copy()
    cv2.rectangle(overlay, (cx - bw // 2, cy - bh // 2), (cx + bw // 2, cy + bh // 2),
                  (10, 14, 22), -1)
    cv2.rectangle(overlay, (cx - bw // 2, cy - bh // 2), (cx + bw // 2, cy + bh // 2),
                  col, int(2 + pulse * 2))
    cv2.addWeighted(overlay, 0.9, img, 0.1, 0, img)

    (tw, th), _ = cv2.getTextSize(title, cv2.FONT_HERSHEY_SIMPLEX, 1.2, 3)
    cv2.putText(img, title, (cx - tw // 2, cy + 6),
                cv2.FONT_HERSHEY_SIMPLEX, 1.2, col, 3, cv2.LINE_AA)
    (tw, _), _ = cv2.getTextSize(sub, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
    cv2.putText(img, sub, (cx - tw // 2, cy + 32),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 210, 220), 1, cv2.LINE_AA)


# ============================================================
#  PLAYER CAR (3rd-person, rendered in screen space after warp)
# ============================================================

def draw_player_car(img, cx, cy, angle_deg, brake_active=False,
                    drift_severity=0.0, smoke_particles=None):
    """Stylized 3rd-person car. Mostly back-view; yaws slightly with drift."""
    theta = math.radians(angle_deg)
    cos_t, sin_t = math.cos(theta), math.sin(theta)

    def rot(px, py):
        return (int(cx + px * cos_t - py * sin_t),
                int(cy + px * sin_t + py * cos_t))

    def poly(*points):
        return np.array([rot(*p) for p in points], dtype=np.int32)

    # ---- Ground shadow (axis-aligned) ----
    shadow_overlay = img.copy()
    sx = int(math.sin(theta) * 4)
    cv2.ellipse(shadow_overlay, (cx + sx, cy + 50), (95, 16), 0, 0, 360, (0, 0, 0), -1)
    cv2.addWeighted(shadow_overlay, 0.45, img, 0.55, 0, img)

    # ---- Tire smoke (drawn under car so smoke trails behind) ----
    if smoke_particles:
        smoke_overlay = img.copy()
        for puff in smoke_particles:
            alpha = max(0.0, 1.0 - puff["age"] / 0.9)
            cv2.circle(smoke_overlay,
                       (int(puff["x"]), int(puff["y"])),
                       int(puff["size"]),
                       (215, 215, 220), -1)
        cv2.addWeighted(smoke_overlay, 0.45, img, 0.55, 0, img)

    # ---- Rear wheels ----
    wheel_dark = (10, 10, 15)
    rim = (50, 50, 55)
    cv2.fillPoly(img, [poly((-74, 26), (-52, 26), (-52, 46), (-74, 46))], wheel_dark)
    cv2.fillPoly(img, [poly((52, 26), (74, 26), (74, 46), (52, 46))], wheel_dark)
    # Rim suggestions
    cv2.fillPoly(img, [poly((-70, 31), (-56, 31), (-56, 41), (-70, 41))], rim)
    cv2.fillPoly(img, [poly((56, 31), (70, 31), (70, 41), (56, 41))], rim)

    # ---- Rear diffuser / lower bumper ----
    cv2.fillPoly(img, [poly((-76, 16), (76, 16), (76, 32), (-76, 32))], (12, 15, 22))
    # Exhaust pipes (twin)
    cv2.fillPoly(img, [poly((-18, 28), (-8, 28), (-8, 34), (-18, 34))], (35, 38, 45))
    cv2.fillPoly(img, [poly((8, 28), (18, 28), (18, 34), (8, 34))], (35, 38, 45))

    # ---- Main chassis (red sports car) ----
    body = (40, 40, 220)
    chassis = poly((-66, -28), (66, -28), (76, 20), (-76, 20))
    cv2.fillPoly(img, [chassis], body)

    # Panel highlight line along the side
    cv2.line(img, rot(-68, -8), rot(-78, 18), (20, 20, 130), 1, cv2.LINE_AA)
    cv2.line(img, rot(68, -8), rot(78, 18), (20, 20, 130), 1, cv2.LINE_AA)

    # Top sheen (lighter strip)
    sheen = (90, 90, 255)
    cv2.fillPoly(img, [poly((-62, -28), (62, -28), (57, -20), (-57, -20))], sheen)

    # ---- Roof ----
    roof = (20, 20, 150)
    cv2.fillPoly(img, [poly((-46, -54), (46, -54), (58, -28), (-58, -28))], roof)

    # ---- Rear windshield ----
    window = (28, 32, 42)
    cv2.fillPoly(img, [poly((-42, -50), (42, -50), (52, -30), (-52, -30))], window)
    # Window reflection
    cv2.fillPoly(img, [poly((-38, -48), (-14, -48), (-22, -38), (-40, -38))], (70, 85, 100))

    # ---- Spoiler line ----
    cv2.line(img, rot(-52, -30), rot(52, -30), (10, 10, 80), 3, cv2.LINE_AA)

    # ---- Taillights ----
    if brake_active:
        # Glow halo first
        glow = img.copy()
        cv2.ellipse(glow, rot(-49, -2), (18, 11), -angle_deg, 0, 360, (0, 50, 255), -1)
        cv2.ellipse(glow, rot(49, -2), (18, 11), -angle_deg, 0, 360, (0, 50, 255), -1)
        cv2.addWeighted(glow, 0.55, img, 0.45, 0, img)
        light_color = (60, 70, 255)
    else:
        light_color = (30, 30, 130)
    cv2.fillPoly(img, [poly((-60, -9), (-38, -9), (-38, 5), (-60, 5))], light_color)
    cv2.fillPoly(img, [poly((38, -9), (60, -9), (60, 5), (38, 5))], light_color)

    # Center brake-light bar across the spoiler (only when braking)
    if brake_active:
        cv2.fillPoly(img, [poly((-30, -34), (30, -34), (30, -29), (-30, -29))], (60, 70, 255))

    # ---- License plate ----
    cv2.fillPoly(img, [poly((-17, 7), (17, 7), (17, 17), (-17, 17))], (220, 220, 220))


def update_smoke_particles(particles, dt, car_cx, car_cy, angle_deg,
                           is_active, max_particles=40):
    """Age existing puffs, spawn new ones at the rear wheels if drifting."""
    # Age + cull
    survivors = []
    for p in particles:
        p["age"] += dt
        p["x"] += p["vx"] * dt
        p["y"] += p["vy"] * dt
        p["size"] += dt * 18
        if p["age"] < 0.9:
            survivors.append(p)
    particles = survivors

    # Spawn
    if is_active and len(particles) < max_particles:
        theta = math.radians(angle_deg)
        cos_t, sin_t = math.cos(theta), math.sin(theta)
        for wx_local, wy_local in [(-63, 44), (63, 44)]:
            wx = car_cx + wx_local * cos_t - wy_local * sin_t
            wy = car_cy + wx_local * sin_t + wy_local * cos_t
            for _ in range(2):
                particles.append({
                    "x": wx + random.uniform(-6, 6),
                    "y": wy + random.uniform(-4, 4),
                    "vx": random.uniform(-8, 8),
                    "vy": random.uniform(-15, -3),
                    "age": 0.0,
                    "size": random.uniform(7, 12),
                })
    return particles


# ============================================================
#  HUD COMPONENTS
# ============================================================

def draw_speedometer(img, cx, cy, radius, speed, max_speed=150):
    start_angle = 135
    sweep = 270
    cv2.ellipse(img, (cx, cy), (radius, radius), 0,
                start_angle, start_angle + sweep, (35, 40, 50), 6)
    for tick in range(0, max_speed + 1, 30):
        ang = math.radians(start_angle + sweep * tick / max_speed)
        x1 = int(cx + (radius - 9) * math.cos(ang))
        y1 = int(cy + (radius - 9) * math.sin(ang))
        x2 = int(cx + (radius + 2) * math.cos(ang))
        y2 = int(cy + (radius + 2) * math.sin(ang))
        cv2.line(img, (x1, y1), (x2, y2), (120, 130, 140), 1, cv2.LINE_AA)

    speed_c = max(0, min(speed, max_speed))
    end_angle = start_angle + sweep * (speed_c / max_speed)
    if speed_c > 100:
        color = (50, 50, 255)
    elif speed_c > 60:
        color = (50, 180, 255)
    else:
        color = (100, 255, 100)
    cv2.ellipse(img, (cx, cy), (radius, radius), 0, start_angle, end_angle, color, 6)

    text = f"{int(speed_c)}"
    (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.95, 2)
    cv2.putText(img, text, (cx - tw // 2, cy + th // 2 - 4),
                cv2.FONT_HERSHEY_SIMPLEX, 0.95, (255, 255, 255), 2, cv2.LINE_AA)
    cv2.putText(img, "KM/H", (cx - 17, cy + 22),
                cv2.FONT_HERSHEY_SIMPLEX, 0.36, (160, 170, 180), 1, cv2.LINE_AA)


def draw_corner_brackets(img, x, y, w, h, color, length=14, thick=2):
    cv2.line(img, (x, y), (x + length, y), color, thick)
    cv2.line(img, (x, y), (x, y + length), color, thick)
    cv2.line(img, (x + w, y), (x + w - length, y), color, thick)
    cv2.line(img, (x + w, y), (x + w, y + length), color, thick)
    cv2.line(img, (x, y + h), (x + length, y + h), color, thick)
    cv2.line(img, (x, y + h), (x, y + h - length), color, thick)
    cv2.line(img, (x + w, y + h), (x + w - length, y + h), color, thick)
    cv2.line(img, (x + w, y + h), (x + w, y + h - length), color, thick)


def draw_freeze_indicator(img, freeze_intensity, time_elapsed, width, height):
    if freeze_intensity <= 0.05:
        return
    pulse = (math.sin(time_elapsed * 6) + 1) / 2
    border = img.copy()
    cv2.rectangle(border, (0, 0), (width - 1, height - 1), (50, 180, 255), 5)
    a = (0.25 + pulse * 0.35) * freeze_intensity
    cv2.addWeighted(border, a, img, 1 - a, 0, img)

    bx1, bx2 = width // 2 - 200, width // 2 + 200
    by1, by2 = 36, 72
    banner = img.copy()
    cv2.rectangle(banner, (bx1, by1), (bx2, by2), (8, 14, 24), -1)
    cv2.rectangle(banner, (bx1, by1), (bx2, by2), (50, 200, 255), 2)
    a = 0.88 * freeze_intensity
    cv2.addWeighted(banner, a, img, 1 - a, 0, img)
    text = "BULLET-TIME // ANALYSIS PAUSED"
    (tw, _), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)
    cv2.putText(img, text, (width // 2 - tw // 2, 60),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (50, 220, 255), 2, cv2.LINE_AA)

    scan_y = int((time_elapsed * 120) % height)
    scan = img.copy()
    cv2.line(scan, (0, scan_y), (width, scan_y), (255, 220, 100), 1)
    cv2.addWeighted(scan, 0.18 * freeze_intensity, img, 1 - 0.18 * freeze_intensity, 0, img)


# ============================================================
#  MAIN
# ============================================================

def run_ar_sim():
    SCENARIOS = {
        "1": {"name": "SUNNY",        "file": "dreamloop_sunny.avi",    "mu": 0.80, "obstacle_m": None},
        "2": {"name": "WAYMO / RAIN", "file": "dreamloop_waymo.avi",    "mu": 0.40, "obstacle_m": None},
        "3": {"name": "BLIZZARD",     "file": "dreamloop_blizzard.avi", "mu": 0.15, "obstacle_m": None},
        "4": {"name": "URBAN STORM",  "file": "blizzard_5s.mp4",        "mu": 0.50, "obstacle_m": 28.0},
    }

    current_mode = "1"
    initial_speed_kmh = 70.0
    reaction_time_sec = 0.5
    GRAVITY = 9.81
    FPS = 30
    DT = 1.0 / FPS
    WIDTH, HEIGHT = 1000, 600

    def reset_state():
        return {
            "v": initial_speed_kmh / 3.6,
            "v_initial": initial_speed_kmh / 3.6,
            "distance_m": 0.0,
            "phase": "CRUISING",
            "reaction_timer": 0.0,
            "is_skidding": False,
            "skid_angle": 0.0,
            "lateral_drift": 0.0,
            "drift_velocity": 0.0,
            "wobble_dir": random.choice([-1, 1]),
            "freeze_intensity": 0.0,
            "time_elapsed": 0.0,
            "impact_flash": 0.0,
            "smoke": [],
            "outcome": "PENDING",   # PENDING / SAFE / COLLISION (only meaningful when obstacle_m is set)
        }

    state = reset_state()
    cap = cv2.VideoCapture(SCENARIOS[current_mode]["file"])
    if not cap.isOpened():
        print(f"ERROR: Could not open {SCENARIOS[current_mode]['file']}")
        return

    print("=" * 60)
    print("  DREAMLOOP V10 — 4 SCENARIOS + OBSTACLE AVOIDANCE")
    print("  > [1] Sunny       Brake = video freezes for analysis")
    print("  > [2] Rain        Brake = video keeps rolling")
    print("  > [3] Blizzard    Brake = video keeps rolling")
    print("  > [4] Urban Storm Brake = obstacle at 28m, can you stop?")
    print("=" * 60)

    raw_frame = None
    ACCENT = (0, 220, 255)

    while True:
        state["time_elapsed"] += DT

        # ---- Only Sunny freezes; Rain/Blizzard keep playing live ----
        should_freeze = (current_mode == "1" and state["phase"] != "CRUISING")
        target = 1.0 if should_freeze else 0.0
        if state["freeze_intensity"] < target:
            state["freeze_intensity"] = min(target, state["freeze_intensity"] + DT * 5)
        else:
            state["freeze_intensity"] = max(target, state["freeze_intensity"] - DT * 5)

        # Read new frames unless the freeze is engaged
        if not should_freeze:
            ret, current_frame = cap.read()
            if not ret:
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, current_frame = cap.read()
            raw_frame = current_frame
        if raw_frame is None:
            continue

        frame = cv2.resize(raw_frame.copy(), (WIDTH, HEIGHT))
        frame = apply_dashcam_filter(frame, current_mode, state["freeze_intensity"])
        mu = SCENARIOS[current_mode]["mu"]

        # ============ PHYSICS ============
        if state["phase"] == "REACTING":
            state["reaction_timer"] += DT
            if state["reaction_timer"] >= reaction_time_sec:
                state["phase"] = "BRAKING"
                if current_mode == "3" and initial_speed_kmh > 40.0:
                    state["is_skidding"] = True
                elif current_mode == "2" and initial_speed_kmh > 80.0:
                    state["is_skidding"] = True
                elif current_mode == "1" and initial_speed_kmh > 130.0:
                    state["is_skidding"] = True

        elif state["phase"] == "BRAKING":
            decel = mu * GRAVITY
            state["v"] = max(0.0, state["v"] - decel * DT)

            if state["is_skidding"] and state["v"] > 0:
                severity = (initial_speed_kmh / 60.0) * (1.0 - mu)
                state["drift_velocity"] += state["wobble_dir"] * severity * 22.0 * DT
                state["skid_angle"] += state["wobble_dir"] * severity * 45.0 * DT
                if random.random() < 0.022:
                    state["wobble_dir"] *= -1

            # Integrate drift + damping toward zero so values stay readable
            state["lateral_drift"] += state["drift_velocity"] * DT
            state["drift_velocity"] *= 0.985
            state["skid_angle"] *= 0.97

            # Hard clamps
            state["lateral_drift"] = max(-55, min(55, state["lateral_drift"]))
            state["skid_angle"] = max(-45, min(45, state["skid_angle"]))

            if state["v"] <= 0:
                state["v"] = 0
                state["phase"] = "STOPPED"
                if state["is_skidding"] and state["impact_flash"] < 0.1:
                    state["impact_flash"] = 1.0
                # Compute outcome if this scenario has an obstacle
                obstacle_m = SCENARIOS[current_mode]["obstacle_m"]
                if obstacle_m is not None and state["outcome"] == "PENDING":
                    if state["distance_m"] < obstacle_m:
                        state["outcome"] = "SAFE"
                    else:
                        state["outcome"] = "COLLISION"

        # Mid-flight collision detection (the car keeps going and hits the line)
        obstacle_m = SCENARIOS[current_mode]["obstacle_m"]
        if (obstacle_m is not None and state["outcome"] == "PENDING"
                and state["distance_m"] >= obstacle_m and state["phase"] != "CRUISING"):
            state["outcome"] = "COLLISION"
            state["impact_flash"] = 1.0
            state["v"] = 0
            state["phase"] = "STOPPED"

        state["distance_m"] += state["v"] * DT
        state["impact_flash"] = max(0.0, state["impact_flash"] - DT * 2)

        # ============ AR LANE LINES (world space) ============
        draw_ar_lane_lines(frame, state["lateral_drift"], state["skid_angle"], WIDTH, HEIGHT)

        # ============ AR DANGER ZONE (obstacle marker on road plane) ============
        obstacle_m = SCENARIOS[current_mode]["obstacle_m"]
        if obstacle_m is not None:
            dist_remaining = max(0.0, obstacle_m - state["distance_m"])
            draw_ar_danger_zone(frame, dist_remaining, obstacle_m,
                                state["lateral_drift"], state["skid_angle"],
                                state["time_elapsed"], state["outcome"],
                                WIDTH, HEIGHT)

        # ============ VIDEO WARP / SHAKE ============
        if state["phase"] != "CRUISING":
            if state["is_skidding"] and state["v"] > 0:
                shake_x = random.randint(-9, 9)
                shake_y = random.randint(-15, 15)
            elif state["v"] > 0:
                shake_x = random.randint(-2, 2)
                shake_y = random.randint(-3, 3)
            else:
                shake_x = random.randint(-1, 1)
                shake_y = random.randint(-1, 1)

            shift_x = int(state["lateral_drift"] * 2.5) + shake_x
            shift_y = shake_y
            cam_tilt = state["skid_angle"] * -0.22
            zoom = 1.13
            M = cv2.getRotationMatrix2D((WIDTH // 2, HEIGHT // 2), cam_tilt, zoom)
            M[0, 2] += shift_x
            M[1, 2] += shift_y
            frame = cv2.warpAffine(frame, M, (WIDTH, HEIGHT), borderMode=cv2.BORDER_REPLICATE)

            if state["is_skidding"] and state["v"] > 5:
                blur_strength = min(13, abs(state["drift_velocity"]) * 1.8 + 3)
                frame = apply_motion_blur(frame, blur_strength, angle_deg=state["skid_angle"])

            if state["impact_flash"] > 0.1:
                frame = apply_chromatic_aberration(frame, state["impact_flash"] * 9)

            if state["is_skidding"]:
                vignette = np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8)
                cv2.rectangle(vignette, (0, 0), (WIDTH, HEIGHT), (0, 0, 255), 32)
                frame = cv2.addWeighted(frame, 1.0, vignette, 0.55, 0)

        if state["impact_flash"] > 0.1:
            flash = np.full((HEIGHT, WIDTH, 3), 255, dtype=np.uint8)
            a = state["impact_flash"] * 0.45
            frame = cv2.addWeighted(frame, 1 - a, flash, a, 0)

        # ============ FREEZE INDICATOR ============
        draw_freeze_indicator(frame, state["freeze_intensity"], state["time_elapsed"], WIDTH, HEIGHT)

        # ============ PLAYER CAR (drawn after warp, screen space) ============
        # Stays near screen center, slides subtly with drift, yaws with skid
        drift_norm = max(-1.0, min(1.0, state["lateral_drift"] / 55.0))
        car_cx = WIDTH // 2 + int(drift_norm * 90)
        car_cy = HEIGHT - 145
        render_angle = state["skid_angle"] * 0.55  # tone down the yaw for back-view feel
        brake_active = state["phase"] in ("BRAKING", "STOPPED") or state["impact_flash"] > 0

        # Update smoke
        smoke_active = state["is_skidding"] and state["v"] > 4
        state["smoke"] = update_smoke_particles(state["smoke"], DT,
                                                car_cx, car_cy, render_angle,
                                                smoke_active)

        # Speed wobble for feel — tiny vertical bob at high speed
        bob = math.sin(state["time_elapsed"] * 8) * (state["v"] / 25.0) * 0.6
        draw_player_car(frame, car_cx, car_cy + int(bob), render_angle,
                        brake_active=brake_active,
                        drift_severity=abs(drift_norm),
                        smoke_particles=state["smoke"])

        # ============ HUD (narrowed) ============
        hud_x, hud_y = 20, HEIGHT - 200
        hud_w, hud_h = 380, 180

        overlay = frame.copy()
        cv2.rectangle(overlay, (hud_x, hud_y), (hud_x + hud_w, hud_y + hud_h), (12, 18, 28), -1)
        cv2.rectangle(overlay, (hud_x, hud_y), (hud_x + 4, hud_y + hud_h), ACCENT, -1)
        cv2.rectangle(overlay, (hud_x, hud_y), (hud_x + hud_w, hud_y + 28), (20, 28, 42), -1)
        cv2.addWeighted(overlay, 0.85, frame, 0.15, 0, frame)
        draw_corner_brackets(frame, hud_x, hud_y, hud_w, hud_h, ACCENT, 14, 2)

        cv2.putText(frame, "// DREAMLOOP TELEMETRY", (hud_x + 16, hud_y + 19),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, ACCENT, 1, cv2.LINE_AA)
        scen_label = f"v9.0  ::  {SCENARIOS[current_mode]['name']}"
        (tw, _), _ = cv2.getTextSize(scen_label, cv2.FONT_HERSHEY_SIMPLEX, 0.42, 1)
        cv2.putText(frame, scen_label, (hud_x + hud_w - tw - 14, hud_y + 19),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.42, (150, 200, 220), 1, cv2.LINE_AA)

        draw_speedometer(frame, hud_x + 65, hud_y + 100, 46, state["v"] * 3.6)

        tx = hud_x + 140
        ty = hud_y + 48

        if state["phase"] == "CRUISING":
            stat_col, stat_txt = (100, 255, 150), "* CRUISING"
        elif state["is_skidding"]:
            stat_col, stat_txt = (40, 80, 255), "! SKIDDING"
        elif state["phase"] == "STOPPED":
            stat_col, stat_txt = (50, 200, 255), "# STOPPED"
        else:
            stat_col, stat_txt = (0, 200, 255), f"> {state['phase']}"

        cv2.putText(frame, "STATUS", (tx, ty),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.38, (130, 135, 145), 1, cv2.LINE_AA)
        cv2.putText(frame, stat_txt, (tx, ty + 18),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.52, stat_col, 2, cv2.LINE_AA)

        cv2.putText(frame, "DISTANCE", (tx + 120, ty),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.38, (130, 135, 145), 1, cv2.LINE_AA)
        cv2.putText(frame, f"{state['distance_m']:.1f} M", (tx + 120, ty + 18),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.52, (100, 255, 100), 2, cv2.LINE_AA)

        g_force = mu if state["phase"] == "BRAKING" else 0.0
        cv2.putText(frame, "DECEL", (tx, ty + 46),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.38, (130, 135, 145), 1, cv2.LINE_AA)
        cv2.putText(frame, f"{g_force:.2f} G", (tx, ty + 64),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.52, (255, 255, 255), 2, cv2.LINE_AA)

        mu_col = (100, 255, 100) if mu > 0.6 else ((50, 180, 255) if mu > 0.3 else (50, 50, 255))
        obstacle_m_hud = SCENARIOS[current_mode]["obstacle_m"]
        if obstacle_m_hud is not None:
            # Replace GRIP slot with TO OBSTACLE for obstacle scenarios
            dist_rem = max(0.0, obstacle_m_hud - state["distance_m"])
            if state["outcome"] == "COLLISION":
                obs_col, obs_txt = (40, 70, 255), "IMPACT"
            elif state["outcome"] == "SAFE":
                obs_col, obs_txt = (80, 230, 120), "CLEAR"
            else:
                obs_col = (40, 70, 255) if dist_rem < 8 else ((50, 180, 255) if dist_rem < 18 else (100, 255, 120))
                obs_txt = f"{dist_rem:.1f} M"
            cv2.putText(frame, "TO OBSTACLE", (tx + 120, ty + 46),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.38, (130, 135, 145), 1, cv2.LINE_AA)
            cv2.putText(frame, obs_txt, (tx + 120, ty + 64),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.52, obs_col, 2, cv2.LINE_AA)
        else:
            cv2.putText(frame, "GRIP (mu)", (tx + 120, ty + 46),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.38, (130, 135, 145), 1, cv2.LINE_AA)
            cv2.putText(frame, f"{mu:.2f}", (tx + 120, ty + 64),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.52, mu_col, 2, cv2.LINE_AA)

        # Slip bar
        bar_x = hud_x + 16
        bar_y = hud_y + hud_h - 28
        bar_w = hud_w - 32
        bar_h = 10
        cv2.putText(frame, "LATERAL SLIP", (bar_x, bar_y - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.36, (130, 135, 145), 1, cv2.LINE_AA)
        cv2.rectangle(frame, (bar_x, bar_y), (bar_x + bar_w, bar_y + bar_h), (35, 40, 50), -1)
        center = bar_x + bar_w // 2
        cv2.line(frame, (center, bar_y - 2), (center, bar_y + bar_h + 2), (90, 95, 105), 1)

        slip_norm = max(-1.0, min(1.0, state["lateral_drift"] / 45.0))
        slip_color = (40, 80, 255) if abs(slip_norm) > 0.5 else (100, 255, 120)
        slip_px = int(slip_norm * (bar_w // 2))
        if slip_px >= 0:
            cv2.rectangle(frame, (center, bar_y), (center + slip_px, bar_y + bar_h), slip_color, -1)
        else:
            cv2.rectangle(frame, (center + slip_px, bar_y), (center, bar_y + bar_h), slip_color, -1)

        # ============ TOP CONTROL BAR ============
        cv2.rectangle(frame, (0, 0), (WIDTH, 28), (8, 12, 18), -1)
        cv2.line(frame, (0, 28), (WIDTH, 28), ACCENT, 1)
        cv2.putText(frame,
                    "[1]SUNNY [2]RAIN [3]BLIZZARD [4]URBAN  |  [W/S]SPEED  |  [SPACE]BRAKE  |  [R]RESET [Q]QUIT",
                    (10, 19), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (190, 220, 240), 1, cv2.LINE_AA)
        speed_label = f"SET: {initial_speed_kmh:.0f} KM/H"
        (tw, _), _ = cv2.getTextSize(speed_label, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
        cv2.putText(frame, speed_label, (WIDTH - tw - 12, 19),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 220, 100), 1, cv2.LINE_AA)

        # ============ OUTCOME BADGE (only for scenarios with obstacle) ============
        draw_outcome_badge(frame, state["outcome"], WIDTH, HEIGHT, state["time_elapsed"])

        cv2.imshow("DreamLoop AR Environment", frame)

        # ============ CONTROLS ============
        key = cv2.waitKey(max(1, int(DT * 1000))) & 0xFF
        if key == ord('q'):
            break
        elif key in [ord('1'), ord('2'), ord('3'), ord('4')]:
            if str(chr(key)) != current_mode:
                current_mode = str(chr(key))
                cap.release()
                cap = cv2.VideoCapture(SCENARIOS[current_mode]["file"])
                state = reset_state()
        elif key == ord('w'):
            initial_speed_kmh = min(150, initial_speed_kmh + 5)
            state = reset_state()
        elif key == ord('s'):
            initial_speed_kmh = max(10, initial_speed_kmh - 5)
            state = reset_state()
        elif key == ord(' '):
            if state["phase"] == "CRUISING":
                state["phase"] = "REACTING"
        elif key == ord('r'):
            state = reset_state()

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    run_ar_sim()