import pygame
import math

pygame.init()

# ---------------- CONFIG ----------------
WIDTH, HEIGHT = 1440, 780
MENU_WIDTH = 220
FPS = 120

k = 2000

screen = pygame.display.set_mode((WIDTH, HEIGHT))
clock = pygame.time.Clock()

# ---------------- COLORS ----------------
WHITE = (255,255,255)
BLACK = (0,0,0)
BLUE = (80,120,255)
RED = (255,0,0)
GREEN = (10,205,150)
CYAN = (120,180,255)
YELLOW = (255,255,100)
GRAY = (180,180,180)
DARK = (40,40,40)

# ---------------- TOGGLES ----------------
show_E = True
show_B = True
paused = False
show_probe = False
use_boris = False

# ---------------- INITIALS ---------------
particles = []
objects = []
drag_start = None
ani_time = 0
spawn_sign = 1

# ---------------- PARTICLE ----------------
class Particle:
    def __init__(self, x, y, q, color, collidable=False):
        self.x, self.y = x, y
        self.vx, self.vy = 0, 0
        self.q = q
        self.color = color
        self.dragging = False
        self.collidable = collidable
        self.col_radius = 6

    def update(self):
        if paused:
            return

        if use_boris:
            self.update_boris()
        else:
            self.update_euler()

    # ---------------- EULER ----------------
    def update_euler(self):
        Ex, Ey = compute_E(self.x, self.y)
        Bz = compute_Bz(self.x, self.y)

        dt = 0.07

        fx = self.q * (Ex + self.vy * Bz)
        fy = self.q * (Ey - self.vx * Bz)

        self.vx += fx * dt
        self.vy += fy * dt

        self.x += self.vx * dt
        self.y += self.vy * dt

    # ---------------- BORIS ----------------
    def update_boris(self):
        dt = 0.07
        q = self.q

        Ex, Ey = compute_E(self.x, self.y)
        Bz = compute_Bz(self.x, self.y)

        # half E kick
        vx_minus = self.vx + q * Ex * dt * 0.5
        vy_minus = self.vy + q * Ey * dt * 0.5

        # rotation
        t = q * Bz * dt * 0.5
        s = 2 * t / (1 + t*t)

        vx_prime = vx_minus + vy_minus * t
        vy_prime = vy_minus - vx_minus * t

        vx_plus = vx_minus + vy_prime * s
        vy_plus = vy_minus - vx_prime * s

        # second half E kick
        self.vx = vx_plus + q * Ex * dt * 0.5
        self.vy = vy_plus + q * Ey * dt * 0.5

        # position update
        self.x += self.vx * dt
        self.y += self.vy * dt

    def draw(self):
        pygame.draw.circle(screen, self.color, (int(self.x), int(self.y)), 6)



# ---------------- ELECTRIC FIELD ----------------
def compute_E(x, y):
    Ex, Ey = 0, 0

    # ---- PARTICLES ----
    for p in particles:
        dx = x - p.x
        dy = y - p.y
        r2 = dx*dx + dy*dy
        r2 = max(r2, 25)
        r = math.sqrt(r2)

        E = k * p.q / r2
        Ex += E * dx / r
        Ey += E * dy / r

    # ---- CHARGE RING ----
    for obj in objects:
        if obj.get("type") == "charge_ring":

            segments = 12
            Q = obj["Q"]
            if obj.get("time_varying"):
               Q *= math.sin(ani_time * obj["omega"])

            R = obj["R"]
            cx, cy = obj["x"], obj["y"]

            dq = Q / segments

            for i in range(segments):
                theta = 2 * math.pi * i / segments

                px = cx + R * math.cos(theta)
                py = cy + R * math.sin(theta)

                dx = x - px
                dy = y - py

                r2 = dx*dx + dy*dy
                if r2 < 25:
                    continue

                r = math.sqrt(r2)

                E = k * dq / r2
                Ex += E * dx / r
                Ey += E * dy / r

    return Ex, Ey

# ---------------- MAGNETIC FIELD ----------------
def compute_B_vec(x, y):
    Bx, By = 0, 0

    for obj in objects:

        

        # WIRE
        if obj["type"] == "wire":
            dx = x - obj["x"]
            dy = y - obj["y"]
            r2 = dx*dx + dy*dy + 1
            r = math.sqrt(r2)
            I = obj["I"]
            if obj.get("time_varying"):
                I *= math.sin(ani_time * obj["omega"])
            B = I / r

        # DIPOLE
        elif obj["type"] == "dipole":
            dx = x - obj["x"]
            dy = y - obj["y"]
            r2 = dx*dx + dy*dy + 1
            r = math.sqrt(r2)

            rx, ry = dx/r, dy/r

            strength = obj["strength"]
            if obj.get("time_varying"):
                strength *= math.sin(ani_time * obj["omega_osci"])
            angle = obj["angle"]
            mx = strength* math.cos(angle)
            my = strength * math.sin(angle)

            dot = mx*rx + my*ry
            factor = 1/(r2*r)

            Bx += factor * (3*dot*rx - mx)
            By += factor * (3*dot*ry - my)

        # CURRENT RING
        elif obj["type"] == "current_ring":
        
            cx, cy = obj["x"], obj["y"]
            R = obj["R"]

            I = obj["I"]
            if obj.get("time_varying"):
                I *= math.sin(ani_time * obj["omega"])

            dist = math.hypot(x - cx, y - cy)

            if dist < 100:
                segments = 18
            elif dist < 300:
                segments = 8
            else:
                segments = 4

            for i in range(segments):
                theta = 2 * math.pi * i / segments

                # point on ring
                px = cx + R * math.cos(theta)
                py = cy + R * math.sin(theta)

                # dl (tangent vector)
                dlx = -math.sin(theta)
                dly =  math.cos(theta)

                dx = x - px
                dy = y - py

                r2 = dx*dx + dy*dy
                if r2 < 25:
                    continue
                
                r = math.sqrt(r2)

                # 2D projection of Biot–Savart
                factor = I / (r2 * r)

                # cross product dl × r → gives perpendicular direction
                Bx += factor * (dly * 0 - 0 * dy)   # simplifies
                By += factor * (0 * dx - dlx * 0)   # simplifies

                # 🔴 Actually in 2D, ring contributes mostly to Bz
                # so we project it into circular flow manually:

                perp_x = -dy / r
                perp_y =  dx / r

                Bx += perp_x * factor
                By += perp_y * factor
    return Bx, By

def compute_Bz(x, y):
    Bz = 0

    for obj in objects:


        if obj["type"] == "wire":
            dx = x - obj["x"]
            I = obj["I"]
            if obj.get("time_varying"):
                I *= math.sin(ani_time * obj["omega"])
            r = max(abs(dx),5)   # distance from wire axis

            # sign gives right-hand rule
            if dx > 0: sign = -1
            else: sign = +1

            Bz += sign * I / r

        elif obj["type"] == "dipole":
            dx = x - obj["x"]
            dy = y - obj["y"]
            r2 = dx*dx + dy*dy + 1

            angle = obj.get("angle", 0)

            mx = math.cos(angle)
            my = math.sin(angle)

            dot = dx*mx + dy*my

            # pseudo Bz projection
            strength = obj["strength"]
            if obj.get("time_varying"):
                strength *= math.sin(ani_time * obj["omega_osci"])
            Bz += strength * dot / (r2 * math.sqrt(r2))


        elif obj["type"] == "current_ring":
            dx = x - obj["x"]
            dy = y - obj["y"]

            I = obj["I"]
            if obj.get("time_varying"):
                I *= math.sin(ani_time * obj["omega"])

            r2 = dx*dx + dy*dy + 1
            r = math.sqrt(r2)

            # inside vs outside ring
            if dx*dx + dy*dy < obj["R"]**2:
                sign = 1   # out of screen
            else:
                sign = -1  # into screen

            Bz += sign * I * obj["R"]**2 / (r2 * r)

        elif obj["type"] == "uniform_B":
            half = obj["size"] // 2
        
            if (obj["x"] - half <= x <= obj["x"] + half and
                obj["y"] - half <= y <= obj["y"] + half):
        
                Bz += obj["Bz"]
                if obj.get("time_varying"):
                    Bz *= math.sin(ani_time * obj["omega"])

    return Bz

# ---------------- FORCES ON OBJECTS ----------------
def force_on_dipole(obj):
    x, y = obj["x"], obj["y"]
    eps = 3

    Bx1, By1 = compute_B_vec(x+eps, y)
    Bx2, By2 = compute_B_vec(x-eps, y)
    Bx3, By3 = compute_B_vec(x, y+eps)
    Bx4, By4 = compute_B_vec(x, y-eps)

    dBx_dx = (Bx1 - Bx2)/(2*eps)
    dBy_dy = (By3 - By4)/(2*eps)

    angle = obj["angle"]
    strength = obj["strength"]
    if obj.get("time_varying"):
        strength *= math.sin(ani_time * obj["omega_osci"])
    mx = strength * math.cos(angle)
    my = strength * math.sin(angle)

    Fx = mx * dBx_dx
    Fy = my * dBy_dy

    return Fx, Fy

def torque_on_dipole(obj):
    Bx, By = compute_B_vec(obj["x"], obj["y"])

    angle = obj["angle"]
    mx = obj["strength"] * math.cos(angle)
    my = obj["strength"] * math.sin(angle)

    # τ = m × B (z-component)
    return mx * By - my * Bx

def force_on_wire(obj):
    Bx, By = compute_B_vec(obj["x"], obj["y"])
    I = obj["I"]
    if obj.get("time_varying"):
        I *= math.sin(ani_time * obj["omega"])

    # vertical wire (0,1)
    Fx = I * Bx
    Fy = -I * 0

    return Fx, Fy

def handle_collisions():

    # =========================================================
    # PARTICLE ↔ PARTICLE
    # =========================================================
    for i in range(len(particles)):
        for j in range(i + 1, len(particles)):

            a = particles[i]
            b = particles[j]

            if not (a.collidable and b.collidable):
                continue

            dx = b.x - a.x
            dy = b.y - a.y

            dist = math.hypot(dx, dy)

            min_dist = a.col_radius + b.col_radius

            if dist < min_dist and dist > 0:

                nx = dx / dist
                ny = dy / dist

                overlap = min_dist - dist

                # separate
                a.x -= nx * overlap * 0.5
                a.y -= ny * overlap * 0.5

                b.x += nx * overlap * 0.5
                b.y += ny * overlap * 0.5

                # elastic bounce
                a.vx, b.vx = b.vx, a.vx
                a.vy, b.vy = b.vy, a.vy


    # =========================================================
    # PARTICLE ↔ OBJECT
    # =========================================================
    for p in particles:

        if not p.collidable:
            continue

        for obj in objects:

            if not obj.get("collidable"):
                continue


            # -------------------------------------------------
            # CIRCLE COLLIDER
            # (rings, magnets)
            # -------------------------------------------------
            if obj.get("collider") == "circle":

                ox = obj["x"]
                oy = obj["y"]

                r = obj.get("col_radius", 20)

                dx = p.x - ox
                dy = p.y - oy

                dist = math.hypot(dx, dy)

                hollow = obj.get("hollow", False)

                # =====================================================
                # SOLID CIRCLE
                # =====================================================
                if not hollow:
                
                    min_dist = p.col_radius + r

                    if dist < min_dist and dist > 0:
                    
                        nx = dx / dist
                        ny = dy / dist

                        overlap = min_dist - dist

                        p.x += nx * overlap
                        p.y += ny * overlap

                        dot = p.vx * nx + p.vy * ny

                        p.vx -= 2 * dot * nx
                        p.vy -= 2 * dot * ny


                # =====================================================
                # HOLLOW CIRCLE CONTAINER
                # =====================================================
                else:
                
                    wall_radius = r - p.col_radius

                    # only interact if particle is INSIDE container
                    if dist < r:
                    
                        # touching wall from inside
                        if dist > wall_radius and dist > 0:
                        
                            nx = dx / dist
                            ny = dy / dist

                            overlap = dist - wall_radius

                            # push back inward
                            p.x -= nx * overlap
                            p.y -= ny * overlap

                            dot = p.vx * nx + p.vy * ny

                            p.vx -= 2 * dot * nx
                            p.vy -= 2 * dot * ny

            # -------------------------------------------------
            # RECT COLLIDER
            # (uniform B region / wire)
            # -------------------------------------------------
            elif obj.get("collider") == "rect":

                half_w = obj.get("w", 40) / 2
                half_h = obj.get("h", 40) / 2

                left   = obj["x"] - half_w
                right  = obj["x"] + half_w
                top    = obj["y"] - half_h
                bottom = obj["y"] + half_h

                hollow = obj.get("hollow", False)

                # =====================================================
                # SOLID RECT
                # =====================================================
                if not hollow:
                
                    nearest_x = max(left, min(p.x, right))
                    nearest_y = max(top, min(p.y, bottom))

                    dx = p.x - nearest_x
                    dy = p.y - nearest_y

                    dist2 = dx*dx + dy*dy

                    if dist2 < p.col_radius * p.col_radius:
                    
                        dist = math.sqrt(dist2) + 1e-6

                        nx = dx / dist
                        ny = dy / dist

                        overlap = p.col_radius - dist

                        p.x += nx * overlap
                        p.y += ny * overlap

                        dot = p.vx * nx + p.vy * ny

                        p.vx -= 2 * dot * nx
                        p.vy -= 2 * dot * ny


                # =====================================================
                # HOLLOW RECT CONTAINER
                # =====================================================
                else:
                
                    # only interact if particle is INSIDE box
                    inside = (
                        left < p.x < right and
                        top < p.y < bottom
                    )
                
                    if inside:
                    
                        # distances to walls
                        dl = p.x - left
                        dr = right - p.x
                        dt = p.y - top 
                        db = bottom - p.y 
                
                        # collide only when touching walls
                        touching_left   = dl < p.col_radius
                        touching_right  = dr < p.col_radius
                        touching_top    = dt < p.col_radius
                        touching_bottom = db < p.col_radius
                
                        # LEFT WALL
                        if touching_left:
                        
                            p.x = left + p.col_radius
                            p.vx = abs(p.vx)
                
                        # RIGHT WALL
                        elif touching_right:
                        
                            p.x = right - p.col_radius
                            p.vx = -abs(p.vx)
                
                        # TOP WALL
                        elif touching_top:
                        
                            p.y = top + p.col_radius
                            p.vy = abs(p.vy)
                
                        # BOTTOM WALL
                        elif touching_bottom:
                        
                            p.y = bottom - p.col_radius
                            p.vy = -abs(p.vy)



    # =========================================================
    # OBJECT ↔ OBJECT
    # =========================================================
    
    for i in range(len(objects)):
        for j in range(i + 1, len(objects)):

            a = objects[i]
            b = objects[j]

            if not (a.get("collidable") and b.get("collidable")):
                continue


            # =====================================================
            # CIRCLE ↔ CIRCLE
            # =====================================================
            if (
                a.get("collider") == "circle" and
                b.get("collider") == "circle"
            ):

                ax, ay = a["x"], a["y"]
                bx, by = b["x"], b["y"]

                ar = a.get("col_radius", 20)
                br = b.get("col_radius", 20)

                dx = bx - ax
                dy = by - ay

                dist = math.hypot(dx, dy)

                min_dist = ar + br

                if dist < min_dist and dist > 0:

                    nx = dx / dist
                    ny = dy / dist

                    overlap = min_dist - dist

                    # separate
                    a["x"] -= nx * overlap * 0.5
                    a["y"] -= ny * overlap * 0.5

                    b["x"] += nx * overlap * 0.5
                    b["y"] += ny * overlap * 0.5

                    # elastic bounce
                    rvx = b["vx"] - a["vx"]
                    rvy = b["vy"] - a["vy"]

                    vn = rvx * nx + rvy * ny

                    if vn < 0:

                        impulse = vn

                        a["vx"] += impulse * nx
                        a["vy"] += impulse * ny

                        b["vx"] -= impulse * nx
                        b["vy"] -= impulse * ny



            # =====================================================
            # RECT ↔ RECT
            # =====================================================
            elif (
                a.get("collider") == "rect" and
                b.get("collider") == "rect"
            ):

                aw = a.get("w", 40)
                ah = a.get("h", 40)

                bw = b.get("w", 40)
                bh = b.get("h", 40)

                ax1 = a["x"] - aw / 2
                ax2 = a["x"] + aw / 2
                ay1 = a["y"] - ah / 2
                ay2 = a["y"] + ah / 2

                bx1 = b["x"] - bw / 2
                bx2 = b["x"] + bw / 2
                by1 = b["y"] - bh / 2
                by2 = b["y"] + bh / 2

                overlap_x = min(ax2, bx2) - max(ax1, bx1)
                overlap_y = min(ay2, by2) - max(ay1, by1)

                if overlap_x > 0 and overlap_y > 0:

                    # =============================================
                    # resolve along smallest overlap axis
                    # =============================================
                    if overlap_x < overlap_y:

                        sep = overlap_x / 2

                        if a["x"] < b["x"]:
                            a["x"] -= sep
                            b["x"] += sep
                            nx, ny = 1, 0
                        else:
                            a["x"] += sep
                            b["x"] -= sep
                            nx, ny = -1, 0

                    else:

                        sep = overlap_y / 2

                        if a["y"] < b["y"]:
                            a["y"] -= sep
                            b["y"] += sep
                            nx, ny = 0, 1
                        else:
                            a["y"] += sep
                            b["y"] -= sep
                            nx, ny = 0, -1


                    # =============================================
                    # bounce
                    # =============================================
                    rvx = b["vx"] - a["vx"]
                    rvy = b["vy"] - a["vy"]

                    vn = rvx * nx + rvy * ny

                    if vn < 0:

                        impulse = vn

                        a["vx"] += impulse * nx
                        a["vy"] += impulse * ny

                        b["vx"] -= impulse * nx
                        b["vy"] -= impulse * ny



            # =====================================================
            # CIRCLE ↔ RECT
            # =====================================================
            elif (
                {"circle", "rect"} ==
                {a.get("collider"), b.get("collider")}
            ):

                if a.get("collider") == "circle":
                    circle = a
                    rect = b
                else:
                    circle = b
                    rect = a

                half_w = rect.get("w", 40) / 2
                half_h = rect.get("h", 40) / 2

                left   = rect["x"] - half_w
                right  = rect["x"] + half_w
                top    = rect["y"] - half_h
                bottom = rect["y"] + half_h

                nearest_x = max(left, min(circle["x"], right))
                nearest_y = max(top, min(circle["y"], bottom))

                dx = circle["x"] - nearest_x
                dy = circle["y"] - nearest_y

                dist2 = dx*dx + dy*dy

                r = circle.get("col_radius", 20)

                if dist2 < r*r:

                    dist = math.sqrt(dist2) + 1e-6

                    nx = dx / dist
                    ny = dy / dist

                    overlap = r - dist

                    # separate
                    circle["x"] += nx * overlap
                    circle["y"] += ny * overlap

                    # bounce
                    dot = circle["vx"] * nx + circle["vy"] * ny

                    circle["vx"] -= 2 * dot * nx
                    circle["vy"] -= 2 * dot * ny

# ---------------- UPDATE OBJECTS ----------------
def update_objects():
    for obj in objects:

        if paused or obj.get("dragging"):
            continue

        if obj["type"] == "dipole":
            Fx, Fy = force_on_dipole(obj)
            tau = torque_on_dipole(obj)

            obj["vx"] += Fx * 0.001
            obj["vy"] += Fy * 0.001
            obj["omega"] += tau * 0.0005

        elif obj["type"] == "wire":
            Fx, Fy = force_on_wire(obj)

            obj["vx"] += Fx * 0.001
            obj["vy"] += Fy * 0.001

        obj["x"] += obj["vx"]
        obj["y"] += obj["vy"]

        if obj["type"] == "dipole":
            obj["angle"] += obj["omega"]

        # damping
        obj["vx"] *= 0.99
        obj["vy"] *= 0.99
        if obj["type"] == "dipole":
            obj["omega"] *= 0.99

            
# ---------------- ELECTRIC FIELD LINES ----------------
def trace_E(x, y, direction=1):
    pts = []

    for _ in range(80):
        Ex, Ey = compute_E(x, y)

        mag = math.sqrt(Ex*Ex + Ey*Ey)
        if mag == 0:
            break

        Ex /= mag
        Ey /= mag

        x += direction * Ex * 8
        y += direction * Ey * 8

        pts.append((x, y))

    return pts

def draw_E_lines():
    #-------- PARTICLES --------
    for p in particles:
        for a in range(0,360,15):
            for direction in [1, -1]:
                x = p.x + math.cos(math.radians(a))*4
                y = p.y + math.sin(math.radians(a))*4

                pts = []
                for _ in range(50):
                    Ex, Ey = compute_E(x, y)

                    mag = math.sqrt(Ex*Ex + Ey*Ey)
                    if mag == 0: break

                    Ex /= mag
                    Ey /= mag

                    x += direction * Ex * 10
                    y += direction * Ey * 10

                    pts.append((x,y))

                if len(pts) > 1:
                    pygame.draw.lines(screen, GREEN, False, pts, 1)

    #-------- CHARGED RING --------
    for obj in objects:
        if obj.get("type") == "charge_ring":

            cx, cy = obj["x"], obj["y"]
            R = obj["R"]

            Q = obj["Q"]
            if obj.get("time_varying"):
                Q *= math.sin(ani_time * obj["omega"])

            seeds = 18
            direction = 1 if Q > 0 else -1

            for i in range(seeds):
                theta = 2 * math.pi * i / seeds

                x = cx + (R + 6) * math.cos(theta)
                y = cy + (R + 6) * math.sin(theta)

                pts = []

                for _ in range(40):

                    Ex, Ey = compute_E(x, y)

                    mag = math.sqrt(Ex*Ex + Ey*Ey)
                    if mag == 0:
                        break

                    Ex /= mag
                    Ey /= mag

                    x += direction * Ex * 8
                    y += direction * Ey * 8

                    pts.append((x, y))

                if len(pts) > 1:
                    pygame.draw.lines(screen, GREEN, False, pts, 1)



# ---------------- MAGNETIC FIELD LINES ----------------
def trace_B(x, y):
    pts_forward = []
    pts_backward = []

    # -------- FORWARD (+B) --------
    fx, fy = x, y
    for _ in range(150):
        Bx, By = compute_B_vec(fx, fy)

        mag = math.sqrt(Bx*Bx + By*By)
        if mag < 1e-5:
            break

        Bx /= mag
        By /= mag

        step = 4
        fx += Bx * step
        fy += By * step

        pts_forward.append((fx, fy))

        if fx < 0 or fx > WIDTH or fy < 0 or fy > HEIGHT:
            break

    # -------- BACKWARD (−B) --------
    bx, by = x, y
    for _ in range(150):
        Bx, By = compute_B_vec(bx, by)

        mag = math.sqrt(Bx*Bx + By*By)
        if mag < 1e-5:
            break

        Bx /= mag
        By /= mag

        step = 4
        bx -= Bx * step   # 🔴 reverse direction
        by -= By * step

        pts_backward.append((bx, by))

        if bx < 0 or bx > WIDTH or by < 0 or by > HEIGHT:
            break

    # combine (backward reversed + forward)
    pts_backward.reverse()
    return pts_backward + [(x, y)] + pts_forward

def draw_B_lines():
    for obj in objects:

        # -------- BAR MAGNET --------
        if obj["type"] == "dipole":
            angle = obj.get("angle", 0)

            # pole positions
            px = obj["x"] + 10 * math.cos(angle)
            py = obj["y"] + 10 * math.sin(angle)

            # ONLY seed from NORTH pole
            for a in range(-80, 81, 16):
                theta = angle + math.radians(a)

                sx = px + math.cos(theta) * 40
                sy = py + math.sin(theta) * 40

                pts = trace_B(sx, sy)
                if len(pts) > 1:
                    pygame.draw.lines(screen, CYAN, False, pts, 1)

        # -------- WIRE --------
        elif obj["type"] == "wire":

            cx = obj["x"]

            GRID = 50

            for gx in range(0, WIDTH, GRID):
                for gy in range(0, HEIGHT, GRID):
                
                    dx = gx - cx

                    # avoid singularity at wire
                    if abs(dx) < 5:
                        continue
                    
                    # 🔥 Bz from infinite wire
                    # right-hand rule: sign depends on side
                    sign = -1 if dx > 0 else 1

                    Bz = compute_Bz(gx, gy)

                    if abs(Bz) < 0.001:
                        continue
                    
                    # 🔥 distance-based fading
                    dist = abs(dx)
                    strength = abs(Bz) / (1 + dist * 0.2)

                    thickness = min(4, int(strength * 300))

                    if Bz < 0:
                        # ⨀ out of screen
                        #pygame.draw.circle(screen, CYAN, (gx, gy), 2 + thickness, 1)
                        pygame.draw.circle(screen, CYAN, (gx, gy), thickness)
                    else:
                        # ⨂ into screen
                        #pygame.draw.circle(screen, CYAN, (gx, gy), 3 + thickness, 1)
                        pygame.draw.line(screen, CYAN,
                                         (gx-3, gy-3), (gx+3, gy+3), thickness)
                        pygame.draw.line(screen, CYAN,
                                         (gx+3, gy-3), (gx-3, gy+3), thickness)

        elif obj["type"] == "current_ring":
            draw_ring_Bz()

                

# ---------------- DRAW OBJECTS ----------------
def draw_objects():
    for obj in objects:


        if obj["type"] == "wire":

            I = obj["I"]
            if obj.get("time_varying"):
                I *= math.sin(ani_time * obj["omega"])

            # ---- wire ----
            pygame.draw.line(
                screen, YELLOW,
                (obj["x"], 0), (obj["x"], HEIGHT),
                4
            )

            # ---- current direction arrow ----
            cx = obj["x"] + 1
            cy = HEIGHT // 2
            arrow_len = 0
            
            # current upward
            if I > 0:
                start = (cx, cy + arrow_len)
                end   = (cx, cy - arrow_len)
                pygame.draw.line(screen, WHITE, start, end, 3)
                pygame.draw.polygon(screen, WHITE, [
                    (cx, cy - arrow_len - 10),
                    (cx - 7, cy - arrow_len + 5),
                    (cx + 7, cy - arrow_len + 5)
                ])

            # current downward
            else:
                start = (cx, cy - arrow_len)
                end   = (cx, cy + arrow_len)
                pygame.draw.line(screen, WHITE, start, end, 3)
                pygame.draw.polygon(screen, WHITE, [
                    (cx, cy + arrow_len + 10),
                    (cx - 7, cy + arrow_len - 5),
                    (cx + 7, cy + arrow_len - 5)
                ])


        elif obj["type"] == "dipole":
            angle = obj["angle"]

            x1 = obj["x"] + 15*math.cos(angle)
            y1 = obj["y"] + 15*math.sin(angle)

            x2 = obj["x"] - 15*math.cos(angle)
            y2 = obj["y"] - 15*math.sin(angle)

            pygame.draw.circle(screen, RED, (int(x1),int(y1)),6)
            pygame.draw.circle(screen, BLUE, (int(x2),int(y2)),6)


        elif obj["type"] == "current_ring":
            I = obj["I"]
            if obj.get("time_varying"):
                I *= math.sin(ani_time * obj["omega"])
        
            cx, cy = obj["x"], obj["y"]
            R = obj["R"]

            pygame.draw.circle(screen, YELLOW, (int(cx), int(cy)), R, 2)

            direction = 1 if I > 0 else -1

            # ---- MULTIPLE MOVING ARROWS ----
            num_arrows = 1

            for i in range(num_arrows):
            
                theta = ani_time * direction + (2 * math.pi * i / num_arrows)

                # point on ring
                px = cx + R * math.cos(theta)
                py = cy + R * math.sin(theta)

                # tangent direction
                tx = -math.sin(theta) * direction
                ty =  math.cos(theta) * direction

                # normalize
                mag = math.sqrt(tx*tx + ty*ty)
                tx /= mag
                ty /= mag

                L = 0

                endx = px + tx * L
                endy = py + ty * L

                # arrow line
                pygame.draw.line(screen, WHITE, (px, py), (endx, endy), 2)

                # arrow head
                angle = math.atan2(ty, tx)

                left = (
                    endx - 10 * math.cos(angle - 0.5),
                    endy - 10 * math.sin(angle - 0.5)
                )
                right = (
                    endx - 10 * math.cos(angle + 0.5),
                    endy - 10 * math.sin(angle + 0.5)
                )

                pygame.draw.polygon(screen, WHITE, [(endx, endy), left, right])


        elif obj["type"] == "charge_ring":
            Q = obj["Q"]
            if obj.get("time_varying"):
                Q *= math.sin(ani_time * obj["omega"])

            if Q > 0: pygame.draw.circle(screen, RED, (int(obj["x"]), int(obj["y"])), obj["R"], 2)
            else : pygame.draw.circle(screen, BLUE, (int(obj["x"]), int(obj["y"])), obj["R"], 2)


        elif obj["type"] == "uniform_B":
            half = obj["size"] // 2

            rect = pygame.Rect(
                obj["x"] - half,
                obj["y"] - half,
                obj["size"],
                obj["size"]
            )

            # semi-transparent fill (optional)
            s = pygame.Surface((obj["size"], obj["size"]), pygame.SRCALPHA)
            s.fill((100, 100, 255, 60))
            screen.blit(s, (obj["x"] - half, obj["y"] - half))

            # border
            pygame.draw.rect(screen, GRAY, rect, 2)

def draw_ring_Bz():
    for obj in objects:
        if obj["type"] != "current_ring":
            continue

        cx, cy = obj["x"], obj["y"]

        # 🔥 Circular grid instead of square
        for r in range(0, 700, 30):
            for a in range(0, 360, 20):

                gx = cx + r * math.cos(math.radians(a))
                gy = cy + r * math.sin(math.radians(a))

                Bz = compute_Bz(gx, gy)

                if abs(Bz) < 0.001:
                    continue

                # 🔥 Fade with distance
                dist = r
                strength = abs(Bz) / (1 + dist * 0.01)

                thickness = min(5, int(strength * 300))

                ch = min(3, int(strength * 200))
                if Bz < 0:
                    # ⨀ (out of screen)
                    pygame.draw.circle(screen, CYAN, (int(gx), int(gy)), 1+ thickness, 1)
                    pygame.draw.circle(screen, CYAN, (int(gx), int(gy)), int(thickness/3))
                else:
                    # ⨂ (into screen)
                    #pygame.draw.circle(screen, CYAN, (int(gx), int(gy)), 3 + thickness, 1)
                    pygame.draw.line(screen, CYAN,
                                     (int(gx-ch), int(gy-ch)),
                                     (int(gx+ch), int(gy+ch)), 2+ int(thickness/2))
                    pygame.draw.line(screen, CYAN,
                                     (int(gx+ch), int(gy-ch)),
                                     (int(gx-ch), int(gy+ch)), 2+ int(thickness/2))

#----------------- PROBE ------------
def draw_probe(mouse):
    x, y = mouse

    Ex, Ey = compute_E(x, y)
    Bx, By = compute_B_vec(x, y)
    Bz = compute_Bz(x, y)

    # magnitude
    Emag = math.sqrt(Ex*Ex + Ey*Ey)
    Bmag = math.sqrt(Bx*Bx + By*By + Bz*Bz)

    font = pygame.font.SysFont(None, 22)

    lines = [
        f"E: ({Ex:.2f}, {Ey:.2f}) |E|={Emag:.2f}",
        f"B: ({Bx:.2f}, {By:.2f}, {Bz:.2f}) |B|={Bmag:.2f}"
    ]

    # position (bottom-left of play area)
    px = 10
    py = HEIGHT - 50

    for i, text in enumerate(lines):
        surf = font.render(text, True, GRAY)
        screen.blit(surf, (px, py + i*20))

    # 🔥 small visual indicator at mouse
    pygame.draw.circle(screen, YELLOW, (int(x), int(y)), 4, 1)

# ---------------- UI ----------------
class Button:
    def __init__(self,x,y,w,h,text):
        self.rect = pygame.Rect(x,y,w,h)
        self.text = text

    def draw(self):
        pygame.draw.rect(screen, DARK, self.rect)
        f = pygame.font.SysFont(None,22)
        screen.blit(f.render(self.text,True,WHITE),(self.rect.x+5,self.rect.y+5))

    def hit(self,pos):
        return self.rect.collidepoint(pos)

class MenuItem:
    def __init__(self,name,y):
        self.name = name
        self.rect = pygame.Rect(WIDTH-MENU_WIDTH+20,y,180,30)

    def draw(self, selected):
        color = (220,220,220) if selected else GRAY
        pygame.draw.rect(screen,color,self.rect)

        f = pygame.font.SysFont(None,30)
        display_name = self.name
        if time_varying:
            if self.name == "Wire": display_name = "AC Wire"
            elif self.name == "Magnet": display_name = "Osc Magnet"
            elif self.name == "Current Ring": display_name = "AC Ring"
            elif self.name == "Charged Ring": display_name = "Osc Charge Ring"
            elif self.name == "Uniform B": display_name = "Oscillating B"

        screen.blit(f.render(display_name, True, BLACK),(self.rect.x+5, self.rect.y+5)) 

        title = f.render("Toolbox", True, WHITE)
        screen.blit(title, (WIDTH - MENU_WIDTH + 80, 20))

        fi = pygame.font.SysFont(None,20,False,True)
        add_inv = fi.render("inverse" if spawn_sign < 0 else "", True , GRAY)
        screen.blit(add_inv,(WIDTH - MENU_WIDTH - 50, 4))
        osci = fi.render("oscillating" if time_varying else "", True , GRAY)
        screen.blit(osci,(WIDTH - MENU_WIDTH - 73, 16))
        col = fi.render("collidable" if collision_mode else "", True , GRAY)
        screen.blit(col,(WIDTH - MENU_WIDTH - 68, 30))


class ToggleSwitch:
    def __init__(self, x, y, w=80, h=30):
        self.rect = pygame.Rect(x, y, w, h)

    def draw(self, state):
        # background
        color = (120, 120, 120) if state else (120, 120, 120)
        pygame.draw.rect(screen, color, self.rect, border_radius=15)

        # knob
        radius = self.rect.height // 2 - 4

        if state:
            cx = self.rect.right - radius - 6
        else:
            cx = self.rect.left + radius + 6

        cy = self.rect.centery

        pygame.draw.circle(screen, WHITE, (cx, cy), radius)

        # labels
        font = pygame.font.SysFont(None, 22)
        screen.blit(font.render("  Euler", True, WHITE),
                    (self.rect.x - 55, self.rect.y + 5))
        screen.blit(font.render(" Boris", True, WHITE),
                    (self.rect.right + 5, self.rect.y + 5))

    def hit(self, pos):
        return self.rect.collidepoint(pos)

# ---------------- INIT ----------------
buttons = [
    Button(10,10,120,30,"Show EFL (e)"),
    Button(10,50,120,30,"Show MFL (b)"),
    Button(10,90,120,30,"Probe (o)"),
    Button(10,130,120,30,"Pause (p)"),
    Button(10,170,120,30,"Clear (c)"),
    
]

menu = [
    MenuItem("Electron",100),
    MenuItem("Positron",150),
    MenuItem("Wire",200),
    MenuItem("Magnet",250),
    MenuItem("Current Ring", 300),
    MenuItem("Charged Ring", 350),
    MenuItem("Uniform B", 400)
]

toggle_switch = ToggleSwitch(WIDTH - MENU_WIDTH + 60, HEIGHT - 60)

selected = None
dragging_particle = None
dragging_object = None

# ---------------- MAIN LOOP ----------------
running = True
while running:
    clock.tick(FPS)
    screen.fill(BLACK)
    mouse = pygame.mouse.get_pos()

    if drag_start and (dragging_particle or dragging_object):
        pygame.draw.line(screen, WHITE, mouse, drag_start, 2)
   
    keys = pygame.key.get_pressed()


    # -----------Modifiers--------
    if keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]: spawn_sign = -1
    else: spawn_sign = 1

    time_varying = (keys[pygame.K_LALT] or keys[pygame.K_RALT])  

    collision_mode = (keys[pygame.K_LCTRL] or keys[pygame.K_RCTRL]) 

    for e in pygame.event.get():
        if e.type == pygame.QUIT:
            running = False

        if e.type == pygame.KEYDOWN:
            if e.key == pygame.K_e: show_E = not show_E
            elif e.key == pygame.K_b: show_B = not show_B
            elif e.key == pygame.K_p: paused = not paused
            elif e.key == pygame.K_c: particles.clear() , objects.clear()
            elif e.key == pygame.K_o: show_probe = not show_probe

            # test uniform velocity
            elif e.key == pygame.K_t:
                if particles:
                    p = particles[-1]
                    p.vx = 0
                    p.vy = 300

        if e.type == pygame.MOUSEBUTTONDOWN:
            if buttons[0].hit(mouse): show_E = not show_E
            elif buttons[1].hit(mouse): show_B = not show_B
            elif buttons[2].hit(mouse): show_probe = not show_probe
            elif buttons[3].hit(mouse): paused = not paused
            elif buttons[4].hit(mouse): particles.clear() , objects.clear()  

            if toggle_switch.hit(mouse):
                use_boris = not use_boris

            for m in menu:
                if m.rect.collidepoint(mouse):
                    selected = m.name

            #---- PLACE NEW--------
            if mouse[0] < WIDTH-MENU_WIDTH:

                if selected == "Electron":
                    particles.append(Particle(mouse[0],mouse[1], -1, BLUE, collidable = collision_mode))

                elif selected == "Positron":
                    particles.append(Particle(mouse[0],mouse[1], 1, RED, collidable = collision_mode))

                elif selected == "Wire":
                    objects.append({
                        "type":"wire",
                        "x":mouse[0],
                        "y":mouse[1],
                        "I": 100 * spawn_sign,
                        "omega":2.0,
                        "time_varying":time_varying,
                        "collider": "rect",
                        "hollow": False,
                        "w": 5,
                        "h": HEIGHT,
                        "collidable": collision_mode,
                        "vx":0,
                        "vy":0
                    }) 
                elif selected == "Magnet":
                    objects.append({
                        "type":"dipole",
                        "x":mouse[0],
                        "y":mouse[1],
                        "strength":1000 * spawn_sign,
                        "omega_osci":2.0,
                        "time_varying":time_varying,
                        "collider": "circle",
                        "hollow": False,
                        "col_radius": 18,
                        "collidable": collision_mode,
                        "vx":0,
                        "vy":0,
                        "angle":0,
                        "omega":0,
                        "dragging":0
                    })     
                elif selected == "Current Ring":
                    objects.append({
                        "type": "current_ring",
                        "x": mouse[0],
                        "y": mouse[1],
                        "R": 40,
                        "I": 500 * spawn_sign,
                        "omega":2.0,
                        "time_varying":time_varying,
                        "collider": "circle",
                        "col_radius": 40,
                        "collidable": collision_mode,
                        "hollow": True,
                        "wall_thickness": 10,
                        "vx": 0,
                        "vy":0
                    })
                elif selected == "Charged Ring":
                    objects.append({
                        "type": "charge_ring",
                        "x": mouse[0],
                        "y": mouse[1],
                        "R": 40,
                        "Q": 100 * spawn_sign,
                        "omega":2.0,
                        "time_varying":time_varying,
                        "collider": "circle",
                        "col_radius": 40,
                        "collidable": collision_mode,
                        "hollow": True,
                        "wall_thickness": 10,
                        "vx": 0,
                        "vy": 0
                    })
                elif selected == "Uniform B":
                    size = 300
                    objects.append({
                        "type": "uniform_B",
                        "x": mouse[0],
                        "y": mouse[1],
                        "size": size,
                        "Bz": 5 * spawn_sign, 
                        "omega":2.0,
                        "time_varying":time_varying,
                        "collider": "rect",
                        "collidable": collision_mode, 
                        "hollow": True,
                        "w": size,
                        "h": size,
                        "wall_thickness": 8,
                        "vx": 0,
                        "vy": 0
                    })
            
            # select particle
            for p in particles:
                if (p.x-mouse[0])**2 + (p.y-mouse[1])**2 < 100:
                    dragging_particle = p
                    p.dragging = True
                    #drag_start = mouse
                    break
            # select object
            if dragging_particle is None:
                for obj in objects:
                    dx=obj["x"]-mouse[0]; dy=obj["y"]-mouse[1]
                    if dx*dx+dy*dy<200:
                        dragging_object=obj
                        obj["dragging"]=True
                        drag_start = mouse
                        break

            if dragging_particle:
                drag_start = mouse

            if dragging_object:
               drag_start = mouse


        
        #-------DRAGGING------
        if e.type == pygame.MOUSEBUTTONUP:

            if drag_start:

                dx = drag_start[0] - mouse[0]
                dy = drag_start[1] - mouse[1]

                power = 0.08   # tweak this

                vx = dx * power
                vy = dy * power

                if dragging_particle:
                    dragging_particle.vx = vx
                    dragging_particle.vy = vy
                    dragging_particle.dragging = False
                    dragging_particle = None

                if dragging_object:
                    dragging_object["vx"] = vx
                    dragging_object["vy"] = vy
                    dragging_object["dragging"] = False
                    dragging_object = None

                drag_start = None

    # ---- DRAGGING OVERRIDE ----
    '''if dragging_particle:
        dragging_particle.x, dragging_particle.y = mouse'''
        

    SUBSTEPS = 2

    for _ in range(SUBSTEPS):

        for p in particles:
            p.update()

        update_objects()

        handle_collisions()


    # -------- REMOVE FAR PARTICLES & OBJECTS --------
    CENTER_X = (WIDTH - MENU_WIDTH) // 2
    CENTER_Y = HEIGHT // 2
    MAX_DIST = 800

    new_particles = []
    for p in particles:
      dx = p.x - CENTER_X
      dy = p.y - CENTER_Y

      if dx*dx + dy*dy < MAX_DIST * MAX_DIST:
        new_particles.append(p)

    particles = new_particles

    new_objects = []
    for obj in objects:
        dx = obj["x"] - CENTER_X
        dy = obj["y"] - CENTER_Y

        if dx*dx + dy*dy < MAX_DIST * MAX_DIST:
            new_objects.append(obj)

    objects = new_objects
    #---------------------------------------

    if show_E:
        draw_E_lines()

    if show_B:
        draw_B_lines()

    draw_objects()

    for p in particles:
        p.draw()

    for b in buttons:
        b.draw()

    if show_probe:
        draw_probe(mouse)

    pygame.draw.rect(screen,DARK,(WIDTH-MENU_WIDTH,0,MENU_WIDTH,HEIGHT))

    toggle_switch.draw(use_boris)

    for m in menu:
        m.draw(m.name == selected)

    if paused == False: ani_time += 0.03     # animation speed

    pygame.display.flip()

pygame.quit()